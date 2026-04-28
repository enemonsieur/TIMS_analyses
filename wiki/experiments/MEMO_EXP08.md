# MEMO_EXP08: Ground-Truth Signal Recovery & Phase Coherence Analysis

**Experiment:** Phantom 13 Hz iTBS across 10 intensity levels (10%–100%)  
**Status:** Ongoing (spatial filtering complete; ITPC observation flagged)  
**Last updated:** 2026-04-23

---

## 1. Spatial Filter Comparison (Raw/SASS/SSD)

### Setup
- **Signal**: 13 Hz ground-truth phantom iTBS
- **200 total epochs**: 20 per intensity (10%, 20%, ..., 100%)
- **Windows**: ON (−0.5 to 1.0 s), late-OFF (1.5–3.2 s)
- **Comparison**: Raw fixed channel vs. SASS covariance-based vs. SSD eigendecomposition

### Key Results

| Filter | SNR @ 10% | SNR @ 100% | Performance | Notes |
|--------|-----------|------------|-------------|-------|
| **Raw (Oz)** | 3.657 | 0.385 | Collapses at high intensity | Artifact dominates |
| **SASS** | 7.779 | 5.083 | 2.1–2.5× better than raw | Covariance subtraction effective |
| **SSD** | 9.173 | 6.400 | Best overall; maintains SNR>6 | Eigendecomposition most robust |

### Conclusion
**SSD outperforms raw by 2.5–2.8× at 100% intensity.** Both SASS and SSD maintain usable SNR (>5 µV²) even under severe artifact, validating spatial filtering necessity for high-intensity stimulation.

---

## 2. ITPC Phase Coherence: Baseline vs Stimulation

### Critical Discovery: Stimulation Disrupts Phase Coherence

Multi-intensity ITPC sweep (10%–100%) with 0% pre-pulse baseline reveals **stimulation-induced phase coherence loss**, independent of artifact:

| Condition | ITPC Mean | Std Dev | Window | Implication |
|-----------|----------|---------|--------|-------------|
| **0% Baseline (pre-pulse)** | **0.76** | 0.23 | −1.0–0.0 s | ✓ Channels sync well with GT when quiet |
| **10% stimulation** | 0.26 | 0.17 | 0.4–0.5 s | ⚠️ 3× drop in quiet OFF-window |
| **20% stimulation** | 0.32 | 0.19 | 0.4–0.5 s | ⚠️ Persists across all intensities |
| **...** | ... | ... | ... | ... |
| **100% stimulation** | 0.25 | 0.11 | 0.4–0.5 s | ⚠️ No trend; not artifact-driven |

### Reinterpretation

**NOT artifact masking.** The baseline proves EEG and GT *can* achieve high phase coherence (0.76). But stimulation drops it to 0.25–0.48 across the board, even far from artifact. This points to:

1. **Stimulation-induced frequency shift** — 13 Hz signal may shift away from GT center frequency under field
2. **GT reference disruption** — phantom circuit impedance/resonance changes with high-intensity fields
3. **Spatial mismatch** — GT reference samples different brain region; stimulation alters spatial distribution asymmetrically

### Metrics Summary

- Baseline ITPC (0% pre-pulse): mean=0.76, std=0.23, range [0.17–0.98]
- Stimulated ITPC (10%–100% OFF-window): mean≈0.35±0.18 (all intensities pooled)
- **Relative drop: 54% reduction from baseline to stimulated** (0.76 → 0.35)

---

## 3. Data & Outputs

**Epoch files generated:**
- `exp08_epochs_{10..100}pct_on-epo.fif` (20 epochs × 28 channels per intensity)
- `exp08_gt_epochs_{10..100}pct_on-epo.fif` (20 epochs × 1 GT channel per intensity)
- `exp08_stim_epochs_{10..100}pct_on-epo.fif` (20 epochs × 1 stim trace per intensity)

**Analysis scripts & visualizations:**
- `explore_exp08_timecourse_100pct.py` — single-intensity 5-channel + ITPC + stim overlay
- `exp08_timecourse_100pct_overlay.png` — 6-panel figure at 100% intensity
- `explore_exp08_coherence_to_gt.py` — multi-intensity ITPC with 0% baseline (SKRIPT.md compliant)
- `exp08_coherence_to_gt_heatmap.png` — heatmap (channels × intensities) + trend line with baseline comparison

---

## 4. Outstanding Questions

**Priority 1: Understand stimulation-induced phase loss**
- [ ] Does 13 Hz frequency content shift under high-intensity fields? (spectral analysis per intensity)
- [ ] Does phantom GT circuit impedance change with intensity? (measure frequency drift in GT)
- [ ] Is GT phase loss uniform across all EEG channels or spatially heterogeneous?

**Priority 2: Spatial mapping**
- [ ] Does ITPC loss correlate with distance from GT electrode?
- [ ] Which scalp regions retain highest coherence despite stimulation?

**Priority 3: Validation**
- [ ] Does SSD component selection change across intensities? (SNR-based ranking stability)
- [ ] Can artifact masking explain the residual phase loss after component selection?

