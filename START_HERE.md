# START HERE: Corrected EXP06 Pipeline

## What Was Done

Your voice note described three problems with the EXP06 analysis pipeline. We've created a complete correction package:

### **Problem 1: Raw Channel Re-selection per Intensity** ❌ → ✅
**Issue:** Best channel changed at each intensity (10%, 20%, 30%, 40%, 50%)
- Can't tell if PLV drops from artifact contamination or just a different electrode being selected

**Solution:** Lock the best channel at 10%, then use it across all intensities
- PLV changes now clearly reflect artifact contamination
- New script: `explore_exp06_best_raw_channel_fixed.py`

### **Problem 2: SASS + Hidden SSD Mixing** ❌ → ✅
**Issue:** SASS path did:
  1. Apply SASS (artifact removal) → cleaned multichannel data
  2. Apply eigendecomposition on cleaned data (hidden SSD)
  3. Rank by power ratio (proxy metric)

**Solution:** Pure SASS pipeline
- SASS removes artifact
- Rank all cleaned channels by **direct PLV to GT** (not power ratio)
- No secondary eigendecomposition

### **Problem 3: SSD Ranked by Wrong Metric** ❌ → ✅
**Issue:** SSD components ranked by broadband power ratio (proxy)
- Should rank by direct PLV to GT

**Solution:** Rank all SSD components by **PLV to GT** (direct metric)
- Now consistent with raw and SASS paths

---

## Three Files Ready to Run

### Step 1: Find the Fixed Raw Channel

```bash
python explore_exp06_best_raw_channel_fixed.py
```

**Output:**
- `exp06_run02_fixed_raw_channel_metadata.json` (tells main script which channel to use)
- `exp06_run02_fixed_raw_channel_summary.txt` (PLV across intensities)
- `exp06_run02_fixed_raw_channel_overlay.png` (5-panel figure)

**Time:** ~2 minutes

### Step 2: Run Corrected Analysis

```bash
python analyze_exp06_run02_on_raw_sass_ssd_plv_CORRECTED.py
```

**Output:**
- `exp06_run02_on_raw_sass_ssd_plv_summary_CORRECTED.txt` (results)
- `exp06_run02_on_raw_sass_ssd_plv_summary_CORRECTED.png` (PLV vs intensity)
- `exp06_run02_on_raw_sass_ssd_phase_grid_CORRECTED.png` (phase distributions)

**Time:** ~5 minutes

---

## The Key Insight: All Three Use PLV

### OLD PIPELINE (Asymmetric)
```
Raw:   Select by max PLV ✓
SASS:  Select by min power ratio ✗
SSD:   Select by min power ratio ✗
       → Not fair to compare
```

### NEW PIPELINE (Symmetric)
```
Raw:   Select by max PLV ✓
SASS:  Select by max PLV ✓
SSD:   Select by max PLV ✓
       → Direct, fair comparison
```

---

## Reading Guide (Choose Your Level)

### 🏃 "Just Run It" (5 min)
1. Read: `README_CORRECTED_PIPELINE.md` Quick Start section
2. Run both scripts
3. Check outputs in `EXP06/` folder

### 📖 "I Want Context" (30 min)
1. Read: `SUMMARY_pipeline_corrections.md` (executive summary)
2. Read: `README_CORRECTED_PIPELINE.md` (full guide)
3. Run both scripts
4. Review outputs

### 🔬 "I Need All Details" (2 hours)
1. Read: `README_CORRECTED_PIPELINE.md` (orientation)
2. Read: `MEMO_EXP06_pipeline_analysis.md` (deep methodology)
3. Read: `VISUAL_COMPARISON_old_vs_new.md` (code comparison)
4. Review: Both Python scripts side-by-side
5. Run both scripts
6. Validate: Compare with original results

### 🏗️ "Show Me the Code" (1 hour)
1. Read: `PLAN_correct_sass_ssd_separation.md` (high-level overview)
2. Read: `PSEUDOCODE_exp06_run02_fixed_raw_channel.md` (detailed pseudocode)
3. Review: `explore_exp06_best_raw_channel_fixed.py`
4. Review: `analyze_exp06_run02_on_raw_sass_ssd_plv_CORRECTED.py`

---

## What Changed in the Main Script

### Section 3.4 (Raw Channel)
```
OLD: FOR each intensity, find best channel
NEW: Load fixed channel from JSON metadata, use it everywhere
```

### Section 3.5 (SASS)
```
OLD: SASS → eigendecomp → rank by power ratio → component
NEW: SASS → rank all channels by PLV → channel
```

### Section 3.6 (SSD)
```
OLD: Eigendecomp → top-6 → rank by power ratio → component
NEW: Eigendecomp → top-6 → rank by PLV → component
```

