---
type: method
status: active
updated: 2026-04-18
tags:
  - artifact
  - modeling
---

# Artifact Modeling

## What It Measures

Artifact modeling in this repo means fitting how stimulation artifact changes across time, intensity, and channel so that cleanup can become predictive instead of purely descriptive.

## Where It Helped

- Framed the next-step plan in [[experiments/EXP06|EXP06]] after raw, SASS, and SSD comparisons stopped being enough.
- Showed that distance and intensity alone only partly explain artifact amplitude in EXP06.
- Defines the bridge between phantom work and the unresolved artifact problem in [[experiments/EXP04|EXP04]].

## Known Failure Modes

- The current linear propagation model underfits severe high-intensity saturation.
- A single summary window can hide decay and channel-specific settling differences.
- Modeling is still incomplete until decay constants and saturation curves are fitted explicitly.
- **Exponential decay removal (A·exp(-t/τ)+C) is insufficient in EXP08**: Even "good" channels retain non-zero baseline after removal; bad channels (P7) show 10K+ µV residual DC offsets. Suggests artifact is multi-component or non-exponential. Single exponential model does not capture the cleanup requirement.

## TIMS Verdict

Artifact modeling is now a blocker method. Stronger ON-state and real-brain claims should wait until this path is operational enough to guide cleanup and validation.

## Open Questions

- What are the per-channel decay constants across intensity?
- Which channels show threshold-like saturation behavior?
- How should the resulting model feed template subtraction, channel selection, or SSD/SASS cleanup?
- **Why does exponential decay removal fail in EXP08?** Standard A·exp(-t/τ)+C fits leave residual DC offsets (P7: 10K+ µV even in "clean" response window). Is artifact multi-component? Non-exponential tail? Per-channel baseline drift? Should we use robust regression, median baseline removal, or skip exponential fitting and rely on DC centering only?
- **Critical gap:** Current artifact model focuses on amplitude. [[experiments/EXP08|EXP08]] shows stimulation disrupts phase coherence (ITPC 0.76 → 0.25) even when artifact is physically small (OFF-window). Need frequency-shift model: does target frequency (13 Hz) drift under field? Does GT circuit impedance change with intensity?

## Relevant Experiments

- [[experiments/EXP04|EXP04]]
- [[experiments/EXP06|EXP06]]

## Relevant Papers

- [Rogasch et al. (2017), TMS-EEG artifact review and TESA introduction](https://doi.org/10.1016/j.neuroimage.2016.10.031)
- [Hernandez-Pavon et al. (2022), TMS-EEG artifact removal methods review](https://doi.org/10.1016/j.jneumeth.2022.109591)
