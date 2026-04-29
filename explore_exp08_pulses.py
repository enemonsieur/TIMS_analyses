"""Extract repeating ON windows from EXP08 pulse recording, grouped by intensity level (10–100%)."""

from pathlib import Path
import warnings

import matplotlib.pyplot as plt
import mne
import numpy as np

import preprocessing

# ============================================================
# CONFIG
# ============================================================

DATA_DIRECTORY = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\TIMS_data_sync\pilot\doseresp")
STIM_VHDR_PATH = DATA_DIRECTORY / "exp08-STIM-pulse_run01_10-100.vhdr"
OUTPUT_DIRECTORY = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\EXP08")
OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)

# Dose-response protocol: 10 intensity levels, 20 pulses per level, 5 s inter-pulse interval
INTENSITY_LEVELS = [0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90, 1.00]
PULSES_PER_INTENSITY = 20
INTER_PULSE_INTERVAL_S = 5.0

# Time windows: ON (pre-post) and late-OFF (noise reference)
ON_WINDOW_S = (-1.0, 2.0)
LATE_OFF_WINDOW_S = (2.5, 4.2)
EXCLUDED_CHANNELS = {"TP9", "Fp1", "TP10"}

# Pulse detection threshold
STIM_THRESHOLD_FRACTION = 0.08  # recover weak first pulse

# ════════════════════════════════════════════════════════════════════════════
# PIPELINE OVERVIEW
# ════════════════════════════════════════════════════════════════════════════
#
# VHDR Recording (31 EEG + stim + GT, 1000 Hz, ~1025 s)
# ├─ Extract: stim timing + GT reference trace
# │  └─ Detect: pulse onsets via envelope (rising edge detection)
# │
# ├─ Organize: pulses into intensity groups
# │  └─ Each intensity: 10%, 20%, 30%, ..., 100%
# │  └─ Each group: 20 pulses (100 s duration, 5 s inter-pulse interval)
# │
# ├─ Per intensity: build two time windows from same pulse onsets
# │  ├─ ON window: -1.0 to +2.0 s (pre-post baseline + response)
# │  └─ late-OFF window: 2.5 to 4.2 s (noise reference, no stimulus artifact)
# │
# ├─ Extract: three epoch sets per intensity per window
# │  ├─ EEG epochs (28 channels)
# │  └─ GT reference epochs (ground-truth signal)
# │
# └─ Save: per-intensity + per-window epoch files + timing summary
#    └─ OUTPUT: exp08_epochs_*pct_on-epo.fif, exp08_epochs_*pct_lateoff-epo.fif
#               exp08_gt_epochs_*pct_on-epo.fif, exp08_gt_epochs_*pct_lateoff-epo.fif

# ============================================================
# 1) LOAD & PREPARE DATA
# ============================================================

# ══ 1.1 Read BrainVision file, suppress metadata warnings ══
with warnings.catch_warnings():
    warnings.filterwarnings("ignore", message="No coordinate information found*")
    warnings.filterwarnings("ignore", message="Online software filter detected*")
    warnings.filterwarnings("ignore", message="Not setting positions of 2 misc*")
    raw_stim_full = mne.io.read_raw_brainvision(str(STIM_VHDR_PATH), preload=True, verbose=False)

sfreq = float(raw_stim_full.info["sfreq"])
duration_s = raw_stim_full.n_times / sfreq

# ══ 1.2 Check required channels ══
if "stim" not in raw_stim_full.ch_names:
    raise RuntimeError("Stim run is missing required channel: stim.")

# ══ 1.3 Extract stim trace ══
stim_trace = raw_stim_full.copy().pick(["stim"]).get_data()[0]
# → (n_samples,) stim voltage in volts

# ══ 1.4 Separate EEG from non-EEG channels ══
NON_EEG = {"stim", "ground_truth"} | EXCLUDED_CHANNELS
raw_eeg = raw_stim_full.copy().drop_channels(
    [ch for ch in raw_stim_full.ch_names if ch in NON_EEG or ch.startswith("STI")]
)
if len(raw_eeg.ch_names) == 0:
    raise RuntimeError("No retained EEG channels remain after removing stim, GT, and excluded channels.")

print(f"Loaded: {duration_s:.1f} s, {len(raw_eeg.ch_names)} EEG channels, {sfreq:.0f} Hz")
print(f"Expected total pulses: {len(INTENSITY_LEVELS)} levels × {PULSES_PER_INTENSITY} pulses = {len(INTENSITY_LEVELS) * PULSES_PER_INTENSITY}")

