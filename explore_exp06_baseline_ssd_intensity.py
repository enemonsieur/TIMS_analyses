"""Export the exp06 baseline SSD component 1 for later stimulation-run reuse."""

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

SIGNAL_BAND_HZ = (12.0, 13.0)
VIEW_BAND_HZ = (4.0, 20.0)
BASELINE_WINDOW_DURATION_S = 1.0
BASELINE_FIRST_WINDOW_START_S = 2.0
BASELINE_WINDOW_STRIDE_S = 1.0
SELECTED_COMPONENT_INDEX = 0
EXCLUDED_CHANNELS = {"TP9", "Fp1", "TP10"}
ACCENT_COLOR = "darkorange"


# ===== Load ===================================================================
# Keep the console quiet so the short status prints stay focused on the SSD
# export rather than BrainVision metadata details.
with warnings.catch_warnings():
    warnings.filterwarnings("ignore", message="No coordinate information found for channels*")
    warnings.filterwarnings("ignore", message="Channels contain different highpass filters*")
    warnings.filterwarnings("ignore", message="Channels contain different lowpass filters*")
    warnings.filterwarnings("ignore", message="Not setting positions of 2 misc channels found in montage*")
    warnings.filterwarnings(
        "ignore",
        message="Online software filter detected. Using software filter settings and ignoring hardware values",
    )
    raw_baseline_full = mne.io.read_raw_brainvision(str(BASELINE_VHDR_PATH), preload=True, verbose=False)

if "ground_truth" not in raw_baseline_full.ch_names:
    raise RuntimeError("Baseline recording is missing required channel: ground_truth")

# Keep the GT trace before dropping non-EEG channels because it anchors the
# saved artifact to the measured baseline target frequency.
ground_truth_baseline_v = raw_baseline_full.copy().pick(["ground_truth"]).get_data()[0]
# SSD is fit on EEG only, so remove the marker/reference channels up front and
# keep the retained channel order stable for later reuse in the stim script.
raw_baseline = raw_baseline_full.copy().drop_channels(
    [
        channel_name
        for channel_name in raw_baseline_full.ch_names
        if channel_name.lower() in {"stim", "ground_truth"}
        or channel_name.startswith("STI")
        or channel_name in EXCLUDED_CHANNELS
    ]
)
sampling_rate_hz = float(raw_baseline.info["sfreq"])
if len(raw_baseline.ch_names) == 0:
    raise RuntimeError("No retained EEG channels remain after excluding stim, GT, and rejected channels.")

print(f"exp06 baseline | {len(raw_baseline.ch_names)} ch | {sampling_rate_hz:.0f} Hz")


# ===== Block 1: Build windows =================================================
# Keep fixed one-second baseline windows because the selected component is
# already established and will be reused as a spatial filter only.
window_duration_samples = int(round(BASELINE_WINDOW_DURATION_S * sampling_rate_hz))
# Build repeated pseudo-events so SSD sees many comparable baseline snippets
# instead of one long continuous segment.
baseline_window_starts = np.arange(
    int(round(BASELINE_FIRST_WINDOW_START_S * sampling_rate_hz)),
    raw_baseline.n_times - window_duration_samples + 1,
    int(round(BASELINE_WINDOW_STRIDE_S * sampling_rate_hz)),
    dtype=int,
)
events_baseline = preprocessing.build_event_array(baseline_window_starts)
if len(events_baseline) == 0:
    raise RuntimeError("No baseline pseudo-events were built for SSD.")

print(f"windows={len(events_baseline)} | dur={BASELINE_WINDOW_DURATION_S:.1f}s | stride={BASELINE_WINDOW_STRIDE_S:.1f}s")


# ===== Block 2: Fit SSD and keep component 1 ==================================
# Fit SSD on the repeated baseline windows, then export component 1 directly
# because the baseline checks already showed that this is the useful solution.
ssd_filters, spatial_patterns, eigenvalues = plot_helpers.run_ssd(
    raw_baseline,
    events_baseline,
    SIGNAL_BAND_HZ,
    VIEW_BAND_HZ,
    n_comp=1,
    epoch_duration_s=BASELINE_WINDOW_DURATION_S,
)
# Re-project the same baseline windows through the SSD filter so the exported
# artifact carries a measured peak and contrast ratio, not just raw weights.
_, component_epochs = plot_helpers.build_ssd_component_epochs(
    raw_baseline,
    events_baseline,
    ssd_filters,
    VIEW_BAND_HZ,
    BASELINE_WINDOW_DURATION_S,
)
# Score the saved component inside the broad view band so the manifest records
# both the target peak and how strongly it separates from its flanks.
component_psd, component_frequencies_hz = mne.time_frequency.psd_array_welch(
    component_epochs,
    sfreq=sampling_rate_hz,
    fmin=VIEW_BAND_HZ[0],
    fmax=VIEW_BAND_HZ[1],
    n_fft=window_duration_samples,
    n_per_seg=window_duration_samples,
    verbose=False,
)
component_signal_mask = (component_frequencies_hz >= SIGNAL_BAND_HZ[0]) & (component_frequencies_hz <= SIGNAL_BAND_HZ[1])
component_flank_mask = (
    (component_frequencies_hz >= VIEW_BAND_HZ[0]) & (component_frequencies_hz <= VIEW_BAND_HZ[1]) & ~component_signal_mask
)
if not np.any(component_signal_mask):
    raise RuntimeError("The SSD component PSD did not include any frequencies inside 12.0-13.0 Hz.")

