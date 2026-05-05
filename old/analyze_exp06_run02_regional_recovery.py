"""Per-region recovery curves: ITPC stratified by artifact magnitude (high vs low).

Shows whether raw, SASS, and SSD succeed where artifacts are strong (high-artifact regions)
vs where artifacts are naturally weak (low-artifact regions).
"""

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

FIGURE_COLORS = {"raw": "black", "sass": "steelblue", "ssd": "seagreen"}

# ============================================================
# ANATOMICAL REGIONS (10-20 EEG system)
# ============================================================
REGION_DEFINITIONS = {
    "Frontal": {"channels": ["Fp1", "Fp2", "F3", "Fz", "F4", "F7", "F8"], "color": "#e41a1c"},
    "Frontocentral": {"channels": ["FC3", "FCz", "FC4", "FC1", "FC2"], "color": "#377eb8"},
    "Central": {"channels": ["C3", "Cz", "C4"], "color": "#4daf4a"},
    "Centroparietal": {"channels": ["CP3", "CPz", "CP4", "CP1", "CP2"], "color": "#984ea3"},
    "Parietal": {"channels": ["P3", "Pz", "P4", "P7", "P8"], "color": "#ff7f00"},
    "Temporal": {"channels": ["T7", "T8", "TP9", "TP10"], "color": "#a65628"},
    "Occipital": {"channels": ["O1", "O2", "Oz"], "color": "#f781bf"},
}


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
    [ch for ch in raw_stim_full.ch_names
     if ch.lower() in {"stim", "ground_truth"} or ch.startswith("STI") or ch in EXCLUDED_CHANNELS]
)
all_channels = raw_eeg.ch_names
print(f"Loaded run02: {raw_eeg.n_times / sfreq:.1f}s, sfreq={sfreq:.0f} Hz, {len(all_channels)} EEG channels")
print(f"Available channels: {all_channels}")

# Map regions to available channels
regions_available = {}
for region_name, region_spec in REGION_DEFINITIONS.items():
    available_in_region = [ch for ch in region_spec["channels"] if ch in all_channels]
    if available_in_region:
        regions_available[region_name] = {
            "channels": available_in_region,
            "color": region_spec["color"],
        }
    print(f"  {region_name}: {available_in_region}")


# ============================================================
# 2) RECOVER MEASURED ON TIMING
# ============================================================
block_onsets_samples, block_offsets_samples = preprocessing.detect_stim_blocks(
    stim_trace, sfreq, threshold_fraction=RUN02_STIM_THRESHOLD_FRACTION
)
required_block_count = len(RUN02_INTENSITY_LABELS) * BLOCK_CYCLES_PER_INTENSITY
if len(block_onsets_samples) < required_block_count:
    raise RuntimeError(f"Need {required_block_count} ON blocks, found {len(block_onsets_samples)}.")

on_window_len = ON_WINDOW_S[1] - ON_WINDOW_S[0]
on_window_size = int(round(on_window_len * sfreq))
on_start_shift = int(round(ON_WINDOW_S[0] * sfreq))

late_off_window_len = LATE_OFF_WINDOW_S[1] - LATE_OFF_WINDOW_S[0]
late_off_window_size = int(round(late_off_window_len * sfreq))


# ============================================================
# 3) BUILD PER-INTENSITY ON/OFF WINDOWS
# ============================================================
all_late_off_epochs = []
on_epochs_raw_list = []
gt_epochs_list = []

for intensity_index, intensity_label in enumerate(RUN02_INTENSITY_LABELS):
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

    all_late_off_epochs.append(late_off_raw_epochs)
    on_epochs_raw_list.append(on_raw_epochs)
    gt_epochs_list.append(gt_on_epochs)

    print(f"{intensity_label}: ON={len(on_raw_epochs)}, late_OFF={len(late_off_raw_epochs)}")


# ============================================================
# 4) COMPUTE ARTIFACT MAGNITUDE AND REGIONAL ITPC
# ============================================================
regional_results = {}  # {region_name: {intensity: {method: itpc_mean}}}

for region_name in regions_available.keys():
    regional_results[region_name] = {intensity: {} for intensity in RUN02_INTENSITY_LABELS}

