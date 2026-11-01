"""Spike 1.5 (v2) — Does the agent pass correct steps AND catch wrong ones?

v1 problem: told "expected step = X", the model hallucinated evidence for X (confirmation bias).
v2 fix: two stages
  1. OBSERVE (blind): Spark describes what happens in the clip WITHOUT being told the expected step.
  2. JUDGE: Spark compares the clip + its blind observation against the expected step, its expected
     end state and the full SOP, then calls pass_step or flag_deviation. Pass only on visible proof.

Run (one line) — pass SOP step ids from spikes/out/spark_steps.json, or free text:
  python spikes/agent_tools.py spikes/media/step.mp4 2 5
Uses spikes/out/spark_steps.json (from spark_video.py) as SOP context if it exists.
Pass: case A -> pass_step, case B -> flag_deviation.
"""
import json
import sys
from pathlib import Path

from common import MEDIA, OUT, SPARK_MODEL, client, save, timed, video_data_url

clip = Path(sys.argv[1]) if len(sys.argv) > 1 else MEDIA / "step.mp4"
real_step = sys.argv[2] if len(sys.argv) > 2 else "Remove one screw from the enclosure using the screwdriver"
fake_step = sys.argv[3] if len(sys.argv) > 3 else "Slide the inner M.2 board out of the aluminium housing"

sop_path = OUT / "spark_steps.json"
sop = json.loads(sop_path.read_text()) if sop_path.exists() else None
sop_text = "\n".join(
    f"{s['id']}. {s['action']} -> done when: {s.get('expected_end_state', '')}" for s in sop["steps"]
) if sop else "(no SOP loaded)"

TOOLS = [
    {
        "type": "function",
        "name": "pass_step",
        "description": "ONLY when the clip visibly shows the expected step performed AND its end state reached.",
        "parameters": {
            "type": "object",
            "properties": {
                "evidence": {"type": "string", "description": "Concrete visual proof with approximate timestamps."},
            },
            "required": ["evidence"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "flag_deviation",
        "description": "When the expected step is not visibly completed, a different step was done, or it's unclear.",
        "parameters": {
            "type": "object",
            "properties": {
                "type": {"type": "string", "enum": ["skip", "wrong_order", "wrong_part", "missing", "unclear"]},
                "observed_step_id": {"type": ["integer", "null"],
                                     "description": "Which SOP step the clip actually shows, if any."},
                "reason": {"type": "string"},
                "instruction_for_worker": {"type": "string", "description": "One short corrective sentence."},
            },
            "required": ["type", "observed_step_id", "reason", "instruction_for_worker"],
            "additionalProperties": False,
        },
    },
]

OBSERVE_PROMPT = (
    "Describe exactly what the person's hands do in this clip, in order, with approximate timestamps. "
    "Then describe the final state of the object in the last 2 seconds. "
    "Only report what is visible. Do not guess intentions or what happens next."
)

JUDGE_SYSTEM = (
    "You are a strict quality inspector on an assembly line. Your default answer is to FLAG. "
    "Call pass_step only if the clip visibly shows the expected action AND the expected end state is "
    "reached by the end of the clip. Narration alone is not proof; a similar-looking action on a different "
    "part is not proof. If the clip shows a different SOP step, flag wrong_order and give its id. "
    "If you cannot see it clearly, flag unclear. Call exactly one tool."
)


def resolve_step(arg: str) -> tuple[str, str]:
    """Arg is an SOP step id ("2") or free text. Returns (step description, expected end state)."""
    if sop and arg.strip().isdigit():
        s = next(s for s in sop["steps"] if int(s["id"]) == int(arg))
        return f"Step {s['id']}: {s['action']}", s.get("expected_end_state", "not specified")
    return arg, "not specified"


data_url = video_data_url(clip)
results = {"model": SPARK_MODEL, "clip": clip.name}

# Stage 1: blind observation (once per clip)
obs_log = {}
with timed("observe_latency_s", obs_log):
    obs = client.responses.create(
        model=SPARK_MODEL,
        input=[{"role": "user", "content": [
            {"type": "input_video", "video_url": data_url},
            {"type": "input_text", "text": OBSERVE_PROMPT},
        ]}],
    )
observation = obs.output_text
results["observation"] = observation
results["observe_latency_s"] = obs_log["observe_latency_s"]
print("== Blind observation ==\n" + observation)

# Stage 2: judge each case
for case, step_arg in [("A_real", real_step), ("B_fake", fake_step)]:
    log = {}
    step, expected_end = resolve_step(step_arg)
    judge_text = (
        f"Full SOP:\n{sop_text}\n\n"
        f"Expected step for this clip: {step}\n"
        f"Expected end state: {expected_end}\n\n"
        f"Independent observation of the clip (written without knowing the expected step):\n{observation}\n\n"
        "Check the video yourself as well, then call exactly one tool."
    )
    with timed("judge_latency_s", log):
        resp = client.responses.create(
            model=SPARK_MODEL,
            instructions=JUDGE_SYSTEM,
            input=[{"role": "user", "content": [
                {"type": "input_video", "video_url": data_url},
                {"type": "input_text", "text": judge_text},
            ]}],
            tools=TOOLS,
            tool_choice="auto",  # Meta API supports only "auto"; the system prompt forces a tool call
        )
    calls = [
        {"name": item.name, "arguments": json.loads(item.arguments)}
        for item in resp.output if getattr(item, "type", "") == "function_call"
    ]
    log.update({"expected_step": step, "expected_end_state": expected_end,
                "tool_calls": calls, "text": resp.output_text})
    results[case] = log
    verdict = calls[0]["name"] if calls else "NO TOOL CALL"
    want = "pass_step" if case == "A_real" else "flag_deviation"
    print(f"\n== Case {case}: '{step}'  ->  {verdict}  ({'OK' if verdict == want else 'WRONG'})")
    print(json.dumps(calls, indent=2, ensure_ascii=False) if calls else resp.output_text)

save("log_agent_tools.json", results)
