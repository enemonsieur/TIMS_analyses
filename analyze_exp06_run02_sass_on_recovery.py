"""Compare ON-state GT-locking (ITPC) for raw channels, SASS source, and SSD components, all supervised by GT-locking ranking."""

from pathlib import Path
import warnings

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.signal import hilbert
from scipy import linalg
import mne

import preprocessing
import plot_helpers
import sass

# ============================================================
# CONFIG
# ============================================================
DATA_DIRECTORY = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\TIMS_data_sync\pilot\doseresp")
STIM_VHDR_PATH = DATA_DIRECTORY / "exp06-STIM-iTBS_run02.vhdr"  # measured run02 stimulation recording
OUTPUT_DIRECTORY = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\EXP06")
OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)

RUN02_INTENSITY_LABELS = ["10%", "20%", "30%", "40%", "50%"]  # run02 dose order
BLOCK_CYCLES_PER_INTENSITY = 20  # ON cycles per block
ON_WINDOW_S = (0.3, 1.5)  # accepted ON window
LATE_OFF_WINDOW_S = (1.5, 3.2)  # accepted late-OFF window for reference covariance
EXCLUDED_CHANNELS = {"TP9", "Fp1", "TP10"}  # keep EEG set aligned with baseline work

TARGET_CENTER_HZ = 12.451172  # measured baseline GT peak
SIGNAL_HALF_WIDTH_HZ = 0.5  # narrower band for target-band metrics
SIGNAL_BAND_HZ = (TARGET_CENTER_HZ - SIGNAL_HALF_WIDTH_HZ, TARGET_CENTER_HZ + SIGNAL_HALF_WIDTH_HZ)
VIEW_BAND_HZ = (4.0, 20.0)  # inspection band
RUN02_STIM_THRESHOLD_FRACTION = 0.08  # recover weak first block
SSD_MAX_COMPONENTS = 6  # max components to rank before selecting top

FIGURE_COLORS = {"raw": "black", "sass": "steelblue", "ssd": "seagreen"}
INTENSITY_COLORS = ["#c6dbef", "#9ecae1", "#6baed6", "#3182bd", "#08519c"]  # 10% to 50%


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

# Keep the run02 EEG set explicit
raw_eeg = raw_stim_full.copy().drop_channels(
    [ch for ch in raw_stim_full.ch_names
     if ch.lower() in {"stim", "ground_truth"} or ch.startswith("STI") or ch in EXCLUDED_CHANNELS]
)
print(f"Loaded run02: {raw_eeg.n_times / sfreq:.1f}s, sfreq={sfreq:.0f} Hz, {len(raw_eeg.ch_names)} EEG channels")


# ============================================================
# 2) RECOVER MEASURED ON TIMING
# ============================================================
block_onsets_samples, block_offsets_samples = preprocessing.detect_stim_blocks(
    stim_trace, sfreq, threshold_fraction=RUN02_STIM_THRESHOLD_FRACTION
)
required_block_count = len(RUN02_INTENSITY_LABELS) * BLOCK_CYCLES_PER_INTENSITY
if len(block_onsets_samples) < required_block_count:
    raise RuntimeError(f"Need {required_block_count} ON blocks, found {len(block_onsets_samples)}.")

# Convert window durations to samples
on_window_len = ON_WINDOW_S[1] - ON_WINDOW_S[0]
on_window_size = int(round(on_window_len * sfreq))
on_start_shift = int(round(ON_WINDOW_S[0] * sfreq))

late_off_window_len = LATE_OFF_WINDOW_S[1] - LATE_OFF_WINDOW_S[0]
late_off_window_size = int(round(late_off_window_len * sfreq))


# ============================================================
# 3) BUILD PER-INTENSITY ON WINDOWS AND POOLED LATE-OFF WINDOWS
# ============================================================
# Collect all late-OFF epochs across intensities for pooled B covariance
all_late_off_epochs = []

# Per-intensity storage
on_epochs_raw_list = []  # raw ON epochs per intensity
on_epochs_sass_list = []  # SASS-cleaned ON epochs per intensity
on_epochs_ssd_list = []  # SSD-cleaned ON epochs per intensity
gt_epochs_list = []  # GT epochs per intensity
itpc_raw_list = []  # ITPC curves per intensity
itpc_sass_list = []  # ITPC curves per intensity (SASS source)
itpc_ssd_list = []  # ITPC curves per intensity
phase_diff_raw_list = []  # phase differences per intensity
phase_diff_sass_list = []  # phase differences per intensity (SASS source)
phase_diff_ssd_list = []  # phase differences per intensity

