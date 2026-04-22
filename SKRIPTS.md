# SKRIPTS: Pseudo-Code Walkthroughs

---

## 1. explore_exp06_best_raw_channel_sync.py

**Purpose:** Identify the single best-performing raw EEG channel per intensity based on phase locking, then visualize sync with ground truth.

### 1.1 Data Flow

```
VHDR Recording (5 intensities × 20 cycles)
├─ Extract: 22 EEG channels + stim + ground truth
├─ Filter: 12.45 Hz bandpass (±0.5 Hz)
├─ Compute: PLV per channel per cycle
├─ Select: Best channel (max PLV) at 10%, lock for 20%–50%
├─ Extract: Filtered time courses (all cycles concatenated)
└─ Output: 5-panel overlay figure + summary table
```

### 1.2 Main Pseudo-Code

```python
# ════════════════════════════════════════════════════════════════
# 1.2.1 LOAD DATA
# ════════════════════════════════════════════════════════════════
raw_stim_full = mne.io.read_raw_brainvision(...)
# → MNE Raw object: 22 EEG + stim + GT, 250 Hz, ~120 s

stim_trace = raw_stim_full.pick(["stim"]).get_data()[0]
gt_trace = raw_stim_full.pick(["ground_truth"]).get_data()[0]
raw_eeg = raw_stim_full.drop_channels(["stim", "ground_truth", ...])
# → Arrays: stim (n_samples,), gt (n_samples,), EEG (22, n_samples)


# ════════════════════════════════════════════════════════════════
# 1.2.2 DETECT STIMULUS BLOCKS
# ════════════════════════════════════════════════════════════════
block_onsets, block_offsets = detect_stim_blocks(stim_trace, ...)
# Uses rising edge detection on stim_trace
# Expected: 100 blocks (5 intensities × 20 cycles)
# → Enables windowing: ON window = [onset + 0.3s, onset + 1.5s]


# ════════════════════════════════════════════════════════════════
# 1.2.3 COMPUTE PHASE LOCKING (PLV) PER CHANNEL PER CYCLE
# ════════════════════════════════════════════════════════════════
# Loop over each stimulus block
for block_idx in range(n_blocks):
    intensity_idx = block_idx // 20  # 0–19 → 10%, 20–39 → 20%, etc.
    on_start = block_onsets[block_idx] + 0.3 * sfreq
    on_end = block_onsets[block_idx] + 1.5 * sfreq
    
    # Extract ON-window traces
    on_eeg = eeg_data[:, on_start:on_end]  # (22, ~300 samples at 250 Hz)
    on_gt = gt_data[on_start:on_end]       # (300,)
    
    # Bandpass filter to 12.45 Hz (±0.5 Hz) to isolate target
    on_eeg_filt = filter_signal(on_eeg, sfreq=250, f_low=11.95, f_high=12.95)
    on_gt_filt = filter_signal(on_gt, sfreq=250, f_low=11.95, f_high=12.95)
    # → Removes artifact harmonics; isolates true phase coherence
    
    # Compute instantaneous phase via Hilbert transform
    on_eeg_phase = np.angle(hilbert(on_eeg_filt, axis=-1))  # (22, 300)
    on_gt_phase = np.angle(hilbert(on_gt_filt, axis=-1))    # (300,)
    
    # PLV: mean magnitude of phase difference
    phase_diff = on_eeg_phase - on_gt_phase[newaxis, :]
    plv_per_ch = |mean(exp(i * phase_diff), axis=1)|  # (22,)
    # → Each channel gets one PLV value for this cycle
    # → PLV ∈ [0, 1]: 1 = perfect sync, 0 = no sync
    
    # Store: plv_by_intensity[intensity_idx][channel_name] += [plv]

# Average PLV across 20 cycles per channel per intensity
for intensity in [10%, 20%, 30%, 40%, 50%]:
    for ch_name in channels:
        mean_plv = mean(plv_by_intensity[intensity][ch_name])


# ════════════════════════════════════════════════════════════════
# 1.2.4 SELECT BEST CHANNEL (LOCK AT 10%, FIX FOR ALL OTHERS)
# ════════════════════════════════════════════════════════════════
# At 10% intensity: find channel with highest PLV
best_ch_10pct = argmax(mean_plv_10pct)  # e.g., "Cz"
FIXED_CHANNEL = best_ch_10pct

# At 20%–50%: always use FIXED_CHANNEL
# Rationale: Locks spatial reference. Any PLV change = artifact contamination,
#            not spatial drift. If best_ch changes per intensity, can't interpret
#            whether decline is artifact or just the best channel shifted.


# ════════════════════════════════════════════════════════════════
# 1.2.5 EXTRACT FILTERED TIME COURSES (ALL CYCLES CONCATENATED)
# ════════════════════════════════════════════════════════════════
for intensity in [10%, 20%, 30%, 40%, 50%]:
    cycles = []
    for each 20 cycles at this intensity:
        on_eeg_raw = eeg_data[FIXED_CHANNEL, on_start:on_end]
        on_gt_raw = gt_data[on_start:on_end]
        
        # Bandpass filter
        on_eeg_filt = filter_signal(on_eeg_raw, ..., 11.95, 12.95)
        on_gt_filt = filter_signal(on_gt_raw, ..., 11.95, 12.95)
        
        cycles.append((on_eeg_filt, on_gt_filt))
    
    # Concatenate: 20 × 1.2s windows → 24 s total per intensity
    timecourse[intensity] = concatenate(cycles)  # (7200,) at 250 Hz


# ════════════════════════════════════════════════════════════════
# 1.2.6 VISUALIZE: 5-PANEL OVERLAY (INTENSITY × CHANNEL vs GT)
# ════════════════════════════════════════════════════════════════
figure with 5 subplots:
    for intensity in [10%, 20%, 30%, 40%, 50%]:
        ax[intensity]
        plot(time_s, gt_timecourse, color=black, linewidth=2, label="GT")
        plot(time_s, eeg_timecourse, color=intensity_color, label=f"{FIXED_CH} (PLV={plv:.4f})")
        # Expected: high intensities (40–50%) show increasing phase drift
        #           low intensities (10–30%) show clean overlay


# ════════════════════════════════════════════════════════════════
# 1.2.7 EXPORT SUMMARY
# ════════════════════════════════════════════════════════════════
table:
    Intensity | Best Channel | Mean PLV | Status
    10%       | Cz           | 0.9876   | ✓ Locked
    20%       | Cz           | 0.9812   | ✓ Fixed
    30%       | Cz           | 0.9654   | ✓ Fixed
    40%       | Cz           | 0.8234   | ⚠ Declining
    50%       | Cz           | 0.7102   | ✗ Poor sync
```

