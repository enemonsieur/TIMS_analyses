"""Plot mean GT-locking across the 5 exported run02 ON stimulation levels."""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


# ============================================================
# CONFIG
# ============================================================
OUTPUT_DIRECTORY = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\EXP06")  # explicit output folder
EXPORT_PATH = OUTPUT_DIRECTORY / "exp06_run02_on_itpc.npz"  # machine-readable SSD ITPC export
FIGURE_PATH = OUTPUT_DIRECTORY / "exp06_run02_on_mean_gt_locking.png"  # claim-first evidence figure
INTENSITY_COLORS = ["#c6dbef", "#9ecae1", "#6baed6", "#3182bd", "#08519c"]  # ordered dose sweep ramp


# ============================================================
# 1) LOAD THE EXPORTED ITPC DATA
# ============================================================
artifact = np.load(EXPORT_PATH)
intensity_labels = artifact["intensity_labels"].astype(str)
intensity_pct = np.asarray(artifact["intensity_pct"], dtype=int)
event_counts = np.asarray(artifact["event_counts"], dtype=int)
time_axis_s = np.asarray(artifact["time_axis_s"], dtype=float)
ssd_itpc_curves = np.asarray(artifact["ssd_itpc_curves"], dtype=float)
signal_band_hz = np.asarray(artifact["signal_band_hz"], dtype=float)
on_window_s = np.asarray(artifact["on_window_s"], dtype=float)

if ssd_itpc_curves.shape[0] != intensity_labels.shape[0]:
    raise RuntimeError("ITPC export mismatch: one SSD ITPC curve is required per intensity label.")
if ssd_itpc_curves.shape[0] != intensity_pct.shape[0]:
    raise RuntimeError("ITPC export mismatch: one intensity percentage is required per SSD ITPC curve.")
if ssd_itpc_curves.shape[0] != event_counts.shape[0]:
    raise RuntimeError("ITPC export mismatch: one event count is required per SSD ITPC curve.")
if ssd_itpc_curves.shape[1] != time_axis_s.shape[0]:
    raise RuntimeError("ITPC export mismatch: curve length must match the shared time axis.")
if len(INTENSITY_COLORS) != len(intensity_labels):
    raise RuntimeError("Need one intensity color per exported ITPC curve.")


# ============================================================
# 2) REDUCE EACH EXPORTED CURVE TO ONE MEAN GT-LOCKING VALUE
# ============================================================
mean_gt_locking = np.mean(ssd_itpc_curves, axis=1)
sort_order = np.argsort(intensity_pct)
intensity_labels = intensity_labels[sort_order]
intensity_pct = intensity_pct[sort_order]
event_counts = event_counts[sort_order]
mean_gt_locking = mean_gt_locking[sort_order]
intensity_colors = [INTENSITY_COLORS[index] for index in sort_order]


# ============================================================
# 3) SAVE THE CLAIM-FIRST SUMMARY FIGURE
# ============================================================
figure, axis = plt.subplots(figsize=(8.6, 5.0), constrained_layout=True)
axis.plot(
    intensity_pct,
    mean_gt_locking,
    color="#2b6ea6",
    lw=2.4,
    marker="o",
    ms=8,
)

for x_value, y_value, event_count, point_color in zip(
    intensity_pct,
    mean_gt_locking,
    event_counts,
    intensity_colors,
    strict=True,
):
    axis.scatter(x_value, y_value, color=point_color, s=62, zorder=3)
    axis.text(
        x_value,
        y_value + 0.01,
        f"n={event_count}",
        ha="center",
        va="bottom",
        fontsize=8.5,
    )

ymin = float(np.min(mean_gt_locking))
ymax = float(np.max(mean_gt_locking))
ypad = max(0.02, 0.1 * (ymax - ymin))
axis.set(
    xticks=intensity_pct,
    xlabel="Run02 stimulation block (%)",
    ylabel="Mean GT-locking",
    title="run02 ON GT-locking stays high across all 5 stimulation levels",
    ylim=(max(0.0, ymin - ypad), min(1.02, ymax + ypad)),
)
axis.grid(alpha=0.15)
axis.spines["top"].set_visible(False)
axis.spines["right"].set_visible(False)
axis.text(
    0.02,
    0.96,
    f"Band: {signal_band_hz[0]:.2f}-{signal_band_hz[1]:.2f} Hz\nMean across time in accepted ON window: {on_window_s[0]:.1f}-{on_window_s[1]:.1f} s",
    transform=axis.transAxes,
    va="top",
    fontsize=8.2,
    color="0.25",
)
figure.savefig(FIGURE_PATH, dpi=220)
plt.close(figure)


# ============================================================
# 4) PRINT SHORT REPORT
# ============================================================
print(f"loaded={EXPORT_PATH.name} | levels={mean_gt_locking.shape[0]}")
print(f"saved={FIGURE_PATH.name} | window={on_window_s[0]:.1f}-{on_window_s[1]:.1f}s")