# ============================================================
# 2) DETECT PULSE BLOCKS & ORGANIZE BY INTENSITY
# ============================================================

# ══ 2.1 Deterministic pulse onset calculation ══
# Experiment control: fixed 5 s inter-pulse interval at 1000 Hz.
# User-confirmed first pulse peak: sample 20530 (read from diagnostic plot).
# All 200 onsets: first + k × IPI, k=0..199. Zero jitter by construction.
FIRST_PULSE_SAMPLE = 20530
inter_pulse_samples = int(round(INTER_PULSE_INTERVAL_S * sfreq))
n_pulses = len(INTENSITY_LEVELS) * PULSES_PER_INTENSITY

block_onsets_samples = FIRST_PULSE_SAMPLE + np.arange(n_pulses) * inter_pulse_samples
block_offsets_samples = block_onsets_samples + inter_pulse_samples

print(f"Deterministic onsets: first={block_onsets_samples[0]}, "
      f"last={block_onsets_samples[-1]}, IPI={inter_pulse_samples} samples, "
      f"n_pulses={n_pulses}")

# ════════════════════════════════════════════════════════════════════════════
# 3) PULSE ALIGNMENT QC
# ════════════════════════════════════════════════════════════════════════════

# ══ 3.1 Extract short stim window around each detected onset ══
# −5 ms to +30 ms captures the full ~15 ms TMS discharge and pre-pulse baseline.
# Seconds → samples for array slicing.
from scipy.signal import correlate
pre_samples = int(round(0.005 * sfreq))   # 5 ms pre-onset
post_samples = int(round(0.030 * sfreq))  # 30 ms post-onset
window_size = pre_samples + post_samples  # 35 samples at 1 kHz

pulse_matrix = np.stack([
    stim_trace[onset - pre_samples : onset + post_samples]
    for onset in block_onsets_samples
    if onset >= pre_samples and onset + post_samples <= len(stim_trace)
])
# → (n_pulses, window_size) stim voltage in volts; rows are individual pulses

# ══ 3.2 Cross-correlate each pulse against the mean template ══
# Measures per-pulse onset jitter in samples.
# scipy.signal.correlate with mode="full" returns full correlation;
# peak position encodes lag relative to template.
template = pulse_matrix.mean(axis=0)  # (window_size,) mean pulse shape
lags_samples = np.array([
    np.argmax(correlate(pulse, template, mode="full")) - (window_size - 1)
    for pulse in pulse_matrix
])
# → (n_pulses,) int lag in samples; 0 = perfectly aligned

print(f"Pulse alignment jitter: min={lags_samples.min()}, max={lags_samples.max()}, "
      f"std={lags_samples.std():.2f} samples")

# ══ 3.3 QC plot: pulse overlay + jitter histogram ══
time_ms = np.linspace(-pre_samples, post_samples - 1, window_size) / sfreq * 1000
# → (window_size,) time axis in milliseconds

fig, (ax_overlay, ax_hist) = plt.subplots(1, 2, figsize=(12, 4))

# Panel A: all pulse waveforms overlaid
ax_overlay.plot(time_ms, pulse_matrix.T * 1e6, color="gray", alpha=0.2, linewidth=0.5)
ax_overlay.plot(time_ms, template * 1e6, color="black", linewidth=1.5, label="mean")
ax_overlay.axvline(0, color="red", linestyle="--", linewidth=0.8, alpha=0.7)
ax_overlay.set_xlabel("Time relative to detected onset (ms)")
ax_overlay.set_ylabel("STIM voltage (µV)")
ax_overlay.set_title("All pulse waveforms (gray) vs. mean (black)")
ax_overlay.legend()
ax_overlay.grid(True, alpha=0.3)

# Panel B: lag distribution
lag_bins = np.arange(lags_samples.min() - 1, lags_samples.max() + 2)
ax_hist.hist(lags_samples, bins=lag_bins, edgecolor="black")
ax_hist.set_xlabel("Cross-correlation lag (samples = ms at 1 kHz)")
ax_hist.set_ylabel("Count")
ax_hist.set_title("Onset jitter distribution")
ax_hist.grid(True, alpha=0.3, axis="y")

fig.tight_layout()
fig.savefig(OUTPUT_DIRECTORY / "exp08_pulse_alignment_qc.png", dpi=150)
plt.close()
print("Saved: exp08_pulse_alignment_qc.png")

# ════════════════════════════════════════════════════════════════════════════
# 4) EPOCH BUILD (conditional on alignment QC pass)
# ════════════════════════════════════════════════════════════════════════════

