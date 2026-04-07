"""Does the saved exp06 baseline SSD recover GT better than raw O2 in run02 late-OFF blocks?"""

from pathlib import Path
import warnings

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import mne
import numpy as np
from scipy.signal import hilbert

import plot_helpers
import preprocessing


# ===== Config =================================================================
DATA_DIRECTORY = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\TIMS_data_sync\pilot\doseresp")
STIM_VHDR_PATH = DATA_DIRECTORY / "exp06-STIM-iTBS_run02.vhdr"
OUTPUT_DIRECTORY = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\EXP06")
OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)
WEIGHTS_PATH = OUTPUT_DIRECTORY / "exp06_baseline_ssd_component1_weights.npz"

# The measured run02 STIM trace contains five ascending dose blocks.
RUN02_INTENSITY_LABELS = ["10%", "20%", "30%", "40%", "50%"]
BLOCK_CYCLES_PER_INTENSITY = 20
LATE_OFF_START_S = 1.5
LATE_OFF_STOP_S = 3.2
FOCUS_CHANNEL = "O2"
# The first run02 block is lower-amplitude than the later blocks, so the
# default 10% global-threshold detector misses it. A slightly lower threshold
# recovers all five measured blocks without merging adjacent cycles.
RUN02_STIM_THRESHOLD_FRACTION = 0.08
TIMING_PADDING_BEFORE_S = 2.0
TIMING_PADDING_AFTER_S = 0.5
RAW_CHANNEL_COLOR = "black"
RECOVERED_COLOR = "steelblue"
GROUND_TRUTH_COLOR = "darkorange"
INTENSITY_COLORS = ["#c6dbef", "#9ecae1", "#6baed6", "#3182bd", "#08519c"]


# ===== Load ===================================================================
# Reuse the saved baseline SSD artifact so the transfer test stays tied to the
# same fixed spatial filter that was already accepted in the baseline script.
weights_artifact = preprocessing.load_exp06_saved_ssd_artifact(WEIGHTS_PATH)
saved_channel_names = weights_artifact["channel_names"]
saved_sampling_rate_hz = weights_artifact["sampling_rate_hz"]
signal_band_hz = weights_artifact["signal_band_hz"]
view_band_hz = weights_artifact["view_band_hz"]
selected_filter = np.asarray(weights_artifact["selected_filter"], dtype=float).ravel()
baseline_peak_hz = float(weights_artifact["baseline_peak_hz"])

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
raw_stim_eeg = raw_stim_full.copy().pick(saved_channel_names)

if list(raw_stim_eeg.ch_names) != list(saved_channel_names):
    raise RuntimeError("Stim EEG channels do not match the saved baseline SSD channel order.")
if not np.isclose(sampling_rate_hz, saved_sampling_rate_hz):
    raise RuntimeError(
        f"Sampling rate mismatch between stim EEG ({sampling_rate_hz:.3f} Hz) and saved SSD weights "
        f"({saved_sampling_rate_hz:.3f} Hz)."
    )
if selected_filter.size != len(saved_channel_names):
    raise RuntimeError("Saved selected_filter length does not match the saved channel list.")
if FOCUS_CHANNEL not in raw_stim_eeg.ch_names:
    raise RuntimeError(f"Required focus channel is missing from retained EEG channels: {FOCUS_CHANNEL}")


# ===== Block 1: Build run02 late-OFF windows ==================================
# Use the validated block detector because the iTBS train is not a trivial
# one-peak marker and the OFF windows must follow measured timing.
block_onsets_samples, block_offsets_samples = preprocessing.detect_stim_blocks(
    stim_marker_v,
    sampling_rate_hz,
    threshold_fraction=RUN02_STIM_THRESHOLD_FRACTION,
)
required_block_count = len(RUN02_INTENSITY_LABELS) * BLOCK_CYCLES_PER_INTENSITY
if len(block_onsets_samples) < required_block_count:
    raise RuntimeError(
        f"Need at least {required_block_count} measured ON blocks to analyze run02, "
        f"but found {len(block_onsets_samples)}."
    )

