---
type: simulation
status: active
updated: 2026-04-29
tags:
  - simnibs
  - dual-coil
  - efield
  - focality
  - depth
---

# SIM: Dual-Coil Cz E-Field (D60T10L8)

## Question

What is the combined E-field magnitude at 30 mm depth below Cz when two coils are placed symmetrically (±40 mm on local X), and how does it fall off with distance?

## Current Conclusion

**ROI weighted mean magET at 30 mm depth: 19.486 V/m** (5 mm GM sphere, volume-weighted). The field peaks at the cortical surface directly under Cz and decays steeply; the distance-vs-field profile shows a clear drop beyond 3 cm from the projected Cz scalp point.

## Setup

- **Coil configuration:** two coils centered on Cz, ±40 mm on local X axis, `coil_distance_mm = 0.001`
- **Head model:** `m2m_ernie`, EEG cap `EEG10-10_UI_Jurak_2007.csv`
- **Field:** `magET` = norm(E1 + E2), computed by `two_coils.py` and saved in `combined.msh`
- **Depth target:** 30 mm inward from SimNIBS-projected Cz scalp point along coil Z axis
- **ROI:** 5 mm GM sphere around snapped GM centroid nearest to the 30 mm target
- **Simulation folder:** `simulation/sim_results/D60T10L8_dual_cz/combined/`

## Evidence

**Extraction:**
- [`simulation/extract_dual_coil_depth_efield.py`](../../simulation/extract_dual_coil_depth_efield.py): reads `combined.msh` geometry + EEG cap, snaps 30 mm target to nearest GM centroid, extracts ROI field values and distance profile. Run with `simnibs_python`.
- [`coil_midpoint_30mm_gm5mm/summary.csv`](../../simulation/sim_results/D60T10L8_dual_cz/combined/coil_midpoint_30mm_gm5mm/summary.csv): single-row table with all key scalar outputs (ROI mean/median/std/min/max, snap distance, whole-GM max, XYZ of surface/target/snapped points).
- [`coil_midpoint_30mm_gm5mm/roi_elements.csv`](../../simulation/sim_results/D60T10L8_dual_cz/combined/coil_midpoint_30mm_gm5mm/roi_elements.csv): element-level table for the 5 mm ROI (element number, centroid XYZ, volume, distance to snap, magET).
- [`coil_midpoint_30mm_gm5mm/gm_over_5v.csv`](../../simulation/sim_results/D60T10L8_dual_cz/combined/coil_midpoint_30mm_gm5mm/gm_over_5v.csv): whole-GM elements with magET ≥ 5 V/m (used for brain maps).
- [`coil_midpoint_30mm_gm5mm/gm_distance_0_6cm.csv`](../../simulation/sim_results/D60T10L8_dual_cz/combined/coil_midpoint_30mm_gm5mm/gm_distance_0_6cm.csv): GM elements within 6 cm of projected Cz scalp point, with distance column.

**Figures:**
- [`simulation/plot_dual_coil_efield_style_figures.py`](../../simulation/plot_dual_coil_efield_style_figures.py): generates all three figures below. Run with `simnibs_python`.
- [`dual_cz_magET_whole_gm_over5v.png`](../../simulation/sim_results/D60T10L8_dual_cz/combined/coil_midpoint_30mm_gm5mm/dual_cz_magET_whole_gm_over5v.png): 3D whole-GM map, all elements ≥ 5 V/m, hot colormap (5–50 V/m).
- [`dual_cz_magET_left_gm_side.png`](../../simulation/sim_results/D60T10L8_dual_cz/combined/coil_midpoint_30mm_gm5mm/dual_cz_magET_left_gm_side.png): left hemisphere lateral view, outermost cortical surface elements, looking from the right (azim=-90).
- [`dual_cz_focality_top3000.png`](../../simulation/sim_results/D60T10L8_dual_cz/combined/coil_midpoint_30mm_gm5mm/dual_cz_focality_top3000.png): E-field vs distance from Cz (0–6 cm), scatter + 0.25 cm bin mean, 3 cm target marked.

## Key Numbers

| Metric | Value |
|---|---|
| ROI weighted mean magET | 19.486 V/m |
| ROI median magET | 18.930 V/m |
| ROI element count | see summary.csv |
| Whole-GM peak magET | see summary.csv |
| Target-to-snap distance | see summary.csv |
