"""Select the exp06 baseline SSD component that best matches the measured ground-truth peak."""

from pathlib import Path
import warnings

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import mne
import numpy as np

import plot_helpers
import preprocessing


# ===== Config =================================================================
DATA_DIRECTORY = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\TIMS_data_sync\pilot\doseresp")
BASELINE_VHDR_PATH = DATA_DIRECTORY / "exp06-baseline-gt_12hz_noSTIM_run01.vhdr"
OUTPUT_DIRECTORY = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\EXP06")
OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)

# Search the measured ground-truth PSD in a wide enough range to recover the
# actual baseline peak instead of trusting the filename label.
GT_SEARCH_RANGE_HZ = (6.0, 18.0)
VIEW_RANGE_HZ = (4.0, 20.0)
SIGNAL_HALF_WIDTH_HZ = 1.0

# Build repeated one-second baseline windows so SSD training and scoring use
# matched baseline segments rather than one long continuous trace.
BASELINE_WINDOW_DURATION_S = 1.0
BASELINE_FIRST_WINDOW_START_S = 2.0
BASELINE_WINDOW_STRIDE_S = 1.0
N_COMPONENTS = 10


# ===== Load ===================================================================
for warning_message in (
    "No coordinate information found for channels*",
    "Channels contain different highpass filters*",
    "Channels contain different lowpass filters*",
    "Not setting positions of 2 misc channels found in montage*",
    "Online software filter detected. Using software filter settings and ignoring hardware values",
):
    warnings.filterwarnings("ignore", message=warning_message)

raw = mne.io.read_raw_brainvision(str(BASELINE_VHDR_PATH), preload=True, verbose=False)
if "ground_truth" not in raw.ch_names:
    raise RuntimeError("Baseline recording is missing required channel: ground_truth")

sfreq = float(raw.info["sfreq"])
baseline_duration_s = raw.n_times / sfreq


# ===== Block 1: Split measured channels =======================================
# raw -> recorded reference channel
gt_trace = raw.copy().pick(["ground_truth"]).get_data()[0]

# raw -> drop stim/reference channels
eeg_raw = raw.copy().drop_channels(["STIM", "ground_truth"])
window_samples = int(round(BASELINE_WINDOW_DURATION_S * sfreq))

print(
    f"Loaded exp06 baseline: duration={baseline_duration_s:.1f}s "
    f"sfreq={sfreq:.0f} Hz channels={len(eeg_raw.ch_names)}"
)


# ===== Block 2: Build repeated windows =======================================
# retained EEG -> fixed one-second windows
events = mne.make_fixed_length_events(
    eeg_raw,
    start=BASELINE_FIRST_WINDOW_START_S,
    duration=BASELINE_WINDOW_DURATION_S,
    overlap=0.0,
)
print(f"Baseline windows: {len(events)}")


# ===== Block 3: Measure the target band ======================================
# recorded reference channel -> PSD -> peak frequency -> SSD signal band
gt_psd, freqs_hz = mne.time_frequency.psd_array_welch(
    gt_trace,
    sfreq=sfreq,
    fmin=VIEW_RANGE_HZ[0],
    fmax=VIEW_RANGE_HZ[1],
    n_fft=min(4096, gt_trace.size),  # keep a stable PSD grid on the full baseline trace
    verbose=False,
)
search_mask = (freqs_hz >= GT_SEARCH_RANGE_HZ[0]) & (freqs_hz <= GT_SEARCH_RANGE_HZ[1])
peak_hz = float(freqs_hz[search_mask][np.argmax(gt_psd[search_mask])])
signal_band_hz = (peak_hz - SIGNAL_HALF_WIDTH_HZ, peak_hz + SIGNAL_HALF_WIDTH_HZ)

print(
    f"Measured baseline GT peak={peak_hz:.3f} Hz "
    f"| signal band={signal_band_hz[0]:.3f}-{signal_band_hz[1]:.3f} Hz "
    f"| windows={len(events)}"
)


# ===== Fig 1: Ground-truth PSD ================================================
fig_gt_psd, gt_axis = plt.subplots(figsize=(8.4, 4.4), constrained_layout=True)
gt_axis.plot(freqs_hz, 10.0 * np.log10(gt_psd + 1e-30), color="darkorange", lw=1.8)
gt_axis.axvspan(signal_band_hz[0], signal_band_hz[1], color=plot_helpers.TIMS_SIGNAL_BAND_COLOR, alpha=0.80)
gt_axis.axvline(peak_hz, color="black", lw=1.0, ls="--")
gt_axis.set(
    xlim=VIEW_RANGE_HZ,
    xlabel="Frequency (Hz)",
    ylabel="Power (dB)",
    title=f"Baseline ground-truth PSD defines the SSD target band near {peak_hz:.2f} Hz",
)
gt_axis.grid(alpha=0.2)
gt_psd_path = OUTPUT_DIRECTORY / "exp06_baseline_ssd_fig1_gt_psd.png"
fig_gt_psd.savefig(gt_psd_path, dpi=220)
plt.close(fig_gt_psd)
print(f"Saved -> {gt_psd_path}")


