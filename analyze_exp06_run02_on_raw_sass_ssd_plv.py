"""Compare run02 ON PLV for top GT-matching raw/SASS channels, selected SSD, and GT-vs-STIM across intensity."""

import os
from pathlib import Path
import warnings

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy import linalg, signal

MNE_CONFIG_ROOT = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS")
(MNE_CONFIG_ROOT / ".mne").mkdir(parents=True, exist_ok=True)
os.environ.setdefault("_MNE_FAKE_HOME_DIR", str(MNE_CONFIG_ROOT))

import mne

import plot_helpers
import preprocessing
import sass


# ============================================================
# CONFIG
# ============================================================
DATA_DIRECTORY = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\TIMS_data_sync\pilot\doseresp")
STIM_VHDR_PATH = DATA_DIRECTORY / "exp06-STIM-iTBS_run02.vhdr"  # measured run02 stimulation recording
OUTPUT_DIRECTORY = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\EXP06")  # explicit output folder
OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)

RUN02_INTENSITY_LABELS = ["10%", "20%", "30%", "40%", "50%"]  # measured run02 dose order
BLOCK_CYCLES_PER_INTENSITY = 20  # expected ON cycles in each dose block
ON_WINDOW_S = (0.3, 1.5)  # accepted interior ON window
LATE_OFF_WINDOW_S = (1.5, 3.2)  # reference window for SASS covariance B
EXCLUDED_CHANNELS = {"TP9", "Fp1", "TP10"}  # keep EEG set aligned with the exp06 SSD work

TARGET_CENTER_HZ = 12.451172  # measured baseline GT peak carried forward as the target frequency
SIGNAL_HALF_WIDTH_HZ = 0.5  # narrow target band for phase metrics
SIGNAL_BAND_HZ = (TARGET_CENTER_HZ - SIGNAL_HALF_WIDTH_HZ, TARGET_CENTER_HZ + SIGNAL_HALF_WIDTH_HZ)
VIEW_BAND_HZ = (4.0, 20.0)  # broad band used for SSD ranking and SASS cleaning
TOP_CHANNEL_COUNT = 1  # compare sensor-space methods using the strongest single in-band channel per block
N_SSD_COMPONENTS = 6  # small candidate pool keeps ON SSD selection readable

RUN02_STIM_THRESHOLD_FRACTION = 0.08  # recover the weak first run02 block
METHOD_COLORS = {
    "raw": "black",
    "sass": "steelblue",
    "ssd": "seagreen",
    "stim": "darkorange",
}

SUMMARY_FIGURE_PATH = OUTPUT_DIRECTORY / "exp06_run02_on_raw_sass_ssd_plv_summary.png"
PHASE_GRID_PATH = OUTPUT_DIRECTORY / "exp06_run02_on_raw_sass_ssd_phase_grid.png"
MANIFEST_PATH = OUTPUT_DIRECTORY / "exp06_run02_on_raw_sass_ssd_plv_summary.txt"


# ============================================================
# PIPELINE
# ============================================================
# run02 recording
#   |
# measured ON timing
#   |
# accepted ON and late-OFF windows
#   |
# per-block raw / SASS / SSD / GT-STIM phase comparison
#   |
# summary figure + phase-grid report


# ============================================================
# 1) LOAD THE RUN02 RECORDING
# ============================================================
with warnings.catch_warnings():
    warnings.filterwarnings("ignore", message="No coordinate information found for channels*")
    warnings.filterwarnings("ignore", message="Online software filter detected*")
    warnings.filterwarnings("ignore", message="Not setting positions of 2 misc channels found in montage*")
    raw_stim_full = mne.io.read_raw_brainvision(str(STIM_VHDR_PATH), preload=True, verbose=False)

if "stim" not in raw_stim_full.ch_names or "ground_truth" not in raw_stim_full.ch_names:
    raise RuntimeError("Stim run is missing required channels: stim and ground_truth.")

sfreq = float(raw_stim_full.info["sfreq"])
stim_trace = raw_stim_full.copy().pick(["stim"]).get_data()[0]  # measured stim voltage trace
gt_trace = raw_stim_full.copy().pick(["ground_truth"]).get_data()[0]  # recorded ground-truth reference trace
raw_eeg = raw_stim_full.copy().drop_channels(
    [
        channel_name
        for channel_name in raw_stim_full.ch_names
        if channel_name.lower() in {"stim", "ground_truth"}
        or channel_name.startswith("STI")
        or channel_name in EXCLUDED_CHANNELS
    ]
)
if len(raw_eeg.ch_names) == 0:
    raise RuntimeError("No retained EEG channels remain after removing stim, GT, and excluded channels.")
