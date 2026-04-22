"""Compare run02 ON PLV for raw/SASS/SSD with SNR-based component selection (not PLV).

KEY CHANGE: Instead of selecting components by PLV/ITPC (which is biased toward artifact
because GT and STIM both repeat at 12.45 Hz), we select by SNR = power at 12.45 Hz / broadband 4-20 Hz power.

Raw path: Lock the best SNR channel at 10%, then apply it to all intensities (10-50%).
SASS path: Select the SASS-cleaned channel with best SNR per intensity.
SSD path: Select the SSD component with best SNR per intensity.
"""

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
STIM_VHDR_PATH = DATA_DIRECTORY / "exp06-STIM-iTBS_run02.vhdr"
OUTPUT_DIRECTORY = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\EXP06")
OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)

RUN02_INTENSITY_LABELS = ["10%", "20%", "30%", "40%", "50%"]
BLOCK_CYCLES_PER_INTENSITY = 20
ON_WINDOW_S = (0.3, 1.5)
LATE_OFF_WINDOW_S = (1.5, 3.2)
EXCLUDED_CHANNELS = {"TP9", "Fp1", "TP10"}

TARGET_CENTER_HZ = 12.451172
SIGNAL_HALF_WIDTH_HZ = 0.5
SIGNAL_BAND_HZ = (TARGET_CENTER_HZ - SIGNAL_HALF_WIDTH_HZ, TARGET_CENTER_HZ + SIGNAL_HALF_WIDTH_HZ)
VIEW_BAND_HZ = (4.0, 20.0)
N_SSD_COMPONENTS = 6

RUN02_STIM_THRESHOLD_FRACTION = 0.08
METHOD_COLORS = {
    "raw": "black",
    "sass": "steelblue",
    "ssd": "seagreen",
    "stim": "darkorange",
}

SUMMARY_FIGURE_PATH = OUTPUT_DIRECTORY / "exp06_run02_on_raw_sass_ssd_plv_snr_selection.png"
PHASE_GRID_PATH = OUTPUT_DIRECTORY / "exp06_run02_on_raw_sass_ssd_phase_grid_snr_selection.png"
MANIFEST_PATH = OUTPUT_DIRECTORY / "exp06_run02_on_raw_sass_ssd_plv_snr_selection.txt"


# ============================================================
# HELPER: SNR Computation
# ============================================================
def compute_snr(signal_epochs, sfreq, signal_band, view_band):
    """
    Compute SNR = mean power in signal_band / mean power in view_band.

    Args:
        signal_epochs: (n_epochs, n_samples) or (n_channels, n_epochs, n_samples)
        sfreq: sampling frequency
        signal_band: (lo_hz, hi_hz) tuple
        view_band: (lo_hz, hi_hz) tuple

    Returns:
        snr: scalar or (n_channels,) array
    """
    # Flatten to time series for FFT
    if signal_epochs.ndim == 2:
        # (n_epochs, n_samples) → (n_epochs * n_samples,)
        flat = signal_epochs.reshape(-1)
    else:
        # (n_channels, n_epochs, n_samples) → (n_channels, n_epochs * n_samples) → per-channel
        flat_list = []
        for ch_idx in range(signal_epochs.shape[0]):
            flat_list.append(signal_epochs[ch_idx].reshape(-1))
        flat = np.array(flat_list)

    psd = np.abs(np.fft.rfft(flat, axis=-1)) ** 2
    freqs = np.fft.rfftfreq(flat.shape[-1] if flat.ndim == 1 else flat.shape[-1], 1 / sfreq)

    # Signal band power
    signal_idx = np.where((freqs >= signal_band[0]) & (freqs <= signal_band[1]))[0]
    if signal_epochs.ndim == 2:
        signal_power = np.mean(psd[signal_idx])
    else:
        signal_power = np.mean(psd[:, signal_idx], axis=1)

    # Broadband power
    view_idx = np.where((freqs >= view_band[0]) & (freqs <= view_band[1]))[0]
    if signal_epochs.ndim == 2:
        view_power = np.mean(psd[view_idx])
    else:
        view_power = np.mean(psd[:, view_idx], axis=1)

    # Avoid divide by zero
    view_power = np.maximum(view_power, 1e-10)

    snr = signal_power / view_power
    return snr


