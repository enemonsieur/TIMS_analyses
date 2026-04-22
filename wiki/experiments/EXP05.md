---
type: experiment
status: active
updated: 2026-04-18
tags:
  - exp05
  - phantom
  - ctbs
---

# EXP05

## Question

Is `30%` cTBS materially cleaner than `100%`, and is the recorded GT signal near `7.08 Hz` recoverable strongly enough to support later ON/OFF analysis?

## Current Conclusion

Across the scalp, `30%` is clearly cleaner than `100%`, but it is not artifact-free. The corrected SSD reruns can recover a plausible baseline component near the GT band, yet transfer to stimulated data drifts toward `~5.13 Hz`. EXP05 therefore ended as a design and constraint experiment, not as a successful recovery proof.

## Evidence

- [`exp05.md`](../../docs/experiments/exp05.md): original experiment goal was "30% negligible, 100% significant."
- [`MEMO_exp05_analysis.md`](../../docs/memos/MEMO_exp05_analysis.md): corrected the Cz-centered reading, showed `30%` is cleaner than `100%` across channels, and documented the GT shift to `~7.08 Hz`.
- [`MEMO_exp05_5_2_ctbs_recovery.md`](../../docs/memos/MEMO_exp05_5_2_ctbs_recovery.md): the stricter FC1-centered pass found no acceptable in-band baseline component and exposed the persistent `~5.13 Hz` fallback mode.
- [`MEMO_exp05_5_3_ctbs_intensity_decision.md`](../../docs/memos/MEMO_exp05_5_3_ctbs_intensity_decision.md): turned exp05 into a design decision, arguing that the next experiment should move the GT farther away from the fixed `5 Hz` cTBS rhythm.

## Conflicts / Caveats

- The earlier "30% and 100% are similar" interpretation was too Cz-centered and is now downgraded.
- "30% is cleaner than 100%" does not mean "30% is clean enough for reliable `~7 Hz` recovery."
- Phase-based metrics can rise on the wrong spectral mode, which is part of why exp05 points forward to the later EXP06 metric dispute.

## Next Step

Treat EXP05 as the experiment that motivated a cleaner target frequency and a programmable intensity sweep. Revisit it mainly when comparing later EXP06 behavior against the older `~7 Hz` design.

## Relevant Methods

- [[methods/SSD|SSD]]
- [[methods/PLV|PLV]]
- [[methods/SNR|SNR]]

## Relevant Papers

No linked papers yet.