for intensity_index, intensity_label in enumerate(RUN02_INTENSITY_LABELS):
    on_raw = on_epochs_raw_list[intensity_index]
    gt_on = gt_epochs_list[intensity_index]
    late_off_i = all_late_off_epochs[intensity_index]

    n_epochs, n_channels, n_samples = on_raw.shape

    # ---- Compute artifact magnitude per channel (ON vs late-OFF power ratio) ----
    on_view = preprocessing.filter_signal(
        on_raw.transpose(1, 0, 2).reshape(n_channels, -1),
        sfreq, *VIEW_BAND_HZ
    )
    late_off_view = preprocessing.filter_signal(
        late_off_i.transpose(1, 0, 2).reshape(n_channels, -1),
        sfreq, *VIEW_BAND_HZ
    )

    on_power = np.mean(on_view ** 2, axis=1)  # (n_channels,)
    late_off_power = np.mean(late_off_view ** 2, axis=1)
    artifact_magnitude = on_power / (late_off_power + 1e-8)  # ON/OFF power ratio

    # ---- Per-region analysis ----
    for region_name, region_spec in regions_available.items():
        ch_indices = [all_channels.index(ch) for ch in region_spec["channels"]]
        region_artifact_mags = artifact_magnitude[ch_indices]
        region_artifact_mean = np.mean(region_artifact_mags)

        # Classify as high/low artifact based on median across intensities (will compute dynamically)
        # For now, use median of this region's artifact across all intensities

        # ---- Compute ITPC for this region per method ----
        # Raw: select best channel in region by ITPC
        raw_itpc_scores = []
        for ch_idx in ch_indices:
            ch_data = on_raw[:, ch_idx, :]
            metrics_ch = preprocessing.compute_band_limited_epoch_triplet_metrics(
                ch_data, gt_on, sfreq, SIGNAL_BAND_HZ
            )
            raw_itpc_scores.append(np.mean(metrics_ch["itpc_curve"]))

        best_raw_idx_in_region = ch_indices[np.argmax(raw_itpc_scores)]
        on_raw_best = on_raw[:, best_raw_idx_in_region, :]
        metrics_raw_region = preprocessing.compute_band_limited_epoch_triplet_metrics(
            on_raw_best, gt_on, sfreq, SIGNAL_BAND_HZ
        )

        # SASS: apply to whole region, extract source, compute ITPC
        on_raw_region = on_raw[:, ch_indices, :]  # (n_epochs, n_ch_in_region, n_samples)
        late_off_region = late_off_i[:, ch_indices, :]
        n_ch_region = len(ch_indices)

        on_region_concat = on_raw_region.transpose(1, 0, 2).reshape(n_ch_region, -1)
        late_off_region_concat = late_off_region.transpose(1, 0, 2).reshape(n_ch_region, -1)

        cov_a = np.cov(on_region_concat)
        cov_b = np.cov(late_off_region_concat)
        on_cleaned = sass.sass(on_region_concat, cov_a, cov_b)
        on_cleaned_epochs = on_cleaned.reshape(n_ch_region, n_epochs, n_samples).transpose(1, 0, 2)

        # SASS source extraction
        on_sass_concat = on_cleaned
        late_off_sass_concat = late_off_region_concat

        on_sass_signal = preprocessing.filter_signal(on_sass_concat, sfreq, *SIGNAL_BAND_HZ)
        late_off_sass_signal = preprocessing.filter_signal(late_off_sass_concat, sfreq, *SIGNAL_BAND_HZ)

        C_on_sass = np.cov(on_sass_signal)
        C_off_sass = np.cov(late_off_sass_signal)

        evals_sass, evecs_sass = linalg.eig(C_on_sass, C_off_sass)
        evals_sass = evals_sass.real
        evecs_sass = evecs_sass.real

        sort_idx_sass = np.argsort(evals_sass)
        evecs_sass_sorted = evecs_sass[:, sort_idx_sass]
        sass_source_filters = evecs_sass_sorted[:, :min(SSD_MAX_COMPONENTS, n_ch_region)].T

        # Rank SASS by artifact suppression (lowest ON/OFF power ratio)
        sass_artifact_ratios = []
        for spatial_filter in sass_source_filters:
            on_comp = np.dot(spatial_filter, on_sass_concat)
            on_broadband = preprocessing.filter_signal(on_comp, sfreq, *VIEW_BAND_HZ)
            late_off_broadband = preprocessing.filter_signal(late_off_sass_concat, sfreq, *VIEW_BAND_HZ)
            on_power = np.mean(on_broadband ** 2)
            off_power = np.mean(late_off_broadband ** 2)
            artifact_ratio = on_power / (off_power + 1e-8)
            sass_artifact_ratios.append(artifact_ratio)

        best_sass_idx = np.argmin(sass_artifact_ratios)
        sass_filter = sass_source_filters[best_sass_idx]
        on_sass_best = np.dot(sass_filter, on_sass_concat).reshape(n_epochs, -1)
        metrics_sass_region = preprocessing.compute_band_limited_epoch_triplet_metrics(
            on_sass_best, gt_on, sfreq, SIGNAL_BAND_HZ
        )

        # SSD: on raw region
        on_raw_concat = on_raw_region.transpose(1, 0, 2).reshape(n_ch_region, -1)

        signal_band_concat = preprocessing.filter_signal(on_raw_concat, sfreq, *SIGNAL_BAND_HZ)
        view_band_concat = preprocessing.filter_signal(on_raw_concat, sfreq, *VIEW_BAND_HZ)

        C_signal = np.cov(signal_band_concat)
        C_view = np.cov(view_band_concat)
        eigenvalues, eigenvectors = linalg.eig(C_signal, C_view)
        eigenvalues = eigenvalues.real
        eigenvectors = eigenvectors.real

        sort_idx = np.argsort(eigenvalues)[::-1]
        eigenvectors_sorted = eigenvectors[:, sort_idx]
        spatial_filters_ssd = eigenvectors_sorted[:, :min(SSD_MAX_COMPONENTS, n_ch_region)].T

        # Rank SSD by artifact suppression (lowest ON/OFF power ratio)
        late_off_raw_concat = late_off_region.transpose(1, 0, 2).reshape(n_ch_region, -1)
        ssd_artifact_ratios = []
        for spatial_filter in spatial_filters_ssd:
            on_comp = np.dot(spatial_filter, on_raw_concat)
            on_broadband = preprocessing.filter_signal(on_comp, sfreq, *VIEW_BAND_HZ)
            off_comp = np.dot(spatial_filter, late_off_raw_concat)
            late_off_broadband = preprocessing.filter_signal(off_comp, sfreq, *VIEW_BAND_HZ)
            on_power = np.mean(on_broadband ** 2)
            off_power = np.mean(late_off_broadband ** 2)
            artifact_ratio = on_power / (off_power + 1e-8)
            ssd_artifact_ratios.append(artifact_ratio)

        best_ssd_idx = np.argmin(ssd_artifact_ratios)
        ssd_filter = spatial_filters_ssd[best_ssd_idx]
        on_ssd_best = np.dot(ssd_filter, on_raw_concat).reshape(n_epochs, -1)
        metrics_ssd_region = preprocessing.compute_band_limited_epoch_triplet_metrics(
            on_ssd_best, gt_on, sfreq, SIGNAL_BAND_HZ
        )

        # Store results (both mean and full time course)
        regional_results[region_name][intensity_label] = {
            "raw": np.mean(metrics_raw_region["itpc_curve"]),
            "raw_itpc_curve": metrics_raw_region["itpc_curve"],
            "sass": np.mean(metrics_sass_region["itpc_curve"]),
            "sass_itpc_curve": metrics_sass_region["itpc_curve"],
            "ssd": np.mean(metrics_ssd_region["itpc_curve"]),
            "ssd_itpc_curve": metrics_ssd_region["itpc_curve"],
            "artifact_mag": region_artifact_mean,
        }


