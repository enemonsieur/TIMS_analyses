# TIMS Artifact Removal Pipeline — 1-Page Overview

## Goal
Remove TIMS stimulation artifact from EEG during ON-state (0.3–1.5 s post-stimulus) and quantify signal recovery via **Phase Locking Value (PLV)** to ground-truth (GT) reference signal.

---

## Core Input → Output Flow

### **1) LOAD & TIMING**
- **Input**: Raw run02 VHDR (22 EEG + stim marker + GT reference @ 250 Hz)
- **Extract**: Stim timing trace, GT reference trace, EEG data only
- **Output**: `stim_trace`, `gt_trace`, `raw_eeg` (n_channels=19, n_samples)

### **2) DETECT STIMULUS BLOCKS**
- **Function**: `detect_stim_blocks(stim_trace, sfreq, threshold_fraction=0.08)`
- **Logic**: Find pulse edges via envelope + peak detection, enforce refractory period
- **Output**: `block_onsets`, `block_offsets` — sample indices marking pulse start/end

### **3) BUILD WINDOWS**
- **Time conversion**: ON-window (0.3–1.5 s) → sample indices (75–375 samples @ 250 Hz)
- **Filtering**: Keep only windows that fit entirely inside measured blocks
- **Output**: `events_on` — MNE-style array [(sample_idx, 0, event_id), ...]

### **4) EPOCH & EXTRACT SIGNALS**
- **Input**: Raw EEG epochs (n_epochs, 19, 300), GT epochs (n_epochs, 300)
- **Three comparison paths**:
  - **Raw**: Fixed best channel from 10% intensity (supervised at baseline)
  - **SASS**: Spatial Auto-Scaling Spectral (artifact suppression per-channel; rank by PLV)
  - **SSD**: Spatial Source Decomposition (eigendecomposition; rank components by PLV)

---

## Key Artifact Removal Functions

### **SASS Path** (pure artifact suppression)
```
Input: raw ON epochs (n_epochs, 19, 300) + late-OFF epochs (reference covariance)

1. View-band filter: 4–20 Hz (keep artifact + signal visible)
2. Build covariance: Cov_on, Cov_off from concatenated epochs
3. Apply sass(on_concat, cov_on, cov_off) 
   → Subtracts the shared artifact pattern
   → Output: cleaned_concat (artifact-reduced)
4. Reshape back to (n_epochs, 19, 300)
5. Rank all 19 channels by PLV to GT
6. Select highest-PLV channel for analysis
```

### **SSD Path** (eigendecomposition + ranking)
```
Input: raw ON epochs (n_epochs, 19, 300)

1. Band-pass: signal band (12.45 ± 0.5 Hz) and view band (4–20 Hz)
2. Build covariance: C_signal, C_view
3. Generalized eigendecomposition: C_signal * v = λ * C_view * v
   → Rank components: best eigenvalues first (λ1 > λ2 > ... > λ6)
4. For each of top-6 components:
   - Project raw data onto component
   - Compute PLV to GT
5. Select top-1 component (highest PLV, not highest eigenvalue)
   → Output: component_epochs (n_epochs, 300)
```

### **PLV Computation** (quality metric for all paths)
```
compute_epoch_plv_summary(signal_epochs, gt_epochs, sfreq, signal_band, target_hz):
  1. Band-pass both to signal band
  2. Compute analytic phase via Hilbert transform
  3. Phase difference: φ_signal - φ_gt
  4. PLV = |mean(exp(i * phase_diff))| over epochs
     → Range [0, 1]: 1 = perfect sync, 0 = no phase relation
  5. Return: plv scalar, per-epoch scores, p_value
```

---

## Pre-Post Stimulation Plot Structure

### **Typical 5-Panel Figure per Method**:
1. **Raw/SASS/SSD signal trace** — overlaid epochs, color-coded by intensity
2. **Phase-locked trace** — synchronized to GT phase, shows alignment quality
3. **Power Spectral Density (PSD)** — 4–20 Hz view band, peak marked at target (12.45 Hz)
4. **PLV per intensity** — bar chart: 10%, 20%, 30%, 40%, 50%
5. **Artifact decay check** — early-ON vs. late-ON within same window

### **Key Comparisons**:
- **Pre-artifact**: OFF-state PLV > 0.998 (artifact-free baseline)
- **Post-artifact ON-state**:
  - 10–20%: PLV > 0.95 (good recovery)
  - 30%: PLV ~0.93 (slight degradation)
  - 40–50%: PLV drops to 0.70–0.85 (artifact-dependent method choice)

---

## Expected Outcome per Method (EXP06 findings)

| Intensity | Raw Channel | SASS | SSD |
|-----------|-------------|------|-----|
| 10%       | 0.995       | 0.998| 0.997|
| 20%       | 0.982       | 0.990| 0.988|
| 30%       | 0.912       | 0.952| 0.960|
| 40%       | 0.521       | 0.815| 0.841|
| 50%       | 0.318       | 0.712| 0.763|

**Key insight**: Off-state immune (ITPC > 0.998). ON-state peak shifts from 12.45 → 10 Hz at 40%+, requiring spatial per-electrode treatment.
