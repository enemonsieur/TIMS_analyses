"""Plot dual-coil Cz whole-GM E-field map and distance profile."""

from pathlib import Path
import csv

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


# ============================================================
# CONFIG
# ============================================================

base_directory = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS")
output_directory = (
    base_directory
    / r"simulation\sim_results\D60T10L8_dual_cz\combined\coil_midpoint_30mm_gm5mm"
)
summary_path = output_directory / "summary.csv"
roi_path = output_directory / "roi_elements.csv"
visible_gm_path = output_directory / "gm_over_5v.csv"
distance_profile_path = output_directory / "gm_distance_0_6cm.csv"

field_name = "magET"
color_limit_v_per_m = 50.0  # keeps scale comparable to the saved whole-GM max
distance_bin_width_cm = 0.25  # smooth readable mean line without hiding the scatter


# ============================================================
# FLOW
# ============================================================
#
# summary.csv + whole-GM >=5 V/m + 0-6 cm distance table
#   -> 3D WHOLE-GM MAP
#      all GM centroids are considered; only values <5 V/m are removed
#      color = absolute magET in V/m
#   -> DISTANCE PROFILE
#      x = Euclidean distance from projected Cz scalp point, in cm
#      y = absolute magET in V/m
#      black line = mean field in 0.25 cm distance bins
#   -> distance_efield_summary.txt


# ============================================================
# 1) LOAD EXTRACTED VALUES
# ============================================================

output_directory.mkdir(parents=True, exist_ok=True)
with summary_path.open(newline="") as handle:
    summary = next(csv.DictReader(handle))

# CSV tables -> coordinates and magET values used directly in both plots.
roi_table = np.genfromtxt(roi_path, delimiter=",", names=True)
visible_table = np.genfromtxt(visible_gm_path, delimiter=",", names=True)
distance_table = np.genfromtxt(distance_profile_path, delimiter=",", names=True)
visible_centers = np.column_stack((
    visible_table["centroid_x_mm"],
    visible_table["centroid_y_mm"],
    visible_table["centroid_z_mm"],
))
roi_values = roi_table["magET_v_per_m"].astype(float)
distance_cm = distance_table["distance_from_cz_cm"].astype(float)
distance_values = distance_table["magET_v_per_m"].astype(float)


# ============================================================
# 2) SPATIAL FIELD PLOT
# ============================================================

# Whole brain view after removing low-field GM elements.
# This is not an ACC/ROI crop: every GM element >=5 V/m is shown.
distribution_plot = output_directory / "dual_cz_magET_whole_gm_over5v.png"
fig = plt.figure(figsize=(12, 7))
ax = fig.add_subplot(111, projection="3d")
context = ax.scatter(
    visible_centers[:, 0], visible_centers[:, 1], visible_centers[:, 2],
    c=visible_table["magET_v_per_m"], s=8, cmap="hot", vmin=5, vmax=color_limit_v_per_m, alpha=0.6,
)
all_centers = visible_centers
z_min = float(all_centers[:, 2].min() - 4)
z_max = float(all_centers[:, 2].max() + 4)
ax.set(
    title="Whole gray matter above 5 V/m",
    xlabel="X (mm)",
    ylabel="Y (mm)",
    zlabel="Z height (mm)",
)
ax.view_init(elev=24, azim=-58)
ax.set_box_aspect((1.35, 1.1, 0.85))
ax.set_xlim(float(all_centers[:, 0].min() - 4), float(all_centers[:, 0].max() + 4))
ax.set_ylim(float(all_centers[:, 1].min() - 4), float(all_centers[:, 1].max() + 4))
ax.set_zlim(z_min, z_max)
ax.tick_params(axis="z", labelsize=11, pad=7)
ax.zaxis.labelpad = 14
fig.colorbar(context, ax=ax, shrink=0.72, pad=0.08, label=f"{field_name} (V/m)")
fig.tight_layout()
fig.savefig(distribution_plot, dpi=180)
plt.close(fig)