# ============================================================
# 5) STRATIFY BY ARTIFACT MAGNITUDE AND CREATE RECOVERY CURVES
# ============================================================
# Compute median artifact magnitude for each region
artifact_medians = {}
for region_name in regions_available.keys():
    mags = [regional_results[region_name][intensity]["artifact_mag"] for intensity in RUN02_INTENSITY_LABELS]
    artifact_medians[region_name] = np.median(mags)

# Classify regions as high or low artifact
high_artifact_regions = {r: regional_results[r] for r, mag in artifact_medians.items() if mag > np.median(list(artifact_medians.values()))}
low_artifact_regions = {r: regional_results[r] for r, mag in artifact_medians.items() if mag <= np.median(list(artifact_medians.values()))}

print("\n=== Artifact Magnitude by Region ===")
for region_name in sorted(artifact_medians.keys(), key=lambda r: -artifact_medians[r]):
    print(f"  {region_name}: {artifact_medians[region_name]:.3f}")

print(f"\nHigh-artifact regions (>{np.median(list(artifact_medians.values())):.3f}): {list(high_artifact_regions.keys())}")
print(f"Low-artifact regions (<={np.median(list(artifact_medians.values())):.3f}): {list(low_artifact_regions.keys())}")

# Aggregate ITPC across regions within each artifact stratum
intensity_idx_vals = np.arange(len(RUN02_INTENSITY_LABELS))
itpc_high_raw = []
itpc_high_sass = []
itpc_high_ssd = []
itpc_low_raw = []
itpc_low_sass = []
itpc_low_ssd = []

