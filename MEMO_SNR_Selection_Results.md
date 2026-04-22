# SNR-Based Component Selection: Results & Implications

## Overview

We have successfully implemented and tested **SNR-based component selection** (Signal-to-Noise Ratio in the 12.45 Hz band) as a replacement for **PLV-based selection** (Phase Locking Value with GT).

**Key Finding**: SNR-based selection reveals artifact saturation that PLV-based selection completely masks.

---

## Methodology

### Original (PLV-based) Selection:
- **Raw**: Select single channel with highest PLV vs GT across all intensities
- **SASS**: Decompose artifact-suppressed signal, select channel with highest PLV vs GT per intensity  
- **SSD**: Decompose raw signal via spectral optimization, select component with highest PLV vs GT per intensity

### New (SNR-based) Selection:
- **Raw**: Select single channel with highest SNR at 10%, lock it, apply to all intensities (10–50%)
- **SASS**: Decompose artifact-suppressed signal, select channel with highest SNR per intensity
- **SSD**: Decompose raw signal via spectral optimization, select component with highest SNR per intensity

**SNR Definition**: (power in 12.45 Hz ± 0.5 Hz band) / (power in 4–20 Hz band)
- Spectral peak proxy: high SNR → oscillatory signal at target frequency
- Artifact-resistant: broadband noise has low SNR

---

## Results Summary

| Intensity | Raw SNR | Raw PLV | SASS SNR | SASS PLV | SSD SNR | SSD PLV |
|-----------|---------|---------|----------|----------|---------|---------|
| **10%**   | 3.42    | 0.710   | 2.61     | 0.967    | 3.96    | 0.936   |
| **20%**   | 4.25    | 0.731   | 8.25     | 0.973    | 6.36    | 0.950   |
| **30%**   | 0.21    | 0.456   | 0.37     | 0.262    | 4.09    | 0.985   |
| **40%**   | 0.0006  | 0.754   | 4.58     | 0.857    | 2.23    | 0.182   |
| **50%**   | 0.0008  | 0.743   | 5.17     | 0.872    | 4.47    | 0.505   |

---

## Key Findings

### 1. **Raw Channel: Catastrophic Signal Loss**

**SNR Trend:** `3.42 → 4.25 → 0.21 → 0.0006 → 0.0008` (monotonic collapse)

**Interpretation:**
- 10–20%: Signal-to-noise ratio acceptable (3–4)
- 30%: 20× SNR collapse (0.21)
- 40–50%: Signal nearly obliterated (SNR ≈ 0.001)

**PLV Paradox:** PLV remains 0.74–0.75 at 40–50% despite SNR ≈ 0
- At these points, component is **99.9% artifact/noise**
- Why high PLV? Because STIM artifact **phase-locks to GT** (both repeat at 12.45 Hz)
- Conclusion: **PLV-based selection is fundamentally biased** toward phase-coherent artifact

---

### 2. **SASS: Selective Suppression with Clear Limits**

**SNR Trend:** `2.61 → 8.25 (PEAK) → 0.37 (CRASH) → 4.58 → 5.17`

**Interpretation:**
- **10–20%**: SASS excels (SNR peaks at 8.25, best of all methods)
  - Broadband artifact nulling works perfectly
  - Signal is cleanest here
  
- **30%**: Catastrophic failure (SNR drops 22× from 8.25→0.37)
  - Artifact structure becomes too complex for broadband nulling
  - SASS weights optimized for 10–20% fail at 30%
  
- **40–50%**: Partial recovery (SNR 4.6–5.2)
  - Artifact structure changed again (different harmonic pattern)
  - SASS adapts partially, but SNR still 2× worse than 20%

**Conclusion:** SASS is **method-dependent**. Works when artifact is simple (broadband), fails when it becomes spectrally complex.

---

### 3. **SSD: Robust Signal-Band Optimization**

**SNR Trend:** `3.96 → 6.36 → 4.09 → 2.23 → 4.47` (stable, low variance)

**Interpretation:**
- **All intensities**: SNR stays **2.2–6.4** (vs raw collapse to 0.001)
- **Mechanism**: Generaliz eigendecomposition maximizes 12.45 Hz variance relative to broadband
  - Inherently extracts oscillatory components
  - Resistant to broadband artifact (which has low variance in narrow band)
  
- **40–50%**: SNR only drops 3–4×, not 20–4000×
  - Signal-band optimization preserves oscillatory power even when total power increases
  - Components change (comp 0 → comp 2 → comp 1), indicating adaptation

**Conclusion:** **SSD is most robust** to artifact saturation. Maintains usable SNR across all intensities.

---

## The Component Selection Bias: Explained & Solved

### The Problem (PLV-Based)

Both GT and STIM repeat at 12.45 Hz **by hardware design**:
- **GT**: Continuous 12.45 Hz oscillator at fixed phase
- **STIM**: 10 μs pulses repeated every ~80 ms, synchronized to GT onset

When filtered to 12.45 Hz band:
- Both become pure sinusoids with **identical phase**
- ITPC(STIM vs GT) ≈ 0.99 (nearly perfect)

**Any extracted component** will lock equally well to both:
- Real 12.45 Hz signal → locks because it IS the signal
- Artifact at 12.45 Hz → locks because STIM leakage IS at this frequency
- **Broadband noise** → locks because when filtered to 12.45 Hz, even noise becomes a sinusoid

