# The Component Selection Bias Problem

## The Paradox

**Observation:**
- GT and STIM are uncorrelated (r ≈ 0)
- But both phase-locked to each other (ITPC ≈ 0.99)
- Any extracted component locks equally well to both

**Root cause:**
Both signals **repeat at 12.45 Hz by design** because:
- STIM: stimulus pulse train repeated every ~80 ms
- GT: continuous oscillator at 12.45 Hz
- They're externally synchronized to start at the same time

When filtered to 12.45 Hz, both become pure sinusoids with identical phase.

**Consequence:**
- ITPC/PLV ranks components that lock to **artifact frequency**, not **brain signal**
- A component can have high PLV by capturing STIM leakage, not brain activity
- This makes all three methods (raw, SASS, SSD) equally contaminated

---

## What Should We Select On Instead?

### Option 1: Signal-to-Noise Ratio (SNR) in the Signal Band

**Idea:** Select component with highest 12.45 Hz power relative to broadband noise.

**Metric:** PSD at 12.45 Hz normalized by broadband (4–20 Hz) power

```python
# For each component:
signal_band_power = mean(PSD[11.95:12.95 Hz])
broadband_power = mean(PSD[4:20 Hz])
snr = signal_band_power / broadband_power
```

**Why it works:**
- Doesn't care about phase locking (phase is corrupted by artifact timing anyway)
- Brain signals have spectral peaks; pure phase-locked noise is broadband
- Artifact is spatially heterogeneous; real brain signal has consistent spectral signature

**Expected result if correct:**
- Raw: Low SNR (artifact dominates broadband)
- SASS: Higher SNR (artifact suppressed, signal visible)
- SSD: Even higher SNR (spatially optimized for signal band)
- **Trend:** SASS/SSD show monotonic SNR with intensity (artifact increasing)

---

### Option 2: Spectral Peak Proximity + SNR Consensus

**Idea:** Require TWO criteria:
1. Peak frequency within ±1 Hz of 12.45 Hz
2. SNR > threshold (e.g., 0.15)

Then select by SNR (not PLV).

**Why it works:**
- Filters out broadband noise (no peak near 12.45 Hz)
- Among peaked components, picks the least noisy one
- Avoids artifact that may have weak harmonic at 12.45 Hz

**Expected result if correct:**
- Same as Option 1, but more robust to low-SNR conditions

---

### Option 3: Temporal Consistency of Amplitude Envelope

**Idea:** Real brain signals should have **stable amplitude within a trial**, 
whereas artifact can have envelope modulation from STIM pulses.

**Metric:** Compute analytic amplitude (Hilbert magnitude) of filtered signal.
Select component with **lowest relative amplitude variance** across epoch.

```python
# For each component (filtered to 12.45 Hz):
analytic_sig = hilbert(filtered_component)
amplitude_envelope = abs(analytic_sig)
amp_cv = std(amplitude_envelope) / mean(amplitude_envelope)  # Coefficient of variation
```

**Why it works:**
- STIM leakage has amplitude modulation (pulse on/off)
- True oscillating signal has stable amplitude
- Captures the "timbre" of the signal

**Expected result if correct:**
- Raw: High amplitude variance (STIM modulates envelope)
- SASS/SSD: Lower variance (cleaner, more stable oscillation)

---

## Recommendation: Use SNR (Option 1)

**Why:** Simplest, most defensible, aligns with classical signal recovery.

**Implementation:**

```python
# Instead of:
# selected_idx = argmax(plv_scores)

# Do:
# selected_idx = argmax(snr_scores)

for ch_idx in channels:
    signal_psd = mean(psd[11.95:12.95 Hz])
    broadband_psd = mean(psd[4:20 Hz])
    snr_scores.append(signal_psd / broadband_psd)

selected_idx = argmax(snr_scores)
```

---

## What You Should See If SNR Selection Is Right

### Raw Channel (Locked at 10%)

```
SNR vs Intensity:

0.3 ┐
    │     ┌─ SNR
0.25┤     │
    │     │   ╱╲
0.2 ┤     │  ╱  ╲
    │     │╱      ╲
0.15┤    ╱        ╲_____
    │   ╱
0.1 ┤  ╱
    │
0.05┴──────────────────────
    10% 20% 30% 40% 50%

Pattern: Monotonic decrease (increasing artifact)
Interpretation: STIM artifact increasingly swamps the signal
```

### SASS (Pure Artifact Removal)

```
SNR vs Intensity:

0.6 ┐
    │  ┌──────────────
0.5 ┤  │
    │  │    ╱╲
0.4 ┤  │   ╱  ╲
    │  │  ╱    ╲__
0.3 ┤  │╱         ╲_
    │  ╱
0.2 ┤
    │
0.1 ┴──────────────────────
    10% 20% 30% 40% 50%

Pattern: High at 10–30%, then drops at 40–50%
Interpretation: SASS removes broadband artifact well,
               but at high intensities, artifact structure
               becomes too complex (peaks outside 4–20 Hz,
               or nonlinear effects)
```

### SSD (Signal-Band Optimized Decomposition)

```
SNR vs Intensity:

0.8 ┐
    │   ┌────────
0.7 ┤   │    ╱╲
    │   │   ╱  ╲
0.6 ┤   │  ╱    ╲___
    │   │╱          ╲
0.5 ┤  ╱             ╲
    │
0.4 ┴──────────────────────
    10% 20% 30% 40% 50%

Pattern: Sustained high SNR across intensities
Interpretation: SSD's spectral optimization finds components
               that preserve signal even when artifact rises
```

---

## Key Difference: PLV vs SNR Selection

### Current (PLV-based) Results:

```
       10%    20%    30%    40%    50%
Raw:   0.716  0.467  0.960  0.963  0.959  ← Noisy, inconsistent
SASS:  0.975  0.973  0.262  0.862  0.872  ← Crashes at 30%
SSD:   0.964  0.932  0.960  0.353  0.767  ← Crashes at 40%
```

**Problem:** High PLV values don't reflect real recovery.
SASS at 30% shows PLV=0.262 (terrible), but that's because 
the component it selected happened to have poor GT phase locking—
not because SASS failed.

### Expected (SNR-based) Results:

```
       10%    20%    30%    40%    50%
Raw:   0.25   0.20   0.15   0.12   0.10   ← Monotonic decline
SASS:  0.45   0.42   0.38   0.25   0.15   ← Slower decline
SSD:   0.55   0.52   0.50   0.48   0.45   ← Most stable
```

**Benefit:** Steady patterns reveal true artifact burden.
- Raw shows pure contamination
- SASS shows moderate cleanup capability
- SSD shows best artifact resilience

---

## Summary

| Aspect | PLV-based | SNR-based |
|--------|-----------|-----------|
| **What it measures** | Phase coherence with GT/STIM | Power in target frequency |
| **Bias** | Toward phase-locked artifact | Toward spectral peaks |
| **Artifact problem** | Vulnerable (STIM is phase-locked) | Resistant (STIM is broadband) |
| **Interpretability** | Confounded (can't distinguish signal from artifact phase) | Clear (signal has spectral signature) |
| **Expected trend** | Noisy, non-monotonic | Smooth, monotonic or systematic |

---

## Recommendation

**Change component selection from PLV to SNR across all three paths (raw, SASS, SSD).**

This will reveal whether artifact suppression actually works, 
or whether we're just picking different artifacts at each intensity.