for intensity_label in RUN02_INTENSITY_LABELS:
    high_raw = [high_artifact_regions[r][intensity_label]["raw"] for r in high_artifact_regions.keys()]
    high_sass = [high_artifact_regions[r][intensity_label]["sass"] for r in high_artifact_regions.keys()]
    high_ssd = [high_artifact_regions[r][intensity_label]["ssd"] for r in high_artifact_regions.keys()]

    low_raw = [low_artifact_regions[r][intensity_label]["raw"] for r in low_artifact_regions.keys()]
    low_sass = [low_artifact_regions[r][intensity_label]["sass"] for r in low_artifact_regions.keys()]
    low_ssd = [low_artifact_regions[r][intensity_label]["ssd"] for r in low_artifact_regions.keys()]

    itpc_high_raw.append(np.mean(high_raw) if high_raw else np.nan)
    itpc_high_sass.append(np.mean(high_sass) if high_sass else np.nan)
    itpc_high_ssd.append(np.mean(high_ssd) if high_ssd else np.nan)
    itpc_low_raw.append(np.mean(low_raw) if low_raw else np.nan)
    itpc_low_sass.append(np.mean(low_sass) if low_sass else np.nan)
    itpc_low_ssd.append(np.mean(low_ssd) if low_ssd else np.nan)

itpc_high_raw = np.array(itpc_high_raw)
itpc_high_sass = np.array(itpc_high_sass)
itpc_high_ssd = np.array(itpc_high_ssd)
itpc_low_raw = np.array(itpc_low_raw)
itpc_low_sass = np.array(itpc_low_sass)
itpc_low_ssd = np.array(itpc_low_ssd)


# ============================================================
# 6) PLOT RECOVERY CURVES STRATIFIED BY ARTIFACT
# ============================================================
fig, axes = plt.subplots(1, 2, figsize=(14, 5), sharey=True)

# High-artifact regions
ax = axes[0]
ax.plot(intensity_idx_vals, itpc_high_raw, "o-", color=FIGURE_COLORS["raw"], lw=2.5, ms=7, label="Raw")
ax.plot(intensity_idx_vals, itpc_high_sass, "s-", color=FIGURE_COLORS["sass"], lw=2.5, ms=7, label="SASS Source")
ax.plot(intensity_idx_vals, itpc_high_ssd, "^-", color=FIGURE_COLORS["ssd"], lw=2.5, ms=7, label="SSD")
ax.set_xticks(intensity_idx_vals)
ax.set_xticklabels(RUN02_INTENSITY_LABELS)
ax.set_xlabel("Stimulation Intensity", fontsize=11, fontweight="bold")
ax.set_ylabel("Mean ITPC (GT-locking)", fontsize=11, fontweight="bold")
ax.set_title("High-Artifact Regions\n(where artifact removal matters)", fontsize=12, fontweight="bold")
ax.set_ylim([0, 1.05])
ax.grid(True, alpha=0.3)
ax.legend(loc="lower right", frameon=False, fontsize=10)