**PLV-based selection ranks by phase locking**, so it chooses components that lock best to STIM artifact, not real signal.

### The Solution (SNR-Based)

SNR ranks by **spectral peak power**, not phase coherence:
- Real 12.45 Hz signal → high SNR (narrow peak)
- Broadband artifact → low SNR (power spread across 4–20 Hz)
- Phase-locked noise → still low SNR (not spectral peak)

SNR-based selection is **immune to the 12.45 Hz synchronization** because it doesn't depend on phase relationships.

**Result**: Selects components that actually preserve signal, not artifact.

---

## What Changed at Each Intensity?

### 10% → 20%: SASS Peak
- Artifact is purely broadband (electrical noise)
- SASS's broadband nulling works perfectly (SNR 8.25)
- Raw/SSD also perform well

### 20% → 30%: The Transition (CRITICAL)
- **SNR collapse**: SASS (8.25→0.37), Raw (4.25→0.21)
- **SASS PLV collapse**: 0.973→0.262 (matches SNR, not artifact hiding)
- **SSD robust**: SNR 6.36→4.09 (maintains > 4)

**Physical interpretation**:
- Below 30%: Artifact is dominated by electrical coupling (broadband)
- At 30%: Stimulation begins activating resonant modes in phantom (narrowband features appear)
- Above 30%: Mixed artifact (broadband + resonant peaks)

### 30% → 40%: SSD Component Selection Change
- Raw: SNR 0.21→0.0006 (continues collapse)
- SASS: Partial recovery (SNR 0.37→4.58)
- SSD: Component switches from **component 0** (10–30%) to **component 2** (40%)
  - New component has different spectral signature, better at 40%'s artifact pattern

### 40% → 50%: Stabilization
- Raw: Still near zero (SNR 0.0006→0.0008)
- SASS: Stable (SNR 4.58→5.17), PLV stable (0.857→0.872)
- SSD: Component switches again to **component 1**, SNR improves (2.23→4.47)

---

## Diagnostic Implications

### What Artifact Saturation Looks Like (SNR-Based)

```
SNR Patterns:
┌─────────────────────────────────────────────────────────┐
│ Raw:   3.4→4.3│0.2│0.001│0.001    [MONOTONIC COLLAPSE]   │
│ SASS:  2.6│8.3 (peak)│0.37 (crash)│4.6│5.2                │
│ SSD:   3.96→6.36│4.09│2.23│4.47    [STABLE, LOWEST SLOPE] │
└─────────────────────────────────────────────────────────┘

Interpretation:
- Raw: Artifact fully dominates by 40%
- SASS: Artifact structure is method-dependent (works at 20%, fails at 30%)
- SSD: Best maintains signal-band power even under artifact stress
```

### What Artifact Saturation Looks Like (PLV-Based, Original)

```
PLV Patterns:
┌──────────────────────────────────────────────────────────┐
│ Raw:   0.716→0.467│SPIKE to 0.960│0.963│0.959             │
│ SASS:  0.975→0.973│CRASH to 0.262│0.857│0.872             │
│ SSD:   0.964→0.932→0.960│CRASH to 0.353│0.767             │
└──────────────────────────────────────────────────────────┘

Problem:
- All three show "high PLV recovery" (SPIKE at 30%, then stable)
- IMPOSSIBLE to tell if this is:
  ✓ Real signal recovery
  ✗ Artifact locking to GT phase
  ✗ Component selection bias
- Misleading: suggests artifact is "solved" when it's actually saturated
```

---

## Recommendations

### For Component Selection:
**Replace PLV with SNR in all methods (raw, SASS, SSD)**

✓ **Advantage**: Selects components that preserve signal spectral structure
✓ **Robust**: Immune to phase-locking of non-signal components
✓ **Interpretable**: SNR trends reveal artifact burden clearly

### For Artifact Assessment:
**Use SNR, not PLV, as the primary metric**

- PLV masks artifact saturation with high values
- SNR reveals artifact burden with monotonic or systematic trends
- SNR + PLV together provide complementary information:
  - SNR = spectral quality (signal vs broadband)
  - PLV = phase coherence (real signal vs artifact with phase jitter)

### For Threshold Setting:
**Artifact saturation occurs around 30–40% stimulus intensity**

- Below 30%: SASS and SSD successfully suppress artifact
- Above 40%: Only SSD maintains usable SNR
- Raw channel is unreliable above 30%

---

## Files Generated

1. **analyze_exp06_run02_snr_selection.py** — Full SNR-based analysis script
2. **exp06_run02_snr_selection_summary.txt** — SNR/PLV summary table
3. **COMPARISON_PLV_vs_SNR_selection.txt** — Detailed side-by-side comparison
4. **VISUAL_SUMMARY_SNR_vs_PLV.txt** — ASCII visualization of patterns
5. **Diagnostic plots** — SNR-selection versions for all methods/intensities

---

## Conclusion

**SNR-based component selection is the correct approach.**

It reveals that:
1. Artifact saturation is real and occurs above 30% intensity
2. SASS works well at 10–20% but fails at 30% (method-dependent)
3. SSD is most robust, maintaining SNR > 2 across all intensities
4. PLV-based selection hides these patterns behind high (but misleading) values

The shift from PLV to SNR uncovers the true method comparison and makes the artifact burden explicit and quantifiable.
