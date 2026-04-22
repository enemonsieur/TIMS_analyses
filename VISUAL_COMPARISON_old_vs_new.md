# Visual Comparison: Old vs. New Pipeline

## The Three Paths

### OLD PIPELINE (Original Script)

```
RAW PATH (Per-Intensity Re-selection)
┌─────────────────────────────────────────────────────────────┐
│ FOR each intensity (10%, 20%, 30%, 40%, 50%):              │
│   1. Extract ON windows for this intensity                 │
│   2. FOR each EEG channel:                                 │
│      a. Compute PLV to GT                                 │
│   3. best_ch = argmax(PLV) ← CHANGES PER INTENSITY        │
│   4. Return best_ch_data, PLV_best_ch                      │
└─────────────────────────────────────────────────────────────┘
                      ↓
        PROBLEM: Channel varies with dose
        → Can't tell if PLV drop is artifact contamination
           or just a different electrode being selected


SASS PATH (Hybrid: SASS + SSD-like Processing)
┌─────────────────────────────────────────────────────────────┐
│ 1. Extract ON, late-OFF windows                            │
│ 2. SASS artifact suppression:                              │
│    a. Cov_A (ON in 4–20 Hz)                                │
│    b. Cov_B (late-OFF in 4–20 Hz)                          │
│    c. Generalized eigendecomp → null top artifact components
│    d. Project back → SASS-cleaned multichannel             │
│ 3. [PROBLEM STARTS HERE]                                   │
│    FOR each of top-6 eigenvalues (SASS-cleaned signal-band):
│      a. Extract component via spatial filter               │
│      b. Compute ON/OFF broadband power ratio               │
│    4. best_component = argmin(power_ratio)                 │
│    5. Return component, PLV                                │
└─────────────────────────────────────────────────────────────┘
                      ↓
        PROBLEM: Applies eigendecomposition AFTER SASS
        → This is a hidden SSD on top of SASS (not pure SASS)
        → SSD components ranked by power ratio, not PLV
        → Inconsistent with raw path (which uses PLV)


SSD PATH (Direct SSD, But Wrong Ranking)
┌─────────────────────────────────────────────────────────────┐
│ 1. Extract ON, late-OFF windows                            │
│ 2. SSD extraction:                                         │
│    a. Cov_signal (ON in 11.95–12.95 Hz)                    │
│    b. Cov_view (ON in 4–20 Hz)                             │
│    c. Generalized eigendecomp → descending eigenvalues     │
│ 3. FOR each of top-6 components:                           │
│      a. Compute ON/OFF broadband power ratio               │
│    4. best_component = argmin(power_ratio)  ← WRONG METRIC │
│    5. Return component, PLV                                │
└─────────────────────────────────────────────────────────────┘
                      ↓
        PROBLEM: Ranked by power ratio (proxy)
        → Should rank by direct PLV to GT
        → Inconsistent with raw path and SASS


SUMMARY TABLE: Selection Metrics
┌──────────┬──────────────────┬─────────────────────┐
│ Path     │ Selection Method │ Final Output        │
├──────────┼──────────────────┼─────────────────────┤
│ RAW      │ max PLV          │ Best channel        │
│ SASS     │ min power_ratio  │ Best component      │
│ SSD      │ min power_ratio  │ Best component      │
└──────────┴──────────────────┴─────────────────────┘
         ↑
    ASYMMETRIC: Two use power_ratio (proxy),
    one uses PLV (direct). Hard to compare fairly.
```

---

## NEW PIPELINE (Corrected Scripts)