# ===== Block 4: Fit SSD and project epochs ===================================
# Reuse the shared SSD helper because the generalized eigenvalue fit is
# non-trivial, but keep the signal band and baseline-window choice visible here.
# SSD here means spatial filters fitted to separate the narrow signal band from flanking activity.
n_components = min(N_COMPONENTS, len(eeg_raw.ch_names))
ssd_filters, spatial_patterns, eigenvalues = plot_helpers.run_ssd(
    eeg_raw,
    events,
    signal_band_hz,
    VIEW_RANGE_HZ,
    n_comp=n_components,
    epoch_duration_s=BASELINE_WINDOW_DURATION_S,
)

# EEG windows -> component epochs
epochs, comp_epochs = plot_helpers.build_ssd_component_epochs(
    eeg_raw,
    events,
    ssd_filters,
    VIEW_RANGE_HZ,
    BASELINE_WINDOW_DURATION_S,
)


# ===== Block 5: Build scoring inputs ==========================================
# reference channel -> band-pass reference trace
ref_trace = preprocessing.filter_signal(gt_trace, sfreq, signal_band_hz[0], signal_band_hz[1])

# window starts -> full-trace scoring mask
score_mask = np.zeros(eeg_raw.n_times, dtype=bool)
for start_sample in events[:, 0]:
    score_mask[int(start_sample):int(start_sample) + window_samples] = True

# retained EEG -> signal-band EEG + view-band EEG
# signal_raw is for reference matching; view_raw is for peak-shape inspection.
signal_raw = eeg_raw.copy().filter(*signal_band_hz, verbose=False)
view_raw = eeg_raw.copy().filter(*VIEW_RANGE_HZ, verbose=False)


# ===== Block 6: Score and select ==============================================
# Reuse the shared ranking helper because it bundles the validated component
# scoring metrics against the measured reference trace.
coherence_scores, peak_ratios, peak_freqs = preprocessing.rank_ssd_components_against_reference(
    spatial_filters=ssd_filters,
    raw_signal_band=signal_raw,
    raw_view_band=view_raw,
    evaluation_mask=score_mask,
    reference_band_signal=ref_trace,
    sampling_rate_hz=sfreq,
    signal_band_hz=signal_band_hz,
    view_range_hz=VIEW_RANGE_HZ,
)

candidate_indices = [
    comp_idx
    for comp_idx, comp_peak_hz in enumerate(peak_freqs)
    if signal_band_hz[0] <= comp_peak_hz <= signal_band_hz[1]
]
used_fallback_selection = len(candidate_indices) == 0
selection_pool = candidate_indices if candidate_indices else list(range(n_components))
selected_index = max(
    selection_pool,
    key=lambda comp_idx: (
        coherence_scores[comp_idx],
        peak_ratios[comp_idx],
        float(eigenvalues[comp_idx]),
    ),
)
selected_number = selected_index + 1
selected_peak_hz = float(peak_freqs[selected_index])
comp_numbers = np.arange(1, n_components + 1, dtype=int)

print(
    f"Selected component={selected_number} "
    f"| coherence={coherence_scores[selected_index]:.3f} "
    f"| peak_ratio={peak_ratios[selected_index]:.2f}x "
    f"| peak_frequency={selected_peak_hz:.2f} Hz"
)


# ===== Fig 2: Component ranking ===============================================
selection_figure, (lambda_axis, metric_axis, peak_axis) = plt.subplots(1, 3, figsize=(13.8, 4.2), constrained_layout=True)
lambda_axis.bar(comp_numbers, eigenvalues[:n_components], color="gray", alpha=0.85)
lambda_axis.axvline(selected_number, color="darkorange", ls="--", lw=1.0)
lambda_axis.axhline(1.0, color="gray", ls="--", lw=0.8)
lambda_axis.set(xlabel="Baseline SSD component", ylabel="Eigenvalue lambda", title="Baseline SSD separation")

metric_axis.bar(comp_numbers, coherence_scores, color="steelblue", alpha=0.90)
metric_axis.axvline(selected_number, color="darkorange", ls="--", lw=1.0)
metric_axis.set(xlabel="Baseline SSD component", ylabel="GT-band coherence", title="Measured reference match")

