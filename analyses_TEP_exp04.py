from pathlib import Path

import mne
import numpy as np
from scipy.optimize import curve_fit

import plot_helpers
import preprocessing


# ============================================================
# FIXED INPUTS
# Edit only this block.
# ============================================================
INPUT_DIRECTORY = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\TIMS_data_sync\pilot\doseresp")
PRE_VHDR_PATH = INPUT_DIRECTORY / "exp04-sub01-baseline-fullOFFstim-run01.vhdr"
STIM_VHDR_PATH = INPUT_DIRECTORY / "exp04-sub01-stim-mod-50hz-pulse-run01.vhdr"
POST_VHDR_PATH = INPUT_DIRECTORY / "exp04-sub01-baseline-after--fullOFFstim-run02.vhdr"

OUTPUT_DIRECTORY = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\EXP04_TEP_analysis")
OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)

BAD_CHANNELS = ["F8", "FT10", "T8", "TP10", "P7", "TP9", "FT9", "F7", "Fp2", "C3", "Fz", "CP1"]
ROI_CHANNELS = ["FC5", "FC1", "Pz", "CP5","CP6"]


# ============================================================
# 1) LOAD THE THREE RECORDINGS
# ============================================================
raw_pre = mne.io.read_raw_brainvision(str(PRE_VHDR_PATH), preload=True, verbose=False)
raw_stim = mne.io.read_raw_brainvision(str(STIM_VHDR_PATH), preload=True, verbose=False)
raw_post = mne.io.read_raw_brainvision(str(POST_VHDR_PATH), preload=True, verbose=False)

# Keep EEG only and drop the same known bad channels in every condition.
raw_pre.pick_types(eeg=True).drop_channels(BAD_CHANNELS)
raw_stim.pick_types(eeg=True).drop_channels(BAD_CHANNELS)
raw_post.pick_types(eeg=True).drop_channels(BAD_CHANNELS)

# Select ROI Channels
raw_pre.pick(ROI_CHANNELS)
raw_stim.pick(ROI_CHANNELS)
raw_post.pick(ROI_CHANNELS)

# Pre / stim / post must stay directly comparable.
if raw_pre.ch_names != raw_stim.ch_names or raw_pre.ch_names != raw_post.ch_names:
    raise ValueError("Channel mismatch across pre/stim/post.")
if float(raw_pre.info["sfreq"]) != float(raw_stim.info["sfreq"]) or float(raw_pre.info["sfreq"]) != float(raw_post.info["sfreq"]):
    raise ValueError("Sampling-rate mismatch across pre/stim/post.")

sfreq = float(raw_stim.info["sfreq"])


# ============================================================
# 2) MANUAL ONSET DETECTION FROM CP6 IN THE STIM RUN
# ============================================================
# CP6 is used only to detect the repeated stimulation blocks.
cp6_data = raw_stim.copy().pick(["CP6"]).get_data()[0]

# Demean with the first 10 s, which are clean pre-stimulation baseline here.
cp6_data = cp6_data - np.mean(cp6_data[:10000])

# A large first derivative marks the start of a stimulation block.
candidate_onsets = np.where(np.abs(np.diff(cp6_data)) > 0.01)[0] + 1
if candidate_onsets.size == 0:
    raise ValueError("Manual onset detection found no candidates.")

# Keep only the first jump in each block.
stim_block_onsets_samples = [int(candidate_onsets[0])]
for sample_index in candidate_onsets[1:]:
    if sample_index - stim_block_onsets_samples[-1] > 1200:
        stim_block_onsets_samples.append(int(sample_index))
stim_block_onsets_samples = np.asarray(stim_block_onsets_samples, dtype=int)

# In this recording the actual pulse is 1008 samples after the detected block start.
stim_pulse_onsets_samples = stim_block_onsets_samples + 1008


# ============================================================
# 3) BUILD MATCHED PRE / STIM / POST EVENTS
# ============================================================
events_pre, events_stim, events_post = preprocessing.build_matched_triplet_events(
    stim_pulse_onsets_samples=stim_pulse_onsets_samples,
    pre_n_times=raw_pre.n_times,
    stim_n_times=raw_stim.n_times,
    post_n_times=raw_post.n_times,
    sampling_rate_hz=sfreq,
    epoch_tmin_s=-2.0,
    epoch_tmax_s=2.5,
)


# ============================================================
# 4) BUILD EPOCHS WITH THE SAME LONG WINDOW
# ============================================================
epochs_pre = mne.Epochs(raw_pre, events_pre, event_id=1, tmin=-2.0, tmax=2.5, baseline=None, preload=True, verbose=False)
epochs_stim = mne.Epochs(raw_stim, events_stim, event_id=1, tmin=-2.0, tmax=2.5, baseline=None, preload=True, verbose=False)
epochs_post = mne.Epochs(raw_post, events_post, event_id=1, tmin=-2.0, tmax=2.5, baseline=None, preload=True, verbose=False)


# ============================================================
# 5) APPLY THE SAME TEP PIPELINE TO ALL THREE CONDITIONS
# ============================================================
# Same baseline, same crop, same low-pass. No condition-specific tricks.
for epochs in (epochs_pre, epochs_stim, epochs_post):
    epochs.apply_baseline((-1.9, -1.3))
    epochs.crop(tmin=0.08, tmax=0.50)
    epochs.filter(l_freq=None, h_freq=42.0, verbose=False)


# ============================================================
# 6) REMOVE THE SLOW POST-PULSE DECAY WITH A PER-CHANNEL EXPONENTIAL FIT
# ============================================================
# Fit the decay on each condition's evoked response, then subtract that fitted
# decay from every epoch of that channel so the TEP sits around its local zero.
for epochs in (epochs_pre, epochs_stim, epochs_post):
    evoked_for_decay = epochs.average()
    time_seconds = evoked_for_decay.times
    fit_mask = time_seconds > 0.02

    for channel_index in range(len(evoked_for_decay.ch_names)):
        channel_trace = evoked_for_decay.data[channel_index]
        fit_parameters, _ = curve_fit(
            lambda t, amplitude, tau, offset: amplitude * np.exp(-t / tau) + offset,
            time_seconds[fit_mask],
            channel_trace[fit_mask],
            maxfev=10000,
        )
        fitted_decay = (
            fit_parameters[0] * np.exp(-time_seconds / fit_parameters[1]) + fit_parameters[2]
        )
        epochs._data[:, channel_index, :] -= fitted_decay[np.newaxis, :]


# ============================================================
# 7) AVERAGE EACH CONDITION
# ============================================================
evoked_pre = epochs_pre.average()
evoked_stim = epochs_stim.average()
evoked_post = epochs_post.average()


# ============================================================
# 8) SAVE THE 3-PANEL TEP FIGURE
# ============================================================
figure_path = OUTPUT_DIRECTORY / "tep_pre_stim_post_triptych.png"
plot_helpers.plot_tep_triptych(
    evoked_pre=evoked_pre,
    evoked_stim=evoked_stim,
    evoked_post=evoked_post,
    output_path=figure_path,
)

print(f"Saved -> {figure_path}")
print(f"Detected stim pulses: {stim_pulse_onsets_samples.size}")
print(f"Matched epochs per condition: {len(epochs_stim)}")
print(f"Retained EEG channels: {len(raw_stim.ch_names)}")