raw_data_2d = raw_eeg.get_data()  # retained EEG channel matrix

print(f"Loaded run02: {raw_eeg.n_times / sfreq:.1f}s | sfreq={sfreq:.0f} Hz | EEG channels={len(raw_eeg.ch_names)}")


# ============================================================
# 2) RECOVER THE MEASURED ON TIMING
# ============================================================
block_onsets_samples, block_offsets_samples = preprocessing.detect_stim_blocks(
    stim_trace,
    sfreq,
    threshold_fraction=RUN02_STIM_THRESHOLD_FRACTION,
)
required_block_count = len(RUN02_INTENSITY_LABELS) * BLOCK_CYCLES_PER_INTENSITY
if len(block_onsets_samples) < required_block_count:
    raise RuntimeError(f"Need {required_block_count} ON blocks, but found {len(block_onsets_samples)}.")

on_window_len = float(ON_WINDOW_S[1] - ON_WINDOW_S[0])
on_window_size = int(round(on_window_len * sfreq))  # fixed ON-window size in samples
on_start_shift = int(round(ON_WINDOW_S[0] * sfreq))  # shift into the accepted ON interior

late_off_window_len = float(LATE_OFF_WINDOW_S[1] - LATE_OFF_WINDOW_S[0])
late_off_window_size = int(round(late_off_window_len * sfreq))


# ============================================================
# Helper: Diagnostic plot (PSD + timecourse + ITPC)
# ============================================================
def plot_component_diagnostic(component_data, gt_data, stim_data, intensity_label, method_name, output_dir, sfreq):
    """Plot: PSD | mean timecourse with SD bands vs GT | dual ITPC (vs GT and vs STIM)"""
    fig, axes = plt.subplots(1, 3, figsize=(14, 3))
    fig.suptitle(f"{intensity_label} - {method_name}", fontsize=10, fontweight='bold')

    # Filter to signal band
    comp_signal = preprocessing.filter_signal(component_data, sfreq, SIGNAL_BAND_HZ[0], SIGNAL_BAND_HZ[1])
    gt_signal = preprocessing.filter_signal(gt_data, sfreq, SIGNAL_BAND_HZ[0], SIGNAL_BAND_HZ[1])
    stim_signal = preprocessing.filter_signal(stim_data, sfreq, SIGNAL_BAND_HZ[0], SIGNAL_BAND_HZ[1])

    # 1) PSD
    comp_psd = np.mean(np.abs(np.fft.rfft(component_data, axis=-1)) ** 2, axis=0)
    freqs = np.fft.rfftfreq(component_data.shape[-1], 1 / sfreq)
    axes[0].semilogy(freqs, comp_psd, 'b-', linewidth=1)
    axes[0].axvline(TARGET_CENTER_HZ, color='r', linestyle='--', alpha=0.7, label='12.45 Hz')
    axes[0].set_xlabel('Freq (Hz)'); axes[0].set_ylabel('Power'); axes[0].set_xlim([4, 20])
    axes[0].legend(fontsize=8); axes[0].grid(True, alpha=0.3)

    # 2) Mean timecourse with SD bands: GT on left axis (black), component on right axis (blue)
    mean_tc = np.mean(comp_signal, axis=0)
    std_tc = np.std(comp_signal, axis=0)
    mean_gt = np.mean(gt_signal, axis=0)
    std_gt = np.std(gt_signal, axis=0)
    time_s = np.arange(len(mean_tc)) / sfreq

    ax1 = axes[1]
    ax2 = ax1.twinx()

    # GT on left axis (black) with SD band
    ax1.plot(time_s, mean_gt, 'k-', linewidth=2, label='GT', alpha=0.8)
    ax1.fill_between(time_s, mean_gt - std_gt, mean_gt + std_gt, color='k', alpha=0.15)
    ax1.set_ylabel('GT (µV)', fontsize=8, color='k')
    ax1.tick_params(axis='y', labelcolor='k', labelsize=7)

    # Component on right axis (colored) with SD band
    color_comp = METHOD_COLORS.get(method_name.lower(), 'steelblue')
    ax2.plot(time_s, mean_tc, color=color_comp, linewidth=1.5, label=method_name, alpha=0.8)
    ax2.fill_between(time_s, mean_tc - std_tc, mean_tc + std_tc, color=color_comp, alpha=0.15)
    ax2.set_ylabel(method_name + ' (µV)', fontsize=8, color=color_comp)
    ax2.tick_params(axis='y', labelcolor=color_comp, labelsize=7)

    ax1.set_xlabel('Time (s)', fontsize=8)
    ax1.grid(True, alpha=0.3)
    ax1.legend(loc='upper left', fontsize=7)
    ax2.legend(loc='upper right', fontsize=7)

    # 3) Dual ITPC timecourse: vs GT (green) and vs STIM (red dashed)
    comp_phase = np.angle(signal.hilbert(comp_signal, axis=-1))
    gt_phase = np.angle(signal.hilbert(gt_signal, axis=-1))
    stim_phase = np.angle(signal.hilbert(stim_signal, axis=-1))

    # ITPC vs GT
    phase_diff_gt = comp_phase - gt_phase
    itpc_ts_gt = np.abs(np.mean(np.exp(1j * phase_diff_gt), axis=0))

    # ITPC vs STIM
    phase_diff_stim = comp_phase - stim_phase
    itpc_ts_stim = np.abs(np.mean(np.exp(1j * phase_diff_stim), axis=0))

    axes[2].plot(time_s, itpc_ts_gt, 'g-', linewidth=1.5, label='vs GT', alpha=0.8)
    axes[2].plot(time_s, itpc_ts_stim, 'r--', linewidth=1.5, label='vs STIM', alpha=0.8)
    axes[2].set_xlabel('Time (s)', fontsize=8)
    axes[2].set_ylabel('ITPC', fontsize=8)
    axes[2].set_ylim([0, 1.0])
    axes[2].legend(loc='upper right', fontsize=7)
    axes[2].grid(True, alpha=0.3)

    plt.tight_layout()
    fig_path = output_dir / f"exp06_run02_{method_name.lower().replace(' ', '_')}_{intensity_label.replace('%', 'pct')}_diagnostic.png"
    plt.savefig(fig_path, dpi=100, bbox_inches='tight')
    plt.close()

