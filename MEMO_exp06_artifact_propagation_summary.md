# MEMO: EXP06 TIMS Artifact Propagation — Status & Next Steps

**Project:** TIMS Phantom Study — Quantifying artifact spatial distribution  
**Date:** 2026-04-14 | **Status:** Phase 1 ✅ complete; Phases 2–4 pending  
**Goal:** Build a predictive model of how TIMS artifacts spread across the scalp, enabling targeted artifact removal for real-brain iTBS-EEG.

---

## THE GOAL

During brain stimulation (iTBS at C3), TMS-evoked artifacts mask brain signals. We need to:
1. **Predict** which EEG channels will saturate (become noise) at different stimulation intensities
2. **Remove** artifact in a principled way (per-channel, distance-aware)
3. **Validate** that artifact removal improves recovery of true brain responses (TEP, ITPC)

---

## METHODS COMPLETED (Phase 1)

**Linear propagation model** relating artifact amplitude to two predictors:
- **Distance from stimulation site (C3):** Euclidean distance in standard 10-20 space
- **Stimulation intensity:** 10%, 20%, 30%, 40%, 50%

**Data:** 27 EEG channels × 5 intensity levels = 135 observations  
**Window:** Mean artifact amplitude in ON period (0.3–1.5 s post-stimulus)  
**Model:** log(amplitude) ~ distance + intensity ± interaction term

---

## KEY FINDINGS

| Finding | Implication |
|---------|-------------|
| **R² = 0.54–0.60** | Model explains moderate variance; ~40–46% unexplained |
| **Distance is 3× more predictive than intensity** in 0.3–1.5 s window | Settling dynamics (not just coil proximity) matter |
| **Counterintuitive:** farther channels (O1, O2, P4, P8 at 8–12 cm) show MORE saturation than close channels (F3, FC1 at 5–7 cm) | Close channels saturate fast & decay fast; far channels accumulate slowly but sustain artifact longer in this window |
| **Distance × intensity interaction (+0.011)** improves fit by 6% | Peripheral channels respond more to intensity changes |
| **Linear model underpredicts severe saturation** at 40–50% intensity (e.g., O2 jumps from 3 µV → 500 µV between 30–40%) | Nonlinear (threshold) saturation behavior not captured |

---

## WHAT'S MISSING (Phases 2–4)

### Phase 2A: Per-Channel Exponential Decay Constants (**Priority 1**)
- **What:** Fit A(t) = A₀ exp(−λt) + offset for each channel × intensity
- **Why:** Explains time-dependent artifact settling; enables predictions at any post-stimulus window
- **Expected gain:** Unlock 2–5× better fit at early (<0.3 s) and late (>1.5 s) windows
- **Effort:** 2–4 hours

### Phase 2B: Per-Channel Saturation Curves (**Priority 1**)
- **What:** Fit Hill saturation A(intensity) = Aₘₐₓ·I^n / (I₅₀^n + I^n) per channel
- **Why:** Captures threshold behavior; essential for 40–50% intensity protocols
- **Expected gain:** R² jumps to 0.85+; identifies which channels have anomalously low/high thresholds
- **Effort:** 2–3 hours

### Phase 2C: Composite 3D Model
- **What:** Combine decay × saturation into A(t, I) = Aₘₐₓ(I) · exp(−λ(I)·t) + offset(I)
- **Why:** Full artifact dynamics per channel (time × intensity × amplitude surface)
- **Effort:** 4–6 hours

### Phase 3: Real-Brain Validation (EXP04)
- **What:** Test EXP06 phantom model predictions on EXP04 (real brain, 100% intensity)
- **Why:** Phantom anatomy ≠ real brain; need to check if model generalizes
- **Effort:** 2–3 hours

### Phase 4: Artifact Removal Pipeline
- **What:** Operationalize the model into a denoising workflow: channel selection → decay filtering → template subtraction → SSD
- **Why:** Turn predictions into actual artifact-free TEP recovery
- **Effort:** 8–12 hours | **Impact:** Ready-to-deploy for human iTBS-EEG

---

## TIMELINE & RECOMMENDATION

| Phase | Est. Hours | Blocker? | Start? |
|-------|-----------|---------|--------|
| 2A (Decay) | 2–4 | No | Ready now |
| 2B (Saturation) | 2–3 | No | Ready now |
| 2C (Composite) | 4–6 | No (depends on 2A+2B) | After 2A+2B |
| 3 (EXP04 validation) | 2–3 | No | After 2C |
| 4 (Artifact pipeline) | 8–12 | No | After 3 |

**Recommendation:** Start **Phase 2A + 2B in parallel** (~4 hours combined) to break the underfitting problem at high intensities. Then proceed to 2C (comprehensive 3D model), 3 (validation), and 4 (pipeline).

---

## DELIVERABLES SO FAR

✅ **Code:** `explore_exp06_artifact_propagation.py` (fully reproducible, ready to extend)  
✅ **Data:** Feature matrix + model coefficients in `EXP06/exp06_run02_propagation_*.csv`  
✅ **Figures:** Distance vs. amplitude scatter, channel heatmap, model diagnostics  
✅ **Docs:** Full MEMO + task specification (TASK_exp06_artifact_spatial_modeling.md)

---

## IMMEDIATE NEXT STEP

**Fit exponential decay constants (Phase 2A) for all 27 channels × 5 intensities.**  
Input: Raw ON window EEG data (0.0–1.5 s post-stimulus)  
Output: Per-channel {A₀, λ, offset} + scatter plots of decay rate vs. distance  
Expected outcome: Explain why far channels show slower decay & higher artifact in our 0.3–1.5 s window

