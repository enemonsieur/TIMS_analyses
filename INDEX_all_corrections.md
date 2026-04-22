# Index: Complete Correction Package for EXP06 Analysis

## Overview

This package contains all files, scripts, and documentation needed to correct the EXP06 phantom study analysis pipeline. Three methodological issues were identified and resolved:

1. **Raw channel selection:** Fixed at 10% instead of re-selecting per intensity
2. **SASS processing:** Pure SASS only, no hidden secondary eigendecomposition
3. **SSD ranking:** Direct PLV ranking instead of power-ratio proxy

All three paths now use **PLV to GT** as the final selection metric, enabling fair comparison.

---

## New Scripts (Ready to Run)

### 1. `explore_exp06_best_raw_channel_fixed.py`
**Purpose:** Find the best raw EEG channel at 10% intensity and compute its PLV across all intensities.

**Inputs:**
- `exp06-STIM-iTBS_run02.vhdr` (stimulation recording)

**Outputs:**
- `exp06_run02_fixed_raw_channel_metadata.json` — Machine-readable metadata
- `exp06_run02_fixed_raw_channel_summary.txt` — Human-readable summary table
- `exp06_run02_fixed_raw_channel_overlay.png` — 5-panel figure

**Run:** `python explore_exp06_best_raw_channel_fixed.py`  
**Duration:** ~2 min  
**Status:** ✅ Ready to use

---

### 2. `analyze_exp06_run02_on_raw_sass_ssd_plv_CORRECTED.py`
**Purpose:** Compare fixed-raw, pure-SASS, and pure-SSD paths using PLV ranking.

**Inputs:**
- `exp06-STIM-iTBS_run02.vhdr` (stimulation recording)
- `exp06_run02_fixed_raw_channel_metadata.json` (from script 1)

**Outputs:**
- `exp06_run02_on_raw_sass_ssd_plv_summary_CORRECTED.txt` — Results table
- `exp06_run02_on_raw_sass_ssd_plv_summary_CORRECTED.png` — PLV vs intensity figure
- `exp06_run02_on_raw_sass_ssd_phase_grid_CORRECTED.png` — Phase distributions

**Run:** `python analyze_exp06_run02_on_raw_sass_ssd_plv_CORRECTED.py`  
**Duration:** ~5 min  
**Status:** ✅ Ready to use

---

## Planning & Pseudocode Documents

### 3. `PLAN_correct_sass_ssd_separation.md`
**Content:** High-level overview of the three corrections with pseudocode.

**Sections:**
- Current state (wrong)
- Desired state (correct)
- Pseudocode per section (3.4, 3.5, 3.6)
- Summary of changes

**Audience:** Project leads, reviewers  
**Length:** ~2 pages  
**Status:** ✅ Complete

---

### 4. `PSEUDOCODE_exp06_run02_fixed_raw_channel.md`
**Content:** Detailed step-by-step pseudocode for finding and fixing the raw channel.

**Sections:**
- Input data specification
- 9 steps (load → detect → extract → compute → select → visualize → export)
- Per-step logic with examples
- Integration with main script
- Output files

**Audience:** Developers implementing the script  
**Length:** ~4 pages  
**Status:** ✅ Complete

---

## Analysis & Reference Documents

### 5. `MEMO_EXP06_pipeline_analysis.md`
**Content:** Detailed analysis of what each signal path does, why, and what concerns exist.

**Sections:**
- Overview of three paths (A=Raw, B=SASS, C=SSD, D=GT-STIM)
- Per-path explanation with concrete units
- Key decisions and their rationale
- Asymmetries and concerns
- Defensibility assessment
- Suggested verifications

**Audience:** Project leads, scientists evaluating the methodology  
**Length:** ~6 pages  
**Status:** ✅ Complete

---

### 6. `SUMMARY_pipeline_corrections.md`
**Content:** Executive summary of problems identified and solutions implemented.

**Sections:**
- Problem statement (3 issues)
- Solutions for each issue
- Key differences (old vs. new, in table)
- Integration workflow
- Expected outcomes
- Verification steps
- File inventory

**Audience:** Team leads, grant reviewers  
**Length:** ~5 pages  
**Status:** ✅ Complete