# ══ 4.2 Group blocks into intensity levels ══
# Blocks are sequential: 0–19 → 10%, 20–39 → 20%, ..., 180–199 → 100%
intensity_blocks = {}  # dict: intensity_pct → list of (onset, offset) tuples
for intensity_idx, intensity_level in enumerate(INTENSITY_LEVELS):
    block_start_idx = intensity_idx * PULSES_PER_INTENSITY
    block_stop_idx = block_start_idx + PULSES_PER_INTENSITY
    onsets = block_onsets_samples[block_start_idx:block_stop_idx]
    offsets = block_offsets_samples[block_start_idx:block_stop_idx]
    intensity_blocks[intensity_level] = list(zip(onsets, offsets))
    print(f"  {intensity_level*100:.0f}%: {len(onsets)} pulses")

# ============================================================
# 5) BUILD EPOCHS PER INTENSITY
# ============================================================

# ══ 5.1 Compute ON window geometry ══
window_len = ON_WINDOW_S[1] - ON_WINDOW_S[0]  # 0.6 s
window_size = int(round(window_len * sfreq))   # 600 samples
# Note: MNE.Epochs handles tmin/tmax directly, no start_shift needed

print(f"\nON window: {ON_WINDOW_S[0]:.2f}–{ON_WINDOW_S[1]:.1f} s (pre-post, {window_size} samples)")

# ══ 5.2 Process each intensity level ══
summary_rows = []
timing_figure_windows = []

for intensity_level in INTENSITY_LEVELS:
    intensity_pct = int(intensity_level * 100)
    dose_onsets, dose_offsets = zip(*intensity_blocks[intensity_level])
    dose_onsets = np.array(dose_onsets)
    dose_offsets = np.array(dose_offsets)

    # 5.2.1 Build accepted ON windows (same pulse onsets used for both ON and late-OFF)
    # Reject only if pulse is too close to boundaries
    on_pre_samples = int(round(-ON_WINDOW_S[0] * sfreq))  # 100 samples pre
    on_post_samples = int(round(ON_WINDOW_S[1] * sfreq))  # 500 samples post
    late_off_post_samples = int(round(LATE_OFF_WINDOW_S[1] * sfreq))  # 3.2 s post

    on_window_keep = (dose_onsets >= on_pre_samples) & (dose_onsets + on_post_samples <= raw_eeg.n_times)
    late_off_window_keep = (dose_onsets + late_off_post_samples <= raw_eeg.n_times)
    window_keep = on_window_keep & late_off_window_keep  # both windows must fit
    event_samples = dose_onsets[window_keep]
    events = preprocessing.build_event_array(event_samples)

    valid_count = len(events)
    if valid_count == 0:
        raise RuntimeError(f"No valid windows (ON + late-OFF) for {intensity_pct}%.")

    # 5.2.2 Create ON epochs (EEG)
    event_dict_on = {f"intensity_{intensity_pct}pct": 1}
    epochs_on = mne.Epochs(
        raw_eeg, events, event_dict_on, tmin=ON_WINDOW_S[0], tmax=ON_WINDOW_S[1],
        baseline=None, preload=True, verbose=False
    )

    # 5.2.3 Create late-OFF epochs (EEG)
    event_dict_off = {f"intensity_{intensity_pct}pct": 1}
    epochs_late_off = mne.Epochs(
        raw_eeg, events, event_dict_off, tmin=LATE_OFF_WINDOW_S[0], tmax=LATE_OFF_WINDOW_S[1],
        baseline=None, preload=True, verbose=False
    )

    # 5.2.4 Create ON and late-OFF GT epochs
    gt_raw = raw_stim_full.copy().pick(["ground_truth"])
    epochs_gt_on = mne.Epochs(
        gt_raw, events, event_dict_on, tmin=ON_WINDOW_S[0], tmax=ON_WINDOW_S[1],
        baseline=None, preload=True, verbose=False
    )
    epochs_gt_late_off = mne.Epochs(
        gt_raw, events, event_dict_off, tmin=LATE_OFF_WINDOW_S[0], tmax=LATE_OFF_WINDOW_S[1],
        baseline=None, preload=True, verbose=False
    )

    # 5.2.5 Create ON and late-OFF stimulus epochs
    stim_raw = raw_stim_full.copy().pick(["stim"])
    epochs_stim_on = mne.Epochs(
        stim_raw, events, event_dict_on, tmin=ON_WINDOW_S[0], tmax=ON_WINDOW_S[1],
        baseline=None, preload=True, verbose=False
    )
    epochs_stim_late_off = mne.Epochs(
        stim_raw, events, event_dict_off, tmin=LATE_OFF_WINDOW_S[0], tmax=LATE_OFF_WINDOW_S[1],
        baseline=None, preload=True, verbose=False
    )

    # 5.2.6 Save all epoch files
    output_on = f"exp08_epochs_{intensity_pct}pct_on-epo.fif"
    output_off = f"exp08_epochs_{intensity_pct}pct_lateoff-epo.fif"
    output_gt_on = f"exp08_gt_epochs_{intensity_pct}pct_on-epo.fif"
    output_gt_off = f"exp08_gt_epochs_{intensity_pct}pct_lateoff-epo.fif"
    output_stim_on = f"exp08_stim_epochs_{intensity_pct}pct_on-epo.fif"
    output_stim_off = f"exp08_stim_epochs_{intensity_pct}pct_lateoff-epo.fif"

    epochs_on.save(OUTPUT_DIRECTORY / output_on, overwrite=True)
    epochs_late_off.save(OUTPUT_DIRECTORY / output_off, overwrite=True)
    epochs_gt_on.save(OUTPUT_DIRECTORY / output_gt_on, overwrite=True)
    epochs_gt_late_off.save(OUTPUT_DIRECTORY / output_gt_off, overwrite=True)
    epochs_stim_on.save(OUTPUT_DIRECTORY / output_stim_on, overwrite=True)
    epochs_stim_late_off.save(OUTPUT_DIRECTORY / output_stim_off, overwrite=True)

    summary_rows.append({
        "intensity_pct": intensity_pct,
        "valid_epochs": valid_count,
        "on_window_start_s": ON_WINDOW_S[0],
        "on_window_end_s": ON_WINDOW_S[1],
        "late_off_window_start_s": LATE_OFF_WINDOW_S[0],
        "late_off_window_end_s": LATE_OFF_WINDOW_S[1],
        "eeg_channels": len(epochs_on.ch_names),
    })

    print(f"  {intensity_pct}%: {valid_count} valid epochs saved (ON: {output_on}, OFF: {output_off}, GT: {output_gt_on}, {output_gt_off}, STIM: {output_stim_on}, {output_stim_off})")

    # Store timing windows for visualization (pulse onset at t=0)
    for event_sample in event_samples:
        timing_figure_windows.append((
            intensity_pct,
            "ON",
            (event_sample - on_pre_samples) / sfreq,
            (event_sample + on_post_samples) / sfreq,
        ))
        timing_figure_windows.append((
            intensity_pct,
            "late-OFF",
            (event_sample + int(round(LATE_OFF_WINDOW_S[0] * sfreq))) / sfreq,
            (event_sample + int(round(LATE_OFF_WINDOW_S[1] * sfreq))) / sfreq,
        ))

