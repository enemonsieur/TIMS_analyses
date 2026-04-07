"""Which exp06 baseline EEG channels look unstable enough to consider removing?"""

from pathlib import Path
import warnings

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import mne
import numpy as np


# ===== Config =================================================================
BASELINE_VHDR_PATH = Path(
    r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\TIMS_data_sync\pilot\doseresp\exp06-baseline-gt_12hz_noSTIM_run01.vhdr"
)
OUTPUT_DIRECTORY = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\EXP06")
OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)

# Skip the first seconds because BrainVision recordings can include short
# startup transients that would dominate the visual QC unfairly.
#TODO: Modify SKIPT.md -- parmaeters/variables should have small shorts comments to explain them. These are Structure comments. 
# Short, simple and guide the Eye of the reader
VIEW_START_S = 2.0
VIEW_DURATION_S = 20.0
SELECTED_VIEW_DURATION_S = 5.0
VIEW_BAND_HZ = (1.0, 40.0)
NOTCH_HZ = 50.0
EXCLUDED_CHANNELS = {"TP9", "Fp1", "TP10"}
N_SELECTED_TIMECOURSE_CHANNELS = 6
ACCENT_COLOR = "darkorange"
CONTEXT_COLOR = "0.55"


# ===== Load ===================================================================
# Read the baseline recording directly and hide known BrainVision metadata
# warnings so the script output stays focused on the QC result.
#TODO: Modify SKIPT.md  I dont think you need these, just remove that. Makes no sense
with warnings.catch_warnings():
    warnings.filterwarnings("ignore", message="No coordinate information found for channels*")
    warnings.filterwarnings("ignore", message="Channels contain different highpass filters*")
    warnings.filterwarnings("ignore", message="Channels contain different lowpass filters*")
    warnings.filterwarnings("ignore", message="Not setting positions of 2 misc channels found in montage*")
    warnings.filterwarnings(
        "ignore",
        message="Online software filter detected. Using software filter settings and ignoring hardware values",
    )
    raw = mne.io.read_raw_brainvision(str(BASELINE_VHDR_PATH), preload=True, verbose=False)

# Keep only EEG traces for the channel scan, leave stim-style channels out,
# and remove channels that were already judged too artifact-heavy to keep.
#TODO: Modify SKIPT.md  -- Naming of obvious stuff like sfreq or t/duration (for time) is fine. make short naming - add strx. comments
sampling_rate_hz = float(raw.info["sfreq"])
baseline_duration_s = raw.n_times / sampling_rate_hz

##TODO: Modify SKIPT.md -- Again, lacks strx. comments. 
eeg_channel_names = [
    channel_name
    for channel_name in raw.ch_names
    if channel_name.lower() not in {"stim", "ground_truth"}
    and not channel_name.upper().startswith("STI")
    and channel_name not in EXCLUDED_CHANNELS
]

#TODO: Modify SKIPT.md -- The strcx. comment Block 1 isnt bad but make it more FLASHY so it retains attention and guide the reader. 
# Like make a block or comment or something
# ===== Block 1: Prepare readable baseline view =================================
#TODO: Modify SKIPT.md -- This view_stop_s is not explicit. I cant read and I figure out why we do that. YOushould have had an
# explanatory comment ; to explain the process of transformation that would happen and why. Like 2-3 lines.
view_stop_s = min(VIEW_START_S + VIEW_DURATION_S, baseline_duration_s)

#TODO: Modify SKIPT.md -- This comment below could hav ebeen short. Its just a fucking filter. 
# But you could have added a strx. comment on the main transfomrations like filter. Very short.
# Use a light 1-40 Hz view filter for bad-channel inspection so slow drifts and
# broadband noise stay visible without leaving the traces dominated by DC offset.
raw_view = raw.copy().pick(eeg_channel_names)
raw_view.notch_filter(freqs=[NOTCH_HZ], verbose=False)
raw_view.filter(VIEW_BAND_HZ[0], VIEW_BAND_HZ[1], verbose=False)
raw_view.crop(tmin=VIEW_START_S, tmax=view_stop_s, include_tmax=False)