### 1.3 Validation Checklist

- [ ] Best channel at 10% PLV > 0.95?
- [ ] Same channel used 20%–50% (no switching)?
- [ ] PLV declining with intensity (expected: 0.98 → 0.71)?
- [ ] Visual overlay: GT and EEG phases aligned at low intensity?
- [ ] At 40–50%: visible phase drift or amplitude collapse in EEG?

---

## 2. analyze_exp06_run02_on_raw_sass_ssd_plv_CORRECTED.py

**Purpose:** Compare three signal recovery paths (raw, SASS, SSD) using PLV ranking instead of mixed metrics.

### 2.1 Data Flow

```
Raw EEG (baseline, 250 Hz, 22 ch)
│
├─────── PATH A: RAW CHANNEL ──────────────────┐
│        Best channel (fixed at 10%)            │
│        Compute PLV to ground truth             │
│        Rank channels: max PLV                  │
│                                               │
├─────── PATH B: SASS (Source Artifact         │
│        Suppression via Spatial filtering)     │
│        Apply SASS filter                      ├─→ Compare PLV
│        Rank channels: max PLV                  │    across paths
│                                               │
└─────── PATH C: SSD (Spatio-Spectral          │
          Decomposition)                        │
          Eigendecompose in target band         │
          Rank components: max PLV              │
          Project back to channel space          │
                                               ├─→ Output: 3-panel PLV vs intensity
                                               │  + multi-row comparison tables
                                               │
                                               └──→ Conclusion: which path
                                                   best preserves signal?
```

### 2.2 Main Pseudo-Code

