# SKRIPT: YOUR EXP06 RUN02 ANALYSIS PIPELINE
## High-Level View + Pseudocode

This document explains how **your script** (`analyze_exp06_run02_on_raw_sass_ssd_plv.py`) transforms raw EEG data through three parallel processing paths (Raw, SASS, SSD) to compare their ability to recover a 12.45 Hz ground-truth signal across five stimulus intensities.

---

## Part 1: The Big Picture

### Data Journey

```
╔══════════════════════════════════════════════════════════════════════════════╗
║                   RUN02 VHDR → 3 PARALLEL PATHS → METRICS                   ║
╚══════════════════════════════════════════════════════════════════════════════╝

Run02 Recording (22 EEG + stim + GT, 250 Hz, ~120 s)
│
├─ Load VHDR file (mne library)
│
├─ Detect stimulus blocks via stim_trace edges
│  └─ Map blocks → intensity indices (blocks 0–19 = 10%, 20–39 = 20%, etc.)
│
├─ Build ON windows: [0.3–1.5 s post-onset] + late-OFF windows [1.5–3.2 s post-offset]
│  └─ Extract epochs: (n_epochs=20, n_channels=22, n_samples=300)
│
├─ Three analysis paths run IN PARALLEL:
│  │
│  ├─ PATH A: RAW CHANNEL
│  │  ├─ Select single best raw channel (highest PLV vs GT at 10%)
│  │  ├─ Lock that channel for all 5 intensities
│  │  ├─ Compute PLV per intensity
│  │  └─ Output: raw_selected_epochs (20, 300)
│  │
│  ├─ PATH B: SASS (Sensor Artifact Spatial Suppression)
│  │  ├─ Apply SASS to ON epochs using late-OFF as clean reference covariance
│  │  ├─ SASS nulls top artifact-dominant eigenvectors
│  │  ├─ Rank all 22 cleaned channels by PLV vs GT
│  │  ├─ Select best cleaned channel per intensity
│  │  └─ Output: sass_selected_epochs (20, 300)
│  │
│  └─ PATH C: SSD (Spatio-Spectral Decomposition)
│     ├─ Generalized eigendecomp: signal-band (11.95–12.95 Hz) vs view-band (4–20 Hz)
│     ├─ Keep top 6 components
│     ├─ Rank by PLV vs GT (narrowband)
│     ├─ Select best component per intensity
│     └─ Output: ssd_selected_epochs (20, 300)
│
├─ Compute metrics for each path + GT-STIM reference:
│  ├─ PLV (phase locking value) vs GT at each intensity
│  ├─ Phase difference distributions (polar histograms)
│  └─ PSD (power spectral density) to check for 12.45 Hz peak
│
└─ Generate diagnostic plots + summary table
```

---

## Part 2: The Three Processing Paths in Detail

### PATH A: RAW CHANNEL SELECTION

```
╔════════════════════════════════════════════════════════════════════════════╗
║ RAW: Find Best Single Channel, Lock It Across Intensities                 ║
╚════════════════════════════════════════════════════════════════════════════╝

STEP 1: At 10% Intensity
  Input:  on_raw_epochs (20 epochs, 22 channels, 300 samples each)
  ────────────────────────────────────────────────────────────────────────
  For each of 22 channels:
    a) Extract ON epochs for this channel: (20, 300)
    b) Band-pass filter to 12.45 Hz (signal band)
    c) Compute phase via Hilbert transform
    d) Measure PLV (phase locking value) vs GT across all 20 epochs
    e) Store: plv[ch_name] = scalar (0 to 1)
  
  Result: plv_scores = [0.716, 0.523, 0.811, ...] per channel
  Action: FIXED_RAW_CH_IDX = argmax(plv_scores)  ← Lock this channel!
  
STEP 2: At 20%, 30%, 40%, 50% Intensities
  Input:  on_raw_epochs (20 epochs, 22 channels, 300 samples each)
  ────────────────────────────────────────────────────────────────────────
  Reuse:  on_raw_selected = on_raw_epochs[:, FIXED_RAW_CH_IDX, :]  ← Same channel!
  Compute: metrics = compute_epoch_plv_summary(on_raw_selected, gt_on_epochs, ...)
  Output:  raw_metrics["plv"] = scalar per intensity
  
RATIONALE:
  - Locked channel isolates artifact effect from spatial drift
  - If PLV declines with intensity, it's artifact contamination (not channel change)
  - Fair comparison with SASS and SSD which also get selected per intensity
  
OUTPUT PER INTENSITY:
  - best_channel_name: "O1" or "P8" (whichever locked at 10%)
  - best_channel_plv: 0.716 → 0.467 → 0.960 → 0.963 → 0.959 (example)
  - phase_samples: ~20 phase samples (one per epoch cycle)
```