# Keep the selected filter as a flat channel-weight vector because the stim
# script will reuse exactly this component without rerunning SSD.
selected_component_number = SELECTED_COMPONENT_INDEX + 1
selected_filter = np.asarray(ssd_filters[SELECTED_COMPONENT_INDEX], dtype=float).copy()
selected_pattern = np.asarray(spatial_patterns[:, SELECTED_COMPONENT_INDEX], dtype=float).copy()
selected_lambda = float(eigenvalues[SELECTED_COMPONENT_INDEX])
selected_component_epochs = component_epochs[SELECTED_COMPONENT_INDEX]
# Reduce the PSD to one mean spectrum so the saved ratio reflects the typical
# baseline window, not a single unusually strong epoch.
selected_component_mean_psd = component_psd[SELECTED_COMPONENT_INDEX].mean(axis=0)
selected_component_target_mean_psd = selected_component_mean_psd[component_signal_mask].mean()
selected_component_flank_mean_psd = selected_component_mean_psd[component_flank_mask].mean()
selected_component_contrast_ratio = selected_component_target_mean_psd / max(selected_component_flank_mean_psd, 1e-30)
selected_component_peak_hz = preprocessing.find_psd_peak_frequency(
    selected_component_epochs.reshape(-1),
    sampling_rate_hz,
    VIEW_BAND_HZ,
)
baseline_gt_peak_hz = preprocessing.find_psd_peak_frequency(
    ground_truth_baseline_v,
    sampling_rate_hz,
    VIEW_BAND_HZ,
)

print(f"comp={selected_component_number} | peak={selected_component_peak_hz:.2f} Hz | ratio={selected_component_contrast_ratio:.1f}x")


# ===== Block 3: Save outputs ==================================================
# Save one PSD figure plus a reusable artifact bundle so later scripts can
# apply the exact baseline filter without rerunning SSD.
selected_component_psd_db = 10.0 * np.log10(selected_component_mean_psd + 1e-30)

component_figure, psd_axis = plt.subplots(figsize=(6.8, 4.2), constrained_layout=True)
# Keep the figure narrow and claim-first: one line, one shaded target band, and
# the measured component peak that the later stim script should preserve.
psd_axis.axvspan(SIGNAL_BAND_HZ[0], SIGNAL_BAND_HZ[1], color=plot_helpers.TIMS_SIGNAL_BAND_COLOR, alpha=0.85)
psd_axis.axvline(selected_component_peak_hz, color="black", ls="--", lw=0.9)
psd_axis.plot(component_frequencies_hz, selected_component_psd_db, color=ACCENT_COLOR, lw=1.8)
psd_axis.set(
    xlabel="Frequency (Hz)",
    ylabel="Power spectral density (dB)",
    title=f"Baseline SSD component {selected_component_number} isolates the {selected_component_peak_hz:.2f} Hz target peak",
)
psd_axis.grid(alpha=0.18)
psd_axis.spines["top"].set_visible(False)
psd_axis.spines["right"].set_visible(False)
component_path = OUTPUT_DIRECTORY / "exp06_baseline_ssd_component1_psd.png"
component_figure.savefig(component_path, dpi=220)
plt.close(component_figure)

weights_path = OUTPUT_DIRECTORY / "exp06_baseline_ssd_component1_weights.npz"
# Save the full filter bundle plus the key measured metadata so the stim script
# can stay decision-free and fail fast on mismatches.
np.savez(
    weights_path,
    channel_names=np.asarray(raw_baseline.ch_names, dtype=str),
    sampling_rate_hz=np.asarray([sampling_rate_hz], dtype=float),
    signal_band_hz=np.asarray(SIGNAL_BAND_HZ, dtype=float),
    view_band_hz=np.asarray(VIEW_BAND_HZ, dtype=float),
    selected_component_index=np.asarray([SELECTED_COMPONENT_INDEX], dtype=int),
    ssd_filters=np.asarray(ssd_filters, dtype=float),
    selected_filter=selected_filter,
    selected_pattern=selected_pattern,
    selected_lambda=np.asarray([selected_lambda], dtype=float),
    baseline_gt_peak_hz=np.asarray([baseline_gt_peak_hz], dtype=float),
    baseline_peak_hz=np.asarray([selected_component_peak_hz], dtype=float),
    baseline_target_vs_flank_ratio=np.asarray([selected_component_contrast_ratio], dtype=float),
)

manifest_path = OUTPUT_DIRECTORY / "exp06_baseline_ssd_component1_weights.txt"
# Pair the machine-readable `.npz` with a short text manifest so the saved
# artifact is still understandable without opening numpy arrays.
manifest_lines = [
    "exp06 baseline ssd component 1 artifact",
    f"baseline_vhdr_path={BASELINE_VHDR_PATH}",
    f"selected_component={selected_component_number}",
    f"channel_count={len(raw_baseline.ch_names)}",
    f"baseline_gt_peak_hz={baseline_gt_peak_hz:.6f}",
    f"baseline_component_peak_hz={selected_component_peak_hz:.6f}",
    f"selected_lambda={selected_lambda:.6f}",
    f"signal_band_hz=({SIGNAL_BAND_HZ[0]:.6f}, {SIGNAL_BAND_HZ[1]:.6f})",
    f"view_band_hz=({VIEW_BAND_HZ[0]:.6f}, {VIEW_BAND_HZ[1]:.6f})",
    f"weights_npz={weights_path.name}",
    f"psd_figure={component_path.name}",
]
manifest_path.write_text("\n".join(manifest_lines) + "\n", encoding="utf-8")

print(f"saved={component_path.name}")
print(f"saved={weights_path.name},{manifest_path.name}")