median_on_duration_s = float(np.median((block_offsets_samples - block_onsets_samples) / sampling_rate_hz))
median_off_duration_s = float(np.median((block_onsets_samples[1:] - block_offsets_samples[:-1]) / sampling_rate_hz))

summary_rows = []
itpc_curves_raw = []
itpc_curves_ssd = []
psd_panels = []
timing_windows = []
late_off_duration_samples = None

for intensity_index, intensity_label in enumerate(RUN02_INTENSITY_LABELS):
    block_start_index = intensity_index * BLOCK_CYCLES_PER_INTENSITY
    block_stop_index = min(block_start_index + BLOCK_CYCLES_PER_INTENSITY + 1, len(block_onsets_samples))
    dose_block_onsets = block_onsets_samples[block_start_index:block_stop_index]
    dose_block_offsets = block_offsets_samples[block_start_index:block_stop_index]

    if intensity_index < len(RUN02_INTENSITY_LABELS) - 1 and len(dose_block_onsets) != BLOCK_CYCLES_PER_INTENSITY + 1:
        raise RuntimeError(f"{intensity_label} in run02 does not contain the required 21 measured ON blocks.")
    if intensity_index == len(RUN02_INTENSITY_LABELS) - 1 and len(dose_block_onsets) != BLOCK_CYCLES_PER_INTENSITY:
        raise RuntimeError("The final run02 block should contain 20 measured ON blocks before recording end.")

    # Keep `build_late_off_events(...)` because this timing rule is non-trivial:
    # it anchors each window to a measured offset and rejects any window that
    # would run into the next measured ON block.
    events_late_off, late_off_duration_s, late_off_duration_samples = preprocessing.build_late_off_events(
        dose_block_onsets,
        dose_block_offsets,
        sampling_rate_hz,
        LATE_OFF_START_S,
        LATE_OFF_STOP_S,
    )
    expected_event_count = len(dose_block_onsets) - 1
    if len(events_late_off) != expected_event_count:
        raise RuntimeError(
            f"Expected {expected_event_count} valid late-OFF windows for {intensity_label}, "
            f"but built {len(events_late_off)}."
        )

    # ===== Block 2: Project the saved SSD filter ===============================
    raw_view = raw_stim_eeg.copy().filter(*view_band_hz, verbose=False)
    tmax_s = late_off_duration_s - (1.0 / sampling_rate_hz)
    epochs_view = mne.Epochs(
        raw_view,
        events_late_off,
        event_id=1,
        tmin=0.0,
        tmax=tmax_s,
        baseline=None,
        proj=False,
        preload=True,
        verbose=False,
    )
    epoch_data = epochs_view.get_data()
    selected_component_epochs = np.einsum("c,ect->et", selected_filter, epoch_data)
    focus_channel_epochs = epochs_view.copy().pick([FOCUS_CHANNEL]).get_data()[:, 0, :]

    # Keep GT slicing inline because it is short and clearer than hiding it.
    gt_starts = events_late_off[:, 0]
    ground_truth_epochs = np.asarray(
        [
            ground_truth_stim_v[int(start_sample):int(start_sample) + late_off_duration_samples]
            for start_sample in gt_starts
        ],
        dtype=float,
    )

    # ===== Block 3: Compute GT-locking inline =================================
    # Keep the scientific comparison visible: band-pass -> phase -> phase
    # difference -> ITPC. This is the core recovery logic, so it should not be
    # hidden in one bundled helper.
    focus_band_epochs = mne.filter.filter_data(
        focus_channel_epochs,
        sfreq=sampling_rate_hz,
        l_freq=signal_band_hz[0],
        h_freq=signal_band_hz[1],
        verbose=False,
    )
    recovered_band_epochs = mne.filter.filter_data(
        selected_component_epochs,
        sfreq=sampling_rate_hz,
        l_freq=signal_band_hz[0],
        h_freq=signal_band_hz[1],
        verbose=False,
    )
    ground_truth_band_epochs = mne.filter.filter_data(
        ground_truth_epochs,
        sfreq=sampling_rate_hz,
        l_freq=signal_band_hz[0],
        h_freq=signal_band_hz[1],
        verbose=False,
    )

    focus_phase = np.angle(hilbert(focus_band_epochs, axis=-1))
    recovered_phase = np.angle(hilbert(recovered_band_epochs, axis=-1))
    ground_truth_phase = np.angle(hilbert(ground_truth_band_epochs, axis=-1))

    focus_phase_diff = focus_phase - ground_truth_phase
    recovered_phase_diff = recovered_phase - ground_truth_phase

    focus_itpc_curve = np.abs(np.mean(np.exp(1j * focus_phase_diff), axis=0))
    recovered_itpc_curve = np.abs(np.mean(np.exp(1j * recovered_phase_diff), axis=0))
    recovered_peak_hz = preprocessing.find_psd_peak_frequency(
        selected_component_epochs.reshape(-1),
        sampling_rate_hz,
        view_band_hz,
    )

    n_fft = min(1024, late_off_duration_samples)
    ground_truth_psd, psd_freqs_hz = mne.time_frequency.psd_array_welch(
        ground_truth_epochs,
        sfreq=sampling_rate_hz,
        fmin=view_band_hz[0],
        fmax=view_band_hz[1],
        n_fft=n_fft,
        verbose=False,
    )
    focus_psd, _ = mne.time_frequency.psd_array_welch(
        focus_channel_epochs,
        sfreq=sampling_rate_hz,
        fmin=view_band_hz[0],
        fmax=view_band_hz[1],
        n_fft=n_fft,
        verbose=False,
    )
    recovered_psd, _ = mne.time_frequency.psd_array_welch(
        selected_component_epochs,
        sfreq=sampling_rate_hz,
        fmin=view_band_hz[0],
        fmax=view_band_hz[1],
        n_fft=n_fft,
        verbose=False,
    )

    ground_truth_mean_psd = np.mean(ground_truth_psd, axis=0)
    focus_mean_psd = np.mean(focus_psd, axis=0)
    recovered_mean_psd = np.mean(recovered_psd, axis=0)
    ground_truth_mean_psd /= np.max(ground_truth_mean_psd) + 1e-30
    focus_mean_psd /= np.max(focus_mean_psd) + 1e-30
    recovered_mean_psd /= np.max(recovered_mean_psd) + 1e-30

    intensity_pct = int(intensity_label.replace("%", ""))
    summary_rows.append(
        {
            "label": intensity_label,
            "intensity_pct": intensity_pct,
            "event_count": int(len(events_late_off)),
            "raw_mean_itpc": float(np.mean(focus_itpc_curve)),
            "ssd_mean_itpc": float(np.mean(recovered_itpc_curve)),
            "recovered_peak_hz": float(recovered_peak_hz),
            "late_off_event_starts": gt_starts.copy(),
        }
    )
    itpc_curves_raw.append(np.asarray(focus_itpc_curve, dtype=float))
    itpc_curves_ssd.append(np.asarray(recovered_itpc_curve, dtype=float))
    psd_panels.append(
        {
            "label": intensity_label,
            "freqs_hz": psd_freqs_hz,
            "ground_truth_mean_psd": ground_truth_mean_psd,
            "focus_mean_psd": focus_mean_psd,
            "recovered_mean_psd": recovered_mean_psd,
            "event_count": int(len(events_late_off)),
        }
    )
    timing_windows.append(gt_starts.copy())


