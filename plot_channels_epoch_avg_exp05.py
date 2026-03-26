"""Plot epoch-averaged EEG for all exp05 channels using STIM-defined block timing."""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import mne
import numpy as np

import preprocessing


# ============================================================
# FIXED INPUTS
# ============================================================
DATA_DIR = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\TIMS_data_sync\pilot\doseresp")
BASELINE_VHDR = DATA_DIR / "exp05-phantom-rs-GT-cTBS-run02.vhdr"
STIM_100_VHDR = DATA_DIR / "exp05-phantom-rs-STIM-ON-GT-cTBS-run01.vhdr"
STIM_30_VHDR = DATA_DIR / "exp05-phantom-rs-STIM-ON-30pctIntensity-GT-cTBS-run01.vhdr"
OUTPUT_DIRECTORY = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\EXP_05\channel_avg")
OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)

EPOCH_PRE_S = 0.5


# ============================================================
# 1) LOAD DATA
# ============================================================
raw_base = mne.io.read_raw_brainvision(str(BASELINE_VHDR), preload=True, verbose=False)
raw_100 = mne.io.read_raw_brainvision(str(STIM_100_VHDR), preload=True, verbose=False)
raw_30 = mne.io.read_raw_brainvision(str(STIM_30_VHDR), preload=True, verbose=False)
sfreq = float(raw_100.info["sfreq"])


# ============================================================
# 2) DEFINE EEG CHANNEL SET AND STIM-TIMED EVENTS
# ============================================================
stim_marker_100 = raw_100.copy().pick(["stim"]).get_data()[0]
stim_marker_30 = raw_30.copy().pick(["stim"]).get_data()[0]
block_onsets_100, block_offsets_100 = preprocessing.detect_stim_blocks(stim_marker_100, sfreq)
block_onsets_30, block_offsets_30 = preprocessing.detect_stim_blocks(stim_marker_30, sfreq)

on_durations_100_s = (block_offsets_100 - block_onsets_100) / sfreq
on_durations_30_s = (block_offsets_30 - block_onsets_30) / sfreq
off_durations_100_s = (block_onsets_100[1:] - block_offsets_100[:-1]) / sfreq
off_durations_30_s = (block_onsets_30[1:] - block_offsets_30[:-1]) / sfreq
median_on_100_s = float(np.median(on_durations_100_s))
median_on_30_s = float(np.median(on_durations_30_s))
median_off_100_s = float(np.median(off_durations_100_s))
median_off_30_s = float(np.median(off_durations_30_s))
max_cycle_s = max(median_on_100_s + median_off_100_s, median_on_30_s + median_off_30_s)

eeg_channels = [
    channel_name
    for channel_name in raw_100.ch_names
    if channel_name in raw_base.ch_names
    and channel_name in raw_30.ch_names
    and channel_name.lower() not in ("stim", "ground_truth")
    and not channel_name.startswith("STI")
]

raw_base_eeg = raw_base.copy().pick(eeg_channels)
raw_100_eeg = raw_100.copy().pick(eeg_channels)
raw_30_eeg = raw_30.copy().pick(eeg_channels)

baseline_stride_samples = int(round(max_cycle_s * sfreq))
baseline_start_sample = int(round(2.0 * sfreq))
baseline_stop_sample = raw_base_eeg.n_times - int(round(1.0 * sfreq))
baseline_pseudo_onsets = np.arange(baseline_start_sample, baseline_stop_sample, baseline_stride_samples, dtype=int)

events_100 = np.column_stack([block_onsets_100, np.zeros(len(block_onsets_100), dtype=int), np.ones(len(block_onsets_100), dtype=int)])
events_30 = np.column_stack([block_onsets_30, np.zeros(len(block_onsets_30), dtype=int), np.ones(len(block_onsets_30), dtype=int)])
events_base = np.column_stack([baseline_pseudo_onsets, np.zeros(len(baseline_pseudo_onsets), dtype=int), np.ones(len(baseline_pseudo_onsets), dtype=int)])

print(f"100% blocks: {len(block_onsets_100)}  |  ON={median_on_100_s:.3f} s  OFF={median_off_100_s:.3f} s")
print(f" 30% blocks: {len(block_onsets_30)}  |  ON={median_on_30_s:.3f} s  OFF={median_off_30_s:.3f} s")
print(f"Baseline pseudo-events: {len(events_base)}")


