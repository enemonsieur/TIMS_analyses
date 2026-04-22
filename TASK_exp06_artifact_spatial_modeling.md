# TASK: EXP06 TIMS Artifact Spatial Modeling — Distance × Intensity × Channel Response

**Status:** ✅ COMPLETED (baseline analysis done; extensions pending)  
**Created:** 2026-04-09  
**Last Updated:** 2026-04-09

---

## Overview

This task establishes a quantitative model of how TIMS artifacts propagate across the scalp as a function of:
1. **Euclidean distance** from the stimulation site (C3, left M1)
2. **Stimulation intensity** (10% to 50%)
3. **Channel-specific properties** (impedance, settling timescale)

**Goal:** Predict artifact magnitude per channel per intensity, and use this to inform artifact-removal strategies for real-brain iTBS-EEG.

---

## Completed Work (Baseline Analysis)

### ✅ Phase 1: Distance × Amplitude × Intensity Propagation Model

#### What Was Done
1. **Loaded electrode positions** from standard 10-20 montage (MNE `standard_1020`)
2. **Computed Euclidean distances** from C3 for all 27 retained EEG channels
3. **Joined with amplitude data** from `exp06_run02_on_channel_saturation.csv` (5 intensities × 27 channels)
4. **Fitted two linear propagation models:**
   - **Model 1 (additive):** log(amplitude) ~ distance + intensity (R² = 0.54)
   - **Model 2 (with interaction):** log(amplitude) ~ distance + intensity + distance×intensity (R² = 0.60)

#### Key Findings
- **Counterintuitive:** Channels **farther from C3** show **more artifact** (in the 0.3–1.5 s ON window)
  - Posterior channels (O1, O2, P4, P8) are most saturated despite distance 8–12 cm
  - Anterior channels (F3, FC1, FC5) stay clean despite proximity (~5–7 cm)
  - Suggests different settling timescales: close channels saturate & decay early; far channels accumulate artifact slowly but sustain it
  
- **Intensity is a weaker predictor than distance** (coefficient 0.116 vs 0.309)
  - Likely because our ON window (0.3–1.5 s) avoids the steepest post-stimulus transient (<0.3 s)
  - Intensity effects are strongest in the very early or raw cycle-amplitude regime
  
- **Distance × Intensity interaction** improves fit by 6%
  - Suggests saturation thresholds vary by channel location
  - Peripheral channels respond more strongly to intensity increases

#### Output Files
```
EXP06/
├── exp06_run02_artifact_propagation_features.csv    # Feature matrix (135 rows)
├── exp06_run02_propagation_models.csv              # Model coefficients
├── exp06_run02_propagation_scatter.png             # Distance vs amp per intensity
├── exp06_run02_propagation_heatmap.png             # Channel × Intensity heatmap
└── exp06_run02_propagation_model_diagnostics.png   # Model fit & residuals

docs/memos/
└── MEMO_exp06_propagation_model.md                 # Full analysis report
```

#### Script
- `explore_exp06_artifact_propagation.py` — end-to-end pipeline

---

## Pending Extensions (Not Yet Started)

### 🔶 Phase 2A: Per-Channel Exponential Decay Constants [RECOMMENDED PRIORITY]

**Why:** Decay timescales vary by channel. Capturing this will improve predictions at different post-stimulus windows.

**What to do:**
1. Extract raw ON window data (0.0–1.5 s post-onset) for each channel × intensity block
2. Compute **20-cycle average waveform** (mean across ON windows)
3. Fit exponential decay model: $A(t) = A_0 \exp(-\lambda t) + \text{offset}$
4. Record per channel × intensity: $\{A_0, \lambda, \text{offset}, R^2_{\text{fit}}\}$
5. Analyze:
   - Does $\lambda$ (decay rate) correlate with distance? (hypothesis: far channels have slower decay)
   - Does $A_0$ (initial amplitude) correlate with intensity?
   - Which channels show biphasic decay (fast + slow components)?

