---
type: home
status: active
updated: 2026-04-18
tags:
  - wiki
  - tims
---

# TIMS Wiki Home

## Current Picture

- [[experiments/EXP03|EXP03]] established the early pulse-centered post-pulse workflow and remains the local anchor for careful [[methods/Post_Pulse_Windowing|post-pulse windowing]], but it is no longer the main decision point. Evidence: [`analysis_summary.txt`](../exp03_pulse_centered_analysis_run03/analysis_summary.txt).
- [[experiments/EXP04|EXP04]] is still exploratory. The repo does not currently treat its TEP or resting-state changes as validated biological effects. Evidence: [`MEMO_exp06.md`](../docs/memos/MEMO_exp06.md).
- [[experiments/EXP05|EXP05]] showed that `30%` cTBS is cleaner than `100%` across the scalp, but the `~7.08 Hz` recovery path remained weak and drifted toward the stimulation rhythm. Evidence: [`MEMO_exp05_analysis.md`](../docs/memos/MEMO_exp05_analysis.md).
- [[experiments/EXP06|EXP06]] is the current anchor experiment: late-OFF recovery is robust, ON-state recovery is intensity dependent, and [[methods/SNR|SNR]] currently gives the most defensible ranking story. Evidence: [`MEMO_SNR_Selection_Results.md`](../MEMO_SNR_Selection_Results.md).
- The strongest blocker before stronger real-brain claims is [[methods/Artifact_Modeling|artifact modeling]] plus explicit validation on [[experiments/EXP04|EXP04]]. Evidence: [`MEMO_exp06_artifact_propagation_summary.md`](../MEMO_exp06_artifact_propagation_summary.md).

## Biggest Unresolved Contradictions

- [[methods/PLV|PLV]] can show strong locking when [[methods/SNR|SNR]] shows catastrophic collapse. The current reading is "artifact locking," but older PLV-led outputs still exist in the repo.
- The relative story of [[methods/SASS|SASS]] vs [[methods/SSD|SSD]] changes with the selection rule. Some PLV-era summaries favor SASS at high intensity, while SNR-based summaries favor SSD as the most stable overall method.
- [[experiments/EXP05|EXP05]] shows that `30%` is cleaner than `100%`, but still not clean enough for a robust `~7 Hz` recovery claim. "Cleaner" must not be read as "clean."
- [[experiments/EXP04|EXP04]] still sits between biology, fatigue, and residual artifact. The current repo record does not resolve that ambiguity.

## Immediate Next Experiments

- Fit per-channel decay constants and saturation curves for [[experiments/EXP06|EXP06]].
- Build a composite time x intensity x channel artifact model and turn it into a cleanup path.
- Validate the cleanup strategy on [[experiments/EXP04|EXP04]] before promoting stronger TEP or resting-state claims.
- Keep using [[methods/SNR|SNR]] together with secondary phase metrics such as [[methods/ITPC|ITPC]] when comparing future ON-state methods.

## Experiments

- [[experiments/EXP03|EXP03]]: early phantom pulse-centered workflow and post-pulse validation.
- [[experiments/EXP04|EXP04]]: exploratory real-brain pilot at `100%` intensity; artifact validity still unresolved.
- [[experiments/EXP05|EXP05]]: phantom cTBS `30%` vs `100%`, `~7.08 Hz` GT, and the design failure that motivated a cleaner target frequency.
- [[experiments/EXP06|EXP06]]: phantom iTBS intensity sweep with the current raw vs SASS vs SSD vs metric-selection disputes.
- [[experiments/EXP07|EXP07]]: continuous dose-response (10–100% modulation) iTBS, 204 ON blocks extracted, ready for per-intensity analysis.
- [[experiments/EXP08|EXP08]]: single-pulse dose-response (10–100% intensity, 20 pulses per level), 200 epochs extracted, comparison point for stimulus-structure effects.

## Methods

- [[methods/Post_Pulse_Windowing|Post-pulse windowing]]: local method anchor for crop placement after the pulse artifact.
- [[methods/PLV|PLV]]: useful phase metric, but biased as a primary selector under synchronized artifact conditions.
- [[methods/SNR|SNR]]: current preferred primary selector for ON-state ranking.
- [[methods/SSD|SSD]]: strongest current signal-extraction path, but still sensitive to artifact structure and ranking logic.
- [[methods/SASS|SASS]]: promising artifact-removal step with strong but method-sensitive behavior.
- [[methods/ITPC|ITPC]]: useful secondary time-resolved phase summary, not a standalone recovery proof.
- [[methods/Artifact_Modeling|Artifact modeling]]: current blocker method for high-intensity cleanup and EXP04 translation.