```python
# ════════════════════════════════════════════════════════════════
# 2.2.1 LOAD & PREPARE BASELINE
# ════════════════════════════════════════════════════════════════
raw = mne.io.read_raw_brainvision(...)  # 22 ch, 250 Hz, ~120 s

# Exclude non-EEG
raw_eeg = raw.drop_channels([...])

# Get per-intensity stimulus blocks (same as above)
block_onsets, block_offsets = detect_stim_blocks(...)
# ON window: [onset + 0.3s, onset + 1.5s]


# ════════════════════════════════════════════════════════════════
# 2.2.2 COMPUTE GROUND TRUTH PHASE (REFERENCE)
# ════════════════════════════════════════════════════════════════
gt_trace = raw.pick(["ground_truth"]).get_data()[0]

# Bandpass to 12.45 Hz (±0.5 Hz)
gt_filt = filter_signal(gt_trace, sfreq=250, f_low=11.95, f_high=12.95)
gt_phase = np.angle(hilbert(gt_filt))  # (n_samples,)
# → Reference phase (ground truth); never changes


# ════════════════════════════════════════════════════════════════
# 2.2.3 PROCESS EACH INTENSITY: COMPARE 3 PATHS
# ════════════════════════════════════════════════════════════════

for intensity in [10%, 20%, 30%, 40%, 50%]:
    # Get all cycles for this intensity
    cycles = [blocks i to i+20]
    
    
    # ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
    # ┃ PATH A: RAW CHANNEL (Best at 10%, fixed for all)      ┃
    # ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
    
    for cycle in cycles:
        on_eeg = eeg_data[:, on_start:on_end]  # (22, 300)
        on_eeg_filt = filter_signal(on_eeg, ..., 11.95, 12.95)
        on_eeg_phase = np.angle(hilbert(on_eeg_filt))  # (22, 300)
        
        phase_diff = on_eeg_phase - gt_phase[on_start:on_end]
        plv_per_ch = |mean(exp(i * phase_diff), axis=1)|  # (22,)
        
        for ch_idx, ch_name in enumerate(ch_names):
            raw_plv[intensity][ch_name] += [plv_per_ch[ch_idx]]
    
    best_raw_ch = argmax(mean(raw_plv[intensity]))
    # Select: FIXED_CHANNEL if intensity > 10%, else argmax
    
    
    # ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
    # ┃ PATH B: SASS (Spatial Artifact Suppression)           ┃
    # ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
    
    # Step 1: Compute spatial filter (SASS = artifact correlation)
    # SASS finds linear combination of channels that cancels artifact
    sass_weights = compute_sass_filter(eeg_data, artifact_template)
    # artifact_template = high-artifact channel (e.g., TP9)
    # sass_weights = spatial projection that removes artifact correlation
    
    # Step 2: Apply SASS to each cycle
    for cycle in cycles:
        on_eeg = eeg_data[:, on_start:on_end]  # (22, 300)
        
        # SASS: subtract weighted correlation
        on_eeg_sass = on_eeg - sass_weights @ on_eeg
        # → Each channel reduced by its artifact contamination
        
        # Filter and compute phase
        on_eeg_filt = filter_signal(on_eeg_sass, ..., 11.95, 12.95)
        on_eeg_phase = np.angle(hilbert(on_eeg_filt))
        
        phase_diff = on_eeg_phase - gt_phase[on_start:on_end]
        plv_per_ch = |mean(exp(i * phase_diff), axis=1)|
        
        for ch_idx, ch_name in enumerate(ch_names):
            sass_plv[intensity][ch_name] += [plv_per_ch[ch_idx]]
    
    best_sass_ch = argmax(mean(sass_plv[intensity]))
    
    
    # ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
    # ┃ PATH C: SSD (Spatio-Spectral Decomposition)           ┃
    # ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
    
    # Step 1: Build covariance matrices in target band (12.45 Hz)
    for cycle in cycles:
        on_eeg = eeg_data[:, on_start:on_end]
        on_eeg_filt = filter_signal(on_eeg, ..., 11.95, 12.95)
        
        # Two covariance matrices:
        cov_signal = on_eeg_filt @ on_eeg_filt.T / n_samples
        cov_noise = on_eeg @ on_eeg.T / n_samples  (whole band, unfiltered)
        
        accumulate += cov_signal, cov_noise
    
    # Average across cycles
    avg_cov_signal = mean(cov_signal_per_cycle)
    avg_cov_noise = mean(cov_noise_per_cycle)
    
    # Step 2: Generalized eigendecomposition
    eigenvecs, eigenvals = eigh(avg_cov_signal, avg_cov_noise)
    # → Eigenvector 0 = channel combination that maximizes power in 12.45 Hz
    #                   while minimizing power in broadband (artifact)
    # → Eigenvalue = signal-to-noise ratio for this component
    
    # Step 3: Project back to channel space; compute PLV per component
    for component in range(22):
        ssd_timecourse[component] = eigenvecs[:, component] @ on_eeg_filt
        ssd_phase[component] = np.angle(hilbert(ssd_timecourse[component]))
        
        phase_diff = ssd_phase[component] - gt_phase
        plv_ssd[intensity][component] = |mean(exp(i * phase_diff))|
    
    best_ssd_comp = argmax(plv_ssd[intensity])


# ════════════════════════════════════════════════════════════════
# 2.2.4 COMPARE ACROSS PATHS
# ════════════════════════════════════════════════════════════════
# Collect mean PLV for best option in each path, each intensity
results = {
    "Raw": [plv_10%, plv_20%, ..., plv_50%],
    "SASS": [plv_10%, plv_20%, ..., plv_50%],
    "SSD": [plv_10%, plv_20%, ..., plv_50%],
}


# ════════════════════════════════════════════════════════════════
# 2.2.5 VISUALIZE: 3-PANEL PLV VS INTENSITY
# ════════════════════════════════════════════════════════════════
# Three subplots: raw | SASS | SSD
# Each shows PLV (y-axis) vs intensity (x-axis)
#
# Expected pattern:
#   10%:   all three ~ 0.98
#   20%:   all three ~ 0.96
#   30%:   all three ~ 0.93
#   40%:   Raw 0.82, SASS 0.85, SSD 0.88  (SSD best)
#   50%:   Raw 0.71, SASS 0.76, SSD 0.81  (SSD best)
#
# Interpretation:
#   - All drop (artifact increasing)
#   - SSD/SASS drop slower (better suppression)
#   - SSD best (combines spatial + spectral info)


# ════════════════════════════════════════════════════════════════
# 2.2.6 EXPORT SUMMARY TABLES
# ════════════════════════════════════════════════════════════════
# Table 1: Best option per path per intensity
# Table 2: Rank all channels/components by PLV (per path, per intensity)
# Table 3: Conclusion (which path wins?)
```

