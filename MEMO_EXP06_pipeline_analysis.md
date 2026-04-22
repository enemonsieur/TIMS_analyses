# EXP06 Pipeline Analysis: Understanding the Transformation Chain

## Overview

The EXP06 phantom study compares three signal processing approaches to recover a 12.45 Hz ground-truth (GT) signal during transcranial stimulation. Each approach transforms raw multichannel EEG in different ways. This memo explains what each path does, why, and what potential concerns exist.

---

## Input Data

All three paths start from the same raw material:
- **Recording:** exp06-STIM-iTBS_run02.vhdr (stimulation recording, 5 intensity blocks: 10%, 20%, 30%, 40%, 50%)
- **ON-state windows:** 0.3–1.5 s after stimulation onset (1.2 s windows), 20 cycles per intensity
- **Late-OFF reference windows:** 1.5–3.2 s after stimulation offset (1.7 s windows) — used as clean EEG baseline
- **Ground-truth signal:** Injected 12.45 Hz oscillation; measured directly from the `ground_truth` channel
- **Target band:** 11.95–12.95 Hz (±0.5 Hz around the measured peak)
- **View band:** 4–20 Hz (for broadband artifact assessment)

---

## Signal Path A: Raw Selected Channel

### What It Does

1. Bandpass-filter all EEG channels into the target band (11.95–12.95 Hz)
2. Compute Phase Locking Value (PLV) between each channel and the GT trace
3. Select the **best single channel** — the one with highest PLV to GT

### Why This Approach Makes Sense

- **Simplicity:** No decomposition or artifact suppression — just the channel most naturally aligned with the target
- **Upper baseline:** Shows what raw sensor data can achieve on its own
- **Direct GT correlation:** PLV directly measures how well the channel's oscillation phase-locks to the intended target
  - Example: if GT cycles at 12.45 Hz and a channel's 12.45 Hz oscillation has phase jitter of ±10°, PLV ~ 0.95; if phase jitter is ±45°, PLV ~ 0.7

### Key Decision

**Selection criterion: Argmax PLV vs GT**

This is defensible because PLV directly answers the question "which channel best locks to the target?" However, it has one implicit assumption: that the best raw channel is being selected *after* contamination by stimulation artifact. If the artifact has a spatial pattern that happens to spare the naturally-best channel, this works well. If artifact scatters to all channels, no raw channel may remain usable.

---

## Signal Path B: SASS Source

### What It Does

A two-stage decomposition:

**Stage 1: SASS (Stimulation Artifact Source Separation)**
1. Bandpass ON and late-OFF epochs into view band (4–20 Hz)
2. Compute two covariance matrices:
   - `cov_A` = covariance of ON signal (contains tACS artifact + noise + signal)
   - `cov_B` = covariance of late-OFF signal (clean, only noise + signal, no artifact)
3. Solve the generalized eigenvalue problem: `cov_A · w = λ · cov_B · w`
4. Components with **high λ** have high variance in ON but not OFF → artifact-dominated
5. Sort by descending eigenvalue; **null the top N components** (N chosen automatically to minimize mean-squared error between projected covariance and `cov_B`)
6. Project back to channel space → artifact-suppressed ON epochs

**Example of what SASS does:**
- If ON signal has a 2 µV artifact component overlaid on a 1 µV neural signal, and OFF has only the 1 µV neural signal, that artifact component will have a high eigenvalue
- SASS identifies and removes it, leaving the 1 µV neural signal intact

**Stage 2: SSD on SASS-cleaned data**
1. Bandpass SASS-cleaned ON and OFF epochs into target band (11.95–12.95 Hz)
2. Compute signal-band and off-band covariances
3. Generalized eigendecomposition: `cov_ON · w = λ · cov_OFF · w`, sorted **ascending**
   - Low λ = low ON variance relative to OFF = most suppressed artifact
4. Keep top 6 components, rank by **broadband (4–20 Hz) ON/OFF power ratio**
5. Select component with **lowest ratio** (least ON-state power inflation)

### Why This Two-Stage Approach Makes Sense

