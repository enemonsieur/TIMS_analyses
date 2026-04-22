# README: Corrected EXP06 Pipeline (Fixed Raw + Pure SASS + Pure SSD)

## Quick Start

### Step 1: Find Fixed Raw Channel

```bash
cd c:/Users/njeuk/OneDrive/Documents/Charite\ Berlin/TIMS
python explore_exp06_best_raw_channel_fixed.py
```

**Outputs:**
- `EXP06/exp06_run02_fixed_raw_channel_metadata.json` — Machine-readable metadata
- `EXP06/exp06_run02_fixed_raw_channel_summary.txt` — Human-readable table
- `EXP06/exp06_run02_fixed_raw_channel_overlay.png` — 5-panel figure

### Step 2: Run Corrected Analysis

```bash
python analyze_exp06_run02_on_raw_sass_ssd_plv_CORRECTED.py
```

**Outputs:**
- `EXP06/exp06_run02_on_raw_sass_ssd_plv_summary_CORRECTED.txt` — Results table
- `EXP06/exp06_run02_on_raw_sass_ssd_plv_summary_CORRECTED.png` — PLV vs intensity figure
- `EXP06/exp06_run02_on_raw_sass_ssd_phase_grid_CORRECTED.png` — Phase distributions

---

## What Changed?

### Problem 1: Raw Channel Selection (FIXED)
**Before:** Best channel selected independently at each intensity → spatial confounding
**After:** Best channel selected at 10%, then fixed across all intensities → clean dose effect isolation

### Problem 2: SASS + SSD Mixing (FIXED)
**Before:** SASS output → secondary eigendecomposition → rank by power ratio (hybrid method)
**After:** SASS output → rank all cleaned channels by PLV (pure SASS pipeline)

### Problem 3: SSD Ranking (FIXED)
**Before:** Top 6 SSD components ranked by broadband power ratio (proxy metric)
**After:** Top 6 SSD components ranked by PLV to GT (direct metric)

---

## Three Pipelines, One Metric

All three paths now use **PLV to GT** as the final selection criterion:

```
Raw Path:
  on_raw_epochs → fixed channel (predetermined at 10%)
              → bandpass to signal band
              → compute PLV to GT
              → output metrics

SASS Path:
  on_raw_epochs → view-band filter
              → SASS artifact removal (ON vs late-OFF cov)
              → multichannel SASS-cleaned data
              → rank all channels by PLV to GT
              → select best channel
              → compute metrics

SSD Path:
  on_raw_epochs → signal-band/view-band filter
              → generalized eigendecomp (signal vs view)
              → top-6 components
              → rank by PLV to GT (not power ratio)
              → select best component
              → compute metrics
```

---

## Key Design Principles

1. **Fixed Raw Channel:** Uses the same electrode across all intensities so PLV changes reflect artifact contamination, not spatial variation.

2. **Pure SASS:** No secondary decomposition. SASS removes artifact; PLV to GT ranks the cleaned channels.

3. **Pure SSD:** Direct PLV ranking replaces power-ratio proxy. SSD extracts components; PLV ranks them.

4. **Consistency:** All three use the same metric (PLV) for final selection, making them directly comparable.

---

## Expected Results

### Intensity Dependence

| Intensity | Raw (fixed) | SASS | SSD | GT-STIM |
|-----------|-----------|------|-----|---------|
| 10% | High (baseline) | High | High | High |
| 20% | Med-High | Med-High | Med-High | High |
| 30% | Medium | Medium | Medium | High |
| 40% | Low-Med | Low-Med | Low-Med | High |
| 50% | Low | Low | Low | High |

- **Raw:** Reflects direct artifact contamination of the fixed electrode
- **SASS:** Shows artifact removal efficacy; should exceed raw at all intensities
- **SSD:** Shows signal extraction efficacy; should match or exceed SASS (if artifact is spatially homogeneous)
- **GT-STIM:** Fixed upper bound (the intended reference signal is always phase-locked to itself)

### Peak Frequency Shifts

