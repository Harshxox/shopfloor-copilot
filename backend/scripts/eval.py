"""Phase 9 evaluation: run every recorded clip through the real agent and measure accuracy.

Reads   eval/ground_truth.csv   (clip, step, expected, expected_type, note)
Clips   eval/clips/<clip>
Writes  eval/results.csv, eval/results.md, eval/summary.json

Each clip is observed ONCE (the blind observation doesn't depend on the step), then judged for every
row that uses it. Rows run in parallel.

Run from backend\\ :
  python scripts/eval.py --sop 3
  python scripts/eval.py --sop 3 --repeats 2     # also measures consistency across repeated runs
"""
import argparse
import csv
import json
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from sqlmodel import Session, select  # noqa: E402

from app.db import engine  # noqa: E402
from app.models import SOP, Step  # noqa: E402
from app.services import media, meta_client  # noqa: E402
from app.services.check import sop_text  # noqa: E402

EVAL = ROOT / "eval"


def load_cases(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if r.get("clip") and not r["clip"].startswith("#")]
    for r in rows:
        r["step"] = int(r["step"])
        r["expected"] = r["expected"].strip().lower()
        assert r["expected"] in ("pass", "flag"), f"expected must be pass/flag: {r}"
    return rows


def evaluate(cases: list[dict], steps: list[Step], clips_dir: Path, workers: int = 3, repeats: int = 1,
             lang: str = "en") -> list[dict]:
    by_idx = {s.idx: s for s in steps}
    sop = sop_text(steps)
    norm_dir = clips_dir / "_normalized"
    norm_dir.mkdir(exist_ok=True)

    # 1. normalize + blind-observe each distinct clip once
    clip_names = sorted({c["clip"] for c in cases})
    observations: dict[str, tuple[Path, str, float]] = {}

    def observe(name: str):
        src = clips_dir / name
        dst = norm_dir / (Path(name).stem + ".mp4")
        if not dst.exists():
            media.normalize_video(src, dst)
        t = time.perf_counter()
        obs = meta_client.observe(dst)
        return name, (dst, obs, time.perf_counter() - t)

    with ThreadPoolExecutor(workers) as pool:
        for name, val in pool.map(observe, clip_names):
            observations[name] = val
            print(f"observed {name} ({val[2]:.1f}s)")

    # 2. judge every case (x repeats)
    jobs = [(c, rep) for c in cases for rep in range(repeats)]

    def judge(job):
        c, rep = job
        clip, obs, obs_s = observations[c["clip"]]
        st = by_idx[c["step"]]
        t = time.perf_counter()
        # simulate a real run: the worker is on this step, so every earlier step is already done
        completed = ", ".join(f"{x.idx}. {x.action}" for x in steps if x.idx < st.idx)
        try:
            v = meta_client.judge(clip, sop, f"Step {st.idx}: {st.action}", st.expected_end_state, obs, lang,
                                  completed=completed)
        except Exception as e:  # noqa: BLE001
            v = {"verdict": "error", "reason": str(e)[:200]}
        judge_s = time.perf_counter() - t
        got = v.get("verdict")
        return {
            "clip": c["clip"], "step": c["step"], "repeat": rep, "expected": c["expected"],
            "expected_type": c.get("expected_type", ""), "note": c.get("note", ""),
            "got": got, "got_type": v.get("type", ""), "observed_step_id": v.get("observed_step_id"),
            "correct": got == c["expected"],
            "reason": v.get("reason") or v.get("evidence", ""),
            "instruction": v.get("instruction_for_worker", ""),
            "latency_s": round(obs_s + judge_s, 2),
        }

    results = []
    with ThreadPoolExecutor(workers) as pool:
        for r in pool.map(judge, jobs):
            mark = "OK " if r["correct"] else "XX "
            print(f"{mark} {r['clip']:<28} step {r['step']}  expected {r['expected']:<4} got {r['got']}"
                  f"{' (' + r['got_type'] + ')' if r['got_type'] else ''}  {r['latency_s']}s")
            if not r["correct"]:
                print(f"     why: {r['reason'][:400]}")
            results.append(r)
    return results


def pct(a: int, b: int):
    return round(a / b, 3) if b else None


def summarize(results: list[dict], truth_steps: dict[str, int]) -> dict:
    ok = [r for r in results if r["got"] != "error"]
    exp_pass = [r for r in ok if r["expected"] == "pass"]
    exp_flag = [r for r in ok if r["expected"] == "flag"]
    wrong_step_cases = [r for r in exp_flag if r["expected_type"] == "wrong_order" and r["clip"] in truth_steps]
    lat = sorted(r["latency_s"] for r in ok)

    # consistency: same (clip, step) judged the same way across repeats
    groups: dict[tuple, set] = {}
    for r in ok:
        groups.setdefault((r["clip"], r["step"]), set()).add(r["got"])
    multi = [g for k, g in groups.items() if sum(1 for r in ok if (r["clip"], r["step"]) == k) > 1]

    return {
        "cases": len(results),
        "errors": len(results) - len(ok),
        "accuracy": pct(sum(r["correct"] for r in ok), len(ok)),
        "correct_work_passed": pct(sum(r["got"] == "pass" for r in exp_pass), len(exp_pass)),
        "mistakes_caught": pct(sum(r["got"] == "flag" for r in exp_flag), len(exp_flag)),
        "false_alarm_rate": pct(sum(r["got"] == "flag" for r in exp_pass), len(exp_pass)),
        "missed_mistakes": sum(r["got"] == "pass" for r in exp_flag),
        "wrong_step_identified": pct(sum(r["observed_step_id"] == truth_steps.get(r["clip"])
                                         for r in wrong_step_cases), len(wrong_step_cases)),
        "consistency": pct(sum(len(g) == 1 for g in multi), len(multi)),
        "latency_p50_s": round(statistics.median(lat), 1) if lat else None,
        "latency_p90_s": round(lat[min(len(lat) - 1, int(0.9 * len(lat)))], 1) if lat else None,
        "n_expected_pass": len(exp_pass),
        "n_expected_flag": len(exp_flag),
    }