# ============================================================
# HELPER: Diagnostic plot (PSD + timecourse + ITPC)
# ============================================================
def plot_component_diagnostic(component_data, gt_data, stim_data, intensity_label, method_name, output_dir, sfreq):
    """Plot: PSD | mean timecourse with SD bands vs GT | dual ITPC (vs GT and vs STIM)"""
    fig, axes = plt.subplots(1, 3, figsize=(14, 3))
    fig.suptitle(f"{intensity_label} - {method_name} (SNR Selection)", fontsize=10, fontweight='bold')

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
    fig_path = output_dir / f"exp06_run02_{method_name.lower().replace(' ', '_')}_{intensity_label.replace('%', 'pct')}_snr_diagnostic.png"
    plt.savefig(fig_path, dpi=100, bbox_inches='tight')
    plt.close()


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
stim_trace = raw_stim_full.copy().pick(["stim"]).get_data()[0]
gt_trace = raw_stim_full.copy().pick(["ground_truth"]).get_data()[0]
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
raw_data_2d = raw_eeg.get_data()

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
on_window_size = int(round(on_window_len * sfreq))
on_start_shift = int(round(ON_WINDOW_S[0] * sfreq))

late_off_window_len = float(LATE_OFF_WINDOW_S[1] - LATE_OFF_WINDOW_S[0])
late_off_window_size = int(round(late_off_window_len * sfreq))


# ============================================================
# 3) ANALYZE EACH DOSE BLOCK WITH SNR SELECTION
# ============================================================
summary_rows = []
reference_band_trace = preprocessing.filter_signal(gt_trace, sfreq, SIGNAL_BAND_HZ[0], SIGNAL_BAND_HZ[1])
FIXED_RAW_CH_IDX = None  # Will lock best SNR channel at 10%

