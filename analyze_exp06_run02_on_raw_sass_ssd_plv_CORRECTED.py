"""Compare run02 ON PLV for fixed raw channel (best at 10%), pure SASS, and pure SSD against GT.

CORRECTIONS FROM ORIGINAL:
1. Raw channel: Fixed at best channel from 10% intensity, reused at all other intensities
2. SASS path: Pure SASS only (no secondary eigendecomposition); rank all SASS-cleaned channels by PLV
3. SSD path: Rank top-N SSD components by PLV to GT (not by power ratio)

All three paths now use PLV to GT as the final selection criterion.
"""

import os
from pathlib import Path
import warnings
import json

import matplotlib
matplotlib.use("Agg")
import numpy as np
from scipy import linalg

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
TOP_CHANNEL_COUNT = 1
N_SSD_COMPONENTS = 6

RUN02_STIM_THRESHOLD_FRACTION = 0.08
METHOD_COLORS = {
    "raw": "black",
    "sass": "steelblue",
    "ssd": "seagreen",
    "stim": "darkorange",
}

# Load fixed raw channel metadata from explorer script
FIXED_CHANNEL_METADATA_PATH = OUTPUT_DIRECTORY / "exp06_run02_fixed_raw_channel_metadata.json"

SUMMARY_FIGURE_PATH = OUTPUT_DIRECTORY / "exp06_run02_on_raw_sass_ssd_plv_summary_CORRECTED.png"
PHASE_GRID_PATH = OUTPUT_DIRECTORY / "exp06_run02_on_raw_sass_ssd_phase_grid_CORRECTED.png"
MANIFEST_PATH = OUTPUT_DIRECTORY / "exp06_run02_on_raw_sass_ssd_plv_summary_CORRECTED.txt"


# ============================================================
# PIPELINE
# ============================================================
# run02 recording
#   |
# measured ON timing
#   |
# accepted ON and late-OFF windows
#   |
# per-block fixed-raw / pure-SASS / pure-SSD / GT-STIM phase comparison
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

# Load fixed raw channel metadata
print(f"\nLoading fixed raw channel metadata...")
if not FIXED_CHANNEL_METADATA_PATH.exists():
    raise RuntimeError(f"Fixed channel metadata not found: {FIXED_CHANNEL_METADATA_PATH}\n"
                       f"Run explore_exp06_best_raw_channel_fixed.py first.")

with open(FIXED_CHANNEL_METADATA_PATH) as f:
    fixed_ch_metadata = json.load(f)

FIXED_RAW_CHANNEL_NAME = fixed_ch_metadata["reference_channel_name"]
FIXED_RAW_CHANNEL_IDX = fixed_ch_metadata["reference_channel_index"]

print(f"Fixed raw channel: {FIXED_RAW_CHANNEL_NAME} (index {FIXED_RAW_CHANNEL_IDX})")
print(f"  PLV at 10%: {fixed_ch_metadata['reference_plv']:.4f}")


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
# 3) ANALYZE EACH DOSE BLOCK
# ============================================================
summary_rows = []
reference_band_trace = preprocessing.filter_signal(gt_trace, sfreq, SIGNAL_BAND_HZ[0], SIGNAL_BAND_HZ[1])