---

### 7. `README_CORRECTED_PIPELINE.md`
**Content:** Quick-start guide and reference manual for the corrected pipeline.

**Sections:**
- Quick start (2 commands)
- What changed (3 problems/solutions)
- Three pipelines, one metric (pseudocode)
- Key design principles
- Expected results
- File organization
- Troubleshooting
- Timeline

**Audience:** Users running the corrected pipeline  
**Length:** ~4 pages  
**Status:** ✅ Complete

---

### 8. `VISUAL_COMPARISON_old_vs_new.md`
**Content:** Side-by-side ASCII diagrams comparing old and new pipelines.

**Sections:**
- The three paths (old architecture)
- The three paths (new architecture)
- Section 3.5 head-to-head (code comparison)
- Section 3.6 head-to-head (code comparison)
- Summary table (old vs. new metrics)
- Expected PLV trends

**Audience:** Visual learners, code reviewers  
**Length:** ~7 pages  
**Status:** ✅ Complete

---

## Original/Reference Documents (Created Earlier)

### 9. `PROMPT_exp06_pipeline_explanation.xml`
**Content:** Structured XML specification of the pipeline (generated from voice note).

**Audience:** Prompt engineering, clarity documentation  
**Status:** ✅ Complete

---

### 10. `AGENTS.md` (Updated)
**Content:** Notes on agent-assisted exploration and code understanding.

**Status:** Pre-existing, not modified

---

## File Organization

```
TIMS/
├── SCRIPTS (NEW)
│   ├── explore_exp06_best_raw_channel_fixed.py           ✅
│   └── analyze_exp06_run02_on_raw_sass_ssd_plv_CORRECTED.py ✅
│
├── PLANNING & PSEUDOCODE
│   ├── PLAN_correct_sass_ssd_separation.md               ✅
│   └── PSEUDOCODE_exp06_run02_fixed_raw_channel.md       ✅
│
├── ANALYSIS & REFERENCE
│   ├── MEMO_EXP06_pipeline_analysis.md                   ✅
│   ├── SUMMARY_pipeline_corrections.md                   ✅
│   ├── README_CORRECTED_PIPELINE.md                      ✅
│   ├── VISUAL_COMPARISON_old_vs_new.md                   ✅
│   └── INDEX_all_corrections.md                          (this file)
│
├── RESOURCES
│   └── PROMPT_exp06_pipeline_explanation.xml             ✅
│
└── EXP06/ (OUTPUT DIRECTORY)
    └── [outputs from corrected scripts]
```

---

## Reading Guide

### For Project Leads (Time: 30 min)
1. Read `SUMMARY_pipeline_corrections.md` (5 min) — understand the 3 problems and solutions
2. Read `README_CORRECTED_PIPELINE.md` section "Three Pipelines, One Metric" (5 min) — visualize the logic
3. Read `VISUAL_COMPARISON_old_vs_new.md` Summary section (10 min) — see code changes
4. Skim `MEMO_EXP06_pipeline_analysis.md` Defensibility section (10 min) — robustness check

### For Developers (Time: 1 hour)
1. Read `PLAN_correct_sass_ssd_separation.md` (10 min) — high-level overview
2. Read `PSEUDOCODE_exp06_run02_fixed_raw_channel.md` (20 min) — understand script logic
3. Review `explore_exp06_best_raw_channel_fixed.py` (15 min) — inspect code
4. Review `analyze_exp06_run02_on_raw_sass_ssd_plv_CORRECTED.py` (15 min) — inspect changes

### For Reviewers (Time: 2 hours)
1. Read `README_CORRECTED_PIPELINE.md` (20 min) — quick orientation
2. Read `SUMMARY_pipeline_corrections.md` (20 min) — understand changes
3. Read `MEMO_EXP06_pipeline_analysis.md` (40 min) — detailed methodology
4. Review `VISUAL_COMPARISON_old_vs_new.md` (20 min) — compare code
5. Inspect both scripts side-by-side (20 min) — verify implementation

---

## Execution Checklist

