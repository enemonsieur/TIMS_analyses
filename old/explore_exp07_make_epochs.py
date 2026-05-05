"""EXP07: Detect pulse onset, build repeating ON/OFF epochs from continuous 100% iTBS."""

from pathlib import Path
import warnings

import matplotlib.pyplot as plt
import mne
import numpy as np
from scipy.signal import hilbert

# ============================================================
# CONFIG
# ============================================================

DATA_DIRECTORY = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\TIMS_data_sync\pilot\doseresp")
STIM_VHDR_PATH = DATA_DIRECTORY / "exp07-STIM-iTBS_run02_mod100pct.vhdr"
OUTPUT_DIRECTORY = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\EXP07")
OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)

PULSE_ONSET_THRESHOLD_UV = 25e-6  # Envelope must exceed baseline + 25 µV to mark first pulse
BASELINE_WINDOW_S = 0.3           # Rolling baseline over 300 ms for threshold calculation
SKIP_STARTUP_S = 5.0              # Ignore first 5 s (startup transients)
ON_DURATION_S = 2.0               # Each ON block lasts 2 s
OFF_DURATION_S = 4.0              # Each OFF block lasts 4 s (for cycle timing, not extracted)
REF_CHANNEL = "CP2"               # Most stable channel (lowest polyfit drift)

# ════════════════════════════════════════════════════════════════════════════
# PIPELINE OVERVIEW
# ════════════════════════════════════════════════════════════════════════════
#
# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  VHDR → LOAD & DEMEAN → FIND STABLE CHANNEL → DETECT PULSE ONSET         ║
# ║                                                        ↓                   ║
# ║                                      BUILD REPEATING ON/OFF WINDOWS       ║
# ║                                                        ↓                   ║
# ║                                        CREATE EPOCHS & SAVE               ║
# ╚═══════════════════════════════════════════════════════════════════════════╝
#
# Input: 1238 s continuous 100% modulated iTBS, 31 EEG channels @ 1000 Hz
# Output: 204 ON epochs (2 s each), MNE-compatible .fif file + timing visualization

# ============================================================
# 1) LOAD & PREPARE DATA
# ============================================================

# ══ 1.1 Read BrainVision file, suppress filter warnings ══
with warnings.catch_warnings():
    warnings.filterwarnings("ignore", message="No coordinate information found*")
    warnings.filterwarnings("ignore", message="Online software filter detected*")
    warnings.filterwarnings("ignore", message="Not setting positions of 2 misc*")
    raw_stim_full = mne.io.read_raw_brainvision(str(STIM_VHDR_PATH), preload=True, verbose=False)

sampling_rate_hz = float(raw_stim_full.info["sfreq"])

# ══ 1.2 Keep only EEG channels (drop STIM and ground_truth) ══
eeg_channel_names = [ch for ch in raw_stim_full.ch_names if ch.lower() not in ("stim", "ground_truth")]
raw_stim_eeg = raw_stim_full.copy().pick(eeg_channel_names)
# → (31, 1238200) @ 1000 Hz

# ══ 1.3 Remove mean per channel ══
# Demean preserves oscillations while centering baseline. Note: channels still
# show DC offset in first 5 s; epochs will center baseline further during analysis.
raw_stim_eeg._data -= raw_stim_eeg._data.mean(axis=-1, keepdims=True)

duration_s = raw_stim_eeg.n_times / sampling_rate_hz
print(f"Loaded: {duration_s:.1f}s, {len(raw_stim_eeg.ch_names)} channels, {sampling_rate_hz:.1f} Hz")

# ============================================================
# 2) FIND REFERENCE CHANNEL & DETECT PULSE ONSET
# ============================================================

# ══ 2.1 Identify most stable channel via polyfit slope ══
# Channel with smallest absolute slope has least linear drift over entire recording.
slopes = np.array([
    np.polyfit(np.arange(raw_stim_eeg.n_times), raw_stim_eeg._data[i], 1)[0]
    for i in range(len(raw_stim_eeg.ch_names))
])
ref_ch_idx = np.argmin(np.abs(slopes))
ref_ch_name = raw_stim_eeg.ch_names[ref_ch_idx]
ref_signal = raw_stim_eeg._data[ref_ch_idx].copy()

print(f"Reference channel: {ref_ch_name} (slope = {slopes[ref_ch_idx]:.3e} V/sample)")

# ══ 2.2 Remove polynomial drift from reference channel ══
# Degree-1 polyfit removes linear drift without introducing filter artifacts.
poly = np.polyfit(np.arange(len(ref_signal)), ref_signal, 1)
ref_detrended = ref_signal - np.polyval(poly, np.arange(len(ref_signal)))

# Visualize detrending (first 60 s)
plt.figure(figsize=(12, 3))
t_plot = np.arange(60000) / sampling_rate_hz
plt.plot(t_plot, ref_signal[:60000] * 1e6, label="Raw", alpha=0.7)
plt.plot(t_plot, ref_detrended[:60000] * 1e6, label="Detrended", alpha=0.7)
plt.xlabel("Time (s)")
plt.ylabel(f"{ref_ch_name} (µV)")
plt.legend()
plt.tight_layout()
plt.savefig(OUTPUT_DIRECTORY / "01_ref_channel_detrending.png", dpi=100)
plt.close()

# ══ 2.3 Detect first pulse onset via Hilbert envelope ══
# Hilbert transform → instantaneous amplitude. Threshold: envelope ≥ baseline + 25 µV.
# Skip first 5 s to avoid startup artifacts.
baseline_window_samples = int(BASELINE_WINDOW_S * sampling_rate_hz)
envelope = np.abs(hilbert(ref_detrended))
baseline = np.convolve(envelope, np.ones(baseline_window_samples) / baseline_window_samples, mode='same')