##TODO: Modify SKIPT.md -- This could have been 3-4 words for the comment. I dont think you should have done that
# anyway this is already plot related. If its plot related it should be in another block, below, , and perhaps even in its own function (if teh USer agree)
# Convert to microvolts only for plotting and the short text summary.
view_data_uv = raw_view.get_data() * 1e6
time_seconds = raw_view.times + VIEW_START_S
channel_std_uv = view_data_uv.std(axis=1)
channel_peak_uv = np.max(np.abs(view_data_uv), axis=1)
selected_view_stop_s = min(VIEW_START_S + SELECTED_VIEW_DURATION_S, view_stop_s)
selected_time_mask = (time_seconds >= VIEW_START_S) & (time_seconds < selected_view_stop_s)

# Use mean absolute amplitude so the summary reflects typical excursion size
# instead of cancelling positive and negative deflections around zero.
channel_mean_abs_uv = np.mean(np.abs(view_data_uv), axis=1)

# Use the same cropped baseline segment for a quick spectral summary with the
# default MNE PSD settings rather than introducing custom Welch choices here.
#TODO: Modify SKIPT.md -- A strx. comment would have been better jere. We already know these mne functions. Acould have been like
# === 2.3 Spectral summary with MNE PSD ===
# Then in the complex line of code you could have had a short comment to explain the key parameters you choose to use. Like why the n_fft is what it is, and why the fmin and fmax are what they are.
psd_spectrum = raw_view.compute_psd(fmin=0.5, fmax=40.0, verbose=False)
psd_data = psd_spectrum.get_data()
psd_frequencies_hz = psd_spectrum.freqs
channel_mean_psd_v2_hz = psd_data.mean(axis=1)
mean_psd_v2_hz = psd_data.mean(axis=0)

# Share one y-scale across channels so large outliers stand out immediately.
shared_ylim_uv = float(np.percentile(np.abs(view_data_uv), 99.5))
shared_ylim_uv = max(shared_ylim_uv, 20.0)
sorted_indices = np.argsort(channel_std_uv)[::-1]

print(
    f"Loaded exp06 baseline EEG QC: duration={baseline_duration_s:.1f}s "
    f"sfreq={sampling_rate_hz:.0f} Hz eeg_channels={len(eeg_channel_names)} "
    f"excluded={sorted(EXCLUDED_CHANNELS)}"
)


# ===== Block 2: Plot all channel traces =======================================
n_channels = len(eeg_channel_names)
view_duration_s = view_stop_s - VIEW_START_S

# Use the MNE raw browser for a fast, native stacked-channel QC export instead
# of maintaining a custom subplot grid for a standard "scan all channels" task.
figure = raw_view.plot(
    duration=view_duration_s,
    start=0.0,
    n_channels=n_channels,
    scalings={"eeg": shared_ylim_uv * 1e-6},
    show=False,
    remove_dc=False,
    clipping=None,
    show_scrollbars=False,
    show_options=False,
    title=(
        f"Use this scan to spot unstable retained channels | {VIEW_START_S:.0f}-{view_stop_s:.0f} s | "
        f"{VIEW_BAND_HZ[0]:.0f}-{VIEW_BAND_HZ[1]:.0f} Hz + notch {NOTCH_HZ:.0f} Hz"
    ),
)
figure_path = OUTPUT_DIRECTORY / "exp06_baseline_channel_timecourse_grid.png"
figure.savefig(figure_path, dpi=220)
plt.close(figure)
print(f"Saved -> {figure_path}")


# ===== Block 3: Plot selected amplitude time courses ===========================
# Pair the full trace scan with a smaller panel that shows only the most
# unstable retained channels as direct time courses.
sorted_channel_names = [eeg_channel_names[channel_index] for channel_index in sorted_indices]
selected_indices = sorted_indices[:N_SELECTED_TIMECOURSE_CHANNELS]
selected_channel_names = [eeg_channel_names[channel_index] for channel_index in selected_indices]

amplitude_figure, amplitude_axes = plt.subplots(
    len(selected_indices),
    1,
    figsize=(8.4, 1.45 * len(selected_indices) + 0.8),
    constrained_layout=True,
    sharex=True,
)
amplitude_axes = np.atleast_1d(amplitude_axes)
for axis_index, (axis, channel_index) in enumerate(zip(amplitude_axes, selected_indices)):
    channel_name = eeg_channel_names[channel_index]
    line_color = ACCENT_COLOR if axis_index < 3 else CONTEXT_COLOR
    axis.plot(
        time_seconds[selected_time_mask],
        view_data_uv[channel_index, selected_time_mask],
        color=line_color,
        lw=1.0,
    )
    axis.axhline(0.0, color="0.75", lw=0.8)
    axis.text(
        0.01,
        0.84,
        f"{channel_name} | mean abs {channel_mean_abs_uv[channel_index]:.1f} uV",
        transform=axis.transAxes,
        fontsize=9,
    )
    axis.set_ylabel("uV")
    axis.grid(alpha=0.14)
    axis.spines["top"].set_visible(False)
    axis.spines["right"].set_visible(False)