- **Stage 1 (SASS):** Removes the gross artifact using ON vs. OFF covariance difference
  - Pro: Uses clean OFF data as a reference — mathematically clean approach
  - Pro: Automatic N-selection (MSE criterion) avoids over-nulling or under-nulling
- **Stage 2 (SSD on cleaned data):** Finds the component that maximizes signal-to-broadband-noise after artifact is suppressed
  - Pro: Re-fitting SSD after SASS removal allows focus on true signal structure, not artifact structure
  - Pro: Ranking by ON/OFF power ratio verifies that the selected component doesn't have artifact residual

### Key Decisions

1. **View band for SASS (4–20 Hz):** Broad band captures the full artifact spectrum. Could be tighter (e.g., 2–30 Hz) but 4–20 Hz is reasonable.
2. **Signal band for second eigendecomp (11.95–12.95 Hz):** Narrow band focuses on the target. Defensible.
3. **N-null selection by MSE:** Minimizes divergence between cleaned covariance and clean reference. This is mathematically principled but assumes that "matched covariance = matched signal quality," which may not always hold.
4. **Top 6 components kept:** Hard-coded; no stated rationale. Why 6 and not 3 or 10? This is underspecified.
5. **Ranking by ON/OFF power ratio, not PLV:** The component is ranked by its broadband power inflation, not by how well it phase-locks to GT. This is a **proxy for artifact suppression**, not a direct measure of signal recovery.

### Potential Concern

The final component selection uses **power ratio as a proxy**, not PLV. If the SASS-cleaned data has a strong 12.45 Hz signal with low broadband power, this method will select it. But if it has multiple candidates with similar power ratios, the tie-break is unclear.

---

## Signal Path C: SSD Component (from Raw)

### What It Does

Direct SSD on raw ON data (no SASS):

1. Bandpass raw ON and OFF epochs into target band (11.95–12.95 Hz) → `cov_signal`
2. Bandpass raw ON and OFF epochs into view band (4–20 Hz) → `cov_view`
3. Generalized eigendecomposition: `cov_signal · w = λ · cov_view · w`
4. Sort by **descending eigenvalue** (high λ = high signal-band variance relative to view-band variance → signal-dominant)
5. Keep top 6 components, rank by **broadband ON/OFF power ratio**
6. Select component with **lowest ratio**

### Why This Approach Makes Sense

- **Signal-optimized eigendecomp:** Directly maximizes the target-band power relative to broadband, which is the opposite of SASS (which suppresses ON variance)
- **Simplicity:** No artifact pre-treatment — just exploit the spectral structure of the target
- **Comparison point:** Tests whether raw SSD without artifact suppression can recover the GT

### Key Decisions

1. **Descending sort (vs. ascending in SASS Stage 2):** Makes sense — highest signal-band/view-band ratio is most target-focused
2. **Top 6 components:** Same hard-coded choice as SASS path B
3. **Ranking by ON/OFF power ratio:** Same proxy as path B

### Potential Concern

SSD on raw data will fit to whatever dominates the target band in the ON window. If artifact has a peak at 12.45 Hz (which it might, due to harmonic structure), SSD may select an artifact component rather than signal. The subsequent ON/OFF power ranking check catches obvious failures, but may miss subtle cases where artifact is phase-locked to the stimulation.

---

## Signal Path D: GT vs STIM (Reference)

### What It Does

Computes PLV between the measured stimulation voltage trace (`stim` channel) and the ground-truth channel. No selection or transformation — direct comparison.

### Why This Matters

