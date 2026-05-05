"""Show why dual-coil E-field scales linearly with current and decays with distance."""

from pathlib import Path
import csv
import math

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
distance_profile_path = output_directory / "gm_distance_0_6cm.csv"
route_figure_path = output_directory / "dual_cz_dril_current_to_distance.png"

current_full_a = 75.0       # saved simulation peak current
current_ten_pct_a = 7.5     # 10% of the saved peak current
frequency_hz = 20_000.0     # saved simulation frequency
roi_mean_full_v_per_m = 19.486  # saved 30 mm GM ROI weighted mean
distance_bin_width_cm = 1.0     # readable DRIL bins for the route figure


# ============================================================
# FLOW
# ============================================================
#
# 75 A and 7.5 A current values
#   -> sinusoidal current waveform, one 20 kHz cycle
#   -> dI/dt = 2*pi*I*f
#   -> ROI E-field = saved ROI field * current fraction
#   -> distance bins from gm_distance_0_6cm.csv
#   -> 2x2 DRIL figure: waveform, dI/dt, ROI, distance decay


# ============================================================
# 1) COMPUTE CURRENT AND dI/dt
# ============================================================

current_fraction = current_ten_pct_a / current_full_a
didt_full_a_per_s = 2 * math.pi * current_full_a * frequency_hz
didt_ten_pct_a_per_s = 2 * math.pi * current_ten_pct_a * frequency_hz
roi_mean_ten_pct_v_per_m = roi_mean_full_v_per_m * current_fraction

# One cycle is enough to show amplitude and slope scaling.
cycle_duration_s = 1.0 / frequency_hz
time_ms = np.linspace(0, cycle_duration_s, 400) * 1_000
current_full_wave = current_full_a * np.sin(2 * np.pi * frequency_hz * time_ms / 1_000)
current_ten_pct_wave = current_ten_pct_a * np.sin(2 * np.pi * frequency_hz * time_ms / 1_000)


# ============================================================
# 2) BIN THE MEASURED DISTANCE PROFILE
# ============================================================

distance_values = []
field_values = []
with distance_profile_path.open(newline="") as handle:
    reader = csv.DictReader(handle)
    for row in reader:
        distance_values.append(float(row["distance_from_cz_cm"]))
        field_values.append(float(row["magET_v_per_m"]))

distance_values = np.asarray(distance_values)
field_values = np.asarray(field_values)
bin_edges = np.arange(2.0, 10.0 + distance_bin_width_cm, distance_bin_width_cm)
bin_centers = bin_edges[:-1] + distance_bin_width_cm / 2
bin_means_full = []
for left, right in zip(bin_edges[:-1], bin_edges[1:]):
    in_bin = (distance_values >= left) & (distance_values < right)
    bin_means_full.append(float(np.mean(field_values[in_bin])))

bin_means_full = np.asarray(bin_means_full)
bin_means_ten_pct = bin_means_full * current_fraction


# ============================================================
# 3) SAVE THE DRIL ROUTE FIGURE
# ============================================================

plt.rcParams.update({
    "font.size": 10,
    "axes.spines.top": False,
    "axes.spines.right": False,
})

fig, axes = plt.subplots(2, 2, figsize=(11.5, 7.2), constrained_layout=True)
fig.suptitle("10% current keeps the dual-coil field pattern but lowers V/m 10x", fontsize=15)

# 3.1 Current amplitude
ax = axes[0, 0]
ax.plot(time_ms, current_full_wave, color="#1f77b4", linewidth=2.2)
ax.plot(time_ms, current_ten_pct_wave, color="#d62728", linewidth=2.2)
ax.text(0.010, 58, "75 A peak", color="#1f77b4", weight="bold")
ax.text(0.026, 11, "7.5 A peak", color="#d62728", weight="bold")
ax.set(
    title="1. Current amplitude is scaled",
    xlabel="Time within one 20 kHz cycle (ms)",
    ylabel="Coil current (A)",
    xlim=(0, cycle_duration_s * 1_000),
    ylim=(-82, 82),
)
ax.grid(alpha=0.2)

# 3.2 dI/dt driver
ax = axes[0, 1]
bars = ax.bar(
    ["75 A", "10% current"],
    [didt_full_a_per_s / 1e6, didt_ten_pct_a_per_s / 1e6],
    color=["#1f77b4", "#d62728"],
)
ax.bar_label(bars, labels=[f"{didt_full_a_per_s / 1e6:.2f}", f"{didt_ten_pct_a_per_s / 1e6:.2f}"], padding=3)
ax.text(
    0.5, 7.8, "dI/dt = 2*pi*I*f",
    ha="center", fontsize=11,
    bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.85, "pad": 3},
)
ax.set(
    title="2. SimNIBS driver scales linearly",
    ylabel="Maximum dI/dt (million A/s)",
    ylim=(0, 10.5),
)
ax.grid(axis="y", alpha=0.2)

# 3.3 ROI E-field
ax = axes[1, 0]
bars = ax.bar(
    ["75 A", "10% current"],
    [roi_mean_full_v_per_m, roi_mean_ten_pct_v_per_m],
    color=["#1f77b4", "#d62728"],
)
ax.bar_label(bars, labels=[f"{roi_mean_full_v_per_m:.2f}", f"{roi_mean_ten_pct_v_per_m:.2f}"], padding=3)
ax.text(
    0.5, 15.8, "30 mm GM ROI\nfield = old field * 0.10",
    ha="center", fontsize=11,
    bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.85, "pad": 3},
)
ax.set(
    title="3. ROI E-field follows the same scale",
    ylabel="magET at 30 mm ROI (V/m)",
    ylim=(0, 22),
)
ax.grid(axis="y", alpha=0.2)

# 3.4 Distance decay
ax = axes[1, 1]
ax.plot(bin_centers, bin_means_full, marker="o", color="#1f77b4", linewidth=2.4)
ax.plot(bin_centers, bin_means_ten_pct, marker="o", color="#d62728", linewidth=2.4)
ax.text(2.8, 25.0, "75 A measured bins", color="#1f77b4", weight="bold")
ax.text(5.8, 2.2, "10% estimate", color="#d62728", weight="bold")
ax.axvline(3.0, color="0.25", linestyle="--", linewidth=1.0)
ax.text(3.08, 28.0, "3 cm target", color="0.25")
ax.set(
    title="4. Distance decay stays shaped, values shrink",
    xlabel="Distance from projected Cz scalp point (cm)",
    ylabel="Mean magET in GM bin (V/m)",
    xlim=(2, 10),
    ylim=(0, 30),
)
ax.grid(axis="y", alpha=0.2)

fig.savefig(route_figure_path, dpi=180)
plt.close(fig)

print(f"Saved DRIL route figure: {route_figure_path}")