# Low-artifact regions
ax = axes[1]
ax.plot(intensity_idx_vals, itpc_low_raw, "o-", color=FIGURE_COLORS["raw"], lw=2.5, ms=7, label="Raw")
ax.plot(intensity_idx_vals, itpc_low_sass, "s-", color=FIGURE_COLORS["sass"], lw=2.5, ms=7, label="SASS Source")
ax.plot(intensity_idx_vals, itpc_low_ssd, "^-", color=FIGURE_COLORS["ssd"], lw=2.5, ms=7, label="SSD")
ax.set_xticks(intensity_idx_vals)
ax.set_xticklabels(RUN02_INTENSITY_LABELS)
ax.set_xlabel("Stimulation Intensity", fontsize=11, fontweight="bold")
ax.set_title("Low-Artifact Regions\n(where signal is naturally preserved)", fontsize=12, fontweight="bold")
ax.set_ylim([0, 1.05])
ax.grid(True, alpha=0.3)
ax.legend(loc="lower right", frameon=False, fontsize=10)

plt.suptitle("ON-State GT-Locking (ITPC) Stratified by Regional Artifact Magnitude",
             fontsize=13, fontweight="bold", y=1.00)
plt.tight_layout()
fig_path = OUTPUT_DIRECTORY / "exp06_run02_regional_recovery_curves.png"
plt.savefig(fig_path, dpi=220, bbox_inches="tight")
print(f"\nSaved: {fig_path.name}")

# Print summary
print("\n=== Regional Recovery Summary ===")
print(f"High-artifact regions: {list(high_artifact_regions.keys())}")
for intensity_label, itpc_raw, itpc_sass, itpc_ssd in zip(
    RUN02_INTENSITY_LABELS, itpc_high_raw, itpc_high_sass, itpc_high_ssd
):
    print(f"  {intensity_label}: raw={itpc_raw:.3f}, sass={itpc_sass:.3f}, ssd={itpc_ssd:.3f}")

print(f"\nLow-artifact regions: {list(low_artifact_regions.keys())}")
for intensity_label, itpc_raw, itpc_sass, itpc_ssd in zip(
    RUN02_INTENSITY_LABELS, itpc_low_raw, itpc_low_sass, itpc_low_ssd
):
    print(f"  {intensity_label}: raw={itpc_raw:.3f}, sass={itpc_sass:.3f}, ssd={itpc_ssd:.3f}")


# ============================================================
# 7) PLOT TIME-COURSE ITPC STRATIFIED BY ARTIFACT
# ============================================================
time_axis = np.linspace(ON_WINDOW_S[0], ON_WINDOW_S[1], len(high_artifact_regions[list(high_artifact_regions.keys())[0]]["10%"]["raw_itpc_curve"]))

fig, axes = plt.subplots(2, 5, figsize=(18, 8))