amplitude_axes[-1].set_xlabel("Time (s)")
amplitude_axes[0].set_title(
    f"Selected retained channels over a readable {selected_view_stop_s - VIEW_START_S:.0f}s window"
)
amplitude_path = OUTPUT_DIRECTORY / "exp06_baseline_selected_channel_timecourses.png"
amplitude_figure.savefig(amplitude_path, dpi=220)
plt.close(amplitude_figure)
print(f"Saved -> {amplitude_path}")


# ===== Block 4: Save average PSD ==============================================
# Plot the channel-averaged PSD so the retained baseline spectrum can be read
# quickly without scanning a separate curve for every channel.
psd_figure, psd_axis = plt.subplots(figsize=(8.4, 4.4), constrained_layout=True)
psd_axis.plot(psd_frequencies_hz, 10.0 * np.log10(mean_psd_v2_hz + 1e-30), color=ACCENT_COLOR, lw=1.8)
psd_axis.set(
    xlabel="Frequency (Hz)",
    ylabel="Power spectral density (dB)",
    title="Retained baseline channels show the shared spectral shape clearly",
)
psd_axis.grid(alpha=0.18)
psd_axis.spines["top"].set_visible(False)
psd_axis.spines["right"].set_visible(False)
psd_path = OUTPUT_DIRECTORY / "exp06_baseline_average_psd.png"
psd_figure.savefig(psd_path, dpi=220)
plt.close(psd_figure)
print(f"Saved -> {psd_path}")


# ===== Block 5: Save short summary ============================================
summary_lines = [
    "exp06 baseline channel qc",
    f"baseline_vhdr_path={BASELINE_VHDR_PATH}",
    f"baseline_duration_s={baseline_duration_s:.6f}",
    f"sampling_rate_hz={sampling_rate_hz:.6f}",
    f"eeg_channel_count={n_channels}",
    f"excluded_channels={sorted(EXCLUDED_CHANNELS)}",
    f"view_start_s={VIEW_START_S:.6f}",
    f"view_stop_s={view_stop_s:.6f}",
    f"selected_view_stop_s={selected_view_stop_s:.6f}",
    f"view_band_hz=[{VIEW_BAND_HZ[0]:.6f}, {VIEW_BAND_HZ[1]:.6f}]",
    f"notch_hz={NOTCH_HZ:.6f}",
    f"average_psd_frequency_min_hz={psd_frequencies_hz[0]:.6f}",
    f"average_psd_frequency_max_hz={psd_frequencies_hz[-1]:.6f}",
    f"selected_timecourse_channels={selected_channel_names}",
    f"top_mean_abs_channels={sorted_channel_names[:3]}",
    "",
    "channels_sorted_by_std_uv_desc",
]
summary_lines.extend(
    [
        f"{eeg_channel_names[channel_index]}: std_uv={channel_std_uv[channel_index]:.3f} "
        f"mean_abs_uv={channel_mean_abs_uv[channel_index]:.3f} "
        f"peak_abs_uv={channel_peak_uv[channel_index]:.3f} "
        f"mean_psd_v2_hz={channel_mean_psd_v2_hz[channel_index]:.6e}"
        for channel_index in sorted_indices
    ]
)

summary_lines.extend(["", "average_psd_v2_hz_by_frequency"])
summary_lines.extend(
    [
        f"{frequency_hz:.6f} Hz: mean_psd_v2_hz={power_v2_hz:.6e}"
        for frequency_hz, power_v2_hz in zip(psd_frequencies_hz, mean_psd_v2_hz)
    ]
)

summary_path = OUTPUT_DIRECTORY / "exp06_baseline_channel_timecourse_summary.txt"
summary_path.write_text("\n".join(summary_lines) + "\n", encoding="utf-8")
print(f"Saved -> {summary_path}")
