---
type: experiment
status: tentative
updated: 2026-04-18
tags:
  - exp03
  - phantom
  - postpulse
---

# EXP03

## Question

Can a pulse-centered phantom workflow produce usable post-pulse epochs for later recovery and denoising work?

## Current Conclusion

EXP03 established a workable post-pulse analysis path and became the early local reference for pulse-centered windowing. The validation outputs support a usable cropped post-pulse epoch, and simple cleanup or ICA-auto preserved high coherence while SSP degraded strongly. This experiment is best treated as an early pipeline anchor, not the current best recovery comparison.

## Evidence

- [`analysis_summary.txt`](../../exp03_pulse_centered_analysis_run03/analysis_summary.txt): `30` valid stim epochs, final crop `0.08-0.999 s`, and the saved final epoch file.
- [`postclean_validation_summary.txt`](../../exp03_pulse_centered_analysis_run03/postclean_validation_summary.txt): `clean_only` and `ica_auto` both keep coherence near `0.98`, while `ssp` drops to `0.27`.
- [`readme.md`](../../readme.md): marks `main_analysis_exp03.py`, `postclean_denoise_validate_exp03.py`, and `compare_stim_baseline_exp03.py` as the main exp03 analyses.

## Conflicts / Caveats

- Coherence stayed high while PLV and correlation remained low in the validation summary, so EXP03 should not be over-read as a strong phase-recovery proof.
- The repo has no modern memo chain dedicated to EXP03, so the narrative is thinner than EXP05 and EXP06.

## Next Step

Use EXP03 mainly as the local reference for post-pulse windowing and early cleanup. If EXP03 becomes active again, write a modern memo-backed recap before treating it as settled evidence.

## Relevant Methods

- [[methods/Post_Pulse_Windowing|Post-pulse windowing]]
- [[methods/PLV|PLV]]
- [[methods/ITPC|ITPC]]

## Relevant Papers

No linked papers yet.
