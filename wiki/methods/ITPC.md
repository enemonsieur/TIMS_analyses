---
type: method
status: active
updated: 2026-04-18
tags:
  - itpc
  - phase
---

# ITPC

## What It Measures

Inter-trial phase coherence summarizes how consistently phase aligns across repeated events and is useful as a time-resolved phase-stability view.

## Where It Helped

- Validated time-course behavior in [[experiments/EXP06|EXP06]] after the shift toward SNR-based ranking.
- Helped show that raw high-intensity data can spike in phase consistency even when artifact dominates.
- Supports post-selection validation more naturally than primary ranking.

## Known Failure Modes

- If the upstream selector is already biased, ITPC will faithfully summarize that bias.
- High ITPC alone does not prove that the right frequency dominates the data.
- Strong synchronization between STIM and GT can make artifact look cleaner than it is.
- **Stimulation-induced frequency shift:** ITPC can drop 3× from baseline even in quiet OFF-windows, suggesting magnetic/electrical stimulation disrupts phase coherence independent of artifact (seen in [[experiments/EXP08|EXP08]]: baseline 0.76 → stimulated 0.25–0.48).

## TIMS Verdict

ITPC is a useful secondary metric for timing and stability checks, but not a standalone proof of successful recovery.

## Open Questions

- Which windows and averaging rules are most stable across intensities?
- Should ITPC be reported only after spectral validity has already passed?
- **Critical:** How should ITPC be interpreted when stimulation itself (not artifact) causes phase loss? [[experiments/EXP08|EXP08]] shows baseline 0.76 → stimulated 0.25–0.48 even in quiet OFF-windows. Is this frequency shift, GT circuit disruption, or spatial reference mismatch?

## Relevant Experiments

- [[experiments/EXP04|EXP04]]
- [[experiments/EXP06|EXP06]]
- [[experiments/EXP08|EXP08]] — baseline vs stimulation comparison reveals stimulation-induced phase loss

## Relevant Papers

- [van Diepen and Mazaheri (2018), caveats of inter-trial phase coherence](https://doi.org/10.1038/s41598-018-20423-z)
