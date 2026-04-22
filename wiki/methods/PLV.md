---
type: method
status: active
updated: 2026-04-18
tags:
  - plv
  - phase
---

# PLV

## What It Measures

Phase Locking Value measures how consistently a signal stays phase-aligned with a reference across time or epochs.

## Where It Helped

- Quick GT-locking checks in [[experiments/EXP06|EXP06]]
- Connectivity and pre/post summaries in [[experiments/EXP04|EXP04]]
- Earlier recovery checks before the repo shifted toward stricter spectral validity

## Known Failure Modes

- Under synchronized artifact conditions, PLV can rank artifact better than signal.
- Filtering everything around a fixed frequency can make very different signals look similarly phase-locked.
- EXP05 and EXP06 both show that phase metrics can rise on the wrong spectral mode.

## TIMS Verdict

PLV is useful as a secondary validation metric after spectral validity has already been established. It is not trusted as the primary selector for EXP06 ON-state channel or component ranking.

## Open Questions

- How useful is PLV after SNR-based preselection?
- Is PLV still safe enough for late-OFF or post-pulse windows where artifact is already low?

## Relevant Experiments

- [[experiments/EXP03|EXP03]]
- [[experiments/EXP04|EXP04]]
- [[experiments/EXP05|EXP05]]
- [[experiments/EXP06|EXP06]]

## Relevant Papers

- [Lachaux et al. (1999), measuring phase synchrony in brain signals](https://doi.org/10.1002/(SICI)1097-0193(1999)8:4<194::AID-HBM4>3.0.CO;2-C)
- [Aydore et al. (2013), note on PLV properties](https://doi.org/10.1016/j.neuroimage.2013.02.008)
