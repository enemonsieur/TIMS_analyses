# Do pre-stim-post evoked response waveforms show consistent channel activity
# across all 5 intensity blocks in the single continuous run02 phantom recording?

from pathlib import Path
import warnings
import mne
import numpy as np
from scipy.optimize import curve_fit
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import plot_helpers
import preprocessing

# ============================================================
# CONFIG
# ============================================================
DATA_DIR = Path(r"c:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\TIMS_data_sync\pilot\doseresp")
VHDR_PATH = DATA_DIR / "exp06-STIM-iTBS_run02.vhdr"
OUTPUT_DIR = Path(r"c:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\EXP06")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

BAD_CHANNELS = ["F8", "FT10", "T8", "TP10", "P7", "TP9", "FT9", "F7", "Fp2", "C3", "Fz", "CP1"]
ROI_CHANNELS = ["FC5", "FC1", "Pz", "CP5", "CP6"]

# ============================================================
# 1) LOAD THE RUN02 RECORDING
# ============================================================
with warnings.catch_warnings():
    warnings.filterwarnings("ignore", message="No coordinate information*")
    warnings.filterwarnings("ignore", message="Online software filter*")
    warnings.filterwarnings("ignore", message="Not setting positions*")
    raw_full = mne.io.read_raw_brainvision(str(VHDR_PATH), preload=True, verbose=False)

if "stim" not in raw_full.ch_names or "ground_truth" not in raw_full.ch_names:
    raise RuntimeError("Missing required stim and/or ground_truth channels.")

sfreq = float(raw_full.info["sfreq"])

# Keep EEG only and drop the same known bad channels (if they exist)
raw_full.pick_types(eeg=True).drop_channels(BAD_CHANNELS, on_missing='ignore')

# Select ROI channels (matching EXP04)
raw_full.pick(ROI_CHANNELS)

# Extract stim trace before dropping aux channels
raw_temp = mne.io.read_raw_brainvision(str(VHDR_PATH), preload=True, verbose=False)
stim_trace = raw_temp.copy().pick(["stim"]).get_data()[0]

print(f"Retained EEG channels: {len(raw_full.ch_names)}")

# ============================================================
# 2) DETECT STIMULATION PULSE ONSETS
# ============================================================
stim_pulse_onsets, _, _, _ = preprocessing.detect_stim_onsets(stim_trace, sfreq)
print(f"Detected stim pulses: {stim_pulse_onsets.size}")

# ============================================================
# 3) BUILD MATCHED PRE / STIM / POST EVENTS
# ============================================================
# For a single continuous file, all three event arrays come from the same recording.
events_pre, events_stim, events_post = preprocessing.build_matched_triplet_events(
    stim_pulse_onsets_samples=stim_pulse_onsets,
    pre_n_times=raw_full.n_times,
    stim_n_times=raw_full.n_times,
    post_n_times=raw_full.n_times,
    sampling_rate_hz=sfreq,
    epoch_tmin_s=-2.0,
    epoch_tmax_s=2.5,
)

# ============================================================
# 4) BUILD EPOCHS WITH THE SAME LONG WINDOW
# ============================================================
epochs_pre = mne.Epochs(raw_full, events_pre, event_id=1, tmin=-2.0, tmax=2.5, baseline=None, preload=True, verbose=False)
epochs_stim = mne.Epochs(raw_full, events_stim, event_id=1, tmin=-2.0, tmax=2.5, baseline=None, preload=True, verbose=False)
epochs_post = mne.Epochs(raw_full, events_post, event_id=1, tmin=-2.0, tmax=2.5, baseline=None, preload=True, verbose=False)

# ============================================================
# 5) APPLY THE SAME TEP PIPELINE TO ALL THREE CONDITIONS
# ============================================================
for epochs in (epochs_pre, epochs_stim, epochs_post):
    epochs.apply_baseline((-1.9, -1.3))
    epochs.crop(tmin=0.08, tmax=0.50)
    epochs.filter(l_freq=None, h_freq=42.0, verbose=False)

# ============================================================
# 6) REMOVE THE SLOW POST-PULSE DECAY WITH A PER-CHANNEL EXPONENTIAL FIT
# ============================================================
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
# 8) SAVE THE 3-PANEL TEP FIGURE (using plot_joint with aligned axes)
# ============================================================
# Create a combined figure with 3 rows: one per condition (pre/stim/post)
# Each row uses MNE's plot_joint() layout: butterfly + topomaps

fig = plt.figure(figsize=(16, 13), constrained_layout=False)
gs = gridspec.GridSpec(3, 1, figure=fig, height_ratios=[1, 1, 1])

evokeds = [
    ("PRE", evoked_pre, "gray"),
    ("STIM", evoked_stim, "steelblue"),
    ("POST", evoked_post, "seagreen"),
]

# Plot each condition using plot_joint on a subplot
for row_idx, (label, evoked, color) in enumerate(evokeds):
    # Create a subplot for this row
    ax_row = fig.add_subplot(gs[row_idx])

    # Use evoked.plot_joint() with ts_args to plot on custom axes
    # The ts_args parameter allows custom styling of the butterfly plot
    ts_args = {"spatial_colors": True, "zorder": "std"}
    topomap_args = {"outlines": "head"}

    # Call plot_joint with show=False to get the figure
    # (We'll extract its content and add it to our grid)
    fig_joint = evoked.plot_joint(
        times="peaks",
        title=f"{label}  (n={evoked.nave})",
        show=False,
        ts_args=ts_args,
        topomap_args=topomap_args,
    )
    # For now, save individual joint plots
    out_path_joint = OUTPUT_DIR / f"exp06_run02_tep_{label.lower()}_joint.png"
    fig_joint.savefig(out_path_joint, dpi=220, bbox_inches="tight")
    plt.close(fig_joint)
    print(f"Saved joint plot -> {out_path_joint}")

# Also save a simple side-by-side triptych using plot_tep_triptych for reference
figure_path = OUTPUT_DIR / "exp06_run02_tep_pre_stim_post_triptych.png"
plot_helpers.plot_tep_triptych(
    evoked_pre=evoked_pre,
    evoked_stim=evoked_stim,
    evoked_post=evoked_post,
    output_path=figure_path,
)

print(f"Saved triptych -> {figure_path}")
print(f"Matched epochs per condition: {len(epochs_stim)}")