- **Upper bound on recoverable phase locking:** The delivered stimulation should, by definition, be phase-locked to the intended 12.45 Hz target
- **Sanity check:** If GT-vs-STIM PLV is low, then either (a) the GT injection is noisy, or (b) the stimulation is not being delivered at the intended frequency
- **Benchmark:** Paths A, B, C should not exceed this reference (they can't be more locked to GT than the stimulus itself)

---

## Key Asymmetries and Concerns

### 1. Selection Criteria Are Not Uniform

| Path | Final Selection Criterion |
|------|--------------------------|
| **A (Raw)** | **PLV directly** vs. GT — ranks channels before extraction |
| **B (SASS)** | **ON/OFF power ratio** — ranks components after SASS + SSD |
| **C (SSD)** | **ON/OFF power ratio** — ranks components after SSD |

**Implication:** Path A uses a direct measure of phase locking. Paths B and C use power ratio as a proxy for artifact suppression. If a component has low power ratio but poor PLV to GT (e.g., it's phase-drifting), path B and C won't catch it. The final PLV is computed post-hoc for comparison, not for ranking.

**Defensibility:** This is not necessarily wrong — power ratio is a reasonable proxy for artifact removal. But it introduces a **two-stage decision problem:** first, assume low ON/OFF power ratio means the artifact was removed; second, measure PLV to see if the actual signal was preserved. If the component fails at the PLV stage, you can't go back and re-rank by a different criterion.

### 2. SSD Ascending vs. Descending Sort in Paths B and C

- **Path B Stage 2 (SSD on SASS-cleaned):** Ascending sort (low λ = artifact-suppressed)
- **Path C (SSD on raw):** Descending sort (high λ = signal-dominant)

Why the flip? Because:
- In path B, SASS has already removed gross artifact, so the target band now represents genuine signal structure. Low ON variance relative to OFF means the component is stable and suppressed.
- In path C, raw data's target band includes both signal and artifact, so high ON/view-band variance indicates the target band is dominant (good extraction).

This is actually correct reasoning, but it's asymmetric in presentation. It could confuse readers.

### 3. Hard-Coded `N_SSD_COMPONENTS = 6`

Both paths B and C keep the top 6 components before ranking. Why 6?

- Could represent a prior belief about the dimensionality of interesting components
- Could be empirically chosen from a pilot
- Could be a safety margin (never discard useful information early)

The code does not explain. This is a **hidden hyperparameter** that affects how many candidates are ranked.

### 4. Automatic SASS Null-Count (MSE Criterion)

The SASS null-count `N` is chosen to minimize:

```
MSE = ||P·cov_A·P^T - cov_B||^2
```

where `P` is the projection matrix nulling the top N components.

**Rationale:** Good — minimizes the difference between projected and clean covariance.

**Potential issue:** This assumes that "matched covariance = matched signal." If the artifact has a simple structure (e.g., a single strong 2 kHz peak from stimulation hardware), SASS might over-null and remove true signal along with it. The MSE criterion can't distinguish. A **power-preserving criterion** (e.g., maximize signal-band power while minimizing view-band inflation) might be more robust.

### 5. No Explicit Artifact Characterization

The pipeline assumes that:
- SASS will identify and remove the artifact from ON vs. OFF covariance difference
- The on/OFF power ratio will confirm removal

But the code never prints:
- How many components SASS nulled per intensity block?
- What was the eigenvalue spectrum before/after SASS?
- How much did on-band power drop as a function of null count?

**Missing visibility:** Without these diagnostics, you can't verify that SASS actually found and removed the artifact, or confirm that the power ratio is a good proxy.

---

## Defensibility Assessment

### Robust Design Decisions
✓ Using ON vs. OFF covariance difference for SASS  
✓ Automatic null-count selection (MSE criterion)  
✓ Two-stage decomposition (coarse artifact suppression, then fine signal extraction)  
✓ Power-ratio ranking as artifact suppression check  
✓ Reference PLV computation post-hoc for all three paths  

### Underspecified or Concerning Decisions
⚠ Hard-coded top-6 components — no rationale stated  
⚠ Asymmetric selection criteria (PLV for raw, power-ratio for components)  
⚠ Asymmetric SSD sort direction (ascending vs. descending) — correct but confusing  
⚠ No per-block diagnostics on SASS null count or eigenvalue structure  
⚠ Power-ratio proxy may miss phase-drifting components with low artifact power  

---

## Verification

To gain confidence in this pipeline, consider adding:

1. **Per-block SASS diagnostics:** Print null count, MSE before/after, eigenvalue breakdown
2. **Component validity checks:** Plot time-frequency spectrograms of selected components to visually confirm they contain 12.45 Hz and not artifact residual
3. **Comparison of selection criteria:** Rank path B and C components by PLV (in addition to power ratio) and see if ranking order changes
4. **Stability across intensity:** Check if the same components are selected at each intensity, or if different components dominate at high intensity (sign of degradation)

---

---

## Update (April 15, 2026): SNR-Based Selection & ITPC Validation

### Key Finding: PLV-Based Selection is Fundamentally Biased

**Problem:** Both GT and STIM repeat at 12.45 Hz by hardware design. When any signal is filtered to 12.45 Hz, it becomes a sinusoid with fixed phase. This means **any extracted component** (signal, noise, or artifact) locks equally well to GT.

**Evidence:** At 40–50% stimulus intensity:
- Raw channel P8: SNR ≈ 0.0006 (99.9% artifact/noise), yet **PLV = 0.75** (high phase locking)
- SASS: SNR = 4.58–5.17 (good), PLV = 0.86–0.87 (high)
- SSD: SNR = 2.23–4.47 (robust), PLV = 0.18–0.50 (variable)

**Conclusion:** PLV is **not reliable for component selection** — it masks artifact saturation by showing high values even when SNR → 0.

### Solution: SNR-Based Selection

Replaced PLV-based ranking with **Signal-to-Noise Ratio** (SNR = power in 12.45 Hz band / power in 4–20 Hz band):
- Raw channel: Locked at 10% (P8), applied to all intensities
- SASS: SNR-selected per intensity (adaptive channel)
- SSD: SNR-selected per intensity (adaptive component)

### ITPC Validation Results

Generated **ITPC time courses** (channel-averaged, time-resolved phase coherence):

| Intensity | Raw ITPC | SASS ITPC | SSD ITPC | SNR Pattern |
|-----------|----------|-----------|----------|-------------|
| **10%** | 0.717 | 0.945 | 0.051 | Raw 3.4, SASS 2.6, SSD 4.0 |
| **20%** | 0.767 | 0.977 | 0.937 | Raw 4.3, SASS 8.3 (peak), SSD 6.4 |
| **30%** | 0.489 | 0.259 | 0.208 | Raw 0.21, SASS 0.37 (crash), SSD 4.1 |
| **40%** | 0.993 | 0.884 | 0.177 | Raw 0.0006, SASS 4.6, SSD 2.2 |
| **50%** | 0.994 | 0.887 | 0.489 | Raw 0.0008, SASS 5.2, SSD 4.5 |

**Interpretation:**
- **Raw:** ITPC spikes erratically (0.49→0.99→0.99) — artifact locking masquerading as recovery
- **SASS:** Peaks at 20% (SNR 8.25), crashes at 30% (SNR 0.37), partial recovery 40–50%
- **SSD:** Most stable across intensities; maintains usable SNR even under artifact saturation

### Revised Assessment

| Path | Selection Method | Validity |
|------|-----------------|----------|
| **A (Raw)** | PLV (original) | ❌ Biased; shows high ITPC at SNR→0 |
| **B (SASS)** | Power ratio (original) | ⚠ Works well at 10–20%, fails at 30% |
| **C (SSD)** | Power ratio (original) | ⚠ Most robust; maintains SNR > 2 across all intensities |
| **All paths (SNR-based)** | SNR-selected | ✅ Reveals true artifact saturation threshold (~30%) |

### Key Insight

The artifact saturation threshold is **real and occurs around 30–40% stimulus intensity**. SNR-based selection makes this explicit:
- Below 30%: All methods can suppress broadband artifact (SNR > 2)
- Above 40%: Only spectral methods (SSD, SASS partially) preserve signal-band power
- Raw method is **unusable above 30%** (SNR < 0.25)

---

## Conclusion

The EXP06 pipeline is **methodologically sound** but **PLV-based selection masks artifact saturation**. 

**Revised recommendation:**
- ✓ Replace PLV with SNR for component ranking
- ✓ Use SNR and ITPC together (complementary metrics)
- ✓ Recognize 30% as the artifact saturation transition point
- ✓ Prefer SSD for high-intensity applications (most robust to saturation)
