"""Visualize EXP08 run01 single-pulse artifact removal before/after quality."""

from pathlib import Path

import matplotlib.gridspec as gridspec
import matplotlib.pyplot as plt
import mne
import numpy as np


OUTPUT_DIRECTORY = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\EXP08")

INTENSITY_LEVELS = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
CHANNEL = "Oz"
ZOOM_WINDOW_S = (-0.05, 0.40)

COLOR_BEFORE = "#888888"
COLOR_AFTER = "#2176ae"
COLOR_PULSE = "#d62828"


# ============================================================
# 1) LOAD RUN01 SINGLE-PULSE EPOCHS
# ============================================================

print("Loading run01 single-pulse epoch files...")
data_store = {}

for intensity_pct in INTENSITY_LEVELS:
    label = f"{intensity_pct}pct"
    original = mne.read_epochs(
        OUTPUT_DIRECTORY / f"exp08_epochs_{label}_on-epo.fif",
        verbose=False,
        preload=True,
    )
    cleaned = mne.read_epochs(
        OUTPUT_DIRECTORY / f"exp08_epochs_{label}_on_artremoved-epo.fif",
        verbose=False,
        preload=True,
    )
    channel_index = original.ch_names.index(CHANNEL)
    data_store[intensity_pct] = {
        "original": original,
        "cleaned": cleaned,
        "channel_index": channel_index,
    }
    print(f"  {intensity_pct}%: {len(original)} epochs")

times = data_store[10]["original"].times
zoom_mask = (times >= ZOOM_WINDOW_S[0]) & (times <= ZOOM_WINDOW_S[1])
time_zoom = times[zoom_mask]


# ============================================================
# 2) CLAIM-FIRST QC FIGURE
# ============================================================

fig = plt.figure(figsize=(18, 22))
outer = gridspec.GridSpec(1, 2, figure=fig, width_ratios=[2, 1], wspace=0.35)
left_grid = gridspec.GridSpecFromSubplotSpec(5, 2, subplot_spec=outer[0], hspace=0.55, wspace=0.35)
right_grid = gridspec.GridSpecFromSubplotSpec(2, 1, subplot_spec=outer[1], hspace=0.4)

for index, intensity_pct in enumerate(INTENSITY_LEVELS):
    row = index // 2
    col = index % 2
    ax = fig.add_subplot(left_grid[row, col])

    store = data_store[intensity_pct]
    channel_index = store["channel_index"]
    raw_oz = store["original"].get_data()[:, channel_index, :][:, zoom_mask] * 1e6
    clean_oz = store["cleaned"].get_data()[:, channel_index, :][:, zoom_mask] * 1e6

    mean_raw = raw_oz.mean(axis=0)
    std_raw = raw_oz.std(axis=0)
    mean_clean = clean_oz.mean(axis=0)
    std_clean = clean_oz.std(axis=0)

    ax.fill_between(time_zoom, mean_raw - std_raw, mean_raw + std_raw, color=COLOR_BEFORE, alpha=0.25)
    ax.plot(time_zoom, mean_raw, color=COLOR_BEFORE, linewidth=1.2, label="Before")
    ax.fill_between(time_zoom, mean_clean - std_clean, mean_clean + std_clean, color=COLOR_AFTER, alpha=0.25)
    ax.plot(time_zoom, mean_clean, color=COLOR_AFTER, linewidth=1.2, label="After")
    ax.axvline(0, color=COLOR_PULSE, linestyle="--", linewidth=0.9, alpha=0.8)
    ax.set_title(f"{intensity_pct}% - Oz mean +/- std", fontsize=9)
    ax.set_xlabel("Time (s)", fontsize=7)
    ax.set_ylabel("uV", fontsize=7)
    ax.tick_params(labelsize=7)
    ax.grid(True, alpha=0.2)
    if index == 0:
        ax.legend(fontsize=7, loc="upper right")

store_100 = data_store[100]
channel_index = store_100["channel_index"]
raw_100 = store_100["original"].get_data()[:, channel_index, :][:, zoom_mask] * 1e6
clean_100 = store_100["cleaned"].get_data()[:, channel_index, :][:, zoom_mask] * 1e6

for panel_index, (title, traces, color) in enumerate([
    ("100% before - all 20 run01 pulses (Oz)", raw_100, COLOR_BEFORE),
    ("100% after - all 20 run01 pulses (Oz)", clean_100, COLOR_AFTER),
]):
    ax = fig.add_subplot(right_grid[panel_index])
    for trace in traces:
        ax.plot(time_zoom, trace, alpha=0.3, linewidth=0.6, color=color)
    ax.plot(time_zoom, traces.mean(axis=0), color=color, linewidth=1.8, label="Mean")
    ax.axvline(0, color=COLOR_PULSE, linestyle="--", linewidth=1.0, alpha=0.9, label="Pulse")
    ax.set_title(title, fontsize=9)
    ax.set_xlabel("Time (s)", fontsize=8)
    ax.set_ylabel("Oz (uV)", fontsize=8)
    ax.tick_params(labelsize=8)
    ax.grid(True, alpha=0.2)
    ax.legend(fontsize=8, loc="upper right")

fig.suptitle(
    "EXP08 Run01 Artifact Removal - Oz before vs after (all intensities)\n"
    "Source: exp08-STIM-pulse_run01_10-100.vhdr; no exp08t/triplet files used",
    fontsize=12,
    fontweight="bold",
    y=0.995,
)

output_path = OUTPUT_DIRECTORY / "exp08_artremoved_dataviz.png"
fig.savefig(output_path, dpi=150, bbox_inches="tight")
plt.close()
print(f"Saved: {output_path.name}")
