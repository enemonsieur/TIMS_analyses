---
type: home
status: active
updated: 2026-04-18
tags:
  - wiki
  - tims
---

# TIMS Wiki Home

## Status Update (2026-04-26)

**Literature search framework updated:** [[methods/Literature_Search_Framework|Literature search framework]] now requires causal-chain paper notes and context-preserving search angles. New [[methods/TIMS_Search_Direction|TIMS search direction]] stores the current TIMS-specific goal, advantages, constraints, accepted angles, and reject rules.

**TEP preprocessing validated:** [[methods/TEP_Preprocessing|decay → bandpass 1–80 Hz (gamma-preserving) → crop → average]] works ≤40% MSO. See script `explore_exp08_tep.py`.

**Artifact validation framework added:** New [[methods/Artifact_Removal_Validation|artifact removal validation]] page frames the central question: how to prove artifacts are actually removed (not masked)? Multi-metric approach with open questions for exploring validation beyond SNR/PLV divergences.

**Blocker:** 50–100% intensity saturates (POST 1.4K–17K µV). Next: per-channel τ or multi-exponential model.

## Current Picture

- [[experiments/EXP03|EXP03]] established the early pulse-centered post-pulse workflow and remains the local anchor for careful [[methods/Post_Pulse_Windowing|post-pulse windowing]], but it is no longer the main decision point. Evidence: [`analysis_summary.txt`](../exp03_pulse_centered_analysis_run03/analysis_summary.txt).
- [[experiments/EXP04|EXP04]] is still exploratory. The repo does not currently treat its TEP or resting-state changes as validated biological effects. Evidence: [`MEMO_exp06.md`](../docs/memos/MEMO_exp06.md).
- [[experiments/EXP05|EXP05]] showed that `30%` cTBS is cleaner than `100%` across the scalp, but the `~7.08 Hz` recovery path remained weak and drifted toward the stimulation rhythm. Evidence: [`MEMO_exp05_analysis.md`](../docs/memos/MEMO_exp05_analysis.md).
- [[experiments/EXP06|EXP06]] is the current anchor experiment: late-OFF recovery is robust, ON-state recovery is intensity dependent, and [[methods/SNR|SNR]] currently gives the most defensible ranking story. Evidence: [`MEMO_SNR_Selection_Results.md`](../MEMO_SNR_Selection_Results.md).
- The strongest blocker before stronger real-brain claims is [[methods/Artifact_Modeling|artifact modeling]] plus explicit validation on [[experiments/EXP04|EXP04]]. Evidence: [`MEMO_exp06_artifact_propagation_summary.md`](../MEMO_exp06_artifact_propagation_summary.md).

## Biggest Unresolved Contradictions

- [[experiments/EXP08|EXP08]] baseline ITPC (pre-pulse) is 0.76, but drops 3× to 0.25–0.48 under stimulation even in quiet OFF-windows. **Contradiction:** Not artifact masking (baseline proves coherence is possible), but something about stimulation itself disrupts phase. Candidate mechanisms: frequency shift under field, GT circuit impedance change, spatial reference mismatch.
- [[methods/PLV|PLV]] can show strong locking when [[methods/SNR|SNR]] shows catastrophic collapse. The current reading is "artifact locking," but older PLV-led outputs still exist in the repo.
- The relative story of [[methods/SASS|SASS]] vs [[methods/SSD|SSD]] changes with the selection rule. Some PLV-era summaries favor SASS at high intensity, while SNR-based summaries favor SSD as the most stable overall method.
- [[experiments/EXP05|EXP05]] shows that `30%` is cleaner than `100%`, but still not clean enough for a robust `~7 Hz` recovery claim. "Cleaner" must not be read as "clean."
- [[experiments/EXP04|EXP04]] still sits between biology, fatigue, and residual artifact. The current repo record does not resolve that ambiguity.

## Immediate Next Experiments

