"""Which channels saturate first as run02 intensity increases, measured by mean absolute amplitude in the ON window?"""

from pathlib import Path
import warnings

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import mne
import numpy as np

import preprocessing


# ============================================================
# CONFIG
# ============================================================
DATA_DIRECTORY = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\TIMS_data_sync\pilot\doseresp")
STIM_VHDR_PATH = DATA_DIRECTORY / "exp06-STIM-iTBS_run02.vhdr"  # measured run02 stimulation recording
OUTPUT_DIRECTORY = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\EXP06")
OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)

RUN02_INTENSITY_LABELS = ["10%", "20%", "30%", "40%", "50%"]  # run02 dose order
BLOCK_CYCLES_PER_INTENSITY = 20  # ON cycles per intensity block
ON_WINDOW_S = (0.3, 1.5)  # accepted ON window — same as the parent ON analysis script
EXCLUDED_CHANNELS = {"TP9", "Fp1", "TP10"}  # keep EEG set aligned with the rest of the run02 analysis
RUN02_STIM_THRESHOLD_FRACTION = 0.08  # recover weak first block — same value as parent script

# Posterior channels from the memo saturation table; edit to inspect others
SATURATION_CHANNELS = ["O1", "O2", "Oz", "Pz", "P4", "P3"]

LINE_FIGURE_PATH = OUTPUT_DIRECTORY / "exp06_run02_on_channel_saturation.png"
HEATMAP_FIGURE_PATH = OUTPUT_DIRECTORY / "exp06_run02_on_channel_saturation_heatmap.png"
CSV_PATH = OUTPUT_DIRECTORY / "exp06_run02_on_channel_saturation.csv"


# ============================================================
# PIPELINE
# ============================================================
# run02 EEG (broadband, unfiltered)
#   |
# measured ON timing
#   |
# per-block: accepted ON windows → raw epoch matrix
#   |
# per-channel mean absolute amplitude (µV) across 20 windows
#   |
# line figure (posterior ROI) + heatmap (all channels) + CSV


# ============================================================
# 1) LOAD THE RUN02 RECORDING
# ============================================================
with warnings.catch_warnings():
    warnings.filterwarnings("ignore", message="No coordinate information found for channels*")
    warnings.filterwarnings("ignore", message="Online software filter detected*")
    warnings.filterwarnings("ignore", message="Not setting positions of 2 misc channels found in montage*")
    raw = mne.io.read_raw_brainvision(str(STIM_VHDR_PATH), preload=True, verbose=False)

if "stim" not in raw.ch_names:
    raise RuntimeError("Stim channel not found in recording.")

sfreq = float(raw.info["sfreq"])
stim_trace = raw.copy().pick(["stim"]).get_data()[0]  # stim channel voltage trace

# Drop stim, GT, and excluded channels; keep EEG only
drop = [
    ch for ch in raw.ch_names
    if ch.lower() in {"stim", "ground_truth"}
    or ch.startswith("STI")
    or ch in EXCLUDED_CHANNELS
]
raw_eeg = raw.copy().drop_channels(drop)
eeg_data = raw_eeg.get_data()  # (n_channels, n_samples) raw broadband EEG in V
channel_names = list(raw_eeg.ch_names)
print(f"Retained EEG channels: {len(channel_names)}")


# ============================================================
# 2) RECOVER MEASURED ON TIMING
# ============================================================
# The first 10% block is weak, so the threshold is part of the timing definition.
block_onsets, block_offsets = preprocessing.detect_stim_blocks(
    stim_trace,
    sfreq,
    threshold_fraction=RUN02_STIM_THRESHOLD_FRACTION,
)

required_blocks = len(RUN02_INTENSITY_LABELS) * BLOCK_CYCLES_PER_INTENSITY
if len(block_onsets) < required_blocks:
    raise RuntimeError(f"Need {required_blocks} ON blocks, found {len(block_onsets)}.")

window_size = int(round((ON_WINDOW_S[1] - ON_WINDOW_S[0]) * sfreq))  # ON window in samples
start_shift = int(round(ON_WINDOW_S[0] * sfreq))  # post-onset shift in samples


# ============================================================
# 3) COMPUTE PER-CHANNEL AMPLITUDE ACROSS INTENSITY BLOCKS
# ============================================================
n_channels = len(channel_names)
n_intensities = len(RUN02_INTENSITY_LABELS)
amplitude_uv = np.zeros((n_intensities, n_channels), dtype=float)  # µV per intensity × channel