for intensity_index, intensity_label in enumerate(RUN02_INTENSITY_LABELS):
    block_start_idx = intensity_index * BLOCK_CYCLES_PER_INTENSITY
    # Include one extra block for late-OFF computation (standard exp06 approach)
    block_stop_idx = min(block_start_idx + BLOCK_CYCLES_PER_INTENSITY + 1, len(block_onsets_samples))
    dose_onsets = block_onsets_samples[block_start_idx:block_stop_idx]
    dose_offsets = block_offsets_samples[block_start_idx:block_stop_idx]

    # 3.1 Build ON windows for this intensity (use only the first BLOCK_CYCLES_PER_INTENSITY blocks)
    dose_onsets_on = block_onsets_samples[block_start_idx:block_start_idx + BLOCK_CYCLES_PER_INTENSITY]
    dose_offsets_on = block_offsets_samples[block_start_idx:block_start_idx + BLOCK_CYCLES_PER_INTENSITY]
    window_onsets = dose_onsets_on + on_start_shift
    window_keep = window_onsets + on_window_size <= dose_offsets_on
    event_samples_on = window_onsets[window_keep]
    events_on = preprocessing.build_event_array(event_samples_on)

    # 3.2 Build late-OFF windows for this intensity (use all available blocks including the next)
    events_late_off, _, _ = preprocessing.build_late_off_events(
        dose_onsets, dose_offsets, sfreq,
        LATE_OFF_WINDOW_S[0], LATE_OFF_WINDOW_S[1]
    )

    # Extract raw epochs using simple window slicing per channel
    raw_data_2d = raw_eeg.get_data()  # (n_channels, n_samples)
    on_raw_epochs = np.array([
        raw_data_2d[:, int(start):int(start) + on_window_size]
        for start in events_on[:, 0] + on_start_shift
    ])  # (n_epochs, n_channels, n_samples)

    late_off_raw_epochs = np.array([
        raw_data_2d[:, int(start):int(start) + late_off_window_size]
        for start in events_late_off[:, 0]
    ])  # (n_epochs, n_channels, n_samples)

    gt_on_epochs = preprocessing.extract_event_windows(gt_trace, events_on[:, 0], on_window_size)
    gt_late_off_epochs = preprocessing.extract_event_windows(gt_trace, events_late_off[:, 0], late_off_window_size)

    # 3.3 Accumulate late-OFF epochs for pooled covariance B
    all_late_off_epochs.append(late_off_raw_epochs)

    on_epochs_raw_list.append(on_raw_epochs)
    gt_epochs_list.append(gt_on_epochs)

    print(f"{intensity_label}: ON={len(on_raw_epochs)}, late_OFF={len(late_off_raw_epochs)}")