- **[[experiments/EXP08|EXP08]] High-intensity decay saturation**: POST baseline ranges spike to 1.4K–17K µV at 50–100% intensity. Current exponential model insufficient. Options: (1) per-channel decay time constants, (2) multi-exponential fit, (3) robust regression, (4) restrict analysis to ≤40% intensity. Requires decision on acceptable baseline noise.
- **[[experiments/EXP08|EXP08]] Phase loss investigation**: 0% baseline shows EEG–GT coherence is achievable (0.76), but stimulation drops it 3× in quiet windows. Investigate: does 13 Hz shift under field? Does GT circuit change impedance? Spatial reference mismatch?
- **EXP08 per-channel distance analysis**: Does ITPC loss correlate with distance from GT electrode? Which scalp regions retain phase coherence best?
- Fit per-channel decay constants and saturation curves for [[experiments/EXP06|EXP06]].
- Build a composite time × intensity × channel artifact model and turn it into a cleanup path. Revisit exponential decay sufficiency in light of EXP08 findings.
- Validate the cleanup strategy on [[experiments/EXP04|EXP04]] before promoting stronger TEP or resting-state claims.
- Keep using [[methods/SNR|SNR]] together with secondary phase metrics such as [[methods/ITPC|ITPC]] when comparing future ON-state methods.

## Experiments

- [[experiments/EXP03|EXP03]]: early phantom pulse-centered workflow and post-pulse validation.
- [[experiments/EXP04|EXP04]]: exploratory real-brain pilot at `100%` intensity; artifact validity still unresolved.
- [[experiments/EXP05|EXP05]]: phantom cTBS `30%` vs `100%`, `~7.08 Hz` GT, and the design failure that motivated a cleaner target frequency.
- [[experiments/EXP06|EXP06]]: phantom iTBS intensity sweep with the current raw vs SASS vs SSD vs metric-selection disputes.
- [[experiments/EXP07|EXP07]]: continuous dose-response (10–100% modulation) iTBS, 204 ON blocks extracted, ready for per-intensity analysis.
- [[experiments/EXP08|EXP08]]: single-pulse dose-response (10–100% intensity, 20 pulses per level), 200 epochs extracted. Spatial filter comparison (SSD > SASS > Raw) complete; ITPC multi-intensity analysis reveals baseline 0.76 but stimulation drops to 0.25–0.48 in quiet windows—not artifact masking, but stimulation-induced phase loss. **TEP cleanup (2026-04-23):** Exponential decay removal + 0.5–42 Hz bandpass filter on full epoch removes DC residuals effectively. Valid TEP extraction for 10–40% intensity (baselines <15 µV); 50–100% shows decay saturation (POST ranges 1.4K–17K µV). Implemented in [[methods/TEP_Preprocessing|TEP preprocessing]] with results table. Evidence: [`explore_exp08_tep.py`](../explore_exp08_tep.py) validated output.

## Methods

- [[methods/Post_Pulse_Windowing|Post-pulse windowing]]: local method anchor for crop placement after the pulse artifact.
- [[methods/TEP_Preprocessing|TEP preprocessing]]: decay removal + 1–80 Hz bandpass filtering (preserves gamma) for DC offset removal; validated on EXP08.
- [[methods/PLV|PLV]]: useful phase metric, but biased as a primary selector under synchronized artifact conditions.
- [[methods/SNR|SNR]]: current preferred primary selector for ON-state ranking.
- [[methods/SSD|SSD]]: strongest current signal-extraction path, but still sensitive to artifact structure and ranking logic.
- [[methods/SASS|SASS]]: promising artifact-removal step with strong but method-sensitive behavior.
- [[methods/ITPC|ITPC]]: useful secondary time-resolved phase summary, not a standalone recovery proof.
- [[methods/Artifact_Modeling|Artifact modeling]]: current blocker method for high-intensity cleanup and EXP04 translation.
- [[methods/Artifact_Removal_Validation|Artifact removal validation]]: exploration framework for distinguishing genuine artifact suppression from masking; multi-metric approach with open questions for novel validation paths.
- [[methods/Literature_Search_Framework|Literature search framework]]: general workflow for context-preserving search angles and causal-chain paper notes.
- [[methods/TIMS_Search_Direction|TIMS search direction]]: TIMS-specific paper-search context, accepted angles, and reject rules.
