# Phase 1 — API spike results

Numbers come from `spikes/out/log_*.json`.

| Spike | Model | Input | Latency (s) | Result | Notes |
|---|---|---|---|---|---|
| 1.2 Spark video → SOP | muse-spark-1.2 | expert.mp4 (70 s, 7.3 MB) | 12.6 | pass | 6 steps, timings correct, critical steps marked; recognised exact product (Zebronics M.2 NVMe enclosure) |
| 1.3 SAM "hand" | sam-3.1 | expert.mp4 (706 frames @ 10 fps) | 48 | pass | 2 hands tracked, IDs stable (#0 in 706 frames, #1 in 628), ~$0.14 per call |
| 1.3 SAM "<part>" | sam-3.1 | expert.mp4 | — | pending | test "screwdriver" / "screw" in Phase 3 |
| 1.4 Transcribe (English) | muse-voice-transcribe-1.0 | expert.wav (70 s) | 13 | pass | timed turns match Spark's steps; strip `<\|speaker_A\|>` tags |
| 1.4 Transcribe (Kannada) | muse-voice-transcribe-1.0 | kn.wav | — | pending | not blocking; fallback = narrate in English, Spark translates for worker |
| 1.5 Agent v1, fake step | muse-spark-1.2 | step.mp4 | 8.9 | FAIL | passed a step that never happened — hallucinated evidence (confirmation bias) |
| 1.5 Agent v2, real step (SOP 2) | muse-spark-1.2 | step.mp4 (23 s) | 21.0 (observe 10.8 + judge 10.2) | pass | `pass_step` with timestamped visual evidence |
| 1.5 Agent v2, fake step (SOP 5) | muse-spark-1.2 | step.mp4 (23 s) | 19.2 (observe 10.8 + judge 8.4) | pass | `flag_deviation`, wrong_order, observed_step_id = 2 (correct) |

## Go / no-go — GO
- [x] Spark understands the assembly video
- [x] SAM returns tracks we can draw (box overlay verified in `overlay_hand.mp4`)
- [x] Transcribe works — English confirmed; Kannada pending
- [x] Agent calls tools correctly in both cases (after v2 fix)

## Design decisions from the spikes
- Check mode = two calls per step: **blind observe** (no expected step given) → **strict judge** (SOP + expected end state + observation, default to flag).
- Steps are referenced by **SOP id**, never by fuzzy text matching.
- Video goes only through the **Responses API** (`input_video`); Chat Completions doesn't take video.
- Use **muse-spark-1.2** (1.3 has degraded audio understanding).
- SAM boxes parsed in Python; masks decoded in the browser with `@meta-sam/parser`.

## Limits found
- Max clip size that worked as base64: 7.3 MB (70 s, 848×478, 10 fps)
- Cost per call (from Billing → Usage): fill in from dashboard
- Failures / surprises:
  - Strict `json_schema` output returned an empty `steps` list → switched to prompt-specified JSON + parse + retry
  - `tool_choice` only supports `"auto"` (not `"required"`) → system prompt forces exactly one tool call
  - Agent v1 confirmed whatever step it was told (hallucinated evidence) → fixed with blind observation + strict judge
  - Fuzzy text → SOP matching picked the wrong step → pass step ids instead
  - Transcript contains `<|speaker_A|>` tokens → strip in code
  - SAM masks use Meta's own compressed encoding (`~` = lossless) → not decodable in plain Python
  - Agent noticed narration ("bottom screw") contradicted the video (top end cap) and trusted the video