"""Eval script math, offline: Meta calls mocked."""
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import eval as ev  # noqa: E402
from app.models import Step  # noqa: E402
from app.services import media, meta_client  # noqa: E402


def test_eval_end_to_end(tmp_path, monkeypatch):
    clips = tmp_path / "clips"
    clips.mkdir()
    for name in ("a.mp4", "b.mp4"):
        subprocess.run([media._ffmpeg(), "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                        "testsrc=size=320x180:rate=10", "-t", "1", "-pix_fmt", "yuv420p", str(clips / name)], check=True)
    truth = tmp_path / "gt.csv"
    truth.write_text(
        "clip,step,expected,expected_type,note\n"
        "a.mp4,1,pass,,correct\n"
        "a.mp4,2,flag,wrong_order,shows step 1 not 2\n"
        "b.mp4,2,flag,missing,incomplete\n"
    )
    observed = []
    monkeypatch.setattr(meta_client, "observe", lambda clip: observed.append(clip.name) or "obs")
    verdicts = {
        ("a.mp4", 1): {"verdict": "pass", "evidence": "ok"},
        ("a.mp4", 2): {"verdict": "flag", "type": "wrong_order", "observed_step_id": 1, "reason": "r"},
        ("b.mp4", 2): {"verdict": "pass", "evidence": "fooled"},  # a missed mistake
    }
    monkeypatch.setattr(meta_client, "judge",
                        lambda clip, sop, label, end, obs, lang, completed='': verdicts[(clip.stem + ".mp4", int(label.split()[1][0]))])

    steps = [Step(sop_id=1, idx=1, action="One", expected_end_state="1"),
             Step(sop_id=1, idx=2, action="Two", expected_end_state="2")]
    cases = ev.load_cases(truth)
    results = ev.evaluate(cases, steps, clips, workers=2, repeats=2)
    s = ev.summarize(results, {"a.mp4": 1, "b.mp4": 2})

    assert sorted(observed) == ["a.mp4", "b.mp4"]  # each clip observed once, despite 6 judgements
    assert s["cases"] == 6 and s["errors"] == 0
    assert s["accuracy"] == round(4 / 6, 3)
    assert s["correct_work_passed"] == 1.0 and s["false_alarm_rate"] == 0.0
    assert s["mistakes_caught"] == 0.5 and s["missed_mistakes"] == 2
    assert s["wrong_step_identified"] == 1.0 and s["consistency"] == 1.0
    md = ev.to_markdown(s, results, "Test SOP", "muse-spark-1.2")
    assert "| Overall accuracy | **67%** |" in md and "2 missed" in md
