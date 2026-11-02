"""Shift report: what went wrong across worker runs, per step, and how to improve the SOP."""
from collections import Counter, defaultdict
from statistics import mean
from typing import Optional

from sqlmodel import Session, select

from ..models import CheckRun, Event, SOP, Step
from . import meta_client

TYPE_LABEL = {"skip": "Step skipped", "wrong_order": "Wrong step", "wrong_part": "Wrong part",
              "missing": "Not finished", "unclear": "Not visible"}


def build(s: Session, sop_id: Optional[int] = None) -> dict:
    sops = list(s.exec(select(SOP).where(SOP.status == "ready")))
    if sop_id is None and sops:
        # default: the SOP with the most runs
        counts = Counter(r.sop_id for r in s.exec(select(CheckRun)))
        sop_id = max(sops, key=lambda x: counts.get(x.id, 0)).id
    sop = s.get(SOP, sop_id) if sop_id else None
    if not sop:
        return {"sop": None, "sops": sops}

    steps = list(s.exec(select(Step).where(Step.sop_id == sop.id).order_by(Step.idx)))
    runs = list(s.exec(select(CheckRun).where(CheckRun.sop_id == sop.id)))
    run_ids = [r.id for r in runs]
    events = list(s.exec(select(Event).where(Event.run_id.in_(run_ids)).order_by(Event.created_at))) if run_ids else []

    checks = [e for e in events if e.kind in ("pass", "flag")]
    flags = [e for e in events if e.kind == "flag"]
    overrides = [e for e in events if e.kind == "override"]

    # first attempt of each (run, step): did it pass straight away?
    first: dict[tuple[int, int], Event] = {}
    for e in checks:
        first.setdefault((e.run_id, e.step_idx), e)

    per_step = []
    by_step = defaultdict(list)
    for e in events:
        by_step[e.step_idx].append(e)
    for st in steps:
        evs = by_step.get(st.idx, [])
        st_flags = [e for e in evs if e.kind == "flag"]
        firsts = [e for (rid, idx), e in first.items() if idx == st.idx]
        per_step.append({
            "idx": st.idx, "action": st.action, "critical": st.critical,
            "attempts": sum(e.kind in ("pass", "flag") for e in evs),
            "passes": sum(e.kind == "pass" for e in evs),
            "flags": len(st_flags),
            "overrides": sum(e.kind == "override" for e in evs),
            "first_try_pass_rate": round(sum(e.kind == "pass" for e in firsts) / len(firsts), 3) if firsts else None,
            "flag_types": dict(Counter(e.deviation_type or "unclear" for e in st_flags)),
        })

    most_failed = max((p for p in per_step if p["flags"]), key=lambda p: p["flags"], default=None)
    first_list = list(first.values())
    clean_runs = [r for r in runs if r.status == "done"
                  and not any(e.run_id == r.id and e.kind == "flag" for e in flags)]

    return {
        "sop": {"id": sop.id, "name": sop.name},
        "sops": [{"id": x.id, "name": x.name} for x in sops],
        "kpis": {
            "runs": len(runs),
            "completed_runs": sum(r.status == "done" for r in runs),
            "clean_runs": len(clean_runs),
            "checks": len(checks),
            "first_try_pass_rate": round(sum(e.kind == "pass" for e in first_list) / len(first_list), 3)
            if first_list else None,
            "corrections": len(flags),
            "false_alarms": len(overrides),
            "false_alarm_rate": round(len(overrides) / len(flags), 3) if flags else None,
            "avg_check_seconds": round(mean(e.latency_s for e in checks if e.latency_s), 1)
            if any(e.latency_s for e in checks) else None,
        },
        "most_failed_step": most_failed,
        "deviation_types": [{"type": t, "label": TYPE_LABEL.get(t, t), "count": c}
                            for t, c in Counter(e.deviation_type or "unclear" for e in flags).most_common()],
        "per_step": per_step,
        "recent_flags": [{
            "id": e.id, "run_id": e.run_id, "step_idx": e.step_idx,
            "action": next((st.action for st in steps if st.idx == e.step_idx), ""),
            "type": e.deviation_type, "label": TYPE_LABEL.get(e.deviation_type, e.deviation_type),
            "reason": e.reason, "instruction": e.instruction, "clip_path": e.clip_path,
            "overridden": any(o.observed_step_id == e.id for o in overrides),
            "created_at": e.created_at.isoformat(),
        } for e in reversed(flags[-12:])],
    }


