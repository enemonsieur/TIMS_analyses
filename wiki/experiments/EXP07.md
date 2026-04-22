---
type: experiment
status: active
updated: 2026-04-21
tags:
  - exp07
  - continuous
  - itbs
  - dose-response
  - 10-to-100-percent
  - pulse-detection
  - epoch-extraction
---

# EXP07

## Question

Can we reliably detect pulse onsets and extract repeating ON/OFF epochs from a continuous dose-response (10–100% modulation) iTBS recording? What is the structure, stability, and artifact dynamics across 204 detected ON blocks spanning 20 minutes?

## What We Did

**Experiment:** Continuous dose-response intertheta burst stimulation (iTBS) with modulation varying from 10% to 100%. Run02 data: `exp07-STIM-iTBS_run02_mod100pct.vhdr`.

**Pipeline:** 
1. Loaded 31 EEG channels + stim timing + ground_truth reference at 1000 Hz
2. Per-channel demeaning to remove DC offsets
3. Identified CP2 as most stable reference channel (polyfit slope method: -1.8e-9 V/sample)
4. Removed polynomial drift (degree 1) from CP2 to enable clean envelope detection
5. Computed Hilbert transform of detrended CP2
6. Detected first pulse onset: envelope ≥ (300 ms rolling baseline) + 25 µV, skipping first 5 s startup
7. Built repeating ON/OFF windows anchored to first onset: 2 s ON + 4 s OFF (6 s cycle)
8. Generated 204 valid ON blocks spanning 11.32 s → 1229.32 s
9. Created MNE Epochs object (204 epochs × 31 channels × 2001 samples @ 1000 Hz)
10. Saved epochs to `exp07_epochs-epo.fif`

## Key Findings

### Data Characteristics
- **Recording duration:** 1238.2 s (~20.6 min)
- **EEG channels:** 31 (after dropping stim + ground_truth)
- **Sampling rate:** 1000 Hz
- **Continuous stimulus:** Dose-response (10–100% modulation, ON/OFF throughout entire session)

### Pulse Onset Detection
- **First pulse onset:** 11.32 s (sample 11322)
- **Detection method:** Hilbert envelope of detrended CP2, threshold 25 µV above 300 ms rolling baseline
- **Why CP2?** Lowest polyfit drift slope (-1.8e-9 V/s), indicating minimal secular drift over 1238 s
- **Threshold choice:** 25 µV above baseline = amplitude change that marks pulse edge without capturing noise

### Block Structure
- **Detected blocks:** 204 ON windows (all valid, within recording bounds)
- **ON block duration:** 2 s (2000 samples)
- **Cycle period:** 6 s (2 s ON + 4 s OFF, repeating from first_onset)
- **First block onset:** 11.32 s
- **Last block onset:** 1229.32 s
- **Block spacing:** Perfectly regular (6000 samples apart = 6 s)
- **Expected blocks:** ⌊(1238200 - 11322) / 6000⌋ = 204 ✓

### Detrending & Stability
- **Per-channel demean:** Applied to all 31 channels to remove individual baselines
- **Polynomial drift removal:** Degree-1 polyfit on CP2 preserves rapid envelope dynamics while removing linear drift
- **Residual offset:** Channels show ~1-3 mV offset in first 5 s (before stimulus starts); this is normal for hardware startup and will be handled during epoch-level baseline correction in downstream analyses

### Envelope Dynamics
- **CP2 envelope pre-onset (0–11.32 s):** Low amplitude (~10–50 µV), noise floor
- **CP2 envelope during ON blocks:** Peak amplitude ~100–200 µV per block (transient response to pulse onset)
- **CP2 envelope during OFF blocks:** Falls back to ~10–50 µV baseline
- **Temporal trend:** Envelope remains stable across all 204 blocks; no visible decay or saturation (unlike EXP06 higher-intensity blocks)

## Outputs

- **Epochs file:** `EXP07/exp07_epochs-epo.fif` — 204 ON epochs, ready for analysis
- **Detrending plot:** `01_ref_channel_detrending.png` — raw vs. detrended CP2 (first 60 s)
- **Pulse detection plot:** `02_pulse_onset_detection.png` — envelope, baseline, detected onset (first 20 s)
- **Block timing plot:** `03_block_timing_all_204_blocks.png` — CP2 envelope (log scale) with all 204 ON blocks shaded (blue)

## Next Steps: Analyses Using the Epochs

The epochs file enables the following downstream analyses:

### 1. **Channel-Level Signal Recovery (Raw Path)**
Load epochs, band-pass to target band (12.5–14.5 Hz), compute per-channel metrics:
- **PLV** (phase locking value) to ground_truth channel per epoch → histogram / time course
- **SNR** (signal-to-broadband-noise power ratio) per channel → identify best raw channel
- **ITPC** (inter-trial phase coherence) per channel → phase stability across 204 blocks
- **Output:** Channel ranking by SNR; identify which channels are least artifact-contaminated

**Expected behavior:** EXP07 is a dose-response study (10–100% modulation), so SNR should vary with intensity across the 204 blocks. Higher modulation = higher artifact; lower modulation = cleaner signal. Compare SNR trends to intensity levels.

### 2. **Spatial Artifact Mapping**
Compute per-electrode artifact metrics:
- **Broadband power ratio** (ON / OFF average power) per channel → identifies spatially-heterogeneous artifact
- **Peak frequency shift** (does 12.5–14.5 Hz peak move under stim?) — requires PSD per epoch, spectral analysis
- **Inter-electrode coherence** during ON blocks → reveals whether artifact is global or localized
- **Output:** Spatial map of artifact burden; identify if artifact clusters near CP2 or spreads evenly