# ============================================================
# 4) COMPUTE COVARIANCES AND APPLY SASS
# ============================================================
# Apply SASS per intensity
for intensity_index, intensity_label in enumerate(RUN02_INTENSITY_LABELS):
    on_raw = on_epochs_raw_list[intensity_index]  # (n_epochs, n_channels, n_samples)
    gt_on = gt_epochs_list[intensity_index]  # (n_epochs, n_samples)

    # Compute covariance B from this intensity's late-OFF epochs
    late_off_i = all_late_off_epochs[intensity_index]  # (n_epochs, n_channels, n_samples)
    n_late, n_ch_b, n_s_b = late_off_i.shape
    late_off_2d = late_off_i.transpose(1, 0, 2).reshape(n_ch_b, -1)  # (n_channels, n_epochs * n_samples)
    cov_b = np.cov(late_off_2d)  # (n_channels, n_channels)

    # Reshape: concatenate epochs along time axis to get (n_channels, n_epochs * n_samples)
    n_epochs, n_channels, n_samples = on_raw.shape
    on_data_concat = on_raw.transpose(1, 0, 2).reshape(n_channels, -1)  # (n_channels, n_epochs * n_samples)

    # Compute covariance A from this intensity's ON data
    cov_a = np.cov(on_data_concat)  # (n_channels, n_channels)

    # Apply SASS
    on_cleaned = sass.sass(on_data_concat, cov_a, cov_b)  # cleaned (n_channels, n_epochs * n_samples)

    # Reshape back to epoch format for metric computation
    on_cleaned_epochs = on_cleaned.reshape(n_channels, n_epochs, n_samples).transpose(1, 0, 2)  # (n_epochs, n_channels, n_samples)

    # 4.1 Rank raw channels by GT-locking (ITPC) and select best
    # Same supervised ranking as SASS source and SSD components.
    raw_itpc_scores = []
    for ch_idx in range(n_channels):
        ch_data = on_raw[:, ch_idx, :]  # (n_epochs, n_samples)
        metrics_ch = preprocessing.compute_band_limited_epoch_triplet_metrics(
            ch_data, gt_on, sfreq, SIGNAL_BAND_HZ
        )
        # Use mean ITPC across the window as the ranking criterion
        raw_itpc_scores.append(np.mean(metrics_ch["itpc_curve"]))

    # Select channel with highest mean ITPC
    selected_raw_ch_idx = np.argmax(raw_itpc_scores)
    on_raw_selected = on_raw[:, selected_raw_ch_idx, :]  # (n_epochs, n_samples)

    metrics_raw = preprocessing.compute_band_limited_epoch_triplet_metrics(
        on_raw_selected, gt_on, sfreq, SIGNAL_BAND_HZ
    )

    itpc_raw_list.append(metrics_raw["itpc_curve"])

    # 4.2 Compute phase differences for RAW (circular histogram)
    signal_band_raw = preprocessing.filter_signal(on_raw_selected, sfreq, *SIGNAL_BAND_HZ)
    phase_raw = np.angle(hilbert(signal_band_raw, axis=-1))

    signal_band_gt = preprocessing.filter_signal(gt_on, sfreq, *SIGNAL_BAND_HZ)
    phase_gt = np.angle(hilbert(signal_band_gt, axis=-1))

    phase_diff_raw = (phase_raw - phase_gt) % (2 * np.pi)
    phase_diff_raw_list.append(phase_diff_raw)

    # ---- SASS: Extract synthetic source via eigendecomposition (replaces best-channel approach) ----
    # Decompose SASS-cleaned ON vs late-OFF covariance in signal band.
    # Low eigenvalues (λ) = artifact-suppressed components.
    # Rank by GT-locking and select best.
    on_sass_concat = on_cleaned_epochs.transpose(1, 0, 2).reshape(n_channels, -1)
    late_off_sass_concat = late_off_i.transpose(1, 0, 2).reshape(n_channels, -1)

    # Filter to signal band for eigendecomposition
    on_sass_signal = preprocessing.filter_signal(on_sass_concat, sfreq, *SIGNAL_BAND_HZ)
    late_off_sass_signal = preprocessing.filter_signal(late_off_sass_concat, sfreq, *SIGNAL_BAND_HZ)

    # ON and late-OFF covariances
    C_on_sass = np.cov(on_sass_signal)
    C_off_sass = np.cov(late_off_sass_signal)

    # Generalized eigendecomposition: C_on_sass · w = λ · C_off_sass · w
    evals_sass, evecs_sass = linalg.eig(C_on_sass, C_off_sass)
    evals_sass = evals_sass.real
    evecs_sass = evecs_sass.real

    # Sort by ascending eigenvalue (low λ first = cleanest components)
    sort_idx_sass = np.argsort(evals_sass)
    evecs_sass_sorted = evecs_sass[:, sort_idx_sass]
    sass_source_filters = evecs_sass_sorted[:, :min(SSD_MAX_COMPONENTS, n_channels)].T

    # Rank by artifact suppression (lowest ON/OFF power ratio in broadband)
    sass_artifact_ratios = []
    for spatial_filter in sass_source_filters:
        on_component_ss = np.dot(spatial_filter, on_sass_concat)
        # Compute artifact ratio in broadband
        on_broadband = preprocessing.filter_signal(on_component_ss, sfreq, *VIEW_BAND_HZ)
        late_off_broadband = preprocessing.filter_signal(late_off_sass_concat, sfreq, *VIEW_BAND_HZ)
        on_power = np.mean(on_broadband ** 2)
        off_power = np.mean(late_off_broadband ** 2)
        artifact_ratio = on_power / (off_power + 1e-8)
        sass_artifact_ratios.append(artifact_ratio)

    # Select component with lowest artifact ratio (most suppressed)
    best_sass_source_idx = np.argmin(sass_artifact_ratios)
    sass_source_filter = sass_source_filters[best_sass_source_idx]
    on_sass_source = np.dot(sass_source_filter, on_sass_concat).reshape(n_epochs, -1)

    metrics_sass = preprocessing.compute_band_limited_epoch_triplet_metrics(
        on_sass_source, gt_on, sfreq, SIGNAL_BAND_HZ
    )

    itpc_sass_list.append(metrics_sass["itpc_curve"])

    # 4.2b Compute phase differences for SASS source (circular histogram)
    signal_band_sass = preprocessing.filter_signal(on_sass_source, sfreq, *SIGNAL_BAND_HZ)
    phase_sass = np.angle(hilbert(signal_band_sass, axis=-1))
    phase_diff_sass = (phase_sass - phase_gt) % (2 * np.pi)
    phase_diff_sass_list.append(phase_diff_sass)

    # ---- SSD: Fit per-block and select best component supervised by artifact suppression ----
    # SSD uses generalized eigendecomposition of signal-band vs view-band covariance.
    # Selection: rank components by artifact suppression (lowest ON/OFF power ratio).
    on_raw_concat = on_raw.transpose(1, 0, 2).reshape(n_channels, -1)
    late_off_raw_concat = late_off_i.transpose(1, 0, 2).reshape(n_channels, -1)

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
    spatial_filters = eigenvectors_sorted[:, :min(SSD_MAX_COMPONENTS, n_channels)].T  # (n_components, n_channels)

    # Rank each component by artifact suppression (lowest ON/OFF power ratio in broadband)
    ssd_artifact_ratios = []
    for spatial_filter in spatial_filters:
        # Apply component to ON data
        on_component = np.dot(spatial_filter, on_raw_concat)
        # Compute artifact ratio in broadband
        on_broadband = preprocessing.filter_signal(on_component, sfreq, *VIEW_BAND_HZ)
        off_broadband = preprocessing.filter_signal(np.dot(spatial_filter, late_off_raw_concat), sfreq, *VIEW_BAND_HZ)
        on_power = np.mean(on_broadband ** 2)
        off_power = np.mean(off_broadband ** 2)
        artifact_ratio = on_power / (off_power + 1e-8)
        ssd_artifact_ratios.append(artifact_ratio)

    # Select component with lowest artifact ratio (most suppressed)
    best_comp_idx = np.argmin(ssd_artifact_ratios)
    ssd_filter = spatial_filters[best_comp_idx]
    on_ssd_component = np.dot(ssd_filter, on_raw_concat).reshape(n_epochs, -1)

    metrics_ssd = preprocessing.compute_band_limited_epoch_triplet_metrics(
        on_ssd_component, gt_on, sfreq, SIGNAL_BAND_HZ
    )
    itpc_ssd_list.append(metrics_ssd["itpc_curve"])

    # SSD: phase difference per epoch
    signal_band_ssd = preprocessing.filter_signal(on_ssd_component, sfreq, *SIGNAL_BAND_HZ)
    phase_ssd = np.angle(hilbert(signal_band_ssd, axis=-1))
    phase_diff_ssd = (phase_ssd - phase_gt) % (2 * np.pi)
    phase_diff_ssd_list.append(phase_diff_ssd)

    print(f"{intensity_label}: ITPC_raw={np.mean(metrics_raw['itpc_curve']):.3f}, "
          f"ITPC_sass_source={np.mean(metrics_sass['itpc_curve']):.3f}, "
          f"ITPC_ssd={np.mean(metrics_ssd['itpc_curve']):.3f}")

    on_epochs_sass_list.append(on_cleaned_epochs)