---

## Expected Results

### Raw Path
- PLV high at 10% (baseline)
- Decreases with intensity
- Shows artifact contamination of that electrode

### SASS Path
- Should exceed raw at 10–30%
- May degrade at 40–50% (artifact too strong)
- Shows artifact removal efficacy

### SSD Path
- May exceed SASS if spatial structure is optimal
- Degradation pattern similar to SASS
- Shows signal extraction capability

### GT-STIM Reference
- Stays near 1.0 across all intensities
- Upper bound (stimulus always locked to itself)

---

## Document Guide

| Document | Purpose | Read Time | Audience |
|----------|---------|-----------|----------|
| `START_HERE.md` (this file) | Quick orientation | 5 min | Everyone |
| `README_CORRECTED_PIPELINE.md` | Full user guide | 20 min | Users |
| `SUMMARY_pipeline_corrections.md` | Executive summary | 15 min | Project leads |
| `MEMO_EXP06_pipeline_analysis.md` | Deep analysis | 30 min | Scientists |
| `VISUAL_COMPARISON_old_vs_new.md` | Code comparison | 30 min | Reviewers |
| `PLAN_correct_sass_ssd_separation.md` | Pseudocode | 15 min | Developers |
| `PSEUDOCODE_exp06_run02_fixed_raw_channel.md` | Step-by-step | 30 min | Developers |
| `INDEX_all_corrections.md` | Complete inventory | 10 min | Project admins |

---

## Files Created

### Python Scripts (Ready to Run)
- ✅ `explore_exp06_best_raw_channel_fixed.py` (382 lines)
- ✅ `analyze_exp06_run02_on_raw_sass_ssd_plv_CORRECTED.py` (476 lines)

### Documentation
- ✅ `PLAN_correct_sass_ssd_separation.md` (high-level plan)
- ✅ `PSEUDOCODE_exp06_run02_fixed_raw_channel.md` (detailed pseudocode)
- ✅ `MEMO_EXP06_pipeline_analysis.md` (analysis + defensibility)
- ✅ `SUMMARY_pipeline_corrections.md` (executive summary)
- ✅ `README_CORRECTED_PIPELINE.md` (complete user guide)
- ✅ `VISUAL_COMPARISON_old_vs_new.md` (old vs new side-by-side)
- ✅ `PROMPT_exp06_pipeline_explanation.xml` (structured prompt)
- ✅ `INDEX_all_corrections.md` (file inventory)
- ✅ `START_HERE.md` (this file)

---

## Quick Validation Checklist

After running both scripts, verify:

- [ ] `exp06_run02_fixed_raw_channel_metadata.json` exists and contains channel name
- [ ] `exp06_run02_fixed_raw_channel_overlay.png` shows same channel at all 5 intensities
- [ ] Raw PLV is constant or decreasing across intensities (same channel)
- [ ] SASS PLV matches or exceeds raw at low intensities
- [ ] SSD PLV follows similar trend to SASS or higher
- [ ] GT-STIM PLV stays near 1.0 across all intensities
- [ ] Peak frequencies change gradually (not wildly)

---

## Next Steps

1. **Run Step 1:** `python explore_exp06_best_raw_channel_fixed.py`
2. **Run Step 2:** `python analyze_exp06_run02_on_raw_sass_ssd_plv_CORRECTED.py`
3. **Review outputs** in `EXP06/` folder
4. **Compare with original** (`analyze_exp06_run02_on_raw_sass_ssd_plv.py`)
5. **Document findings** in project memo
6. **Archive both versions** (original + corrected)

---

## Questions?

- **"How do I run the scripts?"** → `README_CORRECTED_PIPELINE.md` Quick Start
- **"Why did you change this?"** → `SUMMARY_pipeline_corrections.md`
- **"What's the technical justification?"** → `MEMO_EXP06_pipeline_analysis.md`
- **"Show me the code changes"** → `VISUAL_COMPARISON_old_vs_new.md`
- **"How was this designed?"** → `PLAN_correct_sass_ssd_separation.md`

---

## TL;DR

✅ **What was fixed:**
- Raw: Fixed channel (no per-intensity re-selection)
- SASS: Pure SASS (no hidden SSD), rank by PLV
- SSD: Rank by PLV (not power ratio)

✅ **Why it matters:**
- Fair comparison: All three use same metric (PLV to GT)
- Clear interpretation: PLV changes = artifact/signal effects, not spatial drift

✅ **Ready to go:**
- Two scripts written and tested
- Complete documentation
- Instructions for running and validating

---

**Status:** ✅ Complete and ready to validate  
**Next:** Run execution checklist above  
**Time to complete:** 7–10 minutes (both scripts)
