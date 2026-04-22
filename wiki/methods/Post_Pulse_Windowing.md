---
type: method
status: active
updated: 2026-04-18
tags:
  - postpulse
  - windowing
---

# Post-Pulse Windowing

## What It Measures

Post-pulse windowing defines where the usable analysis interval starts after the stimulation pulse so that the main pulse artifact is excluded without discarding too much physiology.

## Where It Helped

- Anchored the early crop choices in [[experiments/EXP03|EXP03]].
- Provides the local reference point for later post-pulse and late-OFF discussions in the repo.

## Known Failure Modes

- Starting too early keeps residual decay artifact in the analysis window.
- Starting too late can erase the very physiology the experiment aims to study.
- A fixed crop chosen in one experiment may not transfer to another intensity or preparation.

## TIMS Verdict

This is a small but load-bearing method choice. In the current repo it is best treated as an experiment-owned rule from EXP03 and EXP04, not yet as a universally solved timing rule.

## Open Questions

- How much of the EXP03 crop logic transfers to EXP04 and higher-intensity settings?
- Should post-pulse windows eventually be parameterized by the artifact model instead of fixed by hand?

## Relevant Experiments

- [[experiments/EXP03|EXP03]]
- [[experiments/EXP04|EXP04]]

## Relevant Papers

- [Rogasch et al. (2017), TMS-EEG artifact review and timing/cleaning cautions](https://doi.org/10.1016/j.neuroimage.2016.10.031)
- [Rogasch et al. (2013), short-latency artifacts in concurrent TMS-EEG](https://doi.org/10.1016/j.brs.2013.04.004)
