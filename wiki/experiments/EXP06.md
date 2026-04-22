---
type: experiment
status: active
updated: 2026-04-18
tags:
  - exp06
  - phantom
  - itbs
---

# EXP06

## Question

Can a known `12.45 Hz` oscillation be recovered during ON and late-OFF windows across an iTBS intensity sweep, and which ranking or cleanup path is trustworthy?

## Current Conclusion

EXP06 is the current anchor experiment. Late-OFF recovery is robust across all intensities. ON-state recovery is strongly intensity dependent, with a transition around `30-40%`. The repo now treats PLV-based selection as biased under synchronized artifact conditions and currently favors SNR-based selection for ranking raw, SASS, and SSD paths.

## Evidence

- [`MEMO_exp06.md`](../../docs/memos/MEMO_exp06.md): baseline and late-OFF recovery are strong; ON-state recovery breaks at higher intensities.
- [`MEMO_EXP06_pipeline_analysis.md`](../../MEMO_EXP06_pipeline_analysis.md): documents the original raw vs SASS vs SSD comparison and the asymmetries in selection logic.
- [`MEMO_SNR_Selection_Results.md`](../../MEMO_SNR_Selection_Results.md): shows that SNR exposes artifact saturation that PLV hides.
- [`MEMO_component_selection_bias.md`](../../MEMO_component_selection_bias.md): explains why GT and STIM synchronization makes PLV a biased selector in the ON state.
- [`MEMO_exp06_sass_artifact_recovery.md`](../../MEMO_exp06_sass_artifact_recovery.md): captures the earlier PLV-led reading where SASS looked strongest at higher intensities.
- [`MEMO_exp06_artifact_propagation_summary.md`](../../MEMO_exp06_artifact_propagation_summary.md): frames artifact propagation, saturation, and decay modeling as the next blocker.

## Conflicts / Caveats

- Old PLV-led pipeline summaries can still favor SASS at `40-50%`, while the newer SNR-led summaries favor SSD as the most stable overall method.
- SASS still lacks enough diagnostics on null count, eigenvalue structure, and signal preservation.
- The artifact model is not finished yet, so the high-intensity ON-state story is still partly descriptive rather than mechanistically removed.

## Next Step

Fit per-channel decay constants and saturation curves, combine them into a composite artifact model, validate that model on EXP04, and keep using SNR with secondary phase metrics in future ON-state comparisons.

## Relevant Methods

- [[methods/PLV|PLV]]
- [[methods/SNR|SNR]]
- [[methods/SSD|SSD]]
- [[methods/SASS|SASS]]
- [[methods/ITPC|ITPC]]
- [[methods/Artifact_Modeling|Artifact modeling]]

## Relevant Papers

- [Nikulin et al. (2011), spatio-spectral decomposition](https://doi.org/10.1016/j.neuroimage.2011.01.057)
- [Haslacher et al. (2021), SASS](https://doi.org/10.1016/j.neuroimage.2020.117571)
- [Lachaux et al. (1999), measuring phase synchrony / PLV foundation](https://doi.org/10.1002/(SICI)1097-0193(1999)8:4<194::AID-HBM4>3.0.CO;2-C)
