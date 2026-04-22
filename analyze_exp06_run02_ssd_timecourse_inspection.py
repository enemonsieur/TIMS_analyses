"""Plot SSD selected component time courses alongside their PLV with GT.

Visually inspect whether artifact-suppression selected components contain
genuine signal or artifact. Shows raw signal, filtered signal band, and
phase relationship with ground truth.
"""

from pathlib import Path
import warnings

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import numpy as np
from scipy.signal import hilbert
from scipy import linalg
import mne

import preprocessing

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
RUN02_STIM_THRESHOLD_FRACTION = 0.08
SSD_MAX_COMPONENTS = 6

# ============================================================
# 1) LOAD DATA
# ============================================================
with warnings.catch_warnings():
    warnings.filterwarnings("ignore", message="No coordinate information found for channels*")
    warnings.filterwarnings("ignore", message="Online software filter detected*")
    warnings.filterwarnings("ignore", message="Not setting positions of 2 misc channels found in montage*")
    raw_stim_full = mne.io.read_raw_brainvision(str(STIM_VHDR_PATH), preload=True, verbose=False)

sfreq = float(raw_stim_full.info["sfreq"])
stim_trace = raw_stim_full.copy().pick(["stim"]).get_data()[0]
gt_trace = raw_stim_full.copy().pick(["ground_truth"]).get_data()[0]

raw_eeg = raw_stim_full.copy().drop_channels(
    [ch for ch in raw_stim_full.ch_names
     if ch.lower() in {"stim", "ground_truth"} or ch.startswith("STI") or ch in EXCLUDED_CHANNELS]
)
print(f"Loaded: {len(raw_eeg.ch_names)} EEG channels, sfreq={sfreq:.0f} Hz")

# ============================================================
# 2) DETECT ON TIMING
# ============================================================
block_onsets_samples, block_offsets_samples = preprocessing.detect_stim_blocks(
    stim_trace, sfreq, threshold_fraction=RUN02_STIM_THRESHOLD_FRACTION
)

on_window_len = ON_WINDOW_S[1] - ON_WINDOW_S[0]
on_window_size = int(round(on_window_len * sfreq))
on_start_shift = int(round(ON_WINDOW_S[0] * sfreq))

late_off_window_len = LATE_OFF_WINDOW_S[1] - LATE_OFF_WINDOW_S[0]
late_off_window_size = int(round(late_off_window_len * sfreq))

# ============================================================
# 3) ANALYZE EACH INTENSITY: EXTRACT AND PLOT SSD COMPONENT
# ============================================================
fig_all = plt.figure(figsize=(16, 12))
gs_outer = gridspec.GridSpec(5, 1, figure=fig_all, hspace=0.35)