# ===== Block 4: Save figures ==================================================
# Figure 1: orientation. Show the measured ON blocks and the accepted late-OFF
# windows so the timing assumption is visible before reading the metric.
timing_start_sample = max(0, block_onsets_samples[0] - int(round(TIMING_PADDING_BEFORE_S * sampling_rate_hz)))
timing_stop_sample = min(
    raw_stim_full.n_times,
    timing_windows[-1][-1] + late_off_duration_samples + int(round(TIMING_PADDING_AFTER_S * sampling_rate_hz)),
)
timing_axis_s = (
    np.arange(timing_stop_sample - timing_start_sample, dtype=float) / sampling_rate_hz
    + timing_start_sample / sampling_rate_hz
    - block_onsets_samples[0] / sampling_rate_hz
)
stim_segment = stim_marker_v[timing_start_sample:timing_stop_sample]

timing_figure, timing_axis = plt.subplots(figsize=(12.4, 3.9), constrained_layout=True)
timing_axis.plot(timing_axis_s, stim_segment, color="black", lw=0.8)
for onset_sample, offset_sample in zip(block_onsets_samples[:required_block_count], block_offsets_samples[:required_block_count], strict=True):
    timing_axis.axvspan(
        onset_sample / sampling_rate_hz - block_onsets_samples[0] / sampling_rate_hz,
        offset_sample / sampling_rate_hz - block_onsets_samples[0] / sampling_rate_hz,
        color="0.82",
        alpha=0.35,
    )