```
RAW PATH (FIXED at 10%)
┌─────────────────────────────────────────────────────────────┐
│ Step 0 (Offline, in separate script):                      │
│   Run explore_exp06_best_raw_channel_fixed.py              │
│   → Find best channel at 10%                               │
│   → Store in JSON metadata                                 │
│                                                             │
│ Step 1 (Main analysis, for each intensity):               │
│   1. Load fixed_channel_name from metadata                 │
│   2. ch_idx = index of fixed_channel_name                  │
│   3. on_raw_selected = on_raw_epochs[:, ch_idx, :]        │
│   4. Compute PLV for fixed_channel (no ranking)            │
│   5. Return fixed_channel_data, PLV_fixed_channel          │
└─────────────────────────────────────────────────────────────┘
                      ↓
        ADVANTAGE: Same electrode across all intensities
        → PLV changes = artifact contamination (clean interpretation)
        → Not confounded by spatial variation


SASS PATH (PURE: Just Channel Ranking)
┌─────────────────────────────────────────────────────────────┐
│ 1. Extract ON, late-OFF windows                            │
│ 2. SASS artifact suppression (same as before):             │
│    a. Cov_A (ON in 4–20 Hz)                                │
│    b. Cov_B (late-OFF in 4–20 Hz)                          │
│    c. Generalized eigendecomp → null top artifact components
│    d. Project back → SASS-cleaned multichannel             │
│ 3. [NO SECONDARY DECOMPOSITION]                            │
│    FOR each of ALL SASS-cleaned channels:                  │
│      a. Compute PLV to GT (not power ratio)                │
│    4. best_ch = argmax(PLV) ← SAME AS RAW                  │
│    5. Return best_channel_data, PLV_best_channel           │
└─────────────────────────────────────────────────────────────┘
                      ↓
        ADVANTAGE: Pure SASS (no hidden SSD)
        → SASS outputs cleaned multichannel signal
        → Rank by direct PLV to GT (not proxy)
        → Consistent with raw path


SSD PATH (Correct Ranking by PLV)
┌─────────────────────────────────────────────────────────────┐
│ 1. Extract ON, late-OFF windows                            │
│ 2. SSD extraction (same as before):                        │
│    a. Cov_signal (ON in 11.95–12.95 Hz)                    │
│    b. Cov_view (ON in 4–20 Hz)                             │
│    c. Generalized eigendecomp → descending eigenvalues     │
│ 3. FOR each of top-6 components:                           │
│      a. Compute PLV to GT (NOT power ratio)  ← FIXED       │
│    4. best_component = argmax(PLV) ← SAME AS RAW & SASS    │
│    5. Return best_component_data, PLV_best_component       │
└─────────────────────────────────────────────────────────────┘
                      ↓
        ADVANTAGE: Ranked by direct PLV to GT
        → Consistent metric across all three paths
        → Direct measure of GT recovery


SUMMARY TABLE: Selection Metrics (CORRECTED)
┌──────────┬─────────────────────────┬──────────────────────┐
│ Path     │ Selection Method        │ Final Output         │
├──────────┼─────────────────────────┼──────────────────────┤
│ RAW      │ Fixed at 10% (by PLV)   │ Best channel (10%)   │
│ SASS     │ max PLV (at each intens)│ Best channel         │
│ SSD      │ max PLV (at each intens)│ Best component       │
└──────────┴─────────────────────────┴──────────────────────┘
         ↓
    SYMMETRIC: All use PLV (direct metric)
    → Fair comparison across all three paths
```

---

## Head-to-Head: Section 3.5 (SASS)

### OLD CODE (Hybrid SASS+SSD)

```python
# Lines 231–294 (original)

# SASS artifact removal (correct part)
sass_cleaned_concat = sass.sass(on_view_concat, cov_a, cov_b)

# [PROBLEM STARTS HERE] Secondary eigendecomposition on SASS output
on_sass_signal = preprocessing.filter_signal(on_sass_concat, sfreq, *SIGNAL_BAND_HZ)
late_off_sass_signal = preprocessing.filter_signal(late_off_sass_concat, sfreq, *SIGNAL_BAND_HZ)
C_on_sass = np.cov(on_sass_signal)
C_off_sass = np.cov(late_off_sass_signal)

# Generalized eigendecomposition (this is SSD, not SASS)
evals_sass, evecs_sass = linalg.eig(C_on_sass, C_off_sass)
sass_source_filters = evecs_sass_sorted[:, :min(N_SSD_COMPONENTS, n_channels)].T

# Rank by power ratio (proxy metric)
for spatial_filter in sass_source_filters:
    on_sass_component = np.dot(spatial_filter, on_sass_concat)
    on_sass_broadband = preprocessing.filter_signal(on_sass_component, sfreq, *VIEW_BAND_HZ)
    artifact_ratio = on_power / off_power
    sass_artifact_ratios.append(artifact_ratio)

selected_sass_source_index = np.argmin(sass_artifact_ratios)  # MIN power ratio
```

**Problem:** Two eigendecompositions in one path. SASS cleans, then SSD extracts.
**Metric:** Power ratio (proxy for artifact suppression)
**Inconsistency:** Raw path uses PLV; SASS uses power ratio

---

### NEW CODE (Pure SASS)

```python
# Lines 231–287 (corrected)

# SASS artifact removal (same as before)
sass_cleaned_concat = sass.sass(on_view_concat, cov_a, cov_b)
on_sass_epochs = sass_cleaned_concat.reshape(n_channels, n_epochs, n_samples).transpose(1, 0, 2)

# [NO SECONDARY DECOMPOSITION] Rank channels by PLV
sass_plv_scores = []
for ch_idx, ch_name in enumerate(raw_eeg.ch_names):
    ch_data = on_sass_epochs[:, ch_idx, :]  # (n_epochs, n_samples)
    
    # Direct PLV computation (not power ratio)
    metrics_ch = preprocessing.compute_epoch_plv_summary(
        ch_data,
        gt_on_epochs,
        sfreq,
        SIGNAL_BAND_HZ,
        TARGET_CENTER_HZ,
    )
    sass_plv_scores.append(metrics_ch["plv"])

# Select best SASS channel by PLV
selected_sass_ch_idx = np.argmax(sass_plv_scores)  # MAX PLV
on_sass_selected = on_sass_epochs[:, selected_sass_ch_idx, :]
```

