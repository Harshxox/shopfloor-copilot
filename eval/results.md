## Evaluation — Disassemble ZEBRONICS M.2 SSD Enclosure

12 judgements on 8 real recorded clips (4 correct-work cases, 8 mistake cases). Model: `muse-spark-1.2` (blind observe + strict judge).

| Metric | Result |
|---|---|
| Overall accuracy | **100%** |
| Mistakes caught | **100%** (0 missed) |
| Correct work passed | 100% |
| False alarm rate | 0% |
| Wrong step identified correctly | 50% |
| Consistency across repeats | — |
| Check time p50 / p90 | 18.1 s / 21.8 s |

<details><summary>Every case</summary>

| Clip | Step | Expected | Got | Note |
|---|---|---|---|---|
| bad1_topscrew_incomplete.mp4 | 2 | flag | ✅ flag (missing) | screwdriver twisted at top but cap stays on |
| bad5_hidden.mp4 | 3 | flag | ✅ flag (missing) | bottom cap removed but hands block the view the whole time |
| ok1_unpack.mp4 | 1 | pass | ✅ pass | correct: enclosure out of sleeve and held up |
| ok1_unpack.mp4 | 3 | flag | ✅ flag (wrong_order) | shows step 1 not 3 |
| ok2_topscrew.mp4 | 2 | flag | ✅ flag (missing) | top screw loosened but cap never removed (incomplete step) |
| ok3_topcap.mp4 | 2 | pass | ✅ pass | correct: top cap off and USB-C end open |
| ok3_topcap.mp4 | 4 | flag | ✅ flag (missing) | shows step 2 not 4 |
| ok4_bottomscrew.mp4 | 3 | flag | ✅ flag (missing) | bottom screw worked but cap never removed (incomplete step) |
| ok5_bottomcap.mp4 | 2 | flag | ✅ flag (unclear) | shows step 3 not 2 (top vs bottom cap - hard) |
| ok5_bottomcap.mp4 | 3 | pass | ✅ pass | correct: bottom cap off and bottom end open |
| ok6_slide.mp4 | 1 | flag | ✅ flag (wrong_order) | shows step 4 not 1 |
| ok6_slide.mp4 | 4 | pass | ✅ pass | correct: PCB slid out and both parts shown |

</details>