# ============================================================
# 3) ANALYZE EACH DOSE BLOCK
# ============================================================
summary_rows = []
reference_band_trace = preprocessing.filter_signal(gt_trace, sfreq, SIGNAL_BAND_HZ[0], SIGNAL_BAND_HZ[1])
FIXED_RAW_CH_IDX = None  # Will lock best channel at 10%

for intensity_index, intensity_label in enumerate(RUN02_INTENSITY_LABELS):
    # 3.1 Build this block's accepted ON windows
    block_start_index = intensity_index * BLOCK_CYCLES_PER_INTENSITY
    block_stop_index = block_start_index + BLOCK_CYCLES_PER_INTENSITY
    dose_onsets_on = block_onsets_samples[block_start_index:block_stop_index]
    dose_offsets_on = block_offsets_samples[block_start_index:block_stop_index]

    window_onsets = dose_onsets_on + on_start_shift
    window_keep = window_onsets + on_window_size <= dose_offsets_on
    event_samples_on = window_onsets[window_keep]  # accepted ON starts
    events_on = preprocessing.build_event_array(event_samples_on)
    if len(events_on) != BLOCK_CYCLES_PER_INTENSITY:
        raise RuntimeError(
            f"Expected {BLOCK_CYCLES_PER_INTENSITY} valid ON windows for {intensity_label}, "
            f"but built {len(events_on)}."
        )

    # 3.2 Build late-OFF windows for this intensity's SASS reference covariance
    block_stop_with_next = min(block_stop_index + 1, len(block_onsets_samples))
    dose_onsets_full = block_onsets_samples[block_start_index:block_stop_with_next]
    dose_offsets_full = block_offsets_samples[block_start_index:block_stop_with_next]
    events_late_off, _, _ = preprocessing.build_late_off_events(
        dose_onsets_full,
        dose_offsets_full,
        sfreq,
        LATE_OFF_WINDOW_S[0],
        LATE_OFF_WINDOW_S[1],
    )

    # 3.3 Extract matched raw EEG, GT, and STIM epochs
    on_raw_epochs = np.asarray(
        [
            raw_data_2d[:, int(start_sample):int(start_sample) + on_window_size]
            for start_sample in events_on[:, 0]
        ],
        dtype=float,
    )
    late_off_raw_epochs = np.asarray(
        [
            raw_data_2d[:, int(start_sample):int(start_sample) + late_off_window_size]
            for start_sample in events_late_off[:, 0]
        ],
        dtype=float,
    )
    gt_on_epochs = preprocessing.extract_event_windows(gt_trace, events_on[:, 0], on_window_size)
    stim_on_epochs = preprocessing.extract_event_windows(stim_trace, events_on[:, 0], on_window_size)

    # 3.4 Rank raw channels by PLV with ground truth and select best (or use fixed)
    n_epochs = len(on_raw_epochs)

    if intensity_index == 0:  # 10% - find and lock best channel
        raw_plv_scores = []
        raw_channels_info = []
        for ch_idx, ch_name in enumerate(raw_eeg.ch_names):
            ch_data = on_raw_epochs[:, ch_idx, :]
            metrics_ch = preprocessing.compute_epoch_plv_summary(
                ch_data, gt_on_epochs, sfreq, SIGNAL_BAND_HZ, TARGET_CENTER_HZ,
            )
            raw_plv_scores.append(metrics_ch["plv"])
            ch_signal = preprocessing.filter_signal(ch_data, sfreq, *VIEW_BAND_HZ)
            ch_psd = np.mean(np.abs(np.fft.rfft(ch_signal, axis=-1)) ** 2, axis=0)
            freqs_ch = np.fft.rfftfreq(ch_signal.shape[-1], 1 / sfreq)
            ch_peak_hz = freqs_ch[np.argmax(ch_psd)]
            raw_channels_info.append({
                "name": ch_name, "ch_idx": ch_idx, "plv": metrics_ch["plv"],
                "peak_hz": ch_peak_hz, "p_value": metrics_ch["p_value"],
                "mean_gt_locking": metrics_ch["mean_gt_locking"],
                "phase_samples": metrics_ch["phase_samples"],
            })
        selected_raw_ch_idx = np.argmax(raw_plv_scores)
        FIXED_RAW_CH_IDX = selected_raw_ch_idx
        selected_ch_info = raw_channels_info[selected_raw_ch_idx]
    else:  # 20-50% - use fixed channel
        selected_raw_ch_idx = FIXED_RAW_CH_IDX
        ch_data = on_raw_epochs[:, selected_raw_ch_idx, :]
        metrics_ch = preprocessing.compute_epoch_plv_summary(
            ch_data, gt_on_epochs, sfreq, SIGNAL_BAND_HZ, TARGET_CENTER_HZ,
        )
        ch_signal = preprocessing.filter_signal(ch_data, sfreq, *VIEW_BAND_HZ)
        ch_psd = np.mean(np.abs(np.fft.rfft(ch_signal, axis=-1)) ** 2, axis=0)
        freqs_ch = np.fft.rfftfreq(ch_signal.shape[-1], 1 / sfreq)
        ch_peak_hz = freqs_ch[np.argmax(ch_psd)]
        selected_ch_info = {
            "name": raw_eeg.ch_names[selected_raw_ch_idx], "ch_idx": selected_raw_ch_idx,
            "plv": metrics_ch["plv"], "peak_hz": ch_peak_hz, "p_value": metrics_ch["p_value"],
            "mean_gt_locking": metrics_ch["mean_gt_locking"], "phase_samples": metrics_ch["phase_samples"],
        }

    on_raw_selected = on_raw_epochs[:, selected_raw_ch_idx, :]
    raw_metrics = preprocessing.compute_epoch_plv_summary(
        on_raw_selected,
        gt_on_epochs,
        sfreq,
        SIGNAL_BAND_HZ,
        TARGET_CENTER_HZ,
    )
    plot_component_diagnostic(on_raw_selected, gt_on_epochs, stim_on_epochs, intensity_label, "Raw", OUTPUT_DIRECTORY, sfreq)

    # Create compatible output structure for consistency with previous code
    raw_selection = {
        "selected_rows": [selected_ch_info],
        "mean_selected_plv": float(raw_metrics["plv"]),
        "best_channel_name": selected_ch_info["name"],
        "best_channel_plv": float(raw_metrics["plv"]),
        "best_phase_samples": selected_ch_info["phase_samples"],
        "best_channel_p_value": float(raw_metrics["p_value"]),
        "selection_note": "GT-locking supervised (PLV)",
    }

    # 3.5 Apply SASS in the broad 4-20 Hz view band, then extract synthetic source via eigendecomposition
    # SASS suppresses artifact by nulling top artifact-dominant eigenvectors.
    # We then re-decompose the cleaned signal to extract a synthetic source (like SSD).
    on_view_epochs = preprocessing.filter_signal(on_raw_epochs, sfreq, VIEW_BAND_HZ[0], VIEW_BAND_HZ[1])
    late_off_view_epochs = preprocessing.filter_signal(
        late_off_raw_epochs,
        sfreq,
        VIEW_BAND_HZ[0],
        VIEW_BAND_HZ[1],
    )
    n_epochs, n_channels, n_samples = on_view_epochs.shape
    on_view_concat = on_view_epochs.transpose(1, 0, 2).reshape(n_channels, -1)
    late_off_view_concat = late_off_view_epochs.transpose(1, 0, 2).reshape(n_channels, -1)
    cov_a = np.cov(on_view_concat)
    cov_b = np.cov(late_off_view_concat)
    sass_cleaned_concat = sass.sass(on_view_concat, cov_a, cov_b)
    on_sass_epochs = sass_cleaned_concat.reshape(n_channels, n_epochs, n_samples).transpose(1, 0, 2)

    # ---- PURE SASS: Rank all cleaned channels by PLV + peak freq validation ----
    on_sass_epochs = sass_cleaned_concat.reshape(n_channels, n_epochs, n_samples).transpose(1, 0, 2)

    sass_plv_scores = []
    sass_channels_info = []
    for ch_idx, ch_name in enumerate(raw_eeg.ch_names):
        ch_data = on_sass_epochs[:, ch_idx, :]
        metrics_ch = preprocessing.compute_epoch_plv_summary(
            ch_data, gt_on_epochs, sfreq, SIGNAL_BAND_HZ, TARGET_CENTER_HZ,
        )
        ch_signal = preprocessing.filter_signal(ch_data, sfreq, *VIEW_BAND_HZ)
        ch_psd = np.mean(np.abs(np.fft.rfft(ch_signal, axis=-1)) ** 2, axis=0)
        freqs_ch = np.fft.rfftfreq(ch_signal.shape[-1], 1 / sfreq)
        ch_peak_hz = freqs_ch[np.argmax(ch_psd)]

        # Compute signal-to-broadband ratio (12.45 Hz band vs 4-20 Hz)
        signal_band_idx = np.where((freqs_ch >= SIGNAL_BAND_HZ[0]) & (freqs_ch <= SIGNAL_BAND_HZ[1]))[0]
        signal_power = np.mean(ch_psd[signal_band_idx]) if len(signal_band_idx) > 0 else 0
        broadband_power = np.mean(ch_psd)
        signal_ratio = signal_power / (broadband_power + 1e-8)

        sass_plv_scores.append(metrics_ch["plv"])
        sass_channels_info.append({
            "name": ch_name, "plv": metrics_ch["plv"], "peak_hz": ch_peak_hz,
            "signal_ratio": signal_ratio,
        })

    # Select: high PLV AND peak near 12.45 Hz (within ±1 Hz) AND high signal/broadband ratio
    valid_idx = [i for i, info in enumerate(sass_channels_info)
                 if abs(info["peak_hz"] - TARGET_CENTER_HZ) < 1.0 and info["signal_ratio"] > 0.15]

    if valid_idx:
        selected_sass_ch_idx = valid_idx[np.argmax([sass_plv_scores[i] for i in valid_idx])]
    else:
        selected_sass_ch_idx = np.argmax(sass_plv_scores)

    selected_sass_ch_info = sass_channels_info[selected_sass_ch_idx]
    on_sass_source = on_sass_epochs[:, selected_sass_ch_idx, :]
    selected_sass_source_index = selected_sass_ch_idx
    sass_selection = preprocessing.compute_epoch_plv_summary(
        on_sass_source,
        gt_on_epochs,
        sfreq,
        SIGNAL_BAND_HZ,
        TARGET_CENTER_HZ,
    )
    plot_component_diagnostic(on_sass_source, gt_on_epochs, stim_on_epochs, intensity_label, "SASS", OUTPUT_DIRECTORY, sfreq)

    # 3.6 Fit SSD on ON windows and select best component supervised by GT-locking (PLV)
    # Generalized eigendecomposition: maximize signal-band variance relative to view-band.
    # Selection: rank components by direct PLV with ground-truth, not spectral power ratio.
    n_components = min(N_SSD_COMPONENTS, len(raw_eeg.ch_names))
    n_epochs = len(on_raw_epochs)

    # Extract ON and late-OFF epochs for SSD covariance estimation
    on_raw_concat = on_raw_epochs.transpose(1, 0, 2).reshape(len(raw_eeg.ch_names), -1)
    late_off_raw_concat = late_off_raw_epochs.transpose(1, 0, 2).reshape(len(raw_eeg.ch_names), -1)

    # Filter to signal and view bands
    signal_band_concat = preprocessing.filter_signal(on_raw_concat, sfreq, *SIGNAL_BAND_HZ)
    view_band_concat = preprocessing.filter_signal(on_raw_concat, sfreq, *VIEW_BAND_HZ)

    # Generalized eigendecomposition: C_signal · w = λ · C_view · w
    C_signal = np.cov(signal_band_concat)
    C_view = np.cov(view_band_concat)
    eigenvalues, eigenvectors = linalg.eig(C_signal, C_view)
    eigenvalues = eigenvalues.real
    eigenvectors = eigenvectors.real

    # Sort by descending eigenvalue and keep top N components
    sort_idx = np.argsort(eigenvalues)[::-1]
    eigenvectors_sorted = eigenvectors[:, sort_idx]
    spatial_filters = eigenvectors_sorted[:, :n_components].T  # (n_components, n_channels)

    # Rank each component by PLV + peak freq validation
    ssd_plv_scores = []
    ssd_components_info = []
    component_epochs_list = []
    for spatial_filter in spatial_filters:
        on_component = np.dot(spatial_filter, on_raw_concat)
        on_component_epochs = on_component.reshape(n_epochs, -1)
        component_epochs_list.append(on_component_epochs)
        metrics_comp = preprocessing.compute_epoch_plv_summary(
            on_component_epochs, gt_on_epochs, sfreq, SIGNAL_BAND_HZ, TARGET_CENTER_HZ,
        )

        # Check peak frequency and signal/broadband ratio
        comp_signal = preprocessing.filter_signal(on_component_epochs, sfreq, *VIEW_BAND_HZ)
        comp_psd = np.mean(np.abs(np.fft.rfft(comp_signal, axis=-1)) ** 2, axis=0)
        freqs_comp = np.fft.rfftfreq(comp_signal.shape[-1], 1 / sfreq)
        comp_peak_hz = freqs_comp[np.argmax(comp_psd)]

        signal_band_idx = np.where((freqs_comp >= SIGNAL_BAND_HZ[0]) & (freqs_comp <= SIGNAL_BAND_HZ[1]))[0]
        signal_power = np.mean(comp_psd[signal_band_idx]) if len(signal_band_idx) > 0 else 0
        broadband_power = np.mean(comp_psd)
        signal_ratio = signal_power / (broadband_power + 1e-8)

        ssd_plv_scores.append(metrics_comp["plv"])
        ssd_components_info.append({
            "plv": metrics_comp["plv"], "peak_hz": comp_peak_hz, "signal_ratio": signal_ratio,
        })

    # Select: high PLV AND peak near 12.45 Hz AND high signal/broadband ratio
    valid_idx = [i for i, info in enumerate(ssd_components_info)
                 if abs(info["peak_hz"] - TARGET_CENTER_HZ) < 1.0 and info["signal_ratio"] > 0.15]

    if valid_idx:
        selected_component_index = valid_idx[np.argmax([ssd_plv_scores[i] for i in valid_idx])]
    else:
        selected_component_index = np.argmax(ssd_plv_scores)
    selected_component_epochs = np.asarray(component_epochs_list[selected_component_index], dtype=float).reshape(n_epochs, -1)
    ssd_metrics = preprocessing.compute_epoch_plv_summary(
        selected_component_epochs,
        gt_on_epochs,
        sfreq,
        SIGNAL_BAND_HZ,
        TARGET_CENTER_HZ,
    )
    plot_component_diagnostic(selected_component_epochs, gt_on_epochs, stim_on_epochs, intensity_label, "SSD", OUTPUT_DIRECTORY, sfreq)

    # Compute peak frequency for reporting (from the selected component)
    component_signal = preprocessing.filter_signal(selected_component_epochs, sfreq, *VIEW_BAND_HZ)
    component_psd = np.mean(np.abs(np.fft.rfft(component_signal, axis=-1)) ** 2, axis=0)
    freqs = np.fft.rfftfreq(component_signal.shape[-1], 1 / sfreq)
    peak_freqs_selected = freqs[np.argmax(component_psd)]

    # 3.7 Keep GT-vs-STIM as an explicit reference condition
    stim_metrics = preprocessing.compute_epoch_plv_summary(
        stim_on_epochs,
        gt_on_epochs,
        sfreq,
        SIGNAL_BAND_HZ,
        TARGET_CENTER_HZ,
    )

    # Compute SASS source peak frequency for reporting
    sass_source_signal = preprocessing.filter_signal(on_sass_source, sfreq, *VIEW_BAND_HZ)
    sass_source_psd = np.mean(np.abs(np.fft.rfft(sass_source_signal, axis=-1)) ** 2, axis=0)
    freqs = np.fft.rfftfreq(sass_source_signal.shape[-1], 1 / sfreq)
    peak_freqs_sass_source = freqs[np.argmax(sass_source_psd)]

    summary_rows.append(
        {
            "label": intensity_label,
            "intensity_pct": int(intensity_label.replace("%", "")),
            "event_count": int(len(events_on)),
            "raw_selection": raw_selection,
            "sass_plv": float(sass_selection["plv"]),
            "sass_p_value": float(sass_selection["p_value"]),
            "sass_mean_gt_locking": float(sass_selection["mean_gt_locking"]),
            "sass_source_component_number": int(selected_sass_source_index + 1),
            "sass_peak_hz": float(peak_freqs_sass_source),
            "sass_phase_samples": np.asarray(sass_selection["phase_samples"], dtype=float),
            "ssd_component_number": int(selected_component_index + 1),
            "ssd_peak_hz": float(peak_freqs_selected),
            "ssd_plv": float(ssd_metrics["plv"]),
            "ssd_p_value": float(ssd_metrics["p_value"]),
            "ssd_mean_gt_locking": float(ssd_metrics["mean_gt_locking"]),
            "ssd_phase_samples": np.asarray(ssd_metrics["phase_samples"], dtype=float),
            "stim_plv": float(stim_metrics["plv"]),
            "stim_p_value": float(stim_metrics["p_value"]),
            "stim_mean_gt_locking": float(stim_metrics["mean_gt_locking"]),
            "stim_phase_samples": np.asarray(stim_metrics["phase_samples"], dtype=float),
        }
    )

    raw_names = ", ".join(row["name"] for row in raw_selection["selected_rows"]) or "none"
    print(
        f"{intensity_label}: raw={raw_selection['mean_selected_plv']:.3f} ({raw_names}) | "
        f"sass_source={sass_selection['plv']:.3f} (comp {selected_sass_source_index + 1}) | "
        f"ssd={ssd_metrics['plv']:.3f} (comp {selected_component_index + 1}) | "
        f"stim={stim_metrics['plv']:.3f}"
    )