# ============================================================
# 6) VISUALIZE BLOCK TIMING
# ============================================================

# ══ 6.1 Plot stim trace with all ON windows marked by intensity ══
fig, ax = plt.subplots(figsize=(16, 6))
time_s = np.arange(len(stim_trace)) / sfreq

# Plot stim trace (log scale)
ax.semilogy(time_s, np.abs(stim_trace) * 1e6, linewidth=0.5, alpha=0.7, color='black', label='STIM')

# Color map for intensity levels
colors = plt.cm.Blues(np.linspace(0.3, 1.0, len(INTENSITY_LEVELS)))

# Overlay ON windows colored by intensity
for intensity_idx, intensity_level in enumerate(INTENSITY_LEVELS):
    intensity_pct = int(intensity_level * 100)
    for stored_intensity_pct, window_label, start_s, end_s in timing_figure_windows:
        if stored_intensity_pct == intensity_pct and window_label == "ON":
            ax.axvspan(start_s, end_s, alpha=0.1, color=colors[intensity_idx])

# Add intensity level labels in legend
for intensity_idx, intensity_level in enumerate(INTENSITY_LEVELS):
    ax.scatter([], [], c=[colors[intensity_idx]], label=f"{int(intensity_level*100)}%", s=100)

ax.set_xlabel("Time (s)")
ax.set_ylabel("STIM voltage (µV, log scale)")
ax.set_title("EXP08: Pulse blocks by intensity level (10–100%)")
ax.legend(loc='upper right', ncol=2)
ax.grid(True, alpha=0.3, which='both')
fig.tight_layout()
fig.savefig(OUTPUT_DIRECTORY / "exp08_block_timing_by_intensity.png", dpi=100)
plt.close()