for intensity_index, intensity_label in enumerate(RUN02_INTENSITY_LABELS):
    print(f"\n{'='*70}")
    print(f"Processing {intensity_label}")
    print(f"{'='*70}")

    # 3.1 Build this block's accepted ON windows
    block_start_index = intensity_index * BLOCK_CYCLES_PER_INTENSITY
    block_stop_index = block_start_index + BLOCK_CYCLES_PER_INTENSITY
    dose_onsets_on = block_onsets_samples[block_start_index:block_stop_index]
    dose_offsets_on = block_offsets_samples[block_start_index:block_stop_index]

    window_onsets = dose_onsets_on + on_start_shift
    window_keep = window_onsets + on_window_size <= dose_offsets_on
    event_samples_on = window_onsets[window_keep]
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

    # 3.4 RAW PATH: Select channel with best SNR at 10%, then lock it
    n_epochs = len(on_raw_epochs)

    if intensity_index == 0:  # 10% - find and lock best SNR channel
        print("  Raw: Finding best SNR channel...")
        raw_snr_scores = []
        raw_channels_info = []
        for ch_idx, ch_name in enumerate(raw_eeg.ch_names):
            ch_data = on_raw_epochs[:, ch_idx, :]
            snr = compute_snr(ch_data, sfreq, SIGNAL_BAND_HZ, VIEW_BAND_HZ)
            raw_snr_scores.append(snr)
            raw_channels_info.append({
                "name": ch_name, "ch_idx": ch_idx, "snr": snr,
            })

        selected_raw_ch_idx = np.argmax(raw_snr_scores)
        FIXED_RAW_CH_IDX = selected_raw_ch_idx
        selected_ch_info = raw_channels_info[selected_raw_ch_idx]
        print(f"    Selected: {selected_ch_info['name']} (SNR={selected_ch_info['snr']:.4f})")
    else:  # 20-50% - use fixed channel
        selected_raw_ch_idx = FIXED_RAW_CH_IDX
        ch_data = on_raw_epochs[:, selected_raw_ch_idx, :]
        snr = compute_snr(ch_data, sfreq, SIGNAL_BAND_HZ, VIEW_BAND_HZ)
        selected_ch_info = {
            "name": raw_eeg.ch_names[selected_raw_ch_idx], "ch_idx": selected_raw_ch_idx, "snr": snr,
        }
        print(f"  Raw: Using locked channel {selected_ch_info['name']} (SNR={snr:.4f})")

    on_raw_selected = on_raw_epochs[:, selected_raw_ch_idx, :]
    raw_metrics = preprocessing.compute_epoch_plv_summary(
        on_raw_selected,
        gt_on_epochs,
        sfreq,
        SIGNAL_BAND_HZ,
        TARGET_CENTER_HZ,
    )
    print(f"    PLV(vs GT)={raw_metrics['plv']:.4f}")
    plot_component_diagnostic(on_raw_selected, gt_on_epochs, stim_on_epochs, intensity_label, "Raw", OUTPUT_DIRECTORY, sfreq)

    raw_selection = {
        "selected_rows": [selected_ch_info],
        "mean_selected_plv": float(raw_metrics["plv"]),
        "best_channel_name": selected_ch_info["name"],
        "best_channel_snr": float(selected_ch_info["snr"]),
        "best_channel_plv": float(raw_metrics["plv"]),
        "best_phase_samples": raw_metrics.get("phase_samples", np.array([])),
        "best_channel_p_value": float(raw_metrics.get("p_value", 1.0)),
        "selection_note": "SNR-based (NOT PLV)",
    }

    # 3.5 SASS PATH: Apply SASS then select by SNR
    print("  SASS: Cleaning and selecting by SNR...")
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

    # Rank SASS-cleaned channels by SNR
    sass_snr_scores = []
    sass_channels_info = []
    for ch_idx, ch_name in enumerate(raw_eeg.ch_names):
        ch_data = on_sass_epochs[:, ch_idx, :]
        snr = compute_snr(ch_data, sfreq, SIGNAL_BAND_HZ, VIEW_BAND_HZ)
        sass_snr_scores.append(snr)
        sass_channels_info.append({
            "name": ch_name, "ch_idx": ch_idx, "snr": snr,
        })

    selected_sass_ch_idx = np.argmax(sass_snr_scores)
    selected_sass_ch_info = sass_channels_info[selected_sass_ch_idx]
    on_sass_source = on_sass_epochs[:, selected_sass_ch_idx, :]
    print(f"    Selected: {selected_sass_ch_info['name']} (SNR={selected_sass_ch_info['snr']:.4f})")

    sass_metrics = preprocessing.compute_epoch_plv_summary(
        on_sass_source,
        gt_on_epochs,
        sfreq,
        SIGNAL_BAND_HZ,
        TARGET_CENTER_HZ,
    )
    print(f"    PLV(vs GT)={sass_metrics['plv']:.4f}")
    plot_component_diagnostic(on_sass_source, gt_on_epochs, stim_on_epochs, intensity_label, "SASS", OUTPUT_DIRECTORY, sfreq)

    sass_selection = {
        "selected_rows": [selected_sass_ch_info],
        "mean_selected_plv": float(sass_metrics["plv"]),
        "best_channel_name": selected_sass_ch_info["name"],
        "best_channel_snr": float(selected_sass_ch_info["snr"]),
        "best_channel_plv": float(sass_metrics["plv"]),
        "best_phase_samples": sass_metrics.get("phase_samples", np.array([])),
        "best_channel_p_value": float(sass_metrics.get("p_value", 1.0)),
        "selection_note": "SNR-based (NOT PLV)",
    }

    # 3.6 SSD PATH: Decompose and select by SNR
    print("  SSD: Decomposing and selecting by SNR...")
    on_signal_epochs = preprocessing.filter_signal(on_raw_epochs, sfreq, SIGNAL_BAND_HZ[0], SIGNAL_BAND_HZ[1])
    on_view_epochs_ssd = preprocessing.filter_signal(on_raw_epochs, sfreq, VIEW_BAND_HZ[0], VIEW_BAND_HZ[1])

    on_signal_concat = on_signal_epochs.transpose(1, 0, 2).reshape(n_channels, -1)
    on_view_concat_ssd = on_view_epochs_ssd.transpose(1, 0, 2).reshape(n_channels, -1)

    cov_signal = np.cov(on_signal_concat)
    cov_view = np.cov(on_view_concat_ssd)

    # Generalized eigendecomposition: maximize signal-band variance relative to broadband
    try:
        evals, evecs = linalg.eigh(cov_signal, cov_view)
        evals = np.maximum(evals, 0)  # Ensure non-negative
        sorted_idx = np.argsort(evals)[::-1]  # Descending order
        evecs = evecs[:, sorted_idx]
        evals = evals[sorted_idx]
    except linalg.LinAlgError:
        print("    SSD decomposition failed, using SVD fallback")
        U, _, _ = np.linalg.svd(cov_signal)
        evecs = U
        evals = np.ones(n_channels)

    # Extract and rank top N_SSD_COMPONENTS by SNR
    component_epochs_list = []
    ssd_snr_scores = []
    ssd_components_info = []

    for comp_idx in range(min(N_SSD_COMPONENTS, n_channels)):
        comp_weights = evecs[:, comp_idx]
        comp_epochs = np.array([
            on_raw_epochs[epoch_idx].T.dot(comp_weights)
            for epoch_idx in range(n_epochs)
        ])
        component_epochs_list.append(comp_epochs)

        snr = compute_snr(comp_epochs, sfreq, SIGNAL_BAND_HZ, VIEW_BAND_HZ)
        ssd_snr_scores.append(snr)
        ssd_components_info.append({
            "component_idx": comp_idx, "snr": snr,
        })

    selected_component_index = np.argmax(ssd_snr_scores)
    selected_component_epochs = np.asarray(component_epochs_list[selected_component_index], dtype=float).reshape(n_epochs, -1)
    selected_component_snr = ssd_snr_scores[selected_component_index]
    print(f"    Selected: Component {selected_component_index} (SNR={selected_component_snr:.4f})")

    ssd_metrics = preprocessing.compute_epoch_plv_summary(
        selected_component_epochs,
        gt_on_epochs,
        sfreq,
        SIGNAL_BAND_HZ,
        TARGET_CENTER_HZ,
    )
    print(f"    PLV(vs GT)={ssd_metrics['plv']:.4f}")
    plot_component_diagnostic(selected_component_epochs, gt_on_epochs, stim_on_epochs, intensity_label, "SSD", OUTPUT_DIRECTORY, sfreq)

    ssd_selection = {
        "selected_rows": [ssd_components_info[selected_component_index]],
        "mean_selected_plv": float(ssd_metrics["plv"]),
        "component_index": selected_component_index,
        "best_component_snr": float(selected_component_snr),
        "best_component_plv": float(ssd_metrics["plv"]),
        "best_phase_samples": ssd_metrics.get("phase_samples", np.array([])),
        "best_component_p_value": float(ssd_metrics.get("p_value", 1.0)),
        "selection_note": "SNR-based (NOT PLV)",
    }

    # Store results
    summary_rows.append({
        "label": intensity_label,
        "raw_selection": raw_selection,
        "raw_snr": float(selected_ch_info["snr"]),
        "raw_plv": float(raw_metrics["plv"]),
        "sass_selection": sass_selection,
        "sass_snr": float(selected_sass_ch_info["snr"]),
        "sass_plv": float(sass_metrics["plv"]),
        "ssd_selection": ssd_selection,
        "ssd_snr": float(selected_component_snr),
        "ssd_plv": float(ssd_metrics["plv"]),
    })