# ============================================================
# 3) EPOCH ALL EEG CHANNELS
# ============================================================
post_samples = int(round(max_cycle_s * sfreq))
epoch_tmax_s = (post_samples - 1) / sfreq
epoch_kwargs = dict(event_id=1, tmin=-EPOCH_PRE_S, tmax=epoch_tmax_s, baseline=None, preload=True, verbose=False)

epochs_base = mne.Epochs(raw_base_eeg, events_base, **epoch_kwargs)
epochs_30 = mne.Epochs(raw_30_eeg, events_30, **epoch_kwargs)
epochs_100 = mne.Epochs(raw_100_eeg, events_100, **epoch_kwargs)

epochs_base_uv = epochs_base.get_data() * 1e6
epochs_30_uv = epochs_30.get_data() * 1e6
epochs_100_uv = epochs_100.get_data() * 1e6
epoch_time_seconds = epochs_base.times

mean_base_uv = np.mean(epochs_base_uv, axis=0)
mean_30_uv = np.mean(epochs_30_uv, axis=0)
mean_100_uv = np.mean(epochs_100_uv, axis=0)

print(f"Epochs used  baseline={len(epochs_base_uv)}  30%={len(epochs_30_uv)}  100%={len(epochs_100_uv)}")


# ============================================================
# 4) SAVE FIGURE AND SUMMARY
# ============================================================
fig, axes = plt.subplots(len(eeg_channels), 1, figsize=(12, 2.5 * len(eeg_channels)), sharex=True, constrained_layout=True)
axes = np.atleast_1d(axes)

for channel_index, (ax, channel_name) in enumerate(zip(axes, eeg_channels)):
    ax.axvspan(0.0, median_on_100_s, color="salmon", alpha=0.15)
    if abs(median_on_30_s - median_on_100_s) > (1.0 / sfreq):
        ax.axvspan(0.0, median_on_30_s, color="cornflowerblue", alpha=0.08)
    ax.plot(epoch_time_seconds, mean_base_uv[channel_index], "k", lw=0.9, alpha=0.7, label=f"baseline (n={len(epochs_base_uv)})" if channel_index == 0 else "_nolegend_")
    ax.plot(epoch_time_seconds, mean_30_uv[channel_index], "C0", lw=1.1, label=f"30% (n={len(epochs_30_uv)})" if channel_index == 0 else "_nolegend_")
    ax.plot(epoch_time_seconds, mean_100_uv[channel_index], "C3", lw=1.1, label=f"100% (n={len(epochs_100_uv)})" if channel_index == 0 else "_nolegend_")
    ax.set_ylabel(channel_name, fontsize=8, rotation=0, labelpad=32, va="center")
    ax.grid(True, alpha=0.2)

axes[0].legend(fontsize=8, loc="upper right")
axes[-1].set_xlabel("Time relative to STIM-defined ON-block onset (s)")
fig.suptitle("exp05: Epoch-averaged EEG across all channels", fontsize=13, fontweight="bold")

figure_path = OUTPUT_DIRECTORY / "fig_all_channels_epoch_avg.png"
fig.savefig(figure_path, dpi=200)
plt.close(fig)
print(f"Saved -> {figure_path}")

summary_lines = [
    "exp05 all-channel epoch average",
    f"100_blocks={len(block_onsets_100)}",
    f"100_on_median_s={median_on_100_s:.3f}",
    f"100_off_median_s={median_off_100_s:.3f}",
    f"30_blocks={len(block_onsets_30)}",
    f"30_on_median_s={median_on_30_s:.3f}",
    f"30_off_median_s={median_off_30_s:.3f}",
    f"baseline_events={len(events_base)}",
    f"baseline_epochs={len(epochs_base_uv)}",
    f"30_epochs={len(epochs_30_uv)}",
    f"100_epochs={len(epochs_100_uv)}",
]
summary_path = OUTPUT_DIRECTORY / "channel_avg_summary.txt"
summary_path.write_text("\n".join(summary_lines) + "\n", encoding="utf-8")
print(f"Saved -> {summary_path}")