### 3. **Artifact Suppression Candidates (SASS + SSD Paths)**
- **SASS:** Compare ON vs. OFF epoch covariances; null high-eigenvalue components; measure residual artifact
- **SSD:** Generalized eigendecomposition of ON vs. OFF → extract artifact-minimized component
- **Output:** Best-preserved component per path; compare SNR before/after filtering
- **Validation:** Use same SNR + ITPC metrics as raw path to compare recovery quality

### 4. **Artifact Decay / Settling Dynamics**
Since each ON block lasts 2 s:
- **Extract sliding windows** within each ON block: 0–0.5 s, 0.5–1 s, 1–1.5 s, 1.5–2 s
- **Compute SNR per sub-window** → does artifact settle faster at start of block or remain constant?
- **Output:** Artifact decay time constant; informs whether artifact is transient (settling) or persistent (saturation)
- **Expectation:** If settling time ~0.3–0.5 s (as in EXP06), earliest sub-window will be noisiest; later windows should recover

### 5. **Within-Block vs. Between-Block Variability**
- **Within-block:** Compute SNR, PLV, ITPC per epoch (204 values)
- **Between-block:** Measure trial-to-trial consistency of phase and power
- **Output:** Coefficient of variation; reveals if stim response is repeatable or noisy
- **Use case:** High within-block stability + low between-block variability = reliable signal; opposite pattern = artifact

### 6. **Comparison to Ground Truth**
The `ground_truth` channel (recorded 12.5–14.5 Hz test signal) allows direct validation:
- Load ground_truth epochs using same block onsets
- Compute cross-epoch correlation between best raw channel and GT per block
- **Output:** Fidelity plot showing how well raw signal tracks GT across 204 blocks
- **Expected:** Near-perfect correlation if artifact is minimal; low correlation if artifact masks signal

### 7. **Frequency Content & Bandwidth Stability**
- **Welch PSD** per epoch in view band (4–20 Hz) → average power spectrum
- **Peak frequency tracking** — does the 12.5 Hz peak remain at 12.5 Hz, or does it shift (artifact harmonic)?
- **Broadband elevation** — compare ON vs. OFF PSD shape; identify if artifact adds 1/f slope
- **Output:** PSD grid (204 epochs × frequency bins); contour plot showing freq evolution over session

### 8. **Phase Alignment & ITPC Reliability**
- Compute ITPC per frequency band (narrow: 12.5–14.5 Hz; broad: 4–20 Hz)
- Compare ITPC to GT phase reference
- **Output:** ITPC by frequency × epoch; reveals phase consistency (high ITPC = reliable phase locking; low = jitter)
- **Interpretation:** ITPC > 0.9 = excellent sync; 0.7–0.9 = acceptable; < 0.7 = unreliable (artifact-driven jitter)

## Conflicts / Caveats

- **First 5 seconds:** Data shows non-zero DC offset during startup (before stimulus onset). This is normal hardware initialization and does NOT affect epoch extraction, since all epochs start at 11.32 s (well after startup). Baseline correction in downstream analyses will handle residual offsets.
- **Demean timing:** Per-channel demean was applied to full recording before epoch extraction. Epochs will also benefit from within-epoch baseline correction (e.g., baseline window 0–0.5 s per epoch) during analysis.
- **Ground truth availability:** Need to verify that ground_truth channel is present and aligned in the epochs file; if not, extract it separately from raw VHDR.
- **Block regularity:** All 204 blocks are perfectly spaced (6 s cycle). If this appears "too perfect," check whether the stimulus itself is software-timed (predictable) vs. hardware-timed (subject to jitter). Current data suggests stimulus is highly regular.

## Methods Used

- [[methods/Hilbert|Hilbert Transform]] — envelope detection for pulse onset
- [[methods/Polyfit|Polynomial Baseline Removal]] — degree-1 drift removal
- [[methods/PLV|PLV]] — phase locking value (for downstream analysis)
- [[methods/SNR|SNR]] — signal-to-noise ratio (recommended metric for 100% constant stim)
- [[methods/ITPC|ITPC]] — inter-trial phase coherence
- [[methods/SSD|SSD]] — spatio-spectral decomposition
- [[methods/SASS|SASS]] — stimulation artifact source separation

## Relevant Prior Work

- EXP06 (dose-response phantom study): artifact saturation at high intensity; SNR more reliable than PLV under high-artifact conditions
- EXP04 (post-pulse timing): refined ON-window selection (0.3–1.5 s); late-OFF stability as artifact-free baseline
- MEMO_exp06_propagation_model.md: artifact amplitude depends on distance + intensity; distance is 3x more predictive than intensity in 0.3–1.5 s window

## Script Reference

**Primary script:** `explore_exp07_make_epochs.py`
- Loads VHDR, detects pulse, builds epochs, saves to .fif
- Configuration parameters: `PULSE_ONSET_THRESHOLD_UV`, `BASELINE_WINDOW_S`, `ON_DURATION_S`, `OFF_DURATION_S`
- Outputs: epochs + 3 diagnostic plots (detrending, onset detection, block timing)
- Line count: ~170 lines, follows SKRIPT.md structure with pipeline overview + section hierarchy + inline comments
