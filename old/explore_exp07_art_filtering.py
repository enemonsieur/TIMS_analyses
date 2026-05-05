"""EXP07 artifact filtering: load run02, visualize channels, detect blocks."""

from pathlib import Path
import warnings

import matplotlib.pyplot as plt
import mne
import numpy as np

import preprocessing


# ===== Config =================================================================
DATA_DIRECTORY = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\TIMS_data_sync\pilot\doseresp")
STIM_VHDR_PATH = DATA_DIRECTORY / "exp07-STIM-iTBS_run02_mod100pct.vhdr"
OUTPUT_DIRECTORY = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\EXP07")
OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)

SIGNAL_BAND_HZ = (12.5, 14.5)
RUN02_STIM_THRESHOLD_FRACTION = 0.13
EXCLUDED_CHANNELS = []


# ===== Load ===================================================================
with warnings.catch_warnings():
    warnings.filterwarnings("ignore", message="No coordinate information found for channels*")
    warnings.filterwarnings("ignore", message="Online software filter detected*")
    warnings.filterwarnings("ignore", message="Not setting positions of 2 misc channels found in montage*")
    raw_stim_full = mne.io.read_raw_brainvision(str(STIM_VHDR_PATH), preload=True, verbose=False)

if "stim" not in raw_stim_full.ch_names or "ground_truth" not in raw_stim_full.ch_names:
    raise RuntimeError("Stim run is missing required channels: stim and ground_truth.")

sampling_rate_hz = float(raw_stim_full.info["sfreq"])
stim_marker_v = raw_stim_full.copy().pick(["stim"]).get_data()[0]
ground_truth_stim_v = raw_stim_full.copy().pick(["ground_truth"]).get_data()[0]

# Drop STIM and ground_truth, keep EEG
eeg_channel_names = [ch for ch in raw_stim_full.ch_names if ch.lower() not in ("stim", "ground_truth")]
if EXCLUDED_CHANNELS:
    eeg_channel_names = [ch for ch in eeg_channel_names if ch not in EXCLUDED_CHANNELS]

raw_stim_eeg = raw_stim_full.copy().pick(eeg_channel_names)

if len(raw_stim_eeg.ch_names) == 0:
    raise RuntimeError("No EEG channels remaining after dropping STIM and ground_truth.")

raw_stim_eeg._data -= raw_stim_eeg._data.mean(axis=-1, keepdims=True)




# ===== Remove DC offset from CP2 ==============================================
cp2_idx = raw_stim_eeg.ch_names.index("CP2")
plt.plot(np.arange(60000) / 1000, raw_stim_eeg._data[cp2_idx, :60000] * 1e6, label="Before")
poly = np.polyfit(np.arange(raw_stim_eeg.n_times), raw_stim_eeg._data[cp2_idx], 1)
raw_stim_eeg._data[cp2_idx] -= np.polyval(poly, np.arange(raw_stim_eeg.n_times))
#plt.plot(np.arange(60000) / 1000, raw_stim_eeg._data[cp2_idx, :60000] * 1e6, label="After"); 
plt.legend(); plt.show()


# ===== Metadata ==============================================================
duration_s = raw_stim_eeg.n_times / sampling_rate_hz
print(f"run=run02 | len={duration_s:.1f}s | chn={len(raw_stim_eeg.ch_names)} | Hz={sampling_rate_hz:.1f}")


# ===== Visualize: Save timecourse and PSD ===================================
# ===== Visualize: Timecourse and PSD =========================================
raw_stim_eeg.plot(picks='CP2', duration=30, n_channels=len(raw_stim_eeg.ch_names))
raw_stim_eeg.plot_psd()
plt.show()
schneurkel
# Plot STIM and ground_truth (first 20 seconds)
time_s = np.arange(stim_marker_v[:80000].shape[0]) / sampling_rate_hz
plt.figure(figsize=(14, 4))
plt.plot(time_s, stim_marker_v[:80000], label="STIM", alpha=0.7)
plt.plot(time_s, ground_truth_stim_v[:80000], label="Ground Truth", alpha=0.7)
plt.xlabel("Time (s)")
plt.ylabel("Amplitude (V)")
plt.legend()
plt.grid(True, alpha=0.3)
plt.tight_layout()
plt.show()


# ===== Phase 2: Block Detection ==============================================
print("\nDetecting stimulation blocks...")
block_onsets_samples, block_offsets_samples = preprocessing.detect_stim_blocks(
    stim_marker_v,
    sampling_rate_hz,
    threshold_fraction=RUN02_STIM_THRESHOLD_FRACTION,
)

print(f"Found {len(block_onsets_samples)} ON blocks.")
print(f"Block onsets (first 10): {block_onsets_samples[:10]}")
print(f"Block offsets (first 10): {block_offsets_samples[:10]}")