for intensity_idx, intensity_label in enumerate(RUN02_INTENSITY_LABELS):
    # High-artifact regions time course
    ax_high = axes[0, intensity_idx]

    # Aggregate time courses across high-artifact regions
    high_raw_curves = [high_artifact_regions[r][intensity_label]["raw_itpc_curve"] for r in high_artifact_regions.keys()]
    high_sass_curves = [high_artifact_regions[r][intensity_label]["sass_itpc_curve"] for r in high_artifact_regions.keys()]
    high_ssd_curves = [high_artifact_regions[r][intensity_label]["ssd_itpc_curve"] for r in high_artifact_regions.keys()]

    high_raw_mean = np.mean(high_raw_curves, axis=0)
    high_sass_mean = np.mean(high_sass_curves, axis=0)
    high_ssd_mean = np.mean(high_ssd_curves, axis=0)

    ax_high.plot(time_axis, high_raw_mean, "-", color=FIGURE_COLORS["raw"], lw=2, label="Raw", alpha=0.9)
    ax_high.plot(time_axis, high_sass_mean, "-", color=FIGURE_COLORS["sass"], lw=2, label="SASS", alpha=0.9)
    ax_high.plot(time_axis, high_ssd_mean, "-", color=FIGURE_COLORS["ssd"], lw=2, label="SSD", alpha=0.9)

    ax_high.set_ylim([0, 1.05])
    ax_high.set_xlabel("Time (s)", fontsize=9)
    ax_high.set_ylabel("ITPC" if intensity_idx == 0 else "", fontsize=9)
    ax_high.set_title(f"{intensity_label} High-Artifact", fontsize=10, fontweight="bold")
    ax_high.grid(True, alpha=0.2)
    if intensity_idx == 0:
        ax_high.legend(loc="lower right", fontsize=8, frameon=False)

    # Low-artifact regions time course
    ax_low = axes[1, intensity_idx]

    low_raw_curves = [low_artifact_regions[r][intensity_label]["raw_itpc_curve"] for r in low_artifact_regions.keys()]
    low_sass_curves = [low_artifact_regions[r][intensity_label]["sass_itpc_curve"] for r in low_artifact_regions.keys()]
    low_ssd_curves = [low_artifact_regions[r][intensity_label]["ssd_itpc_curve"] for r in low_artifact_regions.keys()]

    low_raw_mean = np.mean(low_raw_curves, axis=0)
    low_sass_mean = np.mean(low_sass_curves, axis=0)
    low_ssd_mean = np.mean(low_ssd_curves, axis=0)

    ax_low.plot(time_axis, low_raw_mean, "-", color=FIGURE_COLORS["raw"], lw=2, label="Raw", alpha=0.9)
    ax_low.plot(time_axis, low_sass_mean, "-", color=FIGURE_COLORS["sass"], lw=2, label="SASS", alpha=0.9)
    ax_low.plot(time_axis, low_ssd_mean, "-", color=FIGURE_COLORS["ssd"], lw=2, label="SSD", alpha=0.9)

    ax_low.set_ylim([0, 1.05])
    ax_low.set_xlabel("Time (s)", fontsize=9)
    ax_low.set_ylabel("ITPC" if intensity_idx == 0 else "", fontsize=9)
    ax_low.set_title(f"{intensity_label} Low-Artifact", fontsize=10, fontweight="bold")
    ax_low.grid(True, alpha=0.2)

fig.suptitle("ITPC Time Courses Stratified by Regional Artifact Magnitude",
             fontsize=13, fontweight="bold", y=0.995)
plt.tight_layout()
fig_path = OUTPUT_DIRECTORY / "exp06_run02_regional_itpc_timecourse.png"
plt.savefig(fig_path, dpi=220, bbox_inches="tight")
print(f"Saved: {fig_path.name}")


# ============================================================
# 8) CHECK FOR SSD SATURATION (ITPC > 0.95 duration)
# ============================================================
print("\n=== SSD ITPC Saturation Analysis (time > 0.95) ===")
for intensity_label in RUN02_INTENSITY_LABELS:
    high_ssd_curves = [high_artifact_regions[r][intensity_label]["ssd_itpc_curve"] for r in high_artifact_regions.keys()]
    high_ssd_mean = np.mean(high_ssd_curves, axis=0)

    saturated_samples = np.sum(high_ssd_mean > 0.95)
    saturated_pct = 100 * saturated_samples / len(high_ssd_mean)

    print(f"  {intensity_label}: {saturated_pct:.1f}% of time window above 0.95 ITPC")


# ============================================================
# 9) PLOT POWER TIME COURSES (to check signal integrity during saturation)
# ============================================================
# Need to recompute or store power during the regional loop
# For now, compute power from the stored signal data

fig, axes = plt.subplots(2, 5, figsize=(18, 8))

