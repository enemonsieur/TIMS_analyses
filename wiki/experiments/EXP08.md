---
type: experiment
status: active
updated: 2026-04-22
tags:
  - exp08
  - phantom
  - single-pulse
  - dose-response
  - 10-to-100-percent
---

# EXP08

## Question

Can a single-pulse dose-response protocol (10–100% intensity, 20 pulses per level) produce clean, repeatable on-demand signal recovery without the complexity of continuous iTBS modulation?

## Current Conclusion

EXP08 pulse extraction is complete. 200 pulses detected across 10 intensity levels (10%, 20%, ..., 100%), grouped into per-intensity epoch files (20 epochs each, 28 EEG channels, 0.5 s post-pulse window). The data is ready for downstream SNR/ITPC/SSD analysis to establish whether single pulses provide a cleaner dose-response curve than the iTBS ON-state artifact observed in [[experiments/EXP06|EXP06]].

## Evidence

- [`explore_exp08_pulses.py`](../../explore_exp08_pulses.py): pulse detection and epoch extraction script, following SKRIPT.md standards.
- [`exp08_epoch_summary.txt`](../../EXP08/exp08_epoch_summary.txt): timing summary with per-intensity epoch counts and window definitions.
- [`exp08_block_timing_by_intensity.png`](../../EXP08/exp08_block_timing_by_intensity.png): visualization of all 200 pulses marked by intensity level.
- Epoch files: `exp08_epochs_*pct-epo.fif` (10 files, one per intensity level, 20 epochs × 28 channels × 480 samples each).

## Conflicts / Caveats

- On-window definition (0.02–0.5 s post-pulse) differs from [[experiments/EXP06|EXP06]] and [[experiments/EXP07|EXP07]] (0.3–1.5 s). Single pulses are much shorter (~15 ms) than iTBS blocks (~2 s ON), so the post-pulse response window is necessarily compressed.
- Pulses are delivered at 5 s inter-pulse spacing, leaving 4.98 s of OFF-state between pulses. This differs from iTBS cycles and may reveal different artifact settling dynamics.
- Ground_truth channel was not recorded in EXP08, so direct phase-locking validation against a known 12.45 Hz reference is not possible (unlike EXP06/07). Validation will rely on SNR, PSD peak stability, and ITPC only.

## Next Step

Run per-intensity SNR ranking to establish whether single-pulse artifact is intensity-dependent. Compare SNR curves to [[experiments/EXP06|EXP06]] ON-state decay to assess whether the cleaner stimulus structure improves recovery. If yes, proceed to ITPC and SSD analysis to validate signal preservation.

## Relevant Methods

- [[methods/SNR|SNR]]
- [[methods/ITPC|ITPC]]
- [[methods/SSD|SSD]]
- [[methods/Post_Pulse_Windowing|Post-pulse windowing]]

## Relevant Papers

- No linked papers yet.
