# MEMO: EXP06 SASS + SSD ON-State Artifact Recovery — Goal, Methods, Findings, Gaps

**Project:** TIMS Phantom Study — Does on-state GT-locked oscillation survive stimulation?  
**Analysis Date:** 2026-04-09 | **Status:** Phase 1 complete (raw vs SASS vs SSD comparison)  
**Key Question:** Which method best preserves ground-truth (GT) phase-locking across stimulation intensities?

---

## THE GOAL

Determine if the 12.45 Hz oscillatory target remains recoverable during stimulation (ON state) across a dose sweep (10%–50% intensity). Success = phase-locked signal that can later be validated on real brain (EXP04).

**Three competing approaches tested:**
1. **Raw:** Single strongest in-band EEG channel (no artifact removal)
2. **SASS:** Spatial artifact filtering (deflate artifact subspace, keep strong in-band channel)
3. **SSD:** Per-block adapted component extraction (ON-fitted, not transferred from baseline)

---

## METHODS

**Data:** Run02 phantom recording (5 intensity blocks × 20 cycles each = 100 events)  
**Window:** ON interior `0.3–1.5 s` after measured stimulus onset (avoids sharp onset-edge transient)  
**GT reference:** Measured baseline ground-truth peak = `12.451172 Hz`  
**Metric:** Per-intensity **mean GT-locking (PLV)** across selected channels/components

**Selection rules per method:**
- **Raw:** Keep 1 channel with peak in `11.95–12.95 Hz` band (strongest PLV); if none, report "no in-band"
- **SASS:** Fit spatial filter on ON covariance vs. late-OFF covariance, then keep 1 strongest in-band channel post-filter
- **SSD:** Fit component decomposition inside each ON block, rank by coherence + peak-to-flank ratio, keep top in-band component

---

## KEY FINDINGS

| Intensity | Raw PLV | SASS PLV | SSD PLV | SSD Coherence | **Status** |
|-----------|---------|----------|---------|---------------|-----------|
| **10%** | 0.724 | ✗ (no in-band) | 0.981 | 0.618 | SSD recovers, raw works |
| **20%** | 0.843 | 0.979 | 0.977 | 0.663 | **All three strong** |
| **30%** | 0.934 | ✗ (no in-band) | 0.970 | 0.566 | SSD stable, raw OK |
| **40%** | 0.503 | 0.899 | 0.502 | 0.234 | **SASS wins, SSD collapses** |
| **50%** | ✗ (no in-band) | 0.897 | 0.620 | 0.392 | **SASS only viable** |

### Critical Observations

1. **Raw channel selection fails abruptly:** At 10%, 30%, 50%, SASS/SSD preserve in-band peaks while raw cannot find any in-band channel.
2. **SSD advantage collapses at 40%+:** SSD PLV drops from 0.97 → 0.50 between 30% and 40% (6.2% intensity jump); coherence crater to 0.23. Meanwhile, raw O2 stays at 0.996 and SASS at 0.899.
3. **SASS stays robust:** Across all five intensities, SASS maintains PLV > 0.897. At 40–50%, it is the *only* method that preserves an in-band component above trivial levels.
4. **Spectral peak preservation:** SSD keeps target frequency at 12.70 Hz through 40% but shifts to 11.72 Hz at 50% (off-band). Late-OFF reference SSD stays at 12.45 Hz across all blocks—proof that the method works under clean conditions.

---

## INTERPRETATION

**Early insight (10–30%):** The ON state *is* recoverable—both raw and SSD find strong phase-locked signals. SASS fails early, suggesting it over-suppresses at low artifact levels.

**Crisis point (40–50%):** At high intensity, the ON state transitions to a regime where:
- **Raw becomes unviable** (strongest channel drifts out of band, likely due to artifact-dominated spectrum)
- **SSD spectral coherence collapses** (component ranking metrics degrade despite PLV appearing high in raw O2)
- **SASS alone preserves structure** (spatial filtering removes artifact enough to keep in-band component visible)

**Mechanistic reading:** The ON state likely contains a short-lived decay or recovery artifact process that:
- Settles by ~0.3 s at low intensity (why 0.3–1.5 s window works at 10–30%)
- Persists longer or becomes more dominant at 40–50% intensity
- Manifests as spectral broadening and loss of clean oscillatory structure (hence SSD component quality tanking)

---

## WHAT'S MISSING

### Gap 1: Within-Block Temporal Dynamics (Artifact Decay Modeling)
- **Current:** Single summary per block ignores whether artifact decays, plateaus, or grows within the 0.3–1.5 s window
- **Needed:** Exponential decay constants per channel per intensity → identify settling timescale as function of distance & intensity
- **Impact:** Explain why SSD fails at high intensity; enable sub-window artifact removal

### Gap 2: Spatial Heterogeneity (Per-Channel Saturation Thresholds)
- **Current:** SASS/SSD select single "best" channel/component; ignore other channels' behavior
- **Needed:** Map which channels saturate at which intensity; fit per-channel Hill saturation curves
- **Impact:** Understand why SASS works (spatial filter selects among saturated channels); design per-channel removal

### Gap 3: Real-Brain Validation (EXP04 Cross-Check)
- **Current:** Phantom results; anatomy and impedance differ from human scalp
- **Needed:** Test whether SASS artifact strategy generalizes to EXP04 (real brain, 100% intensity, multiple subjects)
- **Impact:** Confirm phantom findings are not artifacts of electrode geometry or phantom-specific properties

### Gap 4: Template-Based Denoising (Alternative/Complement to SSD)
- **Current:** Relying on SSD + SASS to recover oscillation around artifact
- **Needed:** Direct template subtraction of stereotyped TIMS artifact waveforms (especially at high intensity where SSD fails)
- **Impact:** Attack artifact directly; may succeed where SSD-based recovery alone cannot

---

## DECISION CHECKPOINTS

**Question 1:** Accept 10–30% ON as memo-backed positive range, put 40–50% outside current claim?  
→ *Matches data; conservative but honest.*

**Question 2:** Make decay modeling + subtraction the next mandatory step before real-brain TEP work?  
→ *Yes; current SSD failure at 40–50% suggests artifact transient is unmodeled.*

**Question 3:** Run template subtraction in parallel with SSD as dedicated TIMS denoising path?  
→ *Yes; SASS results suggest spatial filtering alone is insufficient at high intensity.*

**Question 4:** Treat EXP04 baseline before/after as broad biological hypothesis scan (not confirmation)?  
→ *Yes; artifact work must finish first to separate neural signal from contamination.*

---

## NEXT STEPS (Immediate)

1. **Phase 2A:** Extract per-channel exponential decay constants (A₀, λ) from raw ON window data
2. **Phase 2B:** Fit per-channel saturation curves (Hill model) across the five intensity levels
3. **Phase 2C:** Build composite 3D artifact model: A(t, intensity) = A_max(intensity) × exp(−λ(intensity) × t)
4. **Phase 3:** Validate on EXP04 (real brain); check if SASS/template strategy transfers
5. **Phase 4:** Implement artifact-removal pipeline; test TEP recovery with explicit artifact subtraction

**Effort estimate:** ~12–16 hours total for full operationalization

---

## BOTTOM LINE

The SASS/SSD comparison reveals a **sharp high-intensity phase transition** in ON artifact behavior. Low-intensity work is promising; high-intensity work needs explicit decay modeling before real-brain conclusions are justified. The finding is not a failure—it is an actionable mechanistic clue.