for row, intensity_color in zip(summary_rows, INTENSITY_COLORS, strict=True):
    for late_off_start_sample in row["late_off_event_starts"]:
        late_off_start_s = late_off_start_sample / sampling_rate_hz - block_onsets_samples[0] / sampling_rate_hz
        timing_axis.axvspan(
            late_off_start_s,
            late_off_start_s + late_off_duration_samples / sampling_rate_hz,
            color=intensity_color,
            alpha=0.32,
        )
timing_axis.text(
    0.015,
    0.96,
    "Gray = measured ON blocks\nBlue shades = accepted run02 late-OFF windows",
    transform=timing_axis.transAxes,
    va="top",
    fontsize=8.3,
    bbox={"facecolor": "white", "alpha": 0.75, "edgecolor": "none", "pad": 2.5},
)
timing_axis.set(
    xlabel="Time from first run02 ON block (s)",
    ylabel="STIM (V)",
    title="run02 contains five measured late-OFF dose blocks",
)
plot_helpers.style_clean_axis(timing_axis, grid_alpha=0.15)
timing_path = OUTPUT_DIRECTORY / "exp06_run02_art_filtering_timing_windows.png"
timing_figure.savefig(timing_path, dpi=220)
plt.close(timing_figure)

# Figure 2: primary evidence. Summarize mean GT-locking across the four run02
# dose blocks and keep the raw-vs-SSD comparison direct.
intensity_values = np.asarray([row["intensity_pct"] for row in summary_rows], dtype=float)
raw_mean_itpc_values = np.asarray([row["raw_mean_itpc"] for row in summary_rows], dtype=float)
ssd_mean_itpc_values = np.asarray([row["ssd_mean_itpc"] for row in summary_rows], dtype=float)

summary_figure, summary_axis = plt.subplots(figsize=(10.2, 5.2))
summary_axis.plot(intensity_values, raw_mean_itpc_values, color=RAW_CHANNEL_COLOR, lw=1.8, marker="o", ms=6, label=FOCUS_CHANNEL)
summary_axis.plot(intensity_values, ssd_mean_itpc_values, color=RECOVERED_COLOR, lw=2.3, marker="o", ms=6, label="SSD")
for row, x_value, y_value in zip(summary_rows, intensity_values, ssd_mean_itpc_values, strict=True):
    summary_axis.text(x_value, y_value + 0.006, f"n={row['event_count']}", ha="center", va="bottom", fontsize=8)
summary_axis.set(
    xticks=intensity_values,
    xlabel="Run02 stimulation block (%)",
    ylabel="Mean late-OFF GT-locking",
    title=f"Transferred SSD stays more GT-locked than raw {FOCUS_CHANNEL} across run02",
)
summary_axis.legend(frameon=False, loc="upper right")
plot_helpers.style_clean_axis(summary_axis, grid_alpha=0.15)
summary_path = OUTPUT_DIRECTORY / "exp06_run02_art_filtering_itpc_summary.png"
summary_figure.savefig(summary_path, dpi=220)
plt.close(summary_figure)