**Output:**
- `exp06_run02_artifact_decay_constants.csv` (27 channels × 5 intensities × {A0, lambda, offset})
- Decay vs. distance scatter plots (one per intensity)
- Summary: which channels are "fast-settling" vs. "long-tailed"?

**Use:** Build a **time-resolved artifact model** for any post-stimulus window, not just 0.3–1.5 s.

---

### 🔶 Phase 2B: Per-Channel Saturation Curves [RECOMMENDED PRIORITY]

**Why:** Some channels show threshold behavior (e.g., O2: 3 µV at 30%, 500 µV at 40%). Linear model misses this.

**What to do:**
1. For each channel, extract the 5 amplitude values (10%, 20%, 30%, 40%, 50% intensity)
2. Fit **Hill saturation curve:** $A(\text{intensity}) = \frac{A_{\max} \cdot \text{intensity}^n}{I_{50}^n + \text{intensity}^n}$
3. Record per channel: $\{A_{\max}, I_{50}, n\}$ (saturation level, half-saturation intensity, Hill coefficient)
4. Visualize: saturation curves colored by distance from C3
5. Test whether $I_{50}$ or $n$ correlates with distance

**Output:**
- `exp06_run02_artifact_saturation_curves.csv` (27 channels × {Amax, I50, n, distance})
- Saturation curve plot (27 curves overlaid, colored by distance)
- Summary: which channels have low vs. high saturation thresholds?

**Use:** **Better predictions for high-intensity protocols** (40–50%), which is critical for iTBS.

---

### 🔶 Phase 2C: Combine Decay + Saturation [BEST MODEL]

**What to do:**
Fit a **composite per-channel model:**
$$A(t, \text{intensity}) = A_{\max}(\text{intensity}) \cdot \exp(-\lambda(\text{intensity}) \cdot t) + \text{offset}$$

where $A_{\max}$ and $\lambda$ both depend on intensity (via the saturation and decay relationships).

This gives a **3D surface: time × intensity × amplitude** per channel, fully capturing artifact dynamics.

**Output:**
- 3D surface plots per channel
- Validation: predict artifact at any post-stimulus window and intensity

---

### 🟡 Phase 3: Validate on EXP04 (Real Brain, 100% Intensity)

**Why:** The phantom model may not generalize to real brain. Different scalp impedance, cerebrospinal fluid distribution, and anatomy.

**What to do:**
1. If EXP04 has artifact cycle waveforms at 100% intensity, extract per-channel amplitudes
2. Re-compute distances from the actual C3 stimulation site (may differ from standard 10-20 C3)
3. Apply the EXP06 distance model: predict EXP04 artifact
4. Compare predicted vs. actual; compute model error per channel
5. If large errors, re-fit the model on EXP04 data (may be underpowered with 1 subject, but useful baseline)

**Output:**
- EXP04 artifact vs. distance scatter (actual + EXP06 model predictions)
- Cross-validation: EXP06 model applied to EXP04

---

### 🟡 Phase 4: Extend to EXP05 (Real Brain, Variable Intensity)

**Why:** EXP05 had multiple intensities and real brain. Test generalization across experiments and subjects (if available).

---

### 🟢 Phase 5: Build Artifact Removal Pipeline

**Once decay + saturation models are done:**

1. **Channel selection:** Identify channels that will be saturated at a given intensity
2. **Template subtraction:** For high-saturation channels, compute artifact template and subtract
3. **Per-channel decay filtering:** Apply channel-specific exponential filters to remove tail artifact
4. **SSD enhancement:** Re-apply SSD after per-channel denoising
5. **Validation:** Re-analyze EXP06 ON recovery with improved artifact removal

---

## Decision Space

### Which Phase to Do Next?

- **Recommended sequence:** 2A (decay) → 2B (saturation) → 2C (composite) → 3 (EXP04 validation)
- **Minimum viable extension:** 2B (saturation curves) alone will substantially improve predictions for high-intensity regimes
- **Quick win:** 2A (decay) requires only raw file loading + fitting, no new concepts