---

### PATH B: SASS (Sensor Artifact Spatial Suppression)

```
╔════════════════════════════════════════════════════════════════════════════╗
║ SASS: Clean Artifact via Spatial Nulling, Then Rank Channels              ║
╚════════════════════════════════════════════════════════════════════════════╝

STEP 1: Prepare Covariance Matrices
  Input (ON):      on_raw_epochs (20 epochs, 22 channels, 300 samples)
  Input (late-OFF): late_off_raw_epochs (5+ epochs, 22 channels, 800 samples)
  ────────────────────────────────────────────────────────────────────────
  Band-pass to view band (4–20 Hz):
    on_view_epochs = filter(on_raw_epochs, 4, 20)
    late_off_view_epochs = filter(late_off_raw_epochs, 4, 20)
  
  Concatenate all epochs per condition:
    on_view_concat = reshape((22, 20*300)) = (22, 6000 samples)
    late_off_view_concat = reshape((22, 5*800)) = (22, 4000 samples)
  
  Compute covariance (empirical):
    cov_A = cov(on_view_concat)        ← (22, 22) on-state covariance
    cov_B = cov(late_off_view_concat)  ← (22, 22) late-off reference (clean)
  
STEP 2: Apply SASS Decomposition
  Generalized eigendecomposition: cov_A · w = λ · cov_B · w
  ────────────────────────────────────────────────────────────────────────
  Result: 22 eigenvectors w_i with eigenvalues λ_i
          High λ = on-state variance dominates (likely artifact)
          Low λ = on-state ≈ off-state variance (likely clean)
  
  Action: Sort by descending λ
          Identify top N artifact-dominant eigenvectors
          Null them → project back to channel space
          
  Output: sass_cleaned_concat = on_view_concat with top-N projections zeroed
          Shape: (22, 6000) cleaned data
  
Now 
    a) Extract channel data: (20, 300)
    b) Band-pass filter to 12.45 Hz (signal band)
    c) Compute PLV vs GT across 20 epochs
    d) Compute PSD to check for 12.45 Hz peak
    e) Store: plv[ch_name], peak_hz[ch_name]
  
  Result: sass_plv_scores = [0.975, 0.241, 0.862, ...] per cleaned channel
  Action: selected_sass_ch_idx = argmax(sass_plv_scores)
  
STEP 5: SelectSummary(on_sass_selected, gt_on_epochs, ...)
  
OUTPUT PER INTENSITY:
  - selected_channel_name: best cleaned channel for THIS intensity (changes per intensity)
  - best_plv: PLV for selected cleaned channel (0.975 → 0.973 → ... example)
  - phase_samples: ~20 phase samples (one per epoch)
  
RATIONALE FOR PURE SASS PATH:
  - SASS suppresses broadband artifact (4–20 Hz artifact structure)
  - Reselecting best channel per intensity: SASS changes channel quality dynamically
    with stimulus intensity (artifact structure changes with dose)
  - PLV ranks channels by recovery quality (direct metric)
```

---

### PATH C: SSD (Spatio-Spectral Decomposition)