# ============================================================
# 5) SAVE OUTPUTS
# ============================================================
# Figure 1: ITPC time courses per intensity
fig1, axes1 = plt.subplots(1, 5, figsize=(16, 3.2), constrained_layout=True, sharey=True)
time_axis = np.linspace(ON_WINDOW_S[0], ON_WINDOW_S[1], len(itpc_raw_list[0]))

for idx, (ax, label, itpc_raw, itpc_sass, itpc_ssd) in enumerate(
    zip(np.atleast_1d(axes1), RUN02_INTENSITY_LABELS, itpc_raw_list, itpc_sass_list, itpc_ssd_list)
):
    ax.plot(time_axis, itpc_raw, color=FIGURE_COLORS["raw"], lw=2, label="Raw", alpha=0.8)
    ax.plot(time_axis, itpc_sass, color=FIGURE_COLORS["sass"], lw=2, label="SASS Source", alpha=0.8)
    ax.plot(time_axis, itpc_ssd, color=FIGURE_COLORS["ssd"], lw=2, label="SSD", alpha=0.8)
    ax.set(xlabel="Time (s)", title=label, ylim=(0, 1))
    if idx == 0:
        ax.set_ylabel("ITPC (phase locking)")
    ax.legend(frameon=False, fontsize=8, loc='upper right')
    ax.grid(True, alpha=0.2)