peak_axis.bar(comp_numbers, peak_ratios, color="slateblue", alpha=0.90)
peak_axis.axvline(selected_number, color="darkorange", ls="--", lw=1.0)
peak_axis.axhline(1.0, color="gray", ls="--", lw=0.8)
peak_axis.set(xlabel="Baseline SSD component", ylabel="Peak / flank ratio", title="Target-band peak sanity")
peak_freq_axis = peak_axis.twinx()
peak_freq_axis.scatter(comp_numbers, peak_freqs, color="black", s=25, zorder=3)
peak_freq_axis.axhspan(signal_band_hz[0], signal_band_hz[1], color=plot_helpers.TIMS_SIGNAL_BAND_COLOR, alpha=0.45)
peak_freq_axis.axhline(peak_hz, color="darkorange", ls="--", lw=1.0)
peak_freq_axis.set(ylabel="Peak frequency (Hz)", ylim=VIEW_RANGE_HZ)

selection_figure.suptitle("exp06 baseline SSD: component ranking", fontsize=13)
selection_figure_path = OUTPUT_DIRECTORY / "exp06_baseline_ssd_fig2_component_ranking.png"
selection_figure.savefig(selection_figure_path, dpi=220)
plt.close(selection_figure)
print(f"Saved -> {selection_figure_path}")


# ===== Block 7: Prepare the plot overlay =====================================
# windowed reference -> averaged overlay trace
gt_windows = preprocessing.extract_event_windows(gt_trace, events[:, 0], window_samples)
ref_mean_uv = preprocessing.filter_signal(
    gt_windows,
    sfreq,
    signal_band_hz[0],
    signal_band_hz[1],
).mean(axis=0) * 1e6

summary_plot_kwargs = dict(
    epochs=epochs,
    freq_band_hz=signal_band_hz,
    noise_band_hz=VIEW_RANGE_HZ,
    psd_freq_range_hz=VIEW_RANGE_HZ,
    line_color=plot_helpers.TIMS_CONDITION_COLORS["baseline"],
    reference_frequency_hz=peak_hz,
    temporal_reference_data=ref_mean_uv,
)


# ===== Block 8: Save figures and summary =====================================
gallery_path = OUTPUT_DIRECTORY / "exp06_baseline_ssd_fig3_component_gallery.png"
plot_helpers.plot_ssd_component_summary(
    spatial_patterns=spatial_patterns,
    component_epochs=comp_epochs,
    spectral_ratios=eigenvalues,
    condition_name="exp06 baseline SSD",
    output_path=gallery_path,
    n_components=n_components,
    component_numbers=comp_numbers.tolist(),
    **summary_plot_kwargs,
)
print(f"Saved -> {gallery_path}")

selected_summary_path = OUTPUT_DIRECTORY / "exp06_baseline_ssd_fig4_selected_component_summary.png"
plot_helpers.plot_ssd_component_summary(
    spatial_patterns=spatial_patterns[:, [selected_index]],
    component_epochs=comp_epochs[[selected_index]],
    spectral_ratios=[float(eigenvalues[selected_index])],
    condition_name="exp06 selected baseline SSD",
    output_path=selected_summary_path,
    n_components=1,
    component_numbers=[selected_number],
    **summary_plot_kwargs,
)
print(f"Saved -> {selected_summary_path}")

summary_lines = [
    "exp06 baseline ssd skript version",
    f"baseline_vhdr_path={BASELINE_VHDR_PATH}",
    f"baseline_duration_s={baseline_duration_s:.6f}",
    f"sampling_rate_hz={sfreq:.6f}",
    f"eeg_channel_count={len(eeg_raw.ch_names)}",
    f"gt_peak_frequency_hz={peak_hz:.6f}",
    f"signal_band_hz=({signal_band_hz[0]:.6f}, {signal_band_hz[1]:.6f})",
    f"baseline_window_duration_s={BASELINE_WINDOW_DURATION_S:.6f}",
    f"baseline_window_stride_s={BASELINE_WINDOW_STRIDE_S:.6f}",
    f"baseline_windows={len(events)}",
    f"selected_component={selected_number}",
    f"selected_lambda={float(eigenvalues[selected_index]):.6f}",
    f"selected_peak_frequency_hz={selected_peak_hz:.6f}",
    f"selected_coherence={float(coherence_scores[selected_index]):.6f}",
    f"selected_peak_ratio={float(peak_ratios[selected_index]):.6f}",
    f"used_fallback_selection={used_fallback_selection}",
]

summary_path = OUTPUT_DIRECTORY / "exp06_baseline_ssd_summary.txt"
summary_path.write_text("\n".join(summary_lines) + "\n", encoding="utf-8")
print(f"Saved -> {summary_path}")