```
╔════════════════════════════════════════════════════════════════════════════╗
║ SSD: Decompose by Signal-Band Dominance, Rank Components                  ║
╚════════════════════════════════════════════════════════════════════════════╝

STEP 1: Prepare Covariance Matrices (Signal Band vs Broadband)
  Input: on_raw_epochs (20 epochs, 22 channels, 300 samples)
  ────────────────────────────────────────────────────────────────────────
  Band-pass to signal band (11.95–12.95 Hz):
    on_signal_epochs = filter(on_raw_epochs, 11.95, 12.95)
    on_signal_concat = reshape((22, 6000))
    cov_signal = cov(on_signal_concat)  ← Emphasis on target frequency
  
  Band-pass to view band (4–20 Hz):
    on_view_concat = reshape((22, 6000))
    cov_view = cov(on_view_concat)     ← Broadband reference
  
STEP 2: Generalized Eigendecomposition
  Solve: cov_signal · w = λ · cov_view · w
  ────────────────────────────────────────────────────────────────────────
  Result: 22 eigenvectors (spatial filters) w_i with eigenvalues λ_i
          High λ = signal-band power dominates over broadband (good signal)
          Low λ = broadband dominates (artifact-laden)
  
  Action: Sort by descending λ
          Keep top 6 components (N_SSD_COMPONENTS = 6)
  
STEP 3: Project Top 6 Components
  For each top-6 component:
    component_i(t) = w_i^T · raw_data(t)  ← linear combination of 22 channels
  
  Output: ssd_components = (6, 6000) synthetic sources
  
STEP 4: Rank Components by PLV
  For each of 6 components:
    a) Extract component signal: (20, 300) epochs
    b) Band-pass filter to 12.45 Hz (signal band)
    c) Compute PLV vs GT across 20 epochs
    d) Compute PSD to check for 12.45 Hz peak
    e) Store: plv[component_idx], peak_hz[component_idx]
  
  Result: ssd_plv_scores = [0.964, 0.241, 0.125, 0.053, 0.022, 0.011]
  Action: selected_ssd_comp_idx = argmax(ssd_plv_scores)
  
STEP 5: Select Best SSD Component for This Intensity
  on_ssd_selected = ssd_components[selected_ssd_comp_idx, :]  ← Reshape to (20, 300)
  metrics = compute_epoch_plv_summary(on_ssd_selected, gt_on_epochs, ...)
  
OUTPUT PER INTENSITY:
  - selected_component_idx: best of 6 SSD components (usually 0, sometimes 1)
  - best_plv: PLV for selected SSD component (0.964 → 0.932 → ... example)
  - phase_samples: ~20 phase samples (one per epoch)
  
RATIONALE FOR SSD:
  - SSD combines spatial + spectral information
  - Eigenvalue sorting pre-selects components by signal-band dominance
  - PLV ranking provides final selection (recovery quality)
  - Often outperforms raw because it finds spatial combinations optimized for target frequency
```

---

### REFERENCE: GT vs STIM

```
╔════════════════════════════════════════════════════════════════════════════╗
║ REFERENCE: PLV Between Delivered Stimulus and Ground Truth                ║
╚════════════════════════════════════════════════════════════════════════════╝

No processing applied. Just compute:
  PLV = phase_locking(stim_on_epochs, gt_on_epochs) per intensity
  
Output: stim_plv = [0.952, 0.831, 0.861, 0.857, 0.837]

Interpretation:
  - Always near 1.0 or very high (delivered stim and GT are from same physical source)
  - Upper bound: no recovery method can exceed this
  - Shows baseline stimulus-to-GT coupling quality across intensities
```

---

## Part 3: Key Methodological Decisions

### Decision 1: Channel Selection Strategy

```
RAW:
  At 10%:   Select best channel by max PLV
  At 20–50%: Lock and reuse that same channel
  Reason:   Isolates artifact effect from spatial drift
  
SASS & SSD:
  At each intensity: Re-select best channel/component by max PLV
  Reason:   Processing pipeline output changes per intensity
            (artifact structure and cleaning effectiveness vary with dose)
  
Why not lock raw everywhere?
  ✓ Locks spatial reference → PLV changes = artifact, not drift
  ✗ But artifact might physically move with intensity (unmeasurable)
```

### Decision 2: Metric for PLV Computation

