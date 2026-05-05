"""Exp03 first figure: raw EEG overlay for 10-40 s (4 channels, single axis)."""

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import mne
import numpy as np


# constants
STIM_VHDR_PATH = Path(
    r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\TIMS_data_sync\pilot\doseresp\exp03-phantom-stim-pulse-10hz-GT10s-run03.vhdr"
)
OUTPUT_DIRECTORY = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\exp03_pulse_centered_analysis_run03")

T0_SECONDS = 10.0
T1_SECONDS = 40.0
EEG_PICKS = ["C3"] # , "Cz", "FC1", "C3"

OUTPUT_PATH = OUTPUT_DIRECTORY / f"exp03_raw_overlay_10_40s_{'_'.join(EEG_PICKS)}.png"

# load
OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)
if not STIM_VHDR_PATH.exists():
    raise FileNotFoundError(f"Missing required file: {STIM_VHDR_PATH}")

raw = mne.io.read_raw_brainvision(str(STIM_VHDR_PATH), preload=True, verbose=False)
sampling_rate_hz = float(raw.info["sfreq"])


# analyze
start_index = int(T0_SECONDS * sampling_rate_hz)
stop_index = int(T1_SECONDS * sampling_rate_hz)
time_seconds = np.arange(start_index, stop_index, dtype=float) / sampling_rate_hz

eeg_channels = [channel_name for channel_name in EEG_PICKS if channel_name in raw.ch_names]
if not eeg_channels:
    raise RuntimeError(f"None of EEG_PICKS found in raw channels: {EEG_PICKS}")
missing_channels = [channel_name for channel_name in EEG_PICKS if channel_name not in raw.ch_names]
if missing_channels:
    print(f"Warning: skipping missing EEG channels: {missing_channels}")

eeg_data_uv = raw.copy().pick(eeg_channels).get_data()[:, start_index:stop_index] * 1e6


# save
figure, axis = plt.subplots(figsize=(14, 4.8), constrained_layout=True)
for channel_name, signal_uv in zip(eeg_channels, eeg_data_uv):
    axis.plot(time_seconds, signal_uv, lw=0.9, label=channel_name)

axis.set_xlabel("Time (s)")
axis.set_ylabel("Amplitude (uV)")
axis.grid(True, alpha=0.2)
axis.legend(loc="upper right")
figure.suptitle(f"Exp03 raw {', '.join(EEG_PICKS)} overlay: {T0_SECONDS:.0f}-{T1_SECONDS:.0f} s", fontsize=12, fontweight="bold")
figure.savefig(OUTPUT_PATH, dpi=200)
plt.close(figure)

print(f"Saved {OUTPUT_PATH}")