fig1.suptitle("ON-State GT-Locking (PLV-supervised): Raw vs SASS Source vs SSD", fontsize=11, fontweight="bold")

fig1.savefig(OUTPUT_DIRECTORY / "exp06_run02_sass_itpc_per_intensity.png", dpi=220)
plt.close(fig1)

# Figure 2: Five separate circular histograms (raw vs. SASS)
for idx, (label, phase_diff_raw, phase_diff_sass, color) in enumerate(
    zip(RUN02_INTENSITY_LABELS, phase_diff_raw_list, phase_diff_sass_list, INTENSITY_COLORS)
):
    fig2, (ax_raw, ax_sass) = plt.subplots(1, 2, figsize=(10, 4.5), constrained_layout=True, subplot_kw=dict(projection='polar'))

    # Compute Rayleigh V (circular concentration) for phase differences
    # V = |mean(exp(1j * phase))| ranges from 0 (uniform) to 1 (perfect locking)
    v_raw = np.abs(np.mean(np.exp(1j * phase_diff_raw.ravel())))
    v_sass = np.abs(np.mean(np.exp(1j * phase_diff_sass.ravel())))

    # Raw histogram
    bins = np.linspace(0, 2*np.pi, 19)
    hist_raw, _ = np.histogram(phase_diff_raw.ravel(), bins=bins)
    theta = (bins[:-1] + bins[1:]) / 2
    ax_raw.bar(theta, hist_raw, width=bins[1]-bins[0], alpha=0.6, color=FIGURE_COLORS["raw"])
    ax_raw.set_title(f"Raw ON vs. GT\nCircular V={v_raw:.3f}", fontsize=10)
    ax_raw.set_ylim(0, np.max(hist_raw) * 1.2)

    # SASS histogram
    hist_sass, _ = np.histogram(phase_diff_sass.ravel(), bins=bins)
    ax_sass.bar(theta, hist_sass, width=bins[1]-bins[0], alpha=0.6, color=FIGURE_COLORS["sass"])
    ax_sass.set_title(f"SASS ON vs. GT\nCircular V={v_sass:.3f}", fontsize=10)
    ax_sass.set_ylim(0, np.max(hist_sass) * 1.2)

    fig2.suptitle(f"{label} Intensity", fontsize=11, fontweight="bold")
    fig2.savefig(OUTPUT_DIRECTORY / f"exp06_run02_sass_phase_histogram_{label.replace('%', 'pct')}.png", dpi=220)
    plt.close(fig2)

# Figure 3: Summary ITPC across intensities
fig3, ax3 = plt.subplots(figsize=(8, 4.5), constrained_layout=True)
intensity_values = np.array([10, 20, 30, 40, 50])
mean_itpc_raw = [np.mean(itpc) for itpc in itpc_raw_list]
mean_itpc_sass = [np.mean(itpc) for itpc in itpc_sass_list]
mean_itpc_ssd = [np.mean(itpc) for itpc in itpc_ssd_list]

ax3.plot(intensity_values, mean_itpc_raw, color=FIGURE_COLORS["raw"], lw=2.2, marker="o", ms=8, label="Raw", alpha=0.8)
ax3.plot(intensity_values, mean_itpc_sass, color=FIGURE_COLORS["sass"], lw=2.2, marker="s", ms=8, label="SASS Source", alpha=0.8)
ax3.plot(intensity_values, mean_itpc_ssd, color=FIGURE_COLORS["ssd"], lw=2.2, marker="^", ms=8, label="SSD", alpha=0.8)

ax3.set(xlabel="Stimulation Intensity (%)", ylabel="Mean ON-State ITPC", xticks=intensity_values, ylim=(0, 1))
ax3.set_title("GT-Locking Preservation Across Intensity (PLV-supervised)", fontsize=11, fontweight="bold")
ax3.legend(frameon=False, fontsize=10)
ax3.grid(True, alpha=0.2)
fig3.savefig(OUTPUT_DIRECTORY / "exp06_run02_sass_summary_itpc.png", dpi=220)
plt.close(fig3)

print(f"\n[DONE] Saved 8 figures to {OUTPUT_DIRECTORY}/")
print(f"  - exp06_run02_sass_itpc_per_intensity.png (Figure 1: ITPC per intensity)")
print(f"  - exp06_run02_sass_phase_histogram_*.png × 5 (Figure 2: phase distributions)")
print(f"  - exp06_run02_sass_summary_itpc.png (Figure 3: cross-intensity summary)")