```
Before filtering (PREVIOUS — WRONG):
  hilbert(unfiltered_signal) → phase
  Problem: Broadband noise has random-walk phase; artifact can alias to GT phase

After filtering (CURRENT — CORRECT):
  filter(signal, 11.95, 12.95 Hz) → hilbert() → phase
  Benefit: Phase now represents true 12.45 Hz oscillation
  Result: PLV measures real signal coherence, not noise aliasing
```

### Decision 3: PLV Computation Method

```
Per-epoch PLV (what we compute):
  For each epoch: plv_i = |mean(exp(i * phase_diff))|
  Average across epochs: mean_plv = mean([plv_1, ..., plv_20])
  
Alternative (peak sampling):
  Sample phase once at reference peaks per epoch: ~20 samples total
  Compute: plv = |mean(exp(i * sample_phases))|
  
We use per-epoch to capture time-varying coherence across full 1.2 s window
```

---

## Part 4: Pseudocode (Simplified)

```python
"""Transform 22-channel raw EEG through 3 paths; rank by GT phase locking."""

import numpy as np
from scipy.signal import hilbert

# LOAD
raw_eeg = load_vhdr("run02.vhdr")           # (n_samples, 22 channels)
stim_trace = extract_channel("stim")        # (n_samples,)
gt_trace = extract_channel("ground_truth")  # (n_samples,)

# DETECT BLOCKS & EPOCH
blocks = detect_stim_blocks(stim_trace)     # 100 blocks × 5 intensities
on_raw_epochs = epoch(raw_eeg, blocks, "ON", 0.3, 1.5)   # (20, 22, 300) per intensity
late_off_raw_epochs = epoch(raw_eeg, blocks, "OFF", 1.5, 3.2)

# ════════════════════════════════════════════════════════════════════════════
# PATH A: RAW CHANNEL
# ════════════════════════════════════════════════════════════════════════════

for intensity in [10%, 20%, 30%, 40%, 50%]:
    on_epochs = on_raw_epochs[intensity]    # (20, 22, 300)
    
    if intensity == 10%:
        # Find and lock best channel
        best_plv = -1
        for ch_idx in range(22):
            ch_data = on_epochs[:, ch_idx, :]  # (20, 300)
            ch_filt = bandpass(ch_data, 11.95, 12.95)  # Filter to signal band
            plv = compute_plv(ch_filt, gt_on_epochs[intensity])
            if plv > best_plv:
                best_plv = plv
                locked_ch_idx = ch_idx
    
    # Use locked channel for all intensities
    raw_selected = on_epochs[:, locked_ch_idx, :]  # (20, 300)
    raw_metrics[intensity] = compute_plv(raw_selected, gt_on_epochs[intensity])


# ════════════════════════════════════════════════════════════════════════════
# PATH B: SASS
# ════════════════════════════════════════════════════════════════════════════

for intensity in [10%, 20%, 30%, 40%, 50%]:
    on_epochs = on_raw_epochs[intensity]    # (20, 22, 300)
    off_epochs = late_off_raw_epochs[intensity]
    
    # Step 1: Prepare covariance
    on_broad = bandpass(on_epochs, 4, 20)   # Filter to view band
    off_broad = bandpass(off_epochs, 4, 20)
    on_concat = reshape(on_broad, (22, -1))  # (22, 6000)
    off_concat = reshape(off_broad, (22, -1))
    
    cov_on = np.cov(on_concat)
    cov_off = np.cov(off_concat)
    
    # Step 2: SASS
    cleaned_concat = sass_decompose(on_concat, cov_on, cov_off)
    
    # Step 3: Reshape back
    cleaned_epochs = reshape(cleaned_concat, (20, 22, 300))
    
    # Step 4: Rank all 22 cleaned channels
    best_plv = -1
    for ch_idx in range(22):
        ch_data = cleaned_epochs[:, ch_idx, :]
        ch_filt = bandpass(ch_data, 11.95, 12.95)
        plv = compute_plv(ch_filt, gt_on_epochs[intensity])
        if plv > best_plv:
            best_plv = plv
            selected_ch_idx = ch_idx
    
    sass_selected = cleaned_epochs[:, selected_ch_idx, :]
    sass_metrics[intensity] = compute_plv(sass_selected, gt_on_epochs[intensity])


# ════════════════════════════════════════════════════════════════════════════
# PATH C: SSD
# ════════════════════════════════════════════════════════════════════════════

for intensity in [10%, 20%, 30%, 40%, 50%]:
    on_epochs = on_raw_epochs[intensity]
    
    # Step 1: Prepare covariances (signal band vs view band)
    on_signal = bandpass(on_epochs, 11.95, 12.95)
    on_view = bandpass(on_epochs, 4, 20)
    on_signal_concat = reshape(on_signal, (22, -1))
    on_view_concat = reshape(on_view, (22, -1))
    
    cov_signal = np.cov(on_signal_concat)
    cov_view = np.cov(on_view_concat)
    
    # Step 2: Generalized eigendecomposition
    eigvals, eigvecs = scipy.linalg.eigh(cov_signal, cov_view)  # Sort descending
    top_6_vecs = eigvecs[:, -6:]  # Keep top 6 components
    
    # Step 3: Project to components
    components = top_6_vecs.T @ on_view_concat  # (6, 6000)
    components_epochs = reshape(components, (6, 20, 300))
    
    # Step 4: Rank components by PLV
    best_plv = -1
    for comp_idx in range(6):
        comp_data = components_epochs[comp_idx, :, :]  # (20, 300)
        comp_filt = bandpass(comp_data, 11.95, 12.95)
        plv = compute_plv(comp_filt, gt_on_epochs[intensity])
        if plv > best_plv:
            best_plv = plv
            selected_comp_idx = comp_idx
    
    ssd_selected = components_epochs[selected_comp_idx, :, :]
    ssd_metrics[intensity] = compute_plv(ssd_selected, gt_on_epochs[intensity])


# ════════════════════════════════════════════════════════════════════════════
# OUTPUT
# ════════════════════════════════════════════════════════════════════════════

# Summary table
print("Intensity | Raw PLV | SASS PLV | SSD PLV | STIM PLV")
for intensity in [10%, 20%, 30%, 40%, 50%]:
    print(f"{intensity}      | {raw_metrics[intensity]:.3f}   | {sass_metrics[intensity]:.3f}   | {ssd_metrics[intensity]:.3f}   | {stim_metrics[intensity]:.3f}")

# Diagnostic plots per path
for intensity in [10%, 20%, 30%, 40%, 50%]:
    plot_diagnostic(raw_selected[intensity], "Raw", intensity)
    plot_diagnostic(sass_selected[intensity], "SASS", intensity)
    plot_diagnostic(ssd_selected[intensity], "SSD", intensity)
```