skip_samples = int(SKIP_STARTUP_S * sampling_rate_hz)
first_onset_idx = np.where(envelope[skip_samples:] >= baseline[skip_samples:] + PULSE_ONSET_THRESHOLD_UV)[0]
if len(first_onset_idx) == 0:
    raise RuntimeError("No pulse onset detected. Check signal quality or threshold.")

first_onset_sample = skip_samples + first_onset_idx[0]
first_onset_s = first_onset_sample / sampling_rate_hz
# → first onset at sample index; used to anchor all subsequent window starts

print(f"First pulse onset: {first_onset_s:.2f} s (sample {first_onset_sample})")

# Visualize pulse detection (first 20 s)
plt.figure(figsize=(12, 4))
t_plot = np.arange(len(envelope)) / sampling_rate_hz
plt.plot(t_plot, envelope * 1e6, label="Envelope", alpha=0.7)
plt.plot(t_plot, baseline * 1e6, label="300 ms baseline", alpha=0.7)
plt.axvline(first_onset_s, color='red', linestyle='--', label=f"Onset @ {first_onset_s:.2f} s")
plt.xlabel("Time (s)")
plt.ylabel(f"{ref_ch_name} envelope (µV)")
plt.legend()
plt.xlim(0, 20)
plt.tight_layout()
plt.savefig(OUTPUT_DIRECTORY / "02_pulse_onset_detection.png", dpi=100)
plt.close()

# ============================================================
# 3) BUILD REPEATING ON/OFF WINDOWS
# ============================================================

# ══ 3.1 Compute window geometry ══
on_samples = int(ON_DURATION_S * sampling_rate_hz)
off_samples = int(OFF_DURATION_S * sampling_rate_hz)
cycle_samples = on_samples + off_samples
# → ON: 2000 samples, OFF: 4000 samples, cycle: 6000 samples

# ══ 3.2 Generate ON block starts from first pulse, spaced by cycle duration ══
# All block starts = first_onset + n * cycle_samples, where n = 0, 1, 2, ...
n_cycles = int((len(ref_signal) - first_onset_sample) / cycle_samples)
block_onsets_samples = first_onset_sample + np.arange(n_cycles) * cycle_samples
block_offsets_samples = block_onsets_samples + on_samples
# → (n_blocks,) sample indices for each ON window start and end

# ══ 3.3 Keep only complete windows within recording bounds ══
valid_idx = block_offsets_samples < len(ref_signal)
block_onsets_samples = block_onsets_samples[valid_idx]
block_offsets_samples = block_offsets_samples[valid_idx]

print(f"Generated {len(block_onsets_samples)} ON blocks, {ON_DURATION_S} s each")
print(f"  First 5 onsets: {block_onsets_samples[:5]}")

# ============================================================
# 4) CREATE EPOCHS FROM ON WINDOWS
# ============================================================

# ══ 4.1 Build MNE event array ══
# Format: [sample_idx, prev_id, event_id]. Event IDs drive epoch labeling.
events = np.column_stack([
    block_onsets_samples,
    np.zeros(len(block_onsets_samples), dtype=int),
    np.ones(len(block_onsets_samples), dtype=int)
]).astype(int)
# → (n_events, 3) MNE-style event array

event_dict = {"ON": 1}

# ══ 4.2 Create Epochs object with preload ══
# tmin=0 → epoch starts at block onset; tmax=2.0 → epoch ends at ON offset.
# preload=True → data in memory (needed for len(epochs) to work).
epochs = mne.Epochs(raw_stim_eeg, events, event_dict, tmin=0, tmax=ON_DURATION_S,
                     baseline=None, preload=True, verbose=False)
# → (204, 31, 2001) epochs × channels × samples

print(f"Epochs: {len(epochs)} × {len(epochs.ch_names)} channels × {ON_DURATION_S} s")

# ══ 4.3 Save epochs to file ══
epochs.save(OUTPUT_DIRECTORY / "exp07_epochs-epo.fif", overwrite=True)
print(f"Saved: exp07_epochs-epo.fif")

# ============================================================
# 5) VISUALIZE BLOCK TIMING ON CP2 ENVELOPE
# ============================================================

# Plot CP2 envelope with all 204 ON block windows overlaid (log scale).
# This shows regularity of detected blocks and envelope dynamics across session.
plt.figure(figsize=(14, 5))
t_plot = np.arange(len(envelope)) / sampling_rate_hz
plt.semilogy(t_plot, envelope * 1e6, label="CP2 envelope", alpha=0.8, linewidth=0.8)

# Overlay all ON windows as vertical shaded regions
for onset_s in block_onsets_samples / sampling_rate_hz:
    offset_s = onset_s + ON_DURATION_S
    plt.axvspan(onset_s, offset_s, alpha=0.1, color='blue', label='ON' if onset_s == block_onsets_samples[0]/sampling_rate_hz else '')

plt.xlabel("Time (s)")
plt.ylabel(f"{ref_ch_name} envelope (µV, log scale)")
plt.title(f"EXP07: {len(block_onsets_samples)} ON blocks detected (2 s each, +4 s OFF)")
plt.grid(True, alpha=0.3, which='both')
plt.tight_layout()
plt.savefig(OUTPUT_DIRECTORY / "03_block_timing_all_204_blocks.png", dpi=100)
plt.close()

print(f"Saved: 03_block_timing_all_204_blocks.png")
