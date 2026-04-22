# Summary: Pipeline Corrections for EXP06 Analysis

## Problem Statement

The original `analyze_exp06_run02_on_raw_sass_ssd_plv.py` had three methodological issues:

1. **Raw path:** Selected best channel independently at each intensity, introducing spatial variability that confounds the dose effect
2. **SASS path:** Applied a secondary eigendecomposition on SASS-cleaned data, violating the principle that SASS and SSD are separate pipelines
3. **SSD path:** Ranked components by broadband power ratio instead of direct GT phase locking (PLV)

---

## Solutions Implemented

### 1. **Fixed Raw Channel Script** — `explore_exp06_best_raw_channel_fixed.py`

**Purpose:** Identify the single best raw EEG channel at 10% intensity and lock it for use across all intensities.

**Workflow:**
1. Extract ON windows at 10% intensity only (first 20 stimulus cycles)
2. Compute PLV to GT for each raw EEG channel
3. Select channel with highest PLV
4. Compute PLV for that fixed channel at all 5 intensities (20%, 30%, 40%, 50%)
5. Export metadata (JSON) and summary table
6. Plot 5-panel overlay showing fixed channel aligned with GT across all intensities

**Outputs:**
- `exp06_run02_fixed_raw_channel_metadata.json` — machine-readable reference (channel name, index, PLV per intensity)
- `exp06_run02_fixed_raw_channel_summary.txt` — human-readable table
- `exp06_run02_fixed_raw_channel_overlay.png` — 5-panel figure

**Rationale:** Isolates the dose effect on a single electrode without spatial confounding. If PLV drops from 0.95 at 10% to 0.60 at 50%, you know it's the artifact contaminating that channel, not a different channel being selected.

---

### 2. **Corrected Main Analysis Script** — `analyze_exp06_run02_on_raw_sass_ssd_plv_CORRECTED.py`

Three parallel, methodologically clean pipelines:

#### **Section 3.4 — Fixed Raw Channel (No Re-selection)**

**Old Logic:**
```python
FOR each intensity:
    best_ch = argmax(PLV over all channels)
    compute PLV for best_ch
```

**New Logic:**
```python
Load fixed channel name from metadata JSON
FOR each intensity:
    ch_idx = index of fixed channel
    on_raw_selected = on_raw_epochs[:, ch_idx, :]
    compute PLV for fixed channel (no ranking)
```

**Change:** No per-intensity re-selection; channel is predetermined from 10% analysis.

---

#### **Section 3.5 — Pure SASS (No Secondary Eigendecomposition)**

**Old Logic:**
```python
Apply SASS to ON vs late-OFF view-band data
    → sass_cleaned_concat (multichannel, artifact-suppressed)

FOR each of top-6 eigenvalues of SASS-cleaned signal-band:
    extract component via spatial filter
    compute ON/OFF broadband power ratio
SELECT component with lowest power ratio
```

**New Logic:**
```python
Apply SASS to ON vs late-OFF view-band data
    → on_sass_epochs (multichannel, artifact-suppressed)

FOR each SASS-cleaned channel (all n_channels):
    compute PLV to GT
    compute peak frequency

SELECT channel with max PLV to GT
```

**Change:** 
- Remove lines 249–287 (the secondary eigendecomposition)
- Rank all SASS-cleaned channels by PLV, same as raw path
- No power-ratio proxy; direct GT phase locking is the metric

**Rationale:** SASS outputs cleaned multichannel data, not synthetic sources. Applying another eigendecomposition conceptually violates the principle that SASS and SSD are separate. Pure SASS just removes artifact; channel ranking is supervised by PLV to GT.

---

#### **Section 3.6 — Pure SSD (Rank by PLV, Not Power Ratio)**

**Old Logic:**
```python
Fit SSD on raw signal-band vs view-band covariances
    → top-6 components sorted descending

FOR each of top-6 components:
    apply spatial filter to ON raw data
    compute ON/OFF broadband power ratio
SELECT component with lowest power ratio
```

