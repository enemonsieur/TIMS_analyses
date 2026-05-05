from pathlib import Path
import warnings

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import mne
import numpy as np

from preprocessing import detect_stim_onsets

# -------------------------
# CONFIG CONSTANTS
# -------------------------
STIM_VHDR_PATH = r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\TIMS_data_sync\pilot\doseresp\exp03-phantom-stim-pulse-10hz-GT10s-run03.vhdr"
BASELINE_VHDR_PATH = r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\TIMS_data_sync\pilot\doseresp\exp03-phantom-baseline-10hz-GT-fullOFFstim-run01.vhdr"
OUTPUT_DIRECTORY = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\exp03_pulse_centered_analysis_run03")

REFERENCE_CHANNEL = "C4"
CANDIDATE_EEG_PICKS = ["Fp1", "F3", "FC5", "FC1", "C3", "C4", "FC6", "FC2", "F4", "F8", "Fp2", "Cz"]
FLAT_STD_UV_THRESHOLD = 1e-6

EPOCH_WINDOW_S = (-2.0, 1.0)
ARTIFACT_BLOCK_WINDOW_S = (-1.000, 0.030)
ARTIFACT_PRECENTER_WINDOW_S = (-1.25, -1.05)
ARTIFACT_POSTCENTER_WINDOW_S = (0.05, 0.30)
FINAL_WINDOW_S = (0.08, 1.00)
FINAL_HPF_HZ = 0.5
FINAL_HPF_IIR_ORDER = 4

SAVE_FINAL_FIF = True
FINAL_EPOCHS_FIF_PATH = OUTPUT_DIRECTORY / "stim_epochs_final_0p08to1p00_hpf0p5_noica-epo.fif"

OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)

# -------------------------
# LOAD
# -------------------------
with warnings.catch_warnings():
    warnings.filterwarnings("ignore", message="No coordinate information found for channels .*", category=RuntimeWarning)
    warnings.filterwarnings("ignore", message="Channels contain different highpass filters.*", category=RuntimeWarning)
    warnings.filterwarnings("ignore", message="Channels contain different lowpass filters.*", category=RuntimeWarning)
    warnings.filterwarnings("ignore", message="Not setting positions of .* misc channels found in montage.*", category=RuntimeWarning)
    stim_raw = mne.io.read_raw_brainvision(STIM_VHDR_PATH, preload=True, verbose=False)
    baseline_raw = mne.io.read_raw_brainvision(BASELINE_VHDR_PATH, preload=True, verbose=False)

if float(stim_raw.info["sfreq"]) != float(baseline_raw.info["sfreq"]):
    raise ValueError("Stim and baseline sampling rates do not match.")
sfreq = float(stim_raw.info["sfreq"])

required_channels = ["stim", "ground_truth", REFERENCE_CHANNEL]
missing_stim = [channel_name for channel_name in required_channels if channel_name not in stim_raw.ch_names]
missing_base = [channel_name for channel_name in required_channels if channel_name not in baseline_raw.ch_names]
if missing_stim:
    raise ValueError(f"Stim recording missing required channels: {missing_stim}")
if missing_base:
    raise ValueError(f"Baseline recording missing required channels: {missing_base}")

# -------------------------
# CHANNEL PICK
# -------------------------
available_eeg_channels = [
    channel_name
    for channel_name in stim_raw.ch_names
    if channel_name not in {"stim", "ground_truth"} 
]
candidate_channels = [
    channel_name
    for channel_name in CANDIDATE_EEG_PICKS
    if channel_name in available_eeg_channels and channel_name in baseline_raw.ch_names
]
if not candidate_channels:
    raise ValueError("No candidate EEG channels found in stim recording.")

baseline_eeg = baseline_raw.copy().pick(candidate_channels).get_data()  # shape: (n_channels, n_times) in Volts
channel_std_uv = baseline_eeg.std(axis=1) * 1e6
good_mask = channel_std_uv > FLAT_STD_UV_THRESHOLD
good_eeg_channels = [channel_name for channel_name, keep in zip(candidate_channels, good_mask) if keep]
bad_eeg_channels = [channel_name for channel_name, keep in zip(candidate_channels, good_mask) if not keep]
if not good_eeg_channels:
    raise ValueError("All candidate EEG channels were rejected as flat.")

reference_channel = "Cz" if "Cz" in good_eeg_channels else good_eeg_channels[0]