# ============================================================
# 4) SAVE THE SUMMARY FIGURES
# ============================================================
intensity_values = np.asarray([row["intensity_pct"] for row in summary_rows], dtype=int)
event_counts = np.asarray([row["event_count"] for row in summary_rows], dtype=int)
raw_plv_values = np.asarray([row["raw_selection"]["mean_selected_plv"] for row in summary_rows], dtype=float)
sass_plv_values = np.asarray([row["sass_plv"] for row in summary_rows], dtype=float)
ssd_plv_values = np.asarray([row["ssd_plv"] for row in summary_rows], dtype=float)
stim_plv_values = np.asarray([row["stim_plv"] for row in summary_rows], dtype=float)

plot_helpers.save_plv_method_summary_figure(
    x_values=intensity_values,
    event_counts=event_counts,
    method_series=[
        {"label": "Raw top channels", "values": raw_plv_values, "color": METHOD_COLORS["raw"], "linewidth": 2.0},
        {"label": "SASS source (PLV-supervised)", "values": sass_plv_values, "color": METHOD_COLORS["sass"], "linewidth": 2.2},
        {"label": "Selected SSD (PLV-supervised)", "values": ssd_plv_values, "color": METHOD_COLORS["ssd"], "linewidth": 2.2},
        {"label": "GT vs STIM", "values": stim_plv_values, "color": METHOD_COLORS["stim"], "linewidth": 1.8},
    ],
    output_path=SUMMARY_FIGURE_PATH,
    title="run02 ON PLV: raw channels vs SASS source vs SSD source (GT-locking supervised) and GT-STIM",
)