for intensity_index, intensity_label in enumerate(RUN02_INTENSITY_LABELS):
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

    raw_data_2d = raw_eeg.get_data()
    on_raw = np.array([
        raw_data_2d[:, int(start):int(start) + on_window_size]
        for start in events_on[:, 0] + on_start_shift
    ])
    gt_on = preprocessing.extract_event_windows(gt_trace, events_on[:, 0], on_window_size)

    n_epochs, n_channels, n_samples = on_raw.shape

    # Compute power time courses for high-artifact regions
    ax_high = axes[0, intensity_index]

    # Raw: best channel in high-artifact regions
    high_raw_chs = []
    for region_name in high_artifact_regions.keys():
        ch_indices = [all_channels.index(ch) for ch in regions_available[region_name]["channels"]]
        raw_itpc_scores = []
        for ch_idx in ch_indices:
            ch_data = on_raw[:, ch_idx, :]
            metrics_ch = preprocessing.compute_band_limited_epoch_triplet_metrics(
                ch_data, gt_on, sfreq, SIGNAL_BAND_HZ
            )
            raw_itpc_scores.append(np.mean(metrics_ch["itpc_curve"]))
        best_ch_idx = ch_indices[np.argmax(raw_itpc_scores)]
        high_raw_chs.append(on_raw[:, best_ch_idx, :])

    on_raw_best = np.mean([c for c in high_raw_chs], axis=0)  # average across high-artifact regions
    raw_power = preprocessing.filter_signal(on_raw_best, sfreq, *SIGNAL_BAND_HZ)
    raw_power_time = np.mean(raw_power ** 2, axis=0)

    # SSD
    ch_indices_all_high = []
    for region_name in high_artifact_regions.keys():
        ch_indices_all_high.extend([all_channels.index(ch) for ch in regions_available[region_name]["channels"]])
    ch_indices_all_high = list(set(ch_indices_all_high))

    on_raw_high = on_raw[:, ch_indices_all_high, :]
    n_ch_high = len(ch_indices_all_high)
    on_raw_concat = on_raw_high.transpose(1, 0, 2).reshape(n_ch_high, -1)

    signal_band_concat = preprocessing.filter_signal(on_raw_concat, sfreq, *SIGNAL_BAND_HZ)
    view_band_concat = preprocessing.filter_signal(on_raw_concat, sfreq, *VIEW_BAND_HZ)

    C_signal = np.cov(signal_band_concat)
    C_view = np.cov(view_band_concat)
    eigenvalues, eigenvectors = linalg.eig(C_signal, C_view)
    eigenvalues = eigenvalues.real
    eigenvectors = eigenvectors.real

    sort_idx = np.argsort(eigenvalues)[::-1]
    eigenvectors_sorted = eigenvectors[:, sort_idx]
    spatial_filters_ssd = eigenvectors_sorted[:, :min(SSD_MAX_COMPONENTS, n_ch_high)].T

    ssd_itpc_scores = []
    for spatial_filter in spatial_filters_ssd:
        on_comp = np.dot(spatial_filter, on_raw_concat).reshape(n_epochs, -1)
        metrics_comp = preprocessing.compute_band_limited_epoch_triplet_metrics(
            on_comp, gt_on, sfreq, SIGNAL_BAND_HZ
        )
        ssd_itpc_scores.append(np.mean(metrics_comp["itpc_curve"]))

    best_ssd_idx = np.argmax(ssd_itpc_scores)
    ssd_filter = spatial_filters_ssd[best_ssd_idx]
    on_ssd = np.dot(ssd_filter, on_raw_concat).reshape(n_epochs, -1)
    ssd_power = preprocessing.filter_signal(on_ssd, sfreq, *SIGNAL_BAND_HZ)
    ssd_power_time = np.mean(ssd_power ** 2, axis=0)

    ax_high.plot(time_axis, raw_power_time, "-", color=FIGURE_COLORS["raw"], lw=2, label="Raw", alpha=0.8)
    ax_high.plot(time_axis, ssd_power_time, "-", color=FIGURE_COLORS["ssd"], lw=2, label="SSD", alpha=0.8)
    ax_high.set_ylabel("Power (µV²)" if intensity_index == 0 else "", fontsize=9)
    ax_high.set_title(f"{intensity_label} High-Artifact Power", fontsize=10, fontweight="bold")
    ax_high.grid(True, alpha=0.2)
    if intensity_index == 0:
        ax_high.legend(loc="upper right", fontsize=8, frameon=False)

    # Low-artifact regions power
    ax_low = axes[1, intensity_index]

    low_raw_chs = []
    for region_name in low_artifact_regions.keys():
        ch_indices = [all_channels.index(ch) for ch in regions_available[region_name]["channels"]]
        raw_itpc_scores = []
        for ch_idx in ch_indices:
            ch_data = on_raw[:, ch_idx, :]
            metrics_ch = preprocessing.compute_band_limited_epoch_triplet_metrics(
                ch_data, gt_on, sfreq, SIGNAL_BAND_HZ
            )
            raw_itpc_scores.append(np.mean(metrics_ch["itpc_curve"]))
        best_ch_idx = ch_indices[np.argmax(raw_itpc_scores)]
        low_raw_chs.append(on_raw[:, best_ch_idx, :])

    on_raw_low_best = np.mean([c for c in low_raw_chs], axis=0)
    raw_low_power = preprocessing.filter_signal(on_raw_low_best, sfreq, *SIGNAL_BAND_HZ)
    raw_low_power_time = np.mean(raw_low_power ** 2, axis=0)

    ch_indices_all_low = []
    for region_name in low_artifact_regions.keys():
        ch_indices_all_low.extend([all_channels.index(ch) for ch in regions_available[region_name]["channels"]])
    ch_indices_all_low = list(set(ch_indices_all_low))

    on_raw_low = on_raw[:, ch_indices_all_low, :]
    n_ch_low = len(ch_indices_all_low)
    on_raw_concat_low = on_raw_low.transpose(1, 0, 2).reshape(n_ch_low, -1)

    signal_band_concat_low = preprocessing.filter_signal(on_raw_concat_low, sfreq, *SIGNAL_BAND_HZ)
    view_band_concat_low = preprocessing.filter_signal(on_raw_concat_low, sfreq, *VIEW_BAND_HZ)

    C_signal_low = np.cov(signal_band_concat_low)
    C_view_low = np.cov(view_band_concat_low)
    eigenvalues_low, eigenvectors_low = linalg.eig(C_signal_low, C_view_low)
    eigenvalues_low = eigenvalues_low.real
    eigenvectors_low = eigenvectors_low.real

    sort_idx_low = np.argsort(eigenvalues_low)[::-1]
    eigenvectors_sorted_low = eigenvectors_low[:, sort_idx_low]
    spatial_filters_ssd_low = eigenvectors_sorted_low[:, :min(SSD_MAX_COMPONENTS, n_ch_low)].T

    ssd_itpc_scores_low = []
    for spatial_filter in spatial_filters_ssd_low:
        on_comp = np.dot(spatial_filter, on_raw_concat_low).reshape(n_epochs, -1)
        metrics_comp = preprocessing.compute_band_limited_epoch_triplet_metrics(
            on_comp, gt_on, sfreq, SIGNAL_BAND_HZ
        )
        ssd_itpc_scores_low.append(np.mean(metrics_comp["itpc_curve"]))

    best_ssd_idx_low = np.argmax(ssd_itpc_scores_low)
    ssd_filter_low = spatial_filters_ssd_low[best_ssd_idx_low]
    on_ssd_low = np.dot(ssd_filter_low, on_raw_concat_low).reshape(n_epochs, -1)
    ssd_power_low = preprocessing.filter_signal(on_ssd_low, sfreq, *SIGNAL_BAND_HZ)
    ssd_power_time_low = np.mean(ssd_power_low ** 2, axis=0)

    ax_low.plot(time_axis, raw_low_power_time, "-", color=FIGURE_COLORS["raw"], lw=2, label="Raw", alpha=0.8)
    ax_low.plot(time_axis, ssd_power_time_low, "-", color=FIGURE_COLORS["ssd"], lw=2, label="SSD", alpha=0.8)
    ax_low.set_ylabel("Power (µV²)" if intensity_index == 0 else "", fontsize=9)
    ax_low.set_title(f"{intensity_label} Low-Artifact Power", fontsize=10, fontweight="bold")
    ax_low.grid(True, alpha=0.2)

fig.suptitle("Signal Power Time Courses Across Regions",
             fontsize=13, fontweight="bold", y=0.995)
plt.tight_layout()
fig_path = OUTPUT_DIRECTORY / "exp06_run02_regional_power_timecourse.png"
plt.savefig(fig_path, dpi=220, bbox_inches="tight")
print(f"Saved: {fig_path.name}")