**Advantage:** Pure SASS. No secondary decomposition.
**Metric:** PLV (direct measure of GT phase locking)
**Consistency:** Same metric as raw path

---

## Head-to-Head: Section 3.6 (SSD)

### OLD CODE (Power Ratio Ranking)

```python
# Lines 322–338 (original)

# Rank by power ratio
for spatial_filter in spatial_filters:
    on_component = np.dot(spatial_filter, on_raw_concat)
    on_broadband = preprocessing.filter_signal(on_component, sfreq, *VIEW_BAND_HZ)
    off_broadband = preprocessing.filter_signal(late_off_raw_concat, sfreq, *VIEW_BAND_HZ)
    
    on_power = np.mean(on_broadband ** 2)
    off_power = np.mean(off_broadband ** 2)
    artifact_ratio = on_power / (off_power + 1e-8)
    artifact_ratios.append(artifact_ratio)

selected_component_index = np.argmin(artifact_ratios)  # MIN power ratio
```

**Problem:** Power ratio is a proxy for artifact suppression, not GT recovery.
**Metric:** Power ratio
**Inconsistency:** Raw uses PLV; SSD uses power ratio

---

### NEW CODE (PLV Ranking)

```python
# Lines 322–346 (corrected)

# Rank by PLV (direct metric)
ssd_plv_scores = []
for spatial_filter in spatial_filters:
    on_component = np.dot(spatial_filter, on_raw_concat)
    on_component_epochs = on_component.reshape(n_epochs, -1)
    
    # Direct PLV computation
    metrics_comp = preprocessing.compute_epoch_plv_summary(
        on_component_epochs,
        gt_on_epochs,
        sfreq,
        SIGNAL_BAND_HZ,
        TARGET_CENTER_HZ,
    )
    ssd_plv_scores.append(metrics_comp["plv"])

selected_component_index = np.argmax(ssd_plv_scores)  # MAX PLV
```

**Advantage:** Direct PLV ranking (end-to-end metric that matters).
**Metric:** PLV
**Consistency:** Same metric as raw and SASS paths

---

## Summary: Three Corrections, Three Files

| Correction | Old Script | New Script | Key Change |
|------------|-----------|-----------|-----------|
| **Fix 1** | `analyze_exp06_run02_on_raw_sass_ssd_plv.py` Section 3.4 | `analyze_exp06_run02_on_raw_sass_ssd_plv_CORRECTED.py` Section 3.4 | Raw channel fixed at 10%, not re-selected per intensity |
| **Fix 2** | `analyze_exp06_run02_on_raw_sass_ssd_plv.py` Section 3.5 | `analyze_exp06_run02_on_raw_sass_ssd_plv_CORRECTED.py` Section 3.5 | Remove secondary eigendecomp; rank SASS-cleaned channels by PLV |
| **Fix 3** | `analyze_exp06_run02_on_raw_sass_ssd_plv.py` Section 3.6 | `analyze_exp06_run02_on_raw_sass_ssd_plv_CORRECTED.py` Section 3.6 | Rank SSD components by PLV (not power ratio) |
| **New** | N/A | `explore_exp06_best_raw_channel_fixed.py` | Find and lock best raw channel at 10% |

---

## Expected PLV Trends

```
PLV vs. Stimulation Intensity
1.0 ─┐  ╔═══════════════╗
     │  ║    GT-STIM    ║  ← Reference upper bound (always = 1.0)
0.9 ─┤  ║  (dashed line)║
     │  ╚═════╤═════════╝
     │        │
0.8 ─┤        ├─ SASS    ← Should follow raw or exceed it
     │        ├─ SSD       
0.7 ─┤        ├─ Raw (fixed)
     │        │
0.6 ─┤        │
     │        │
0.5 ─┤        │  ↓ Artifact increasingly contaminates all paths
     │        ├─ ...
0.4 ─┤        │
     │        │
0.3 ─┤        │
     │        │
0.2 ─┤        │
     │        │
0.1 ─┤        │
     │        │
0.0 ─┴────────┴───────────────
     10%  20%  30%  40%  50%
     
Expected behavior:
- RAW:   Monotonic decrease (artifact contamination)
- SASS:  High at 10–30%, drops at 40–50% (artifact structure too complex)
- SSD:   Peaks when signal dominates spatial patterns; drops when artifact dominates
- GT-STIM: Flat at 1.0 (delivered stimulus is always phase-locked to itself)
```

---

**Bottom Line:**

Old pipeline mixes metrics and processing logic across paths, making comparison unfair.
New pipeline uses pure, consistent methods with direct PLV ranking across all three paths.