for intensity_index, intensity_label in enumerate(RUN02_INTENSITY_LABELS):
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

    # 3.2 Build late-OFF windows for SASS reference covariance
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

    # ========== 3.4 FIXED RAW CHANNEL (no re-selection) ==========
    # Use the best channel from 10% across all intensities
    on_raw_selected = on_raw_epochs[:, FIXED_RAW_CHANNEL_IDX, :]
    raw_metrics = preprocessing.compute_epoch_plv_summary(
        on_raw_selected,
        gt_on_epochs,
        sfreq,
        SIGNAL_BAND_HZ,
        TARGET_CENTER_HZ,
    )

    # Compute peak frequency for fixed raw channel
    raw_signal = preprocessing.filter_signal(on_raw_selected, sfreq, *VIEW_BAND_HZ)
    raw_psd = np.mean(np.abs(np.fft.rfft(raw_signal, axis=-1)) ** 2, axis=0)
    freqs_raw = np.fft.rfftfreq(raw_signal.shape[-1], 1 / sfreq)
    peak_freq_raw = freqs_raw[np.argmax(raw_psd)]

    raw_selection = {
        "selected_rows": [{"name": FIXED_RAW_CHANNEL_NAME, "plv": raw_metrics["plv"]}],
        "mean_selected_plv": float(raw_metrics["plv"]),
        "best_channel_name": FIXED_RAW_CHANNEL_NAME,
        "best_channel_plv": float(raw_metrics["plv"]),
        "best_phase_samples": raw_metrics["phase_samples"],
        "best_channel_p_value": float(raw_metrics["p_value"]),
        "selection_note": "Fixed at 10% (GT-locking supervised)",
    }

    # ========== 3.5 PURE SASS (no secondary eigendecomposition) ==========
    # Apply SASS, then rank ALL cleaned channels by PLV to GT
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

    # Reshape back to (n_epochs, n_channels, n_samples) for channel-wise analysis
    on_sass_epochs = sass_cleaned_concat.reshape(n_channels, n_epochs, n_samples).transpose(1, 0, 2)

    # Rank all SASS-cleaned channels by PLV to GT
    sass_plv_scores = []
    sass_channels_info = []
    for ch_idx, ch_name in enumerate(raw_eeg.ch_names):
        ch_data = on_sass_epochs[:, ch_idx, :]  # (n_epochs, n_samples)
        metrics_ch = preprocessing.compute_epoch_plv_summary(
            ch_data,
            gt_on_epochs,
            sfreq,
            SIGNAL_BAND_HZ,
            TARGET_CENTER_HZ,
        )
        sass_plv_scores.append(metrics_ch["plv"])

        # Compute peak frequency
        ch_signal = preprocessing.filter_signal(ch_data, sfreq, *VIEW_BAND_HZ)
        ch_psd = np.mean(np.abs(np.fft.rfft(ch_signal, axis=-1)) ** 2, axis=0)
        freqs_ch = np.fft.rfftfreq(ch_signal.shape[-1], 1 / sfreq)
        ch_peak_hz = freqs_ch[np.argmax(ch_psd)]

        sass_channels_info.append({
            "name": ch_name,
            "ch_idx": ch_idx,
            "plv": metrics_ch["plv"],
            "peak_hz": ch_peak_hz,
            "p_value": metrics_ch["p_value"],
            "mean_gt_locking": metrics_ch["mean_gt_locking"],
            "phase_samples": metrics_ch["phase_samples"],
        })

    # Select SASS channel with highest PLV
    selected_sass_ch_idx = np.argmax(sass_plv_scores)
    selected_sass_ch_info = sass_channels_info[selected_sass_ch_idx]
    on_sass_selected = on_sass_epochs[:, selected_sass_ch_idx, :]
    sass_selection = preprocessing.compute_epoch_plv_summary(
        on_sass_selected,
        gt_on_epochs,
        sfreq,
        SIGNAL_BAND_HZ,
        TARGET_CENTER_HZ,
    )

    # Peak frequency for selected SASS channel
    sass_signal = preprocessing.filter_signal(on_sass_selected, sfreq, *VIEW_BAND_HZ)
    sass_psd = np.mean(np.abs(np.fft.rfft(sass_signal, axis=-1)) ** 2, axis=0)
    freqs_sass = np.fft.rfftfreq(sass_signal.shape[-1], 1 / sfreq)
    peak_freq_sass = freqs_sass[np.argmax(sass_psd)]

    # ========== 3.6 PURE SSD (rank by PLV, not power ratio) ==========
    on_raw_concat = on_raw_epochs.transpose(1, 0, 2).reshape(len(raw_eeg.ch_names), -1)
    late_off_raw_concat = late_off_raw_epochs.transpose(1, 0, 2).reshape(len(raw_eeg.ch_names), -1)

    signal_band_concat = preprocessing.filter_signal(on_raw_concat, sfreq, *SIGNAL_BAND_HZ)
    view_band_concat = preprocessing.filter_signal(on_raw_concat, sfreq, *VIEW_BAND_HZ)

    C_signal = np.cov(signal_band_concat)
    C_view = np.cov(view_band_concat)
    eigenvalues, eigenvectors = linalg.eig(C_signal, C_view)
    eigenvalues = eigenvalues.real
    eigenvectors = eigenvectors.real

    sort_idx = np.argsort(eigenvalues)[::-1]
    eigenvectors_sorted = eigenvectors[:, sort_idx]
    spatial_filters = eigenvectors_sorted[:, :N_SSD_COMPONENTS].T  # (n_components, n_channels)

    # Rank each SSD component by PLV to GT (not by power ratio)
    ssd_plv_scores = []
    component_epochs_list = []
    for spatial_filter in spatial_filters:
        on_component = np.dot(spatial_filter, on_raw_concat)
        on_component_epochs = on_component.reshape(n_epochs, -1)
        component_epochs_list.append(on_component_epochs)

        metrics_comp = preprocessing.compute_epoch_plv_summary(
            on_component_epochs,
            gt_on_epochs,
            sfreq,
            SIGNAL_BAND_HZ,
            TARGET_CENTER_HZ,
        )
        ssd_plv_scores.append(metrics_comp["plv"])

    # Select SSD component with highest PLV
    selected_component_index = np.argmax(ssd_plv_scores)
    selected_component_epochs = component_epochs_list[selected_component_index]
    ssd_metrics = preprocessing.compute_epoch_plv_summary(
        selected_component_epochs,
        gt_on_epochs,
        sfreq,
        SIGNAL_BAND_HZ,
        TARGET_CENTER_HZ,
    )

    # Peak frequency for selected SSD component
    component_signal = preprocessing.filter_signal(selected_component_epochs, sfreq, *VIEW_BAND_HZ)
    component_psd = np.mean(np.abs(np.fft.rfft(component_signal, axis=-1)) ** 2, axis=0)
    freqs_comp = np.fft.rfftfreq(component_signal.shape[-1], 1 / sfreq)
    peak_freq_ssd = freqs_comp[np.argmax(component_psd)]

    # ========== 3.7 GT vs STIM reference ==========
    stim_metrics = preprocessing.compute_epoch_plv_summary(
        stim_on_epochs,
        gt_on_epochs,
        sfreq,
        SIGNAL_BAND_HZ,
        TARGET_CENTER_HZ,
    )

    # Store results
    summary_rows.append(
        {
            "label": intensity_label,
            "intensity_pct": int(intensity_label.replace("%", "")),
            "event_count": int(len(events_on)),
            "raw_selection": raw_selection,
            "raw_peak_hz": float(peak_freq_raw),
            "sass_plv": float(sass_selection["plv"]),
            "sass_p_value": float(sass_selection["p_value"]),
            "sass_mean_gt_locking": float(sass_selection["mean_gt_locking"]),
            "sass_selected_channel": selected_sass_ch_info["name"],
            "sass_peak_hz": float(peak_freq_sass),
            "sass_phase_samples": np.asarray(sass_selection["phase_samples"], dtype=float),
            "ssd_component_number": int(selected_component_index + 1),
            "ssd_peak_hz": float(peak_freq_ssd),
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

    print(
        f"{intensity_label}: raw={raw_metrics['plv']:.3f} ({FIXED_RAW_CHANNEL_NAME}) | "
        f"sass={sass_selection['plv']:.3f} ({selected_sass_ch_info['name']}) | "
        f"ssd={ssd_metrics['plv']:.3f} (comp {selected_component_index + 1}) | "
        f"stim={stim_metrics['plv']:.3f}"
    )


# ============================================================
# 4) GENERATE FIGURES (placeholder for now)
# ============================================================
print(f"\nFigure generation would occur here (using plot_helpers module).")
print(f"Summary outputs:")
print(f"  - {SUMMARY_FIGURE_PATH}")
print(f"  - {PHASE_GRID_PATH}")
print(f"  - {MANIFEST_PATH}")

# Write manifest
manifest_lines = [
    "EXP06 RUN02 — CORRECTED ANALYSIS (Fixed Raw + Pure SASS + Pure SSD)",
    "=" * 100,
    "",
    "CORRECTIONS APPLIED:",
    "1. Raw channel: Fixed at best channel from 10% intensity, reused at all other intensities",
    "2. SASS path: Pure SASS only (no secondary eigendecomposition); rank all cleaned channels by PLV",
    "3. SSD path: Rank top-N SSD components by PLV to GT (not by power ratio)",
    "",
    "All three paths use PLV to GT as the final selection criterion.",
    "",
    "RESULTS:",
    "-" * 100,
]

for row in summary_rows:
    manifest_lines.append(
        f"{row['label']:6s} | raw={row['raw_selection']['mean_selected_plv']:.3f} ({row['raw_selection']['best_channel_name']}) | "
        f"sass={row['sass_plv']:.3f} ({row['sass_selected_channel']}) | "
        f"ssd={row['ssd_plv']:.3f} (comp {row['ssd_component_number']}) | "
        f"stim={row['stim_plv']:.3f}"
    )

with open(MANIFEST_PATH, "w") as f:
    f.write("\n".join(manifest_lines))

print(f"\nSaved manifest: {MANIFEST_PATH}")
print("\nDone!")