phase_grid_rows = []
for row in summary_rows:
    phase_grid_rows.append(
        [
            {
                "title": f"{row['label']} Raw {row['raw_selection']['best_channel_name']}\nPLV={float(row['raw_selection']['best_channel_plv']):.2f}",
                "phases": row["raw_selection"]["best_phase_samples"] if row["raw_selection"]["best_phase_samples"].size else np.array([0.0]),
                "plv": row["raw_selection"]["best_channel_plv"] if np.isfinite(row["raw_selection"]["best_channel_plv"]) else 0.0,
                "p_value": row["raw_selection"]["best_channel_p_value"] if np.isfinite(row["raw_selection"]["best_channel_p_value"]) else 1.0,
                "color": METHOD_COLORS["raw"],
            },
            {
                "title": f"{row['label']} SASS Source (comp {row['sass_source_component_number']})\nPLV={float(row['sass_plv']):.2f}",
                "phases": row["sass_phase_samples"],
                "plv": row["sass_plv"],
                "p_value": row["sass_p_value"],
                "color": METHOD_COLORS["sass"],
            },
            {
                "title": f"{row['label']} SSD (comp {row['ssd_component_number']})\nPLV={float(row['ssd_plv']):.2f}",
                "phases": row["ssd_phase_samples"],
                "plv": row["ssd_plv"],
                "p_value": row["ssd_p_value"],
                "color": METHOD_COLORS["ssd"],
            },
            {
                "title": f"{row['label']} GT-STIM\nPLV={float(row['stim_plv']):.2f}",
                "phases": row["stim_phase_samples"],
                "plv": row["stim_plv"],
                "p_value": row["stim_p_value"],
                "color": METHOD_COLORS["stim"],
            },
        ]
    )
