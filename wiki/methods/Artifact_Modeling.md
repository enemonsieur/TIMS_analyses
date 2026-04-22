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

## TIMS Verdict

Artifact modeling is now a blocker method. Stronger ON-state and real-brain claims should wait until this path is operational enough to guide cleanup and validation.

## Open Questions

- What are the per-channel decay constants across intensity?
- Which channels show threshold-like saturation behavior?
- How should the resulting model feed template subtraction, channel selection, or SSD/SASS cleanup?

## Relevant Experiments

- [[experiments/EXP04|EXP04]]
- [[experiments/EXP06|EXP06]]

## Relevant Papers

- [Rogasch et al. (2017), TMS-EEG artifact review and TESA introduction](https://doi.org/10.1016/j.neuroimage.2016.10.031)
- [Hernandez-Pavon et al. (2022), TMS-EEG artifact removal methods review](https://doi.org/10.1016/j.jneumeth.2022.109591)