### Effort Estimates (Rough)

| Phase | Time | Difficulty | Impact |
|-------|------|-----------|--------|
| 2A: Decay | 2–4 hours | Low | High (unlocks time-resolved predictions) |
| 2B: Saturation | 2–3 hours | Low | High (fixes 40–50% intensity predictions) |
| 2C: Composite | 4–6 hours | Medium | Very high (3D artifact model) |
| 3: EXP04 validation | 2–3 hours | Low | High (cross-experiment validation) |
| 4: Real pipeline | 8–12 hours | Medium–High | Critical for human TMS-EEG |

---

## Questions for Planning

### Open Questions

1. **Should we prioritize decay or saturation first?**
   - Decay is easier but saturation is more immediately useful for 40–50% protocols
   - Recommendation: do both in parallel (separate scripts), takes ~4 hours total

2. **Should EXP04 validation wait until Phase 2 is done?**
   - Yes, unless EXP04 has confounding artifact issues that would invalidate the model
   - Phase 1 baseline is publishable on its own; Phase 2 + 3 make it much stronger

3. **Do we need to fit per-channel models, or can we use a global equation?**
   - Per-channel is richer but noisier (27 independent models)
   - Global (as in Phase 1) is simpler but less flexible
   - Recommendation: Phase 2B (saturation) should be per-channel; it's simple (3 parameters per curve) and reveals which channels have anomalous thresholds

---

## Success Criteria

- ✅ **Phase 1 (baseline):** R² > 0.50, distance coefficient significant, interpreted
  - **Status:** DONE ✅
  
- 🔶 **Phase 2 (decay + saturation):** Per-channel exponential fit & Hill saturation, R² > 0.85 when combined with distance
  - **Status:** Not started
  
- 🔶 **Phase 3 (validation):** EXP04 predicted vs. actual agreement within 1–2 log units for all channels
  - **Status:** Not started
  
- 🟢 **Phase 4 (pipeline):** Real-brain TEP recovery improves by >10% (ITPC or coherence) after per-channel denoising
  - **Status:** Not started

---

## Related Work

- `MEMO_exp06_run02_on_artifact_filtering.md` — ON state saturation analysis (context for why saturation matters)
- `MEMO_exp06.md` — Full EXP06 results and findings
- `explore_exp06_artifact_propagation.py` — Baseline script (reuse for Phase 2)
- `explore_exp06_run02_on_channel_saturation.py` — Amplitude computation (reference for methodology)

---

## Files to Preserve & Extend

```
explore_exp06_artifact_propagation.py        # Main script; extend for Phases 2A–2C
EXP06/exp06_run02_*_propagation_*.csv        # Feature outputs; add decay/saturation CSVs here
docs/memos/MEMO_exp06_propagation_model.md   # Update with Phase 2 findings
```

---

## Implementation Notes

### Code Reuse
- MNE montage loading: already in script ✅
- Scipy `curve_fit` for exponential: import scipy.optimize; should work fine
- Hill saturation fit: use scipy.optimize.curve_fit with Hill function
- Plotting: matplotlib, seaborn ready to extend

### Data Availability
- All amplitude data in `exp06_run02_on_channel_saturation.csv` ✅
- Raw EEG at `TIMS_data_sync/pilot/doseresp/exp06-STIM-iTBS_run02.vhdr` ✅
- No missing data; ready to proceed

---

## History

| Date | Phase | Status | Notes |
|------|-------|--------|-------|
| 2026-04-09 | 1 | ✅ Complete | Baseline distance × amplitude × intensity model; R² = 0.54–0.60 |
| TBD | 2A | 🔶 Pending | Exponential decay constants per channel per intensity |
| TBD | 2B | 🔶 Pending | Per-channel saturation curves (Hill model) |
| TBD | 2C | 🔶 Pending | Composite time × intensity × amplitude model |
| TBD | 3 | 🟡 Pending | EXP04 real-brain validation |
| TBD | 4 | 🟢 Pending | Artifact removal pipeline & real-brain TEP recovery |