for intensity_index, intensity_label in enumerate(RUN02_INTENSITY_LABELS):
    block_start = intensity_index * BLOCK_CYCLES_PER_INTENSITY
    dose_onsets = block_onsets[block_start : block_start + BLOCK_CYCLES_PER_INTENSITY]
    dose_offsets = block_offsets[block_start : block_start + BLOCK_CYCLES_PER_INTENSITY]

    # Shift each ON block into the accepted interior segment, reject windows that overrun the offset
    window_onsets = dose_onsets + start_shift
    window_keep = window_onsets + window_size <= dose_offsets
    event_samples = window_onsets[window_keep]  # accepted window start samples

    if len(event_samples) == 0:
        raise RuntimeError(f"No valid ON windows for {intensity_label}.")

    # Stack raw EEG windows: (n_events, n_channels, window_size)
    # Inline extraction keeps the metric choice visible: mean absolute amplitude, not filtered.
    epochs = np.stack(
        [eeg_data[:, s : s + window_size] for s in event_samples],
        axis=0,
    )
    # EEG in V → µV; mean absolute amplitude averaged across events and time
    amplitude_uv[intensity_index, :] = np.mean(np.abs(epochs) * 1e6, axis=(0, 2))

    print(f"{intensity_label}: {len(event_samples)} windows | "
          + " | ".join(
              f"{ch}={amplitude_uv[intensity_index, channel_names.index(ch)]:.1f}µV"
              for ch in SATURATION_CHANNELS
              if ch in channel_names
          ))


# ============================================================
# 4) SAVE CSV
# ============================================================
header = "intensity," + ",".join(channel_names)
rows = [header]
for intensity_index, label in enumerate(RUN02_INTENSITY_LABELS):
    row_values = ",".join(f"{amplitude_uv[intensity_index, ci]:.4f}" for ci in range(n_channels))
    rows.append(f"{label},{row_values}")
CSV_PATH.write_text("\n".join(rows) + "\n", encoding="utf-8")


# ============================================================
# 5) SAVE FIGURES
# ============================================================
intensity_pct = [int(label.replace("%", "")) for label in RUN02_INTENSITY_LABELS]
colors = plt.cm.tab10.colors  # qualitative palette — channels, not intensities

# 5.1 Primary figure: line plot of ALL EEG channels with log scale
# Use a larger colormap to distinguish all channels
cmap = plt.cm.get_cmap("tab20")
n_all_channels = len(channel_names)
channel_colors = [cmap(i / max(n_all_channels - 1, 1)) for i in range(n_all_channels)]

fig, ax = plt.subplots(figsize=(10, 5))
for ci, ch in enumerate(channel_names):
    ax.plot(
        intensity_pct,
        amplitude_uv[:, ci],
        marker="o",
        linewidth=1.2,
        markersize=5,
        color=channel_colors[ci],
        label=ch,
        alpha=0.7,
    )

# Highlight the saturation channels with thicker lines and darker color
for ch in SATURATION_CHANNELS:
    if ch in channel_names:
        ci = channel_names.index(ch)
        ax.plot(
            intensity_pct,
            amplitude_uv[:, ci],
            marker="o",
            linewidth=2.2,
            markersize=6,
            color=channel_colors[ci],
            alpha=1.0,
            zorder=10,
        )

ax.set_title("EEG channel saturation across stimulation intensities\n(log scale; saturation channels highlighted)", fontsize=11, pad=10)
ax.set_xlabel("Stimulation intensity (%)")
ax.set_ylabel("Mean absolute amplitude (µV, log scale)")
ax.set_xticks(intensity_pct)
ax.set_yscale("log")
ax.set_ylim(5, 10000)  # log scale from 5 µV to 10 mV
ax.yaxis.grid(True, alpha=0.2, linewidth=0.7, which="both")
ax.xaxis.grid(True, alpha=0.15, linewidth=0.5)
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)
# Legend outside plot area
ax.legend(
    loc="center left",
    bbox_to_anchor=(1.01, 0.5),
    fontsize=7,
    framealpha=0.9,
    ncol=1,
)
fig.tight_layout()
fig.savefig(LINE_FIGURE_PATH, dpi=150, bbox_inches="tight")
plt.close(fig)

# 5.2 Qualification figure: heatmap over all channels, sorted by 50% amplitude
sort_order = np.argsort(amplitude_uv[-1, :])[::-1]  # descending by 50% amplitude
sorted_amplitudes = amplitude_uv[:, sort_order]
sorted_channel_names = [channel_names[i] for i in sort_order]

# Log scale handles the wide dynamic range (up to ~1000× between Pz and O2 at 50%)
log_amplitudes = np.log10(sorted_amplitudes + 0.01)  # +0.01 to avoid log(0)

fig, ax = plt.subplots(figsize=(5, max(4, n_channels * 0.22)))
im = ax.imshow(
    log_amplitudes.T,  # (n_channels, n_intensities)
    aspect="auto",
    cmap="YlOrRd",
    interpolation="nearest",
)
ax.set_xticks(range(n_intensities))
ax.set_xticklabels(RUN02_INTENSITY_LABELS, fontsize=9)
ax.set_yticks(range(n_channels))
ax.set_yticklabels(sorted_channel_names, fontsize=7)
ax.set_xlabel("Stimulation intensity")
ax.set_title("Saturation concentrated in a few posterior channels\n(log₁₀ µV, sorted by 50% amplitude)", fontsize=9)
cbar = fig.colorbar(im, ax=ax, shrink=0.6)
cbar.set_label("log₁₀(µV)", fontsize=8)
fig.tight_layout()
fig.savefig(HEATMAP_FIGURE_PATH, dpi=150)
plt.close(fig)

print(f"Saved -> {LINE_FIGURE_PATH.name}")
print(f"Saved -> {HEATMAP_FIGURE_PATH.name}")
print(f"Saved -> {CSV_PATH.name}")