Expect ~0.3–0.5 Hz shifts due to:
- SASS filtering (removes broadband, leaving narrowband signal)
- SSD component extraction (optimizes for signal-band variance)
- Artifact harmonics at high intensities (second harmonic around 24.9 Hz; subharmonics around 6.2 Hz)

---

## File Organization

```
TIMS/
├── explore_exp06_best_raw_channel_fixed.py          ← Run first
├── analyze_exp06_run02_on_raw_sass_ssd_plv_CORRECTED.py  ← Run second
├── PLAN_correct_sass_ssd_separation.md              (reference)
├── PSEUDOCODE_exp06_run02_fixed_raw_channel.md      (reference)
├── SUMMARY_pipeline_corrections.md                  (reference)
├── README_CORRECTED_PIPELINE.md                     (this file)
│
└── EXP06/ (outputs)
    ├── exp06_run02_fixed_raw_channel_metadata.json
    ├── exp06_run02_fixed_raw_channel_summary.txt
    ├── exp06_run02_fixed_raw_channel_overlay.png
    ├── exp06_run02_on_raw_sass_ssd_plv_summary_CORRECTED.txt
    ├── exp06_run02_on_raw_sass_ssd_plv_summary_CORRECTED.png
    └── exp06_run02_on_raw_sass_ssd_phase_grid_CORRECTED.png
```

---

## Comparison with Original Script

| Aspect | Original | Corrected |
|--------|----------|-----------|
| **Script name** | `analyze_exp06_run02_on_raw_sass_ssd_plv.py` | `analyze_exp06_run02_on_raw_sass_ssd_plv_CORRECTED.py` |
| **Dependencies** | Original explorer script (exploratory) | `explore_exp06_best_raw_channel_fixed.py` (required) |
| **Raw selection** | Per-intensity best channel | Fixed at 10% (via JSON metadata) |
| **SASS method** | SASS + secondary eigendecomp | Pure SASS + channel ranking |
| **SSD ranking** | Power ratio | PLV |
| **Output suffix** | None | `_CORRECTED` |

Original script remains in codebase for reference and legacy comparisons.

---

## Troubleshooting

### Error: "Fixed channel metadata not found"
**Cause:** Did not run `explore_exp06_best_raw_channel_fixed.py` first
**Solution:** Run the explorer script to generate metadata JSON

### Unexpected PLV values (very high or very low)
**Cause:** Check that GT trace is clean and properly extracted
**Solution:** Inspect `gt_trace` in the script; verify 12.45 Hz peak in baseline PSD

### SASS PLV worse than raw
**Cause:** SASS null-count may be over-suppressing signal along with artifact
**Solution:** Inspect SASS eigenvalue spectrum; check how many components are nulled per intensity

### SSD components drifting across intensities
**Cause:** At high intensity (40–50%), artifact structure dominates; components reorient
**Solution:** Check peak frequency and phase distribution to confirm artifact vs. signal

---

## References

- **MEMO_EXP06_pipeline_analysis.md** — Detailed analysis of pipeline decisions
- **PLAN_correct_sass_ssd_separation.md** — High-level pseudocode for corrections
- **SUMMARY_pipeline_corrections.md** — Detailed summary of all three corrections

---

## Contact / Questions

If results differ from expectations, verify:
1. ON/OFF window timing matches config (0.3–1.5 s for ON, 1.5–3.2 s for late-OFF)
2. SASS null-count is automatic (MSE criterion) — inspect per-block values
3. Fixed raw channel is correctly identified (highest PLV at 10%)
4. PLV computation uses bandpass (11.95–12.95 Hz) not raw signal
5. Peak frequency is computed from broadband PSD (4–20 Hz), not narrowband

---

## Timeline

- **Explorer script:** ~2 min (extracts 10% data, computes PLV, visualizes)
- **Main analysis script:** ~5 min (processes all 5 intensities, generates figures)
- **Total:** ~7 min for full corrected pipeline

---

**Last Updated:** 2026-04-15
**Status:** Ready for validation against original results
