---
type: method
status: active
updated: 2026-04-18
tags:
  - ssd
  - spatial
---

# SSD

## What It Measures

Spectral Source Decomposition finds spatial filters that maximize target-band structure relative to neighboring frequencies or a broader comparison band.

## Where It Helped

- Recovered a plausible baseline GT component in [[experiments/EXP05|EXP05]] after the target band was corrected.
- Generalized strongly to late-OFF windows in [[experiments/EXP06|EXP06]].
- Under SNR-based ranking in EXP06, it remained the most stable overall ON-state method across intensity.

## Known Failure Modes

- If the target is weak or absent, SSD can drift to a nearby artifact mode.
- Transfer can look good at baseline and then fail in stimulated data, as in EXP05.
- The conclusions depend on component ranking logic; PLV and SNR do not always tell the same story.

## TIMS Verdict

SSD is currently the strongest signal-extraction path in the repo, especially under SNR-based ranking, but it still needs explicit artifact modeling at high intensity.

## Open Questions

- How many components should be kept before ranking?
- When should baseline-trained SSD be transferred, and when should SSD be re-fit per block?

## Relevant Experiments

- [[experiments/EXP05|EXP05]]
- [[experiments/EXP06|EXP06]]

## Relevant Papers

- [Nikulin et al. (2011), spatio-spectral decomposition](https://doi.org/10.1016/j.neuroimage.2011.01.057)