- [ ] Read `README_CORRECTED_PIPELINE.md` Quick Start section
- [ ] Run `python explore_exp06_best_raw_channel_fixed.py`
- [ ] Verify outputs in `EXP06/` directory:
  - [ ] `exp06_run02_fixed_raw_channel_metadata.json` exists
  - [ ] `exp06_run02_fixed_raw_channel_summary.txt` is readable
  - [ ] `exp06_run02_fixed_raw_channel_overlay.png` looks reasonable
- [ ] Run `python analyze_exp06_run02_on_raw_sass_ssd_plv_CORRECTED.py`
- [ ] Verify outputs in `EXP06/` directory:
  - [ ] `exp06_run02_on_raw_sass_ssd_plv_summary_CORRECTED.txt` exists
  - [ ] `exp06_run02_on_raw_sass_ssd_plv_summary_CORRECTED.png` looks reasonable
  - [ ] `exp06_run02_on_raw_sass_ssd_phase_grid_CORRECTED.png` exists
- [ ] Compare results with original (same channel, consistent trends)
- [ ] Document findings in project memo

---

## Key Metrics & Expectations

### Raw Path
- **Selection:** Fixed at 10% (predetermined)
- **Expected PLV:** High at 10% (baseline), decreasing with intensity
- **Interpretation:** Shows direct artifact contamination of that electrode

### SASS Path
- **Selection:** Best SASS-cleaned channel by PLV (per intensity)
- **Expected PLV:** Exceeds raw at low/medium intensity, may degrade at high
- **Interpretation:** Shows artifact removal efficacy

### SSD Path
- **Selection:** Best SSD component by PLV (per intensity)
- **Expected PLV:** May exceed SASS if spatial structure is optimal
- **Interpretation:** Shows signal extraction capability

### GT-STIM Reference
- **Expected PLV:** ~1.0 across all intensities (upper bound)
- **Interpretation:** The delivered stimulus is always phase-locked to itself

---

## Validation

To validate the corrected pipeline:

1. **Check fixed channel:** Does `metadata.json` contain correct channel name from 10%?
2. **Check raw path:** Is PLV constant-or-decreasing across intensities (same channel)?
3. **Check SASS:** Does SASS PLV exceed raw at low intensity?
4. **Check SSD:** Does SSD component differ from raw channel at high intensity?
5. **Check figures:** Do overlays show reasonable phase alignment?

---

## Troubleshooting

| Issue | Cause | Solution |
|-------|-------|----------|
| "Fixed channel metadata not found" | Script 1 not run | Run `explore_exp06_best_raw_channel_fixed.py` first |
| Unexpected PLV values | GT trace issue | Verify GT peak = 12.451 Hz in baseline |
| SASS worse than raw | Over-nulling | Check SASS null count per intensity |
| SSD drifting across blocks | High artifact at 40–50% | Inspect eigenvalue spectrum |
| Figures missing | Plot module not run | Uncomment `plot_helpers` calls in script 2 |

---

## Next Steps

After validation:

1. **Compare with original:** Run both scripts side-by-side, compare PLV trends
2. **Document findings:** Update project memo with corrected results
3. **Validate physics:** Do trends match expected artifact behavior?
4. **Archive:** Keep both versions in git (original + corrected) for reproducibility
5. **Publish:** Include corrected analysis in manuscript

---

## Contact & Questions

Refer to specific documents for detailed information:
- **Methodology questions** → `MEMO_EXP06_pipeline_analysis.md`
- **Implementation questions** → `README_CORRECTED_PIPELINE.md` Troubleshooting
- **Code review questions** → `VISUAL_COMPARISON_old_vs_new.md`
- **Design questions** → `PLAN_correct_sass_ssd_separation.md`

---

## Summary Statistics

| Metric | Count |
|--------|-------|
| New scripts | 2 |
| Planning/pseudocode documents | 2 |
| Analysis/reference documents | 6 |
| Total documents | 10 |
| Total pages | ~40 |
| Code changes | 3 sections (3.4, 3.5, 3.6) |
| Lines added/modified | ~300 (main script) |
| Backward compatibility | Preserved (original scripts unchanged) |

---

**Version:** 1.0  
**Date:** 2026-04-15  
**Status:** ✅ All files complete and ready for validation  
**Next:** Run execution checklist and validate results against original