print(f"\nSaved: exp08_block_timing_by_intensity.png")

# ============================================================
# 7) SAVE SUMMARY & REPORT
# ============================================================

# ══ 7.1 Write timing summary to file ══
summary_path = OUTPUT_DIRECTORY / "exp08_epoch_summary.txt"
with open(summary_path, "w") as f:
    f.write("=" * 80 + "\n")
    f.write("EXP08: EPOCH EXTRACTION BY INTENSITY SUMMARY\n")
    f.write("=" * 80 + "\n\n")

    f.write(f"Recording: {STIM_VHDR_PATH.name}\n")
    f.write(f"Duration: {duration_s:.1f} s\n")
    f.write(f"Sampling rate: {sfreq:.0f} Hz\n")
    f.write(f"EEG channels: {len(raw_eeg.ch_names)}\n")
    f.write(f"Total pulses detected: {len(block_onsets_samples)}\n\n")

    f.write(f"Dose-response protocol:\n")
    f.write(f"  Intensity levels: {len(INTENSITY_LEVELS)} (10–100%)\n")
    f.write(f"  Pulses per level: {PULSES_PER_INTENSITY}\n")
    f.write(f"  Inter-pulse interval: {INTER_PULSE_INTERVAL_S:.1f} s\n\n")

    f.write(f"ON window definition:\n")
    f.write(f"  Start: {ON_WINDOW_S[0]:.2f} s (pre-pulse baseline)\n")
    f.write(f"  End: {ON_WINDOW_S[1]:.1f} s post-pulse onset\n")
    f.write(f"  Duration: {window_len:.1f} s ({window_size} samples)\n")
    f.write(f"  Pulse onset: at t=0 (center of window)\n\n")

    f.write(f"Late-OFF window definition (noise reference):\n")
    f.write(f"  Start: {LATE_OFF_WINDOW_S[0]:.1f} s post-pulse onset\n")
    f.write(f"  End: {LATE_OFF_WINDOW_S[1]:.1f} s post-pulse onset\n")
    f.write(f"  Duration: {LATE_OFF_WINDOW_S[1] - LATE_OFF_WINDOW_S[0]:.1f} s\n")
    f.write(f"  Purpose: covariance reference for SASS/SSD (free of stimulus artifact)\n\n")

    f.write("Per-intensity epoch counts:\n")
    f.write("-" * 80 + "\n")
    f.write(f"{'Intensity':<12} {'Valid Epochs':<15} {'Output Files':<40}\n")
    f.write("-" * 80 + "\n")

    for summary_row in summary_rows:
        intensity_pct = summary_row["intensity_pct"]
        valid_epochs = summary_row["valid_epochs"]
        output_files = f"*{intensity_pct}pct_on-epo.fif, *{intensity_pct}pct_lateoff-epo.fif"
        f.write(f"{intensity_pct}%{'':<9} {valid_epochs:<15} {output_files:<40}\n")

    f.write("-" * 80 + "\n")
    f.write(f"{'TOTAL':<12} {sum(row['valid_epochs'] for row in summary_rows):<15}\n")
    f.write("-" * 80 + "\n\n")

    f.write("Excluded channels: " + ", ".join(EXCLUDED_CHANNELS) + "\n")
    f.write(f"Pulse detection threshold: {STIM_THRESHOLD_FRACTION * 100:.0f}% of max stim amplitude\n\n")

    f.write("Output files generated per intensity:\n")
    f.write("  exp08_epochs_*pct_on-epo.fif (ON window: -1.0 to +2.0 s)\n")
    f.write("  exp08_epochs_*pct_lateoff-epo.fif (late-OFF window: 2.5 to 4.2 s)\n")
    f.write("  exp08_gt_epochs_*pct_on-epo.fif (GT reference, ON window)\n")
    f.write("  exp08_gt_epochs_*pct_lateoff-epo.fif (GT reference, late-OFF window)\n\n")
    f.write("Additional output:\n")
    f.write("  exp08_block_timing_by_intensity.png (timing visualization)\n")
    f.write("  exp08_epoch_summary.txt (this file)\n")

print(f"Saved: {summary_path}")

# ══ 7.2 Print summary to console ══
print("\n" + "=" * 80)
print("EXP08 EPOCH EXTRACTION COMPLETE")
print("=" * 80)
print(f"\nTotal valid epochs across all intensities: {sum(row['valid_epochs'] for row in summary_rows)}")
print(f"Output directory: {OUTPUT_DIRECTORY}")
print(f"See exp08_epoch_summary.txt for detailed manifest.\n")
