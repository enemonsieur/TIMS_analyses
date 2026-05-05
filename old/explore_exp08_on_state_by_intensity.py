"""Visualize ON-state pulse response at each intensity level (10–100%), locked to best channel at 10%."""

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

EXP08_DIR = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\EXP08")
INTENSITY_LEVELS = [0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90, 1.00]
INTENSITY_LABELS = ["10%", "20%", "30%", "40%", "50%", "60%", "70%", "80%", "90%", "100%"]
EPOCHS_PER_INTENSITY = 20

# Pre-post window definition
WINDOW_TMIN_S = -0.1
WINDOW_TMAX_S = 0.5
WINDOW_DURATION_S = WINDOW_TMAX_S - WINDOW_TMIN_S  # 0.6 s

# 10-step blue ramp (light → dark) matching EXP07 palette
INTENSITY_COLORS = [
    "#deebf7", "#c6dbef", "#9ecae1", "#6baed6", "#4292c6",
    "#2171b5", "#08519c", "#08306b", "#041d40", "#01101f",
]

OUTPUT_PATH = EXP08_DIR / "exp08_on_state_best_channel_by_intensity.png"

# ════════════════════════════════════════════════════════════════════════════
# PIPELINE OVERVIEW
# ════════════════════════════════════════════════════════════════════════════
#
# Epoch Files (exp08_epochs_*pct-epo.fif, 10 files)
# ├─ Load: 10% intensity file
# │  └─ Detect: best channel by mean absolute amplitude
# │
# ├─ Load & Process: all 10 intensity files
# │  ├─ Extract: best channel timecourse
# │  ├─ Demean: per-epoch baseline subtraction
# │  └─ Compute: epoch-wise mean
# │
# └─ Visualize: 10 stacked subplots (faint trials + bold mean)
#    └─ OUTPUT: exp08_on_state_best_channel_by_intensity.png

# ============================================================
# 1) DETECT BEST CHANNEL AT 10% INTENSITY
# ============================================================

# ══ 1.1 Load 10% intensity epochs ══
epochs_10pct_path = EXP08_DIR / "exp08_epochs_10pct-epo.fif"
epochs_10pct = mne.read_epochs(str(epochs_10pct_path), preload=True, verbose=False)
# → (20, 28, 600) epochs × channels × samples

sfreq = float(epochs_10pct.info["sfreq"])
n_channels = len(epochs_10pct.ch_names)
n_samples = len(epochs_10pct.times)

print(f"Loaded 10% epochs: {len(epochs_10pct)} epochs, {n_channels} channels, {sfreq:.0f} Hz")
print(f"  Shape: {epochs_10pct.get_data().shape}, window: {WINDOW_TMIN_S:.2f}–{WINDOW_TMAX_S:.2f} s")

# ============================================================
# 2) EXTRACT & PREPARE DATA FOR ALL INTENSITIES
# ============================================================

# ══ 2.1 Time axis for plotting ══
time_s = np.arange(n_samples) / sfreq + WINDOW_TMIN_S
# → time relative to pulse onset (t=0); ranges -0.1 to +0.5 s

# ══ 2.2 Process each intensity level ══
panel_rows = []

for i, (intensity_level, label) in enumerate(zip(INTENSITY_LEVELS, INTENSITY_LABELS)):
    intensity_pct = int(intensity_level * 100)

    # 2.2.1 Load intensity-specific epoch file
    epochs_path = EXP08_DIR / f"exp08_epochs_{intensity_pct}pct-epo.fif"
    epochs = mne.read_epochs(str(epochs_path), preload=True, verbose=False)
    # → (20, 28, 600) epochs × channels × samples

    # 2.2.2 Extract all channels, convert to µV
    data_all_ch = epochs.get_data() * 1e6  # (20, 28, 600) µV

    # 2.2.3 Demean each channel within each epoch
    data_all_ch -= data_all_ch.mean(axis=2, keepdims=True)
    # → (20, 28, 600) zero-mean per channel per epoch

    # 2.2.4 Average across channels → (20, 600) per-epoch timecourse
    data_uv = data_all_ch.mean(axis=1)

    # 2.2.5 Compute mean and std across epochs
    mean_uv = data_uv.mean(axis=0)
    std_uv = data_uv.std(axis=0)
    # → (600,) mean timecourse, (600,) std

    # 2.2.6 Store in panel row
    panel_rows.append({
        "label": label,
        "color": INTENSITY_COLORS[i],
        "n_epochs": len(epochs),
        "data_uv": data_uv,
        "mean_uv": mean_uv,
        "std_uv": std_uv,
    })

    print(f"  {label}: n={data_uv.shape[0]} epochs, mean_abs={np.mean(np.abs(mean_uv)):.2f} µV")

# ============================================================
# 3) VISUALIZE 10 STACKED SUBPLOTS
# ============================================================

# ══ 3.1 Create figure with 10 subplots (shared x-axis) ══
fig, axes = plt.subplots(len(panel_rows), 1, figsize=(10, 20),
                         constrained_layout=True, sharex=True, sharey=False)

# ══ 3.2 Plot each intensity level ══
for ax, row in zip(np.atleast_1d(axes), panel_rows):

    # 3.2.1 Plot faint individual epoch traces (all channels averaged per epoch)
    for trace in row["data_uv"]:
        ax.plot(time_s, trace, color=row["color"], lw=0.5, alpha=0.1)

    # 3.2.2 Plot SD band (mean ± std)
    ax.fill_between(time_s, row["mean_uv"] - row["std_uv"], row["mean_uv"] + row["std_uv"],
                    color=row["color"], alpha=0.2)

    # 3.2.3 Plot bold mean
    ax.plot(time_s, row["mean_uv"], color=row["color"], lw=2.1)

    # 3.2.4 Set y-limits (data range + padding)
    all_vals = row["data_uv"].reshape(-1)
    ypad = max(5.0, 0.08 * (all_vals.max() - all_vals.min()))
    ax.set(
        ylim=(float(all_vals.min()) - ypad, float(all_vals.max()) + ypad),
        xlim=(WINDOW_TMIN_S, WINDOW_TMAX_S),
        ylabel="All channels avg (µV)",
    )

    # 3.2.5 Add title with trial count and intensity
    ax.set_title(f"{row['label']} (n={row['n_epochs']})", color=row["color"], pad=6)

    # 3.2.6 Clean axis styling
    plot_helpers.style_clean_axis(ax, grid_alpha=0.10)

# ══ 3.3 Set shared labels and figure title ══
axes = np.atleast_1d(axes)
axes[-1].set_xlabel("Time within ON window (s)")
fig.suptitle(
    f"EXP08 ON-state response: all channels averaged by intensity (mean ± SD, {WINDOW_TMIN_S:.1f}–{WINDOW_TMAX_S:.1f} s)",
    fontsize=12.2,
)

# ============================================================
# 4) SAVE & REPORT
# ============================================================

# ══ 4.1 Save figure ══
fig.savefig(OUTPUT_PATH, dpi=220)
plt.close(fig)

# ══ 4.2 Print summary ══
print(f"\nSaved: {OUTPUT_PATH.name}")
