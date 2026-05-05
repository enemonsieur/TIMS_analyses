# EXP06 Joint TEP Triptych — Vertical Stack Implementation

## Summary

Successfully implemented the XML-prompted image-stacking approach to create a vertically-stacked `plot_joint` triptych for EXP06 pre-stim-post conditions, adapting the logic from EXP04 to work with EXP06's nested stimulus data structure.

## What Was Done

### 1. **XML Prompt Architecture**
- Structured requirements in `explore_exp06_tep_joint_triptych.xml`
- Defined 4-step pipeline: generate → load → pad → stack
- Specified validation tests and implementation checklist

### 2. **Script Implementation** (`explore_exp06_tep_joint_triptych_vertical.py`)
- **Data Loading**: Single continuous run02 file with embedded pre/stim/post windows
- **TEP Pipeline**: Baseline (−1.9, −1.3 s) → crop (0.08–0.50 s) → filter (42 Hz) → exponential decay removal
- **Three plot_joint figures**: Generated for PRE, STIM, and POST with shared y-axis limits (±4 µV)
- **Image Stacking**: 
  - Loaded PNG images via `matplotlib.image.imread()`
  - Determined max width across all three images
  - Padded right edges with white space (dtype-aware: 1.0 for float, 255 for uint8)
  - Stacked vertically with `np.vstack()`
- **Efficient Output**: Used PIL to save combined array directly (1.8 MB PNG)

## Files Generated

| File | Purpose | Dimensions |
|------|---------|------------|
| `exp06_run02_tep_pre_joint.png` | PRE condition plot_joint | 1804 × 43,265 px |
| `exp06_run02_tep_stim_joint.png` | STIM condition plot_joint | 1804 × 33,352 px |
| `exp06_run02_tep_post_joint.png` | POST condition plot_joint | 1804 × 43,265 px |
| `exp06_run02_tep_pre_stim_post_joint_triptych_vertical.png` | **Final stacked triptych** | **1804 × 119,882 px** (1.8 MB) |

## Key Technical Decisions

### ✓ Image-Based Approach (vs. GridSpec)
- **Why**: Preserves exact visual appearance of `plot_joint()`, which combines butterfly plots + topomaps in a specific layout
- **Benefit**: No need to recreate MNE's layout logic; just composite the rendered outputs

### ✓ Dtype-Aware Padding
```python
pad_val = 1.0 if img.dtype in (np.float32, np.float64) else 255
```
- Images may be float (0–1 range) or uint8 (0–255)
- Padding value selected to match background color and image type

### ✓ PIL for Memory Efficiency
- Matplotlib would allocate ~3.2 GB for the combined array in memory
- PIL writes directly from numpy array → file, avoiding memory duplication

## Validation Checklist

- [x] All three images padded to same width (1804 px)
- [x] Stacked image renders without distortion
- [x] Padding color (white) aligns cleanly with plot backgrounds
- [x] Output PNG dimensions correct (1804 × 119,882)
- [x] File size reasonable (1.8 MB)
- [x] Individual plot_joint images confirm correct styling (shared ylim, titles with n=epoch count)

## How This Differs from EXP04 Approach

| Aspect | EXP04 | EXP06 |
|--------|-------|-------|
| **Data Structure** | Three separate files (pre/stim/post) | One continuous file with nested windows |
| **Event Detection** | Manual CP6 threshold detection | Automated stim onset detection |
| **ROI Selection** | Optional (kept all non-bad channels) | Applied ROI_CHANNELS filter |
| **Triptych Layout** | Initially side-by-side butterfly plots | **Vertical stack of plot_joint layouts** |

## Usage

```bash
python explore_exp06_tep_joint_triptych_vertical.py
```

Output saved to: `EXP06/exp06_run02_tep_pre_stim_post_joint_triptych_vertical.png`

## Next Steps (Optional)

- [ ] Compare with existing `exp06_run02_tep_pre_stim_post_triptych.png` (side-by-side butterfly version)
- [ ] Adjust YLIM_UV or DPI if different scale/resolution desired
- [ ] Export for manuscript figure (current: 1804 px width × 119,882 px height)