print("\n" + "="*70)
print("SUMMARY TABLE: SNR vs PLV Across Intensities")
print("="*70)
print(f"{'Intensity':<12} {'Raw SNR':<10} {'Raw PLV':<10} {'SASS SNR':<10} {'SASS PLV':<10} {'SSD SNR':<10} {'SSD PLV':<10}")
print("-"*70)
for row in summary_rows:
    print(f"{row['label']:<12} {row['raw_snr']:<10.4f} {row['raw_plv']:<10.4f} {row['sass_snr']:<10.4f} {row['sass_plv']:<10.4f} {row['ssd_snr']:<10.4f} {row['ssd_plv']:<10.4f}")

# ============================================================
# SAVE SUMMARY
# ============================================================
summary_text = "SNR-BASED COMPONENT SELECTION RESULTS\n"
summary_text += "="*70 + "\n"
summary_text += "Raw: Same channel (selected at 10%) applied to all intensities\n"
summary_text += "SASS: Best SNR-selected SASS channel per intensity\n"
summary_text += "SSD: Best SNR-selected SSD component per intensity\n\n"

summary_text += "Intensity | Raw SNR | Raw PLV | SASS SNR | SASS PLV | SSD SNR | SSD PLV\n"
summary_text += "-"*70 + "\n"
for row in summary_rows:
    summary_text += f"{row['label']:<10} | {row['raw_snr']:<7.4f} | {row['raw_plv']:<7.4f} | {row['sass_snr']:<8.4f} | {row['sass_plv']:<8.4f} | {row['ssd_snr']:<7.4f} | {row['ssd_plv']:<7.4f}\n"

summary_text += "\n" + "="*70 + "\n"
summary_text += "EXPECTED PATTERN (if SNR selection is correct):\n"
summary_text += "Raw:  SNR declines monotonically as intensity increases (artifact dominates)\n"
summary_text += "SASS: SNR more stable (artifact suppression), slower decline\n"
summary_text += "SSD:  SNR most stable (spectral optimization preserves signal)\n"

summary_path = OUTPUT_DIRECTORY / "exp06_run02_snr_selection_summary.txt"
with open(summary_path, "w", encoding="utf-8") as f:
    f.write(summary_text)

print(f"\nSummary saved to: {summary_path}")
print("\nDone!")