**New Logic:**
```python
Fit SSD on raw signal-band vs view-band covariances
    → top-6 components sorted descending

FOR each of top-6 components:
    apply spatial filter to ON raw data
    compute PLV to GT
    compute peak frequency

SELECT component with max PLV to GT
```

**Change:**
- Keep eigendecomposition (lines 310–320)
- Replace ranking criterion from power ratio to PLV (lines 322–346)
- All three paths now use the same selection metric

**Rationale:** Power ratio is a proxy for artifact suppression; PLV directly measures GT recovery. PLV is the end-to-end metric that matters. Consistency across all three paths ensures fair comparison.

---

## Key Differences: Old vs. New

| Aspect | Old | New |
|--------|-----|-----|
| **Raw channel** | Best per intensity (varies) | Fixed at 10% (constant) |
| **Raw selection metric** | PLV | PLV |
| **SASS processing** | SASS + eigendecomp + power ratio | SASS + channel ranking by PLV |
| **SASS selection metric** | Power ratio proxy | PLV |
| **SSD processing** | Eigendecomp + power ratio | Eigendecomp + component ranking by PLV |
| **SSD selection metric** | Power ratio proxy | PLV |
| **Selection consistency** | Asymmetric (PLV vs power) | Symmetric (all PLV) |

---

## Integration Workflow

1. **Run explorer script first:**
   ```bash
   python explore_exp06_best_raw_channel_fixed.py
   ```
   Outputs: metadata JSON, summary table, 5-panel figure

2. **Run corrected main script:**
   ```bash
   python analyze_exp06_run02_on_raw_sass_ssd_plv_CORRECTED.py
   ```
   Inputs: metadata JSON from step 1
   Outputs: PLV summary, phase-grid figures, manifest

---

## Expected Outcomes

### Raw Path
- PLV should remain stable across intensities (same channel)
- Shows baseline contamination of that electrode due to artifact

### SASS Path
- Should recover PLV at low intensities (10–30%)
- May degrade at high intensities (40–50%) if artifact is too strong or has complex spatial structure

### SSD Path
- Should extract spatially-optimized 12.45 Hz component
- May degrade at high intensities if the signal is obscured by artifact

### Comparison
All three paths are now **directly comparable** because they use the same metric (PLV to GT) for selection and evaluation. Differences reflect:
- Raw = no processing
- SASS = artifact removal via covariance matching
- SSD = signal extraction via spectral optimization

---

## Files Created

1. **`explore_exp06_best_raw_channel_fixed.py`** — Finds and locks best raw channel at 10%
2. **`analyze_exp06_run02_on_raw_sass_ssd_plv_CORRECTED.py`** — Corrected main analysis with all three fixes
3. **`PLAN_correct_sass_ssd_separation.md`** — High-level pseudocode (earlier)
4. **`PSEUDOCODE_exp06_run02_fixed_raw_channel.md`** — Detailed pseudocode for channel finder (earlier)
5. **`SUMMARY_pipeline_corrections.md`** — This file

---

## Verification

To verify correctness:

1. Run explorer script → check that metadata JSON contains correct channel and PLV values
2. Run corrected main script → check that:
   - Raw PLV is constant across intensities (since channel is fixed)
   - SASS PLV is computed for the best SASS-cleaned channel (not a synthetic component)
   - SSD PLV is computed for the best component (ranked by direct PLV, not power ratio)
3. Visual inspection:
   - 5-panel raw overlay should show the same channel repeated at each intensity
   - Summary figure should show trends consistent with artifact degradation
   - Peak frequency shifts should be explained by spectral analysis

---

## Notes

- The corrected scripts use `_CORRECTED` suffix to avoid overwriting original analysis
- Original scripts are preserved for reference and comparison
- Both scripts use the same `preprocessing` module utilities (no API changes)
- Metadata JSON ensures reproducibility and transparency