for intensity_index, intensity_label in enumerate(RUN02_INTENSITY_LABELS):
    # Extract ON windows for this intensity
    block_start_idx = intensity_index * BLOCK_CYCLES_PER_INTENSITY
    block_stop_idx = min(block_start_idx + BLOCK_CYCLES_PER_INTENSITY + 1, len(block_onsets_samples))
    dose_onsets = block_onsets_samples[block_start_idx:block_stop_idx]
    dose_offsets = block_offsets_samples[block_start_idx:block_stop_idx]

    dose_onsets_on = block_onsets_samples[block_start_idx:block_start_idx + BLOCK_CYCLES_PER_INTENSITY]
    dose_offsets_on = block_offsets_samples[block_start_idx:block_start_idx + BLOCK_CYCLES_PER_INTENSITY]
    window_onsets = dose_onsets_on + on_start_shift
    window_keep = window_onsets + on_window_size <= dose_offsets_on
    event_samples_on = window_onsets[window_keep]
    events_on = preprocessing.build_event_array(event_samples_on)

    events_late_off, _, _ = preprocessing.build_late_off_events(
        dose_onsets, dose_offsets, sfreq,
        LATE_OFF_WINDOW_S[0], LATE_OFF_WINDOW_S[1]
    )

    raw_data_2d = raw_eeg.get_data()
    on_raw_epochs = np.array([
        raw_data_2d[:, int(start):int(start) + on_window_size]
        for start in events_on[:, 0] + on_start_shift
    ])

    late_off_raw_epochs = np.array([
        raw_data_2d[:, int(start):int(start) + late_off_window_size]
        for start in events_late_off[:, 0]
    ])

    gt_on_epochs = preprocessing.extract_event_windows(gt_trace, events_on[:, 0], on_window_size)

    n_epochs, n_channels, n_samples = on_raw_epochs.shape

    # ---- SSD: Fit on ON windows, select by artifact suppression ----
    on_raw_concat = on_raw_epochs.transpose(1, 0, 2).reshape(n_channels, -1)
    late_off_raw_concat = late_off_raw_epochs.transpose(1, 0, 2).reshape(n_channels, -1)

    signal_band_concat = preprocessing.filter_signal(on_raw_concat, sfreq, *SIGNAL_BAND_HZ)
    view_band_concat = preprocessing.filter_signal(on_raw_concat, sfreq, *VIEW_BAND_HZ)

    C_signal = np.cov(signal_band_concat)
    C_view = np.cov(view_band_concat)
    eigenvalues, eigenvectors = linalg.eig(C_signal, C_view)
    eigenvalues = eigenvalues.real
    eigenvectors = eigenvectors.real

    sort_idx = np.argsort(eigenvalues)[::-1]
    eigenvectors_sorted = eigenvectors[:, sort_idx]
    spatial_filters = eigenvectors_sorted[:, :min(SSD_MAX_COMPONENTS, n_channels)].T

    # Rank by artifact suppression
    ssd_artifact_ratios = []
    for spatial_filter in spatial_filters:
        on_comp = np.dot(spatial_filter, on_raw_concat)
        on_broadband = preprocessing.filter_signal(on_comp, sfreq, *VIEW_BAND_HZ)
        off_broadband = preprocessing.filter_signal(np.dot(spatial_filter, late_off_raw_concat), sfreq, *VIEW_BAND_HZ)
        on_power = np.mean(on_broadband ** 2)
        off_power = np.mean(off_broadband ** 2)
        artifact_ratio = on_power / (off_power + 1e-8)
        ssd_artifact_ratios.append(artifact_ratio)

    best_ssd_idx = np.argmin(ssd_artifact_ratios)
    ssd_filter = spatial_filters[best_ssd_idx]
    on_ssd_component = np.dot(ssd_filter, on_raw_concat).reshape(n_epochs, -1)

    # Compute PLV summary for this component
    metrics_ssd = preprocessing.compute_epoch_plv_summary(
        on_ssd_component,
        gt_on_epochs,
        sfreq,
        SIGNAL_BAND_HZ,
        TARGET_CENTER_HZ,
    )

    # ---- Plot this intensity ----
    gs_intensity = gridspec.GridSpecFromSubplotSpec(3, 1, subplot_spec=gs_outer[intensity_index], hspace=0.25)

    # Row 1: Broadband component time course
    ax1 = fig_all.add_subplot(gs_intensity[0])
    on_broadband = preprocessing.filter_signal(on_ssd_component, sfreq, *VIEW_BAND_HZ)
    time_axis = np.linspace(ON_WINDOW_S[0], ON_WINDOW_S[1], on_broadband.shape[-1])

    # Plot mean ± std across epochs
    broadband_mean = np.mean(on_broadband, axis=0)
    broadband_std = np.std(on_broadband, axis=0)
    ax1.fill_between(time_axis, broadband_mean - broadband_std, broadband_mean + broadband_std,
                      color="seagreen", alpha=0.3, label="±1σ")
    ax1.plot(time_axis, broadband_mean, color="seagreen", lw=2, label="Selected SSD component")
    ax1.set_ylabel("Amplitude (µV)", fontsize=10)
    ax1.set_title(f"{intensity_label} — SSD Selected Component (Broadband 4–20 Hz)", fontsize=11, fontweight="bold")
    ax1.grid(True, alpha=0.2)
    ax1.legend(loc="upper right", fontsize=9, frameon=False)

    # Row 2: Signal-band filtered component + GT
    ax2 = fig_all.add_subplot(gs_intensity[1])
    on_signal = preprocessing.filter_signal(on_ssd_component, sfreq, *SIGNAL_BAND_HZ)
    gt_on_signal = preprocessing.filter_signal(gt_on_epochs, sfreq, *SIGNAL_BAND_HZ)

    on_signal_mean = np.mean(on_signal, axis=0)
    gt_signal_mean = np.mean(gt_on_signal, axis=0)

    # Normalize to same scale for comparison
    on_signal_norm = on_signal_mean / (np.std(on_signal_mean) + 1e-8)
    gt_signal_norm = gt_signal_mean / (np.std(gt_signal_mean) + 1e-8)

    ax2.plot(time_axis, on_signal_norm, color="seagreen", lw=2, label="SSD component (signal band)")
    ax2.plot(time_axis, gt_signal_norm, color="darkorange", lw=2, label="Ground truth reference")
    ax2.set_ylabel("Normalized Amplitude", fontsize=10)
    ax2.set_title("Signal Band (11.95–12.95 Hz) — Phase Relationship", fontsize=11, fontweight="bold")
    ax2.grid(True, alpha=0.2)
    ax2.legend(loc="upper right", fontsize=9, frameon=False)
    ax2.set_ylim([-3.5, 3.5])

    # Row 3: Instantaneous phase + PLV summary
    ax3 = fig_all.add_subplot(gs_intensity[2])
    phase_ssd = np.angle(hilbert(on_signal, axis=-1))
    phase_gt = np.angle(hilbert(gt_on_signal, axis=-1))
    phase_diff = (phase_ssd - phase_gt) % (2 * np.pi)
    phase_diff_mean = np.mean(phase_diff, axis=0)

    # Overlay phase difference on ax3, add PLV text
    ax3.plot(time_axis, phase_diff_mean, color="darkviolet", lw=2.5, label="Phase difference (SSD - GT)")
    ax3.axhline(y=np.pi, color="gray", linestyle="--", alpha=0.5, linewidth=1)
    ax3.set_ylabel("Phase Diff (rad)", fontsize=10)
    ax3.set_xlabel("Time (s)", fontsize=10)
    ax3.set_ylim([0, 2*np.pi])
    ax3.set_yticks([0, np.pi, 2*np.pi])
    ax3.set_yticklabels(["0", "π", "2π"])
    ax3.grid(True, alpha=0.2)

    # Add PLV annotation
    plv_text = f"PLV = {metrics_ssd['plv']:.3f} | p={metrics_ssd['p_value']:.4f}"
    ax3.text(0.98, 0.95, plv_text, transform=ax3.transAxes,
             fontsize=10, fontweight="bold", ha="right", va="top",
             bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.7))

    ax3.legend(loc="upper right", fontsize=9, frameon=False)

    print(f"{intensity_label}: SSD comp {best_ssd_idx+1}/{len(spatial_filters)}, "
          f"artifact_ratio={ssd_artifact_ratios[best_ssd_idx]:.3f}, PLV={metrics_ssd['plv']:.3f}")

fig_all.suptitle("SSD Selected Components: Broadband, Signal-Band Phase, and PLV Summary",
                 fontsize=13, fontweight="bold", y=0.995)
plt.tight_layout()
fig_path = OUTPUT_DIRECTORY / "exp06_run02_ssd_selected_timecourse_inspection.png"
plt.savefig(fig_path, dpi=220, bbox_inches="tight")
print(f"\nSaved: {fig_path.name}")