SUGGEST_PROMPT = """You are a manufacturing engineer improving a standard operating procedure (SOP).
Below is the SOP and what happened when workers followed it (checked by an AI inspector).
Suggest exactly 3 concrete changes to the SOP that would prevent the most frequent errors.
Ground every suggestion in the data: name the step and the evidence. If a step's flags were mostly
overridden as false alarms, suggest making that step's end state easier to show on camera instead.
Return ONLY JSON: {{"suggestions": [{{"step_idx": 1, "title": "short title", "change": "the exact SOP edit",
"why": "the evidence from the data"}}]}}

SOP:
{sop}

Per-step results:
{stats}

Inspector's reasons for recent corrections:
{reasons}
"""


def suggestions(s: Session, sop_id: int) -> list[dict]:
    rep = build(s, sop_id)
    if not rep.get("sop"):
        raise ValueError("SOP not found")
    if not rep["kpis"]["corrections"]:
        return []
    steps = list(s.exec(select(Step).where(Step.sop_id == sop_id).order_by(Step.idx)))
    sop_text = "\n".join(f"{st.idx}. {st.action} (done when: {st.expected_end_state})"
                         f"{' [critical]' if st.critical else ''}" for st in steps)
    stats = "\n".join(f"Step {p['idx']}: {p['attempts']} checks, {p['flags']} corrections, "
                      f"{p['overrides']} overridden as false alarm, types {p['flag_types']}" for p in rep["per_step"])
    reasons = "\n".join(f"- Step {f['step_idx']} ({f['label']}): {f['reason']}" for f in rep["recent_flags"])
    resp = meta_client.client().responses.create(
        model=meta_client.config.SPARK_MODEL,
        input=[{"role": "user", "content": [{"type": "input_text",
                                              "text": SUGGEST_PROMPT.format(sop=sop_text, stats=stats, reasons=reasons)}]}],
        reasoning={"effort": "medium"},
    )
    return meta_client.parse_json(resp.output_text).get("suggestions", [])[:3]


def markdown(rep: dict, sugg: Optional[list[dict]] = None) -> str:
    k = rep["kpis"]
    pct = lambda x: "—" if x is None else f"{x * 100:.0f}%"  # noqa: E731
    lines = [
        f"# Shift report — {rep['sop']['name']}", "",
        f"- Worker runs: {k['runs']} ({k['completed_runs']} completed, {k['clean_runs']} with zero corrections)",
        f"- Step checks: {k['checks']} · first-try pass rate {pct(k['first_try_pass_rate'])}",
        f"- Corrections: {k['corrections']} · false alarms (supervisor override): {k['false_alarms']}"
        f" ({pct(k['false_alarm_rate'])})",
        f"- Average check time: {k['avg_check_seconds'] or '—'} s", "",
    ]
    if rep["most_failed_step"]:
        m = rep["most_failed_step"]
        lines += [f"**Most-failed step:** {m['idx']}. {m['action']} — {m['flags']} corrections", ""]
    lines += ["## Per step", "", "| # | Step | Checks | Corrections | First-try pass |", "|---|---|---|---|---|"]
    lines += [f"| {p['idx']} | {p['action']}{' (critical)' if p['critical'] else ''} | {p['attempts']} | "
              f"{p['flags']} | {pct(p['first_try_pass_rate'])} |" for p in rep["per_step"]]
    if rep["deviation_types"]:
        lines += ["", "## Corrections by type", ""] + [f"- {d['label']}: {d['count']}" for d in rep["deviation_types"]]
    if sugg:
        lines += ["", "## Suggested SOP changes (Muse Spark)", ""]
        lines += [f"{i}. **Step {x.get('step_idx')}: {x.get('title')}** — {x.get('change')} _(Why: {x.get('why')})_"
                  for i, x in enumerate(sugg, 1)]
    return "\n".join(lines) + "\n"
