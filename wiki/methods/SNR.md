---
type: method
status: active
updated: 2026-04-18
tags:
  - snr
  - spectral
---

# SNR

## What It Measures

In the current TIMS wiki, SNR means target-band power divided by broadband power, typically `12.45 Hz +/- 0.5 Hz` over `4-20 Hz`.

## Where It Helped

- Re-ranked the EXP06 raw, SASS, and SSD paths in a way that exposed artifact saturation.
- Made the raw high-intensity collapse visible when PLV still looked strong.
- Turned method comparison from "who locks best?" to "who preserves target-band structure best?"

## Known Failure Modes

- Narrowband artifact can still fool SNR if the artifact itself carries power near the target.
- SNR depends strongly on band choice and window placement.
- SNR alone does not describe phase stability.
- **Artifact suppression ≠ signal recovery:** [[experiments/EXP08|EXP08]] shows SSD maintains SNR>6 µV² at 100% intensity but ITPC drops 3× from baseline (0.76 → 0.25) in quiet OFF-window. High SNR can hide phase disruption caused by stimulation itself.

## TIMS Verdict

SNR is the current preferred primary ranking metric for EXP06 ON-state selection and for contradiction checks against PLV-led interpretations.

## Open Questions

- Should SNR always be combined with peak-frequency gating?
- Should amplitude-envelope stability or temporal consistency be added as a tie-breaker?

## Relevant Experiments

- [[experiments/EXP05|EXP05]]
- [[experiments/EXP06|EXP06]]
- [[experiments/EXP08|EXP08]]
- [[experiments/EXP06|EXP06]]

## Relevant Papers

- [Nikulin et al. (2011), spectral extraction logic behind target-band emphasis](https://doi.org/10.1016/j.neuroimage.2011.01.057)
- [van Diepen and Mazaheri (2018), why phase consistency alone can mislead](https://doi.org/10.1038/s41598-018-20423-z)