# Figure 3: qualification. Show whether the spectral peak stays near the saved
# baseline target even when GT-locking looks favorable.
psd_figure, psd_axes = plt.subplots(1, len(psd_panels), figsize=(14.8, 3.8), constrained_layout=True, sharey=True)
for axis, panel, intensity_color in zip(np.atleast_1d(psd_axes), psd_panels, INTENSITY_COLORS, strict=True):
    axis.plot(panel["freqs_hz"], panel["ground_truth_mean_psd"], color=GROUND_TRUTH_COLOR, lw=1.9, label="GT")
    axis.plot(panel["freqs_hz"], panel["focus_mean_psd"], color=RAW_CHANNEL_COLOR, lw=1.4, label=FOCUS_CHANNEL)
    axis.plot(panel["freqs_hz"], panel["recovered_mean_psd"], color=RECOVERED_COLOR, lw=2.0, label="SSD")
    axis.axvspan(signal_band_hz[0], signal_band_hz[1], color=plot_helpers.TIMS_SIGNAL_BAND_COLOR, alpha=0.75)
    axis.axvline(baseline_peak_hz, color=GROUND_TRUTH_COLOR, ls="--", lw=0.9)
    axis.set_title(f"{panel['label']} (n={panel['event_count']})", color=intensity_color, pad=8)
    axis.set_xlabel("Frequency (Hz)")
    axis.set_xlim(*view_band_hz)
    plot_helpers.style_clean_axis(axis, grid_alpha=0.15)
psd_axes = np.atleast_1d(psd_axes)
psd_axes[0].set_ylabel("Normalized PSD")
psd_axes[-1].legend(frameon=False, loc="upper right")
psd_figure.suptitle("GT, raw O2, and SSD spectra across run02 late-OFF blocks", fontsize=12.2)
psd_path = OUTPUT_DIRECTORY / "exp06_run02_art_filtering_psd_panels.png"
psd_figure.savefig(psd_path, dpi=220)
plt.close(psd_figure)


# ===== Block 5: Save summary ==================================================
summary_lines = [
    "exp06 run02 artifact filtering summary",
    f"stim_vhdr_path={STIM_VHDR_PATH}",
    f"weights_path={WEIGHTS_PATH}",
    f"signal_band_hz=({signal_band_hz[0]:.6f}, {signal_band_hz[1]:.6f})",
    f"view_band_hz=({view_band_hz[0]:.6f}, {view_band_hz[1]:.6f})",
    f"baseline_peak_hz={baseline_peak_hz:.6f}",
    f"focus_channel={FOCUS_CHANNEL}",
    f"median_on_duration_s={median_on_duration_s:.6f}",
    f"median_off_duration_s={median_off_duration_s:.6f}",
    f"stim_threshold_fraction={RUN02_STIM_THRESHOLD_FRACTION:.3f}",
    "run02_note=run02 contains five measured dose blocks; the final block contributes 19 late-OFF windows because the recording ends after the last ON block.",
    "",
]
for row in summary_rows:
    summary_lines.extend(
        [
            f"{row['label']}",
            f"event_count={row['event_count']}",
            f"raw_mean_itpc={row['raw_mean_itpc']:.6f}",
            f"ssd_mean_itpc={row['ssd_mean_itpc']:.6f}",
            f"ssd_minus_raw_itpc={row['ssd_mean_itpc'] - row['raw_mean_itpc']:.6f}",
            f"recovered_peak_hz={row['recovered_peak_hz']:.6f}",
            "",
        ]
    )
summary_text_path = OUTPUT_DIRECTORY / "exp06_run02_art_filtering_summary.txt"
summary_text_path.write_text("\n".join(summary_lines), encoding="utf-8")


print(f"run=run02 | blocks={len(summary_rows)} | focus={FOCUS_CHANNEL}")
print(f"10% raw_itpc={summary_rows[0]['raw_mean_itpc']:.4f} | 10% ssd_itpc={summary_rows[0]['ssd_mean_itpc']:.4f}")
print(f"baseline_peak={baseline_peak_hz:.2f} Hz | 50% peak={summary_rows[-1]['recovered_peak_hz']:.2f} Hz")