plot_helpers.save_phase_histogram_grid(
    phase_grid_rows=phase_grid_rows,
    output_path=PHASE_GRID_PATH,
    title="run02 ON phase distributions against GT",
)


# ============================================================
# 5) SAVE THE SHORT REPORT
# ============================================================
manifest_lines = [
    "exp06 run02 ON raw vs SASS source vs SSD PLV summary",
    "question=Which run02 ON representation stays most GT-locked across intensity when raw, SASS source, and SSD all select their representations supervised by direct GT-locking (PLV), and GT-STIM is kept as a reference?",
    f"stim_vhdr_path={STIM_VHDR_PATH}",
    f"excluded_channels={sorted(EXCLUDED_CHANNELS)}",
    f"signal_band_hz=({SIGNAL_BAND_HZ[0]:.6f}, {SIGNAL_BAND_HZ[1]:.6f})",
    f"view_band_hz=({VIEW_BAND_HZ[0]:.6f}, {VIEW_BAND_HZ[1]:.6f})",
    f"reference_peak_hz={TARGET_CENTER_HZ:.6f}",
    f"on_window_s=({ON_WINDOW_S[0]:.6f}, {ON_WINDOW_S[1]:.6f})",
    f"late_off_window_s=({LATE_OFF_WINDOW_S[0]:.6f}, {LATE_OFF_WINDOW_S[1]:.6f})",
    f"top_channel_count={TOP_CHANNEL_COUNT}",
    f"stim_threshold_fraction={RUN02_STIM_THRESHOLD_FRACTION:.3f}",
    "raw_selection=rank all raw EEG channels by direct PLV with ground truth in the 12.45 Hz band; keep the highest-locking channel (same supervised selection as SASS source and SSD).",
    "sass_selection=fit SASS in the 4-20 Hz view band using this block's ON covariance against its measured late-OFF covariance; then decompose the artifact-suppressed signal via generalized eigendecomposition (ON vs late-OFF covariance in 12.45 Hz band); rank components by direct PLV with ground truth and keep the highest-locking synthetic source.",
    "ssd_selection=fit SSD (generalized eigendecomposition) on the accepted ON windows of each block, maximizing signal-band variance relative to view-band; rank all components by direct PLV with ground truth and keep the highest-locking component.",
    "plv_definition=band-pass signal and GT into the 12.45 Hz target band, sample the wrapped phase difference once per GT cycle inside each epoch, then compute PLV from those cycle samples.",
    "summary_note=raw, SASS source, and SSD are each summarized by one highest-GT-locking channel/component per block (all supervised by direct PLV).",
    f"summary_figure={SUMMARY_FIGURE_PATH.name}",
    f"phase_grid={PHASE_GRID_PATH.name}",
    "",
]
for row in summary_rows:
    raw_rows = row["raw_selection"]["selected_rows"]
    raw_peaks_text = ", ".join(f"{channel_row['peak_hz']:.6f}" for channel_row in raw_rows)
    raw_plv_text = ", ".join(f"{channel_row['plv']:.6f}" for channel_row in raw_rows)
    report_block = {
        "event_count": row["event_count"],
        "raw_selected_channels": ", ".join(channel_row["name"] for channel_row in raw_rows),
        "raw_selected_peaks_hz": raw_peaks_text,
        "raw_selected_plv": raw_plv_text,
        "raw_selection_note": row["raw_selection"]["selection_note"],
        "raw_mean_selected_plv": f"{row['raw_selection']['mean_selected_plv']:.6f}",
        "raw_best_channel": row["raw_selection"]["best_channel_name"],
        "raw_best_channel_plv": f"{row['raw_selection']['best_channel_plv']:.6f}",
        "sass_source_component": row["sass_source_component_number"],
        "sass_peak_hz": f"{row['sass_peak_hz']:.6f}",
        "sass_plv": f"{row['sass_plv']:.6f}",
        "sass_mean_gt_locking": f"{row['sass_mean_gt_locking']:.6f}",
        "ssd_component": row["ssd_component_number"],
        "ssd_peak_hz": f"{row['ssd_peak_hz']:.6f}",
        "ssd_plv": f"{row['ssd_plv']:.6f}",
        "ssd_mean_gt_locking": f"{row['ssd_mean_gt_locking']:.6f}",
        "stim_plv": f"{row['stim_plv']:.6f}",
        "stim_mean_gt_locking": f"{row['stim_mean_gt_locking']:.6f}",
    }
    manifest_lines.append(f"{row['label']}")
    manifest_lines.extend(f"{key}={value}" for key, value in report_block.items())
    manifest_lines.append("")
MANIFEST_PATH.write_text("\n".join(manifest_lines) + "\n", encoding="utf-8")

print(f"saved={SUMMARY_FIGURE_PATH.name}")
print(f"saved={PHASE_GRID_PATH.name}")
print(f"saved={MANIFEST_PATH.name}")