---

## Part 5: Expected Output Pattern

```
╔════════════════════════════════════════════════════════════════════════════╗
║                    PLV vs Stimulation Intensity                           ║
║               (What You Should See in Results)                            ║
╚════════════════════════════════════════════════════════════════════════════╝

PLV (Phase Locking)

1.0 │
    │                 GT-STIM (reference upper bound)
0.95│      ╔═══════════════════════════════════════════════
    │      ║
0.9 │      ├─ SASS (artifact removal)
    │      │    ├─ high at 10–20% (good cleaning)
    │      │    ├─ drops at 40–50% (artifact too complex)
0.8 │      │    │
    │      ├─ SSD (signal extraction)
    │      │    ├─ peaks when spatial structure optimal
0.7 │      │    │
    │      ├─ Raw (fixed channel)
    │      │    └─ monotonic decline (increasing artifact)
0.6 │      │
    │      │
0.5 │      │  Artifact burden
    │      │  increases with
0.4 │      │  stimulus intensity
    │      │
0.3 └──────┴────────────────────────────────────────────────
         10%  20%  30%  40%  50%
         Stimulation Intensity

KEY INSIGHT FROM YOUR RESULTS:
  10%: All three paths high (minimal artifact)
  20%: SASS/SSD maintain high PLV; Raw slightly lower
  30%: SASS crashes; SSD stays high; Raw stays moderate ← Interesting!
  40%: SSD crashes; SASS recovers; Raw stays moderate
  50%: All decline; Raw most robust
```

---

