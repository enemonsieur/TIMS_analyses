"""EXP07: Visualize ON-state artifact on CP2 for each of the 10 intensity levels (10%–100%)."""

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import mne
import numpy as np

import plot_helpers

# ============================================================
# CONFIG
# ============================================================
EXP07_DIR = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\EXP07")
EPOCHS_PATH = EXP07_DIR / "exp07_epochs-epo.fif"
OUTPUT_PATH = EXP07_DIR / "exp07_on_state_cp2_by_intensity.png"

CHANNEL = "CP2"
INTENSITY_LABELS = ["10%", "20%", "30%", "40%", "50%", "60%", "70%", "80%", "90%", "100%"]
CYCLES_PER_BLOCK = 20  # 20 ON epochs per intensity block
CROP_TMIN_S = 0.1      # skip first 100 ms (onset transient)
CROP_TMAX_S = 1.9      # skip last 100 ms (offset transient)

# 10-step blue ramp matching exp06 palette (light → dark)
INTENSITY_COLORS = [
    "#deebf7", "#c6dbef", "#9ecae1", "#6baed6", "#4292c6",
    "#2171b5", "#08519c", "#08306b", "#041d40", "#01101f",
]

# ============================================================
# 1) LOAD EPOCHS
# ============================================================
epochs = mne.read_epochs(str(EPOCHS_PATH), preload=True, verbose=False)
sfreq = float(epochs.info["sfreq"])
# → (204, 31, 2001) epochs × channels × samples

print(f"Loaded: {len(epochs)} epochs, {len(epochs.ch_names)} channels, {sfreq:.0f} Hz")
print(f"  Shape: {epochs.get_data().shape}")

if CHANNEL not in epochs.ch_names:
    raise RuntimeError(f"Channel {CHANNEL!r} not found. Available: {epochs.ch_names}")

n_required = len(INTENSITY_LABELS) * CYCLES_PER_BLOCK  # = 200
if len(epochs) < n_required:
    raise RuntimeError(f"Need at least {n_required} epochs, found {len(epochs)}.")
if len(epochs) > n_required:
    print(f"  Warning: {len(epochs) - n_required} extra epochs beyond 10×20 — ignoring tail.")

# ============================================================
# 2) SPLIT INTO 10 INTENSITY BLOCKS & EXTRACT CP2
# ============================================================
# Crop sample indices for inner window (avoids onset/offset transients)
crop_start = int(round(CROP_TMIN_S * sfreq))
crop_stop = int(round(CROP_TMAX_S * sfreq)) + 1  # +1 for exclusive slice
time_s = np.arange(crop_stop - crop_start) / sfreq + CROP_TMIN_S
# → time axis from 0.1 to 1.9 s

panel_rows = []
for i, label in enumerate(INTENSITY_LABELS):
    block_epochs = epochs[i * CYCLES_PER_BLOCK : (i + 1) * CYCLES_PER_BLOCK]
    data_uv = block_epochs.copy().pick([CHANNEL]).get_data()[:, 0, :] * 1e6
    # → (20, 2001) µV

    # Crop to inner window then demean each epoch
    data_uv = data_uv[:, crop_start:crop_stop]
    data_uv -= data_uv.mean(axis=1, keepdims=True)
    # → (20, n_inner_samples), zero-mean per epoch

    mean_uv = data_uv.mean(axis=0)

    panel_rows.append({
        "label": label,
        "color": INTENSITY_COLORS[i],
        "n": data_uv.shape[0],
        "data_uv": data_uv,
        "mean_uv": mean_uv,
    })
    print(f"  {label}: n={data_uv.shape[0]} epochs, mean_abs={np.mean(np.abs(mean_uv)):.2f} µV")

# ============================================================
# 3) PLOT — 10 STACKED SUBPLOTS
# ============================================================
fig, axes = plt.subplots(len(panel_rows), 1, figsize=(9.2, 18.0),
                         constrained_layout=True, sharex=True, sharey=False)

for ax, row in zip(np.atleast_1d(axes), panel_rows):
    for trace in row["data_uv"]:
        ax.plot(time_s, trace, color=row["color"], lw=0.6, alpha=0.08)
    ax.plot(time_s, row["mean_uv"], color=row["color"], lw=2.1)

    all_vals = row["data_uv"].reshape(-1)
    ypad = max(5.0, 0.08 * (all_vals.max() - all_vals.min()))
    ax.set(
        ylim=(float(all_vals.min()) - ypad, float(all_vals.max()) + ypad),
        xlim=(CROP_TMIN_S, CROP_TMAX_S),
        ylabel=f"{CHANNEL} (µV)",
    )
    ax.set_title(f"{row['label']} (n={row['n']})", color=row["color"], pad=6)
    plot_helpers.style_clean_axis(ax, grid_alpha=0.10)

axes = np.atleast_1d(axes)
axes[-1].set_xlabel("Time within ON window (s)")
fig.suptitle(
    f"EXP07 ON-state artifact on {CHANNEL} by intensity (demeaned, 0.1–1.9 s)",
    fontsize=12.2,
)
fig.savefig(OUTPUT_PATH, dpi=220)
plt.close(fig)

print(f"Saved: {OUTPUT_PATH.name}")