# -------------------------
# STIM -> EVENTS + EPOCHING
# -------------------------
# Detect pulse onsets from the stim marker channel; these drive epoch alignment.
stim_marker = stim_raw.copy().pick(["stim"]).get_data()[0]
stim_onsets_samples, median_ioi_seconds, _, _ = detect_stim_onsets(stim_marker=stim_marker, sampling_rate_hz=sfreq)
# MNE event format: [sample_index, 0, event_id=1].
events = np.c_[stim_onsets_samples, np.zeros_like(stim_onsets_samples), np.ones_like(stim_onsets_samples)].astype(int)

raw_eeg = stim_raw.copy().pick(good_eeg_channels)
# No baseline correction here — artifact zeroing handles the pre-pulse period explicitly below.
epochs_raw = mne.Epochs(
    raw_eeg,
    events,
    event_id=1,
    tmin=EPOCH_WINDOW_S[0],
    tmax=EPOCH_WINDOW_S[1],
    baseline=None,
    preload=True,
    verbose=False,
)

# -------------------------
# ARTIFACT HANDLING (explicit numpy lines)
# -------------------------
epoch_time_seconds = epochs_raw.times
artifact_mask = (epoch_time_seconds >= ARTIFACT_BLOCK_WINDOW_S[0]) & (epoch_time_seconds <= ARTIFACT_BLOCK_WINDOW_S[1])
pre_center_mask = (epoch_time_seconds >= ARTIFACT_PRECENTER_WINDOW_S[0]) & (epoch_time_seconds <= ARTIFACT_PRECENTER_WINDOW_S[1])
post_center_mask = (epoch_time_seconds >= ARTIFACT_POSTCENTER_WINDOW_S[0]) & (epoch_time_seconds <= ARTIFACT_POSTCENTER_WINDOW_S[1])
pre_segment_mask = epoch_time_seconds < ARTIFACT_BLOCK_WINDOW_S[0]
post_segment_mask = epoch_time_seconds > ARTIFACT_BLOCK_WINDOW_S[1]

if not np.any(artifact_mask) or not np.any(pre_center_mask) or not np.any(post_center_mask):
    raise ValueError("One or more artifact windows do not overlap epoch time axis.")
if np.any(artifact_mask & pre_center_mask) or np.any(artifact_mask & post_center_mask):
    raise ValueError("Center windows must not overlap artifact window.")
if not np.any(pre_segment_mask) or not np.any(post_segment_mask):
    raise ValueError("Artifact block leaves no pre or post segment.")

blockzero_data = epochs_raw.get_data(copy=True)  # shape: (n_epochs, n_channels, n_samples) in Volts
blockzero_data[:, :, pre_segment_mask] -= blockzero_data[:, :, pre_center_mask].mean(axis=-1, keepdims=True)
blockzero_data[:, :, post_segment_mask] -= blockzero_data[:, :, post_center_mask].mean(axis=-1, keepdims=True)
blockzero_data[:, :, artifact_mask] = 0.0
if not np.all(np.isfinite(blockzero_data)):
    raise RuntimeError("Artifact handling produced non-finite values.")

epochs_blockzero = mne.EpochsArray(
    blockzero_data,
    epochs_raw.info.copy(),
    tmin=float(epoch_time_seconds[0]),
    baseline=None,
    verbose=False,
)

# -------------------------
# FINAL CROP + HPF
# -------------------------
epochs_postpulse = epochs_blockzero.copy().crop(tmin=FINAL_WINDOW_S[0], tmax=FINAL_WINDOW_S[1])
epochs_final = epochs_postpulse.copy().filter(
    l_freq=FINAL_HPF_HZ,
    h_freq=None,
    method="iir",
    iir_params={"order": FINAL_HPF_IIR_ORDER, "ftype": "butter"},
    verbose=False,
)

# -------------------------
# SIMPLE MNE PLOTS
# -------------------------
stage_epochs = {
    "01_raw_epoch": epochs_raw,
    "02_blockzero": epochs_blockzero,
    "03_postpulse": epochs_postpulse,
    "04_final_hpf": epochs_final,
}
for stage_name, stage in stage_epochs.items():
    figure = stage.average().plot(spatial_colors=False, show=False)
    figure.savefig(OUTPUT_DIRECTORY / f"{stage_name}_evoked.png", dpi=220)
    plt.close(figure)

# -------------------------
# OPTIONAL SAVE
# -------------------------
if SAVE_FINAL_FIF:
    epochs_final.save(FINAL_EPOCHS_FIF_PATH, overwrite=True, verbose=False)

print(
    f"Done. n_onsets={stim_onsets_samples.size}, n_epochs_valid={len(epochs_raw)}, "
    f"median_ioi_s={median_ioi_seconds:.3f}, bad_channels={bad_eeg_channels}"
)