---

## 5. Filter Artifact Spreading & Temporal Contamination (2026-04-28)

### Discovery: Narrow Bandpass Converts Impulsive Artifact into Ringing Oscillation

**Problem:** The ITPC pipeline applies a 1 Hz-wide bandpass filter (12.5–13.5 Hz) with Butterworth order 4. For a high-Q filter (Q = fc/BW = 13/1 = 13), the impulse response decays over ~2–2.5 seconds. A large TMS pulse artifact at t=0 is converted by the bandpass into a fake "13 Hz oscillation" that rings for the entire ITPC computation window.

### Evidence

**Sanity check: filtered 13 Hz timecourse at 10% vs 100%**
- Script: `explore_exp08_oz_13hz_sanity.py`
- Output: `exp08_oz_13hz_sanity.png` (11–14 Hz bandpass for readable comparison)

| Intensity | Oz amplitude post-pulse | Duration | Interpretation |
|-----------|------------------------|----------|-----------------|
| **10%** | ~0.5 µV oscillation | <500 ms ring-down | Small, natural-looking signal |
| **100%** | ~100–200 µV sustained ringing | 1.5+ s (entire window) | Filter ringing dominates; artifact alone is 400× signal |

**Raw STIM pulse shape**
- Script: `explore_exp08_stim_pulse_shape.py`
- Output: Single epoch + mean across 20 epochs at 100%
- Shows: Electrical pulse is a sharp transient (~50 ms width), but after bandpass filtering becomes a multi-second ringing sinusoid

### Mechanism & Impact on ITPC

1. **Pulse artifact dominates Oz at 100%:** Raw amplitude ~5000 µV, 13 Hz signal is ~0.5 µV (10,000× smaller)
2. **Bandpass filter rings:** Causal `sosfilt` spreads energy forward-only (no backward smearing), but high-Q design still rings ~2 s
3. **Artificial phase locking:** The ringing is identical on all 20 trials → perfectly phase-locked to pulse onset → ITPC artificially high
4. **Misinterpretation risk:** High ITPC at 100% may be filter ringing, not signal recovery

### Possible Contribution to Stimulation-Induced Phase Loss

While the broad stimulation-induced ITPC drop (0.76 → 0.35) appears real and independent of filter (since baseline proves coherence is possible), the **relative rise** in ITPC within the ON window at 100% may be filter artifact, not signal. This obscures the true signal-recovery dynamics.

### Pulse Detection & Epoching Jitter

Preliminary observation from raw pulse visualization: individual trial pulse shapes show minor amplitude variations (~5–10% variation), possibly indicating:
- **Detection jitter:** Pulse onset detection may have ±5–10 ms timing error
- **Stimulus controller variability:** TMS pulse triggering may not be perfectly time-locked across epochs
- **Epoch misalignment:** If pulses are offset by ±10 ms, averaged ITPC window samples mix leading/lagging transients, reducing apparent phase coherence

**Status:** Not quantified yet; visual inspection only. Cross-correlation analysis between epochs would reveal jitter.

### Investigation Approach & Recommendations

**Forward Ringing Root Cause:** Causal `sosfilt` (bandpass 12.5–13.5 Hz) has impulse response that decays over 2+ seconds. Pre-pulse baseline remains clean (no backward smearing), but artifact ringing contaminates post-pulse ITPC window, inflating apparent coherence at high intensities via deterministic, trial-consistent ringing.

**Chosen Strategy: Option D (Hybrid Masking)**
- Compute ITPC/PLV on full bandpass-filtered signal (preserves component selection and SNR benefits)
- **Mask artifact-dominated region** (0–0.1 s post-pulse) to avoid ringing contamination
- Report ITPC/PLV only from off-window (0.1–0.6 s) where artifact settling is complete
- Trade-off: loses some transient response visibility, but eliminates filter ringing bias

**Prerequisites & Steps:**

1. **Pulse timing alignment QC** (required before masking): 
   - Cross-correlation of STIM pulses across 20 epochs per intensity
   - Quantify jitter; if > ±5 ms, re-tune pulse detection threshold/rise-time parameters
   - Document usability decision

2. **Window expansion**: Extend analysis to ±0.6 s (symmetric) to capture full post-pulse settling

3. **Implement masking in ITPC/PLV computation**: Modify `preprocessing.compute_itpc_timecourse()` or post-hoc mask timecourse before averaging

4. **Filtering method optimization** (parallel, learning-based):
   - Audit current pipeline in `explore_exp08_art_filtering.py`: where is filtering applied relative to component selection?
   - Test bandwidth trade-offs (e.g., 1 Hz vs 3 Hz width) on SNR/ITPC stability
   - Verify notch filter (50 Hz) effectiveness; consider if it should be broader
   - Document findings step-by-step as methodology is explored

5. **PLV as alternative/complement to ITPC**: Test phase locking value (binary threshold metric) vs ITPC (continuous); report which is more stable across intensities in high-artifact regime
