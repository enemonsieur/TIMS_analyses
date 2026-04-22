---
type: experiment
status: tentative
updated: 2026-04-18
tags:
  - exp04
  - human
  - tep
---

# EXP04

## Question

Do the real-brain `100%` TIMS pilot recordings contain interpretable TEP and pre/post resting-state changes after artifact cleanup?

## Current Conclusion

EXP04 remains an exploratory single-subject pilot. The repo contains usable-looking TEP and pre/post resting-state outputs, but the current interpretation is still conditional: artifact behavior at `100%` intensity has not been characterized well enough to promote these findings to a strong biological claim.

## Evidence

- [`MEMO_exp06.md`](../../docs/memos/MEMO_exp06.md): the appendix treats EXP04 as exploratory and explicitly says post-pulse spectral and TEP results remain unverified until artifact characterization is done.
- [`exp04_topo_video_summary.txt`](../../EXP04_TEP_analysis/exp04_topo_video/exp04_topo_video_summary.txt): `75` valid pulses, `19` retained channels, `0.08-0.508 s` post window, and per-channel exponential decay subtraction.
- [`readme.md`](../../readme.md): lists `analyses_TEP_exp04.py`, `analyses_spectral_exp04.py`, and `analyses_dynamics_exp04.py` as the main exp04 analyses.

## Conflicts / Caveats

- TEP differences may still reflect residual artifact rather than neural response.
- The pre/post power and PLV changes can also be explained by fatigue or drowsiness; there is no sham and no replication in the current record.
- EXP06 makes the artifact question harder, not easier, because it shows how intensity-dependent and channel-dependent the artifact can be.

## Next Step

Run an EXP04 artifact characterization pass analogous to EXP06 and confirm that the chosen post-pulse windows are genuinely artifact-free before promoting stronger TEP or connectivity claims.

## Relevant Methods

- [[methods/PLV|PLV]]
- [[methods/ITPC|ITPC]]
- [[methods/Artifact_Modeling|Artifact modeling]]

## Relevant Papers

- [Rogasch et al. (2017), TMS-EEG artifact review and TESA introduction](https://doi.org/10.1016/j.neuroimage.2016.10.031)
- [Hernandez-Pavon et al. (2022), TMS-EEG artifact removal methods review](https://doi.org/10.1016/j.jneumeth.2022.109591)