## Part 6: How to Read the Diagnostic Plots

Each `.png` diagnostic figure shows 3 sub-panels for one intensity + method:

### Panel 1: PSD (Power Spectral Density)

```
Semilogy plot:  Frequency (Hz) vs Power (log scale)
─────────────────────────────────────────────────────

Expected:
  ✓ Clear peak at 12.45 Hz (red dashed line) = signal present
  ✗ No peak, broadband noise = artifact dominates or poor extraction

Example interpretation:
  SASS at 20%:     Tall peak at 12.45 → Good recovery
  SASS at 40%:     Flat spectrum, no peak → Artifact destroyed signal
```

### Panel 2: Dual Time Course (Mean ± SD)

```
Two y-axes: GT (left, black) and Component (right, colored)
─────────────────────────────────────────────────────────────

GT (left axis):
  ─ Black line = mean GT across 20 epochs
  ─ Light gray band = ±1 SD (variability across epochs)

Component (right axis):
  ─ Blue/teal/orange line = method's extracted signal
  ─ Colored band = ±1 SD
  
Expected alignment:
  ✓ Black and colored traces oscillate in phase (syn across 1.2 s)
  ✗ Traces out of phase or component is flat = poor recovery
  
Why independent scaling?
  → Amplitudes differ; we care about phase alignment, not amplitude match
```

### Panel 3: Dual ITPC Time Course

```
ITPC (Inter-Trial Phase Coherence) vs time [0, 1.2 s]
─────────────────────────────────────────────────────

Green line (ITPC vs GT):
  – Measures phase consistency of component against GT
  – High ITPC = component phase stable and locked to GT
  – Low ITPC = component phase random (noise-like)

Red dashed (ITPC vs STIM):
  – Measures phase consistency against delivered stimulus
  – Shows whether recovered component tracks stimulus or noise
  
Expected pattern:
  ✓ Both lines > 0.8 starting ~0.2 s → signal emerges
  ✓ Green and red might differ if artifact locks differently
  ✗ Both near 0 = no coherent oscillation (pure noise)
  
Historical insight:
  – When you ran this BEFORE filtering: both green & red identical
  – When you FILTERED before Hilbert: they diverged (true signals differ from artifacts)
  – This filtering fix revealed SASS fails at 30% but SSD survives
```

---

## Summary: The Three Paths

| **PATH** | **Processing** | **Selection** | **Best At** | **Fails At** |
|----------|---|---|---|---|
| **Raw** | None | Best channel at 10%, locked | Low intensities (10–20%) | High artifact (40–50%) |
| **SASS** | Nulls artifact eigenvectors | Reranks all channels per intensity | Medium intensities (10–30%) | Complex artifact (40–50%) |
| **SSD** | Signal-band spatial filter + top-6 ranking | Reranks top 6 components per intensity | Varies with stimulus structure | Sometimes (depends on spatial alignment) |
| **GT-STIM** | None (reference) | N/A | All intensities (~0.95) | Should never fail |

---

## Next Steps After Running

1. **Check the summary table** (`exp06_run02_on_raw_sass_ssd_plv_summary.txt`)
   - Do Raw, SASS, SSD, STIM PLV values match the pattern above?

2. **Review diagnostic plots** (5 figures per path × 3 paths = 15 figures)
   - Do PSDs show 12.45 Hz peaks in Raw/SASS/SSD?
   - Do time courses align (black vs colored)?
   - Does ITPC divergence (green vs red) match expected behavior?

3. **Check phase grid** (`exp06_run02_on_raw_sass_ssd_phase_grid.png`)
   - Polar histograms showing phase-difference distributions
   - Should be concentrated around 0 rad (phase-locked) for good recovery

4. **Compare across intensities**
   - Does PLV decline monotonically for Raw (expected)?
   - Do SASS/SSD show non-monotonic patterns (expected)?
   - Why does SASS crash at 30% while SSD survives?

---

This is how **your pipeline** transforms data. Each path uses different preprocessing (none, SASS nulling, or SSD filtering) and different selection criteria (channel vs component) to extract the best 12.45 Hz recovery from a noisy stimulation recording.

