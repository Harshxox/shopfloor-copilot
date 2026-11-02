## Evaluation — Disassemble ZEBRONICS M.2 SSD Enclosure

14 judgements on 8 real recorded clips (6 correct-work cases, 8 mistake cases). Model: `muse-spark-1.2` (blind observe + strict judge).

| Metric | Result |
|---|---|
| Overall accuracy | **79%** |
| Mistakes caught | **100%** (0 missed) |
| Correct work passed | 50% |
| False alarm rate | 50% |
| Wrong step identified correctly | 17% |
| Consistency across repeats | — |
| Check time p50 / p90 | 19.0 s / 23.9 s |

<details><summary>Every case</summary>

| Clip | Step | Expected | Got | Note |
|---|---|---|---|---|
| bad1_topscrew_incomplete.mp4 | 2 | flag | ✅ flag (missing) | screwdriver twisted at top but screw never comes out |
| bad5_hidden.mp4 | 5 | flag | ✅ flag (missing) | bottom cap removed but hands block the view the whole time |
| ok1_unpack.mp4 | 1 | pass | ❌ flag (missing) | correct: enclosure out of wrapper and held up |
| ok1_unpack.mp4 | 5 | flag | ✅ flag (missing) | shows step 1 not 5 |
| ok2_topscrew.mp4 | 2 | pass | ❌ flag (missing) | correct: top screw out and held up close |
| ok2_topscrew.mp4 | 4 | flag | ✅ flag (missing) | shows step 2 not 4 (top vs bottom screw - hard) |
| ok3_topcap.mp4 | 3 | pass | ✅ pass | correct: top cap off and held next to enclosure |
| ok3_topcap.mp4 | 6 | flag | ✅ flag (missing) | shows step 3 not 6 |
| ok4_bottomscrew.mp4 | 2 | flag | ✅ flag (wrong_order) | shows step 4 not 2 (bottom vs top screw - hard) |
| ok4_bottomscrew.mp4 | 4 | pass | ❌ flag (wrong_order) | correct: bottom screw out and held up close |
| ok5_bottomcap.mp4 | 3 | flag | ✅ flag (unclear) | shows step 5 not 3 (bottom vs top cap - hard) |
| ok5_bottomcap.mp4 | 5 | pass | ✅ pass | correct: bottom cap off and held next to enclosure |
| ok6_slide.mp4 | 1 | flag | ✅ flag (wrong_order) | shows step 6 not 1 |
| ok6_slide.mp4 | 6 | pass | ✅ pass | correct: inner part slid out and both pieces shown |

</details>