def to_markdown(summary: dict, results: list[dict], sop_name: str, model: str) -> str:
    p = lambda x: "—" if x is None else f"{x * 100:.0f}%"  # noqa: E731
    s = summary
    lines = [
        f"## Evaluation — {sop_name}", "",
        f"{s['cases']} judgements on {len({r['clip'] for r in results})} real recorded clips "
        f"({s['n_expected_pass']} correct-work cases, {s['n_expected_flag']} mistake cases). "
        f"Model: `{model}` (blind observe + strict judge).", "",
        "| Metric | Result |", "|---|---|",
        f"| Overall accuracy | **{p(s['accuracy'])}** |",
        f"| Mistakes caught | **{p(s['mistakes_caught'])}** ({s['missed_mistakes']} missed) |",
        f"| Correct work passed | {p(s['correct_work_passed'])} |",
        f"| False alarm rate | {p(s['false_alarm_rate'])} |",
        f"| Wrong step identified correctly | {p(s['wrong_step_identified'])} |",
        f"| Consistency across repeats | {p(s['consistency'])} |",
        f"| Check time p50 / p90 | {s['latency_p50_s']} s / {s['latency_p90_s']} s |", "",
        "<details><summary>Every case</summary>", "",
        "| Clip | Step | Expected | Got | Note |", "|---|---|---|---|---|",
    ]
    for r in sorted(results, key=lambda r: (r["clip"], r["step"], r["repeat"])):
        got = r["got"] + (f" ({r['got_type']})" if r["got_type"] else "")
        lines.append(f"| {r['clip']} | {r['step']} | {r['expected']} | {'✅' if r['correct'] else '❌'} {got} | {r['note']} |")
    lines += ["", "</details>", ""]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sop", type=int, required=True)
    ap.add_argument("--truth", default=str(EVAL / "ground_truth.csv"))
    ap.add_argument("--clips", default=str(EVAL / "clips"))
    ap.add_argument("--repeats", type=int, default=1)
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--lang", default="en")
    a = ap.parse_args()

    with Session(engine) as s:
        sop = s.get(SOP, a.sop)
        if not sop:
            raise SystemExit(f"SOP {a.sop} not found")
        steps = list(s.exec(select(Step).where(Step.sop_id == a.sop).order_by(Step.idx)))
    cases = load_cases(Path(a.truth))
    clips_dir = Path(a.clips)
    # accept .mov/.webm/etc. recorded under the same name
    for c in cases:
        if not (clips_dir / c["clip"]).exists():
            alt = next(iter(sorted(clips_dir.glob(Path(c["clip"]).stem + ".*"))), None)
            if alt and alt.parent.name != "_normalized":
                c["clip"] = alt.name
    missing = sorted({c["clip"] for c in cases if not (clips_dir / c["clip"]).exists()})
    if missing:
        print(f"Skipping {len(missing)} clip(s) not recorded yet: {', '.join(missing)}\n")
        cases = [c for c in cases if c["clip"] not in missing]
    if not cases:
        raise SystemExit(f"No clips found in {clips_dir}")
    bad = sorted({c["step"] for c in cases} - {st.idx for st in steps})
    if bad:
        raise SystemExit(f"Steps {bad} are not in SOP {a.sop} (it has {len(steps)} steps)")

    # the true step a clip shows = the step of its 'pass' row, or its 'truth_step' hint in the note
    truth_steps = {c["clip"]: c["step"] for c in cases if c["expected"] == "pass"}
    for c in cases:
        if "shows step" in c.get("note", ""):
            truth_steps.setdefault(c["clip"], int(c["note"].split("shows step")[1].split()[0]))

    print(f"Evaluating {len(cases)} cases x {a.repeats} on SOP {a.sop} '{sop.name}'\n")
    results = evaluate(cases, steps, Path(a.clips), a.workers, a.repeats, a.lang)
    summary = summarize(results, truth_steps)

    EVAL.mkdir(exist_ok=True)
    with (EVAL / "results.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        w.writeheader()
        w.writerows(results)
    (EVAL / "summary.json").write_text(json.dumps(summary, indent=2))
    from app import config
    (EVAL / "results.md").write_text(to_markdown(summary, results, sop.name, config.SPARK_MODEL), encoding="utf-8")

    print("\n" + json.dumps(summary, indent=2))
    print(f"\nSaved eval/results.md (paste into README), eval/results.csv, eval/summary.json")


if __name__ == "__main__":
    main()
