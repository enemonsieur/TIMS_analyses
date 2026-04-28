---
type: method
status: active
updated: 2026-04-18
tags:
  - sass
  - artifact
---

# SASS

## What It Measures

SASS removes stimulation-dominant subspaces by comparing ON-state covariance against a cleaner OFF-state covariance reference.

## Where It Helped

- Preserved in-band structure in EXP06 when raw selection became unreliable.
- In earlier PLV-led EXP06 summaries, it was the strongest method at some higher intensities.
- It remains the clearest artifact-removal step in the current repo, even when its downstream ranking story changes.

## Known Failure Modes

- It can over-null signal when artifact and signal share covariance structure.
- The SNR-based EXP06 summaries show a sharp crash at `30%`, so its benefit is method-dependent rather than monotonic.
- The current repo gives too little visibility into null counts, eigenvalues, and signal preservation.

## TIMS Verdict

SASS is promising and sometimes crucial, but more method-sensitive than SSD. It should be treated as a strong artifact-removal candidate that still needs better diagnostics and a clearer high-intensity story.

## Open Questions

- Should SASS be judged only after SNR-based ranking?
- How should null-count and eigenvalue diagnostics be exposed in future analyses?
- How well will SASS transfer to EXP04 real-brain data?

## Relevant Experiments

- [[experiments/EXP06|EXP06]]
- [[experiments/EXP08|EXP08]]
- [[experiments/EXP04|EXP04]]

## Relevant Papers

- [Haslacher et al. (2021), SASS](https://doi.org/10.1016/j.neuroimage.2020.117571)