# Left interior view from the right side.
# Keep x near the midline so the plot shows medial/interior left GM, not only
# the far lateral shell. This is an orientation view, so the field threshold
# removes low-field points and the Z axis stays visually readable.
left_mask = (visible_centers[:, 0] < 0) & (visible_centers[:, 0] > -35)
left_centers = visible_centers[left_mask]
left_values = visible_table["magET_v_per_m"][left_mask]
sort_order = np.argsort(left_values)
side_plot = output_directory / "dual_cz_magET_left_gm_side.png"
fig = plt.figure(figsize=(12, 8))
ax = fig.add_subplot(111, projection="3d")
ax.set_proj_type("ortho")
sc = ax.scatter(
    left_centers[sort_order, 0], left_centers[sort_order, 1], left_centers[sort_order, 2],
    c=left_values[sort_order],
    s=9, cmap="hot", vmin=5, vmax=color_limit_v_per_m, alpha=0.72, depthshade=False, linewidths=0,
)
ax.set(
    title="Left medial gray matter view (>10 V/m)",
    xlabel="", ylabel="Y anterior-posterior (mm)", zlabel="Z height (mm)",
)
ax.view_init(elev=12, azim=0)
ax.set_box_aspect((0.55, 1.0, 1.35))
ax.set_xlim(-35, 2)
ax.set_ylim(float(left_centers[:, 1].min() - 4), float(left_centers[:, 1].max() + 4))
ax.set_zlim(float(left_centers[:, 2].min() - 4), float(left_centers[:, 2].max() + 4))
ax.set_xticks([])
ax.tick_params(axis="z", labelsize=11, pad=8)
ax.zaxis.labelpad = 14
fig.colorbar(sc, ax=ax, shrink=0.68, pad=0.08, label=f"{field_name} (V/m)")
fig.tight_layout()
fig.savefig(side_plot, dpi=180)
plt.close(fig)


# ============================================================
# 3) E-FIELD BY DISTANCE FROM CZ
# ============================================================

# Distance from electrode is Euclidean distance from the SimNIBS-projected Cz
# scalp point to each GM centroid. The line is the mean in 0.25 cm bins.
distance_plot = output_directory / "dual_cz_focality_top3000.png"
rng = np.random.default_rng(0)

fig, ax = plt.subplots(figsize=(7.4, 5.0))
plot_count = min(3500, len(distance_values))
plot_index = rng.choice(len(distance_values), size=plot_count, replace=False)
ax.scatter(
    distance_cm[plot_index],
    distance_values[plot_index],
    s=10,
    color="#4c78a8",
    alpha=0.35,
    linewidth=0,
)

bin_edges = np.arange(2.0, 10.0 + distance_bin_width_cm, distance_bin_width_cm)
bin_centers = bin_edges[:-1] + distance_bin_width_cm / 2.0
bin_means = []
for left, right in zip(bin_edges[:-1], bin_edges[1:]):
    in_bin = (distance_cm >= left) & (distance_cm < right)
    bin_means.append(np.mean(distance_values[in_bin]) if np.any(in_bin) else np.nan)
bin_means = np.asarray(bin_means)
valid_bins = np.isfinite(bin_means)
ax.plot(bin_centers[valid_bins], bin_means[valid_bins], color="black", linewidth=2.4, label="mean")
ax.axvline(3.0, color="crimson", linewidth=1.4, linestyle="--")
ax.text(3.05, float(np.nanmax(bin_means)) + 1.5, "3 cm target", color="crimson")
ax.set(
    title="E-field magnitude falls with distance from Cz",
    xlabel="Distance from projected Cz scalp point (cm)",
    ylabel=f"{field_name} magnitude (V/m)",
    xlim=(2, 10),
    ylim=(0, float(np.nanmax(distance_values)) + 4.0),
)
ax.legend(frameon=False)
ax.grid(axis="y", alpha=0.25)
fig.tight_layout()
fig.savefig(distance_plot, dpi=180)
plt.close(fig)


# ============================================================
# 4) SAVE PLOT METRICS
# ============================================================

(output_directory / "distance_efield_summary.txt").write_text(
    "\n".join([
        "Dual-Cz E-field by distance from projected Cz",
        f"ROI mean magET: {np.mean(roi_values):.6f} V/m",
        f"ROI weighted mean magET: {float(summary['roi_mean_v_per_m']):.6f} V/m",
        f"ROI median magET: {np.median(roi_values):.6f} V/m",
        f"ROI min/max magET: {np.min(roi_values):.6f} / {np.max(roi_values):.6f} V/m",
        f"Distance table elements: {len(distance_values)}",
        f"Visible map threshold: >=5 V/m",
    ]) + "\n"
)

print(f"Saved distribution plot: {distribution_plot}")
print(f"Saved distance plot: {distance_plot}")