### 2.3 Key Design Decisions

| Decision | Why |
|----------|-----|
| **Lock raw channel at 10%** | Prevents spatial drift from confounding artifact detection. PLV changes → artifact only. |
| **Rank all by PLV (not power_ratio)** | Direct metric (phase coherence to GT). Consistent across raw/SASS/SSD for fair comparison. |
| **SASS weights from artifact template** | Targets the dominant artifact (TP9 or high-amplitude channel). Spatial filtering is data-driven. |
| **SSD: eigendecompose signal vs noise** | Targets 12.45 Hz specifically (signal-to-noise ratio). Removes broadband artifact without filtering. |

### 2.4 Validation Checklist

- [ ] All three paths show decreasing PLV with intensity (expected behavior)?
- [ ] SSD/SASS decay slower than raw (i.e., better artifact suppression)?
- [ ] SSD > SASS > Raw at 40–50% (hierarchy holds)?
- [ ] Raw PLV at 10% matches `explore_exp06_best_raw_channel_sync.py` output?
- [ ] Summary tables show clear interpretation (e.g., "SSD is 15% better at 50%")?

---

## 3. generate_all_metadata.py

**Purpose:** Orchestrate all analysis scripts and collect results into unified metadata.

### 3.1 Execution Order

```
1. explore_exp06_best_raw_channel_sync.py
   → Outputs: metadata.json (best_channel), overlay.png, summary.txt

2. analyze_exp06_run02_on_raw_sass_ssd_plv_CORRECTED.py
   → Reads: metadata.json (best_channel)
   → Outputs: comparison tables, 3-panel figure, conclusions.txt

3. generate_all_metadata.py (aggregate)
   → Reads: all outputs from (1) and (2)
   → Outputs: unified_metadata.json, final_report.txt
```

### 3.2 Pseudo-Code

```python
# ════════════════════════════════════════════════════════════════
# 3.2.1 COLLECT RESULTS FROM UPSTREAM SCRIPTS
# ════════════════════════════════════════════════════════════════
metadata_raw = load_json("exp06_run02_fixed_raw_channel_metadata.json")
metadata_comparison = load_json("exp06_run02_comparison_results.json")

# ════════════════════════════════════════════════════════════════
# 3.2.2 UNIFY AND ANNOTATE
# ════════════════════════════════════════════════════════════════
unified = {
    "exp_id": "EXP06",
    "date": timestamp,
    "best_channel_fixed": metadata_raw["best_channel"],
    "plv_by_intensity": {...},
    "comparison": {
        "raw": {...},
        "sass": {...},
        "ssd": {...},
    },
    "conclusion": "SSD achieves 81% PLV at 50%; recommended for recovery."
}

# ════════════════════════════════════════════════════════════════
# 3.2.3 GENERATE FINAL REPORT
# ════════════════════════════════════════════════════════════════
report = format_for_human(unified)
# → Markdown file with findings, figures, interpretation
```

---

## Appendix: Drawing Symbols & Conventions

- `├─` Branch (data flow)
- `│` Vertical line (data stream)
- `└─` End of branch
- `┌─` Start of box
- `┗━` Emphasized box start
- `→` Transformation arrow
- `(type, shape)` Data annotation (type, array dimensions)
- `#` Comment (structural or explanatory)
- `#====` Section divider (major boundary)
- `# ┏━━━` Highlighted subsection (key decision point)
