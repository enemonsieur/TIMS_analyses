"""Generate ON ITPC time courses for all methods: Raw, SASS, SSD.

QUESTION: How does ITPC evolve in time during the ON window for each method across intensities?
Do all methods show phase locking at all time points, or is there a latency/window of recovery?

KEY FEATURE: Time-resolved ITPC (not averaged), per method, per intensity.
Shows temporal dynamics of phase locking during the ON window (0.3–1.5 s).

OUTPUT FIGURES:
  - exp06_run02_all_methods_itpc_timecourse.png (5 rows × 3 columns grid)
    Row i = intensity i (10%, 20%, ..., 50%)
    Col j = method j (Raw, SASS, SSD)
    Each cell shows ITPC(t) from 0.3–1.5 s
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
import preprocessing
import sass


# ============================================================
# CONFIG
# ============================================================
DATA_DIR = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\TIMS_data_sync\pilot\doseresp")
STIM_VHDR = DATA_DIR / "exp06-STIM-iTBS_run02.vhdr"
OUTPUT_DIR = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\EXP06")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

INTENSITIES = ["10%", "20%", "30%", "40%", "50%"]
BLOCK_CYCLES = 20
ON_WINDOW_S = (0.3, 1.5)
LATE_OFF_WINDOW_S = (1.5, 3.2)
EXCLUDED_CH = {"TP9", "Fp1", "TP10"}

TARGET_HZ = 12.451172
SIGNAL_BAND_HZ = (TARGET_HZ - 0.5, TARGET_HZ + 0.5)
VIEW_BAND_HZ = (4.0, 20.0)
N_SSD_COMPONENTS = 6

METHOD_COLORS = {
    "raw": "black",
    "sass": "steelblue",
    "ssd": "seagreen",
}

OUTPUT_PATH = OUTPUT_DIR / "exp06_run02_all_methods_itpc_timecourse.png"


# ============================================================
# HELPERS
# ============================================================
def compute_snr(sig_epochs, sfreq, sig_band, view_band):
    """SNR = power in signal_band / power in view_band."""
    flat = sig_epochs.reshape(-1) if sig_epochs.ndim == 2 else sig_epochs.reshape(sig_epochs.shape[0], -1)
    psd = np.abs(np.fft.rfft(flat, axis=-1)) ** 2
    freqs = np.fft.rfftfreq(flat.shape[-1], 1 / sfreq)

    sig_idx = np.where((freqs >= sig_band[0]) & (freqs <= sig_band[1]))[0]
    view_idx = np.where((freqs >= view_band[0]) & (freqs <= view_band[1]))[0]

    if sig_epochs.ndim == 2:
        return np.mean(psd[sig_idx]) / np.maximum(np.mean(psd[view_idx]), 1e-10)
    else:
        return np.mean(psd[:, sig_idx], axis=1) / np.maximum(np.mean(psd[:, view_idx], axis=1), 1e-10)


def compute_itpc_timecourse(sig_epochs, ref_epochs, sfreq, signal_band):
    """
    Compute time-resolved ITPC: ITPC(t) at each time point.

    sig_epochs: (n_epochs, n_channels, n_samples) or (n_epochs, n_samples)
    ref_epochs: (n_epochs, n_samples)

    Returns: ITPC time course (n_samples,)
    """
    sig_filtered = preprocessing.filter_signal(sig_epochs, sfreq, signal_band[0], signal_band[1])
    ref_filtered = preprocessing.filter_signal(ref_epochs, sfreq, signal_band[0], signal_band[1])

    sig_phase = np.angle(signal.hilbert(sig_filtered, axis=-1))
    ref_phase = np.angle(signal.hilbert(ref_filtered, axis=-1))

    # ITPC per time point
    if sig_epochs.ndim == 3:
        # Multi-channel: average phase difference over channels and epochs
        itpc_ts = []
        for t in range(sig_filtered.shape[-1]):
            phase_diff = sig_phase[:, :, t] - ref_phase[:, t]
            itpc_at_t = np.abs(np.mean(np.exp(1j * phase_diff)))
            itpc_ts.append(itpc_at_t)
    else:
        # Single channel
        phase_diff = sig_phase - ref_phase
        itpc_ts = np.abs(np.mean(np.exp(1j * phase_diff), axis=0))

    return np.array(itpc_ts)


# ============================================================
# 1) LOAD & PREPARE
# ============================================================
print("Loading run02...")
with warnings.catch_warnings():
    warnings.filterwarnings("ignore")
    raw_full = mne.io.read_raw_brainvision(str(STIM_VHDR), preload=True, verbose=False)

sfreq = float(raw_full.info["sfreq"])
stim_trace = raw_full.copy().pick(["stim"]).get_data()[0]
gt_trace = raw_full.copy().pick(["ground_truth"]).get_data()[0]
raw_eeg = raw_full.copy().drop_channels(
    [ch for ch in raw_full.ch_names
     if ch.lower() in {"stim", "ground_truth"} or ch.startswith("STI") or ch in EXCLUDED_CH]
)
raw_data = raw_eeg.get_data()

print(f"Loaded: {raw_eeg.n_times / sfreq:.1f}s | {len(raw_eeg.ch_names)} EEG channels")

block_onsets, block_offsets = preprocessing.detect_stim_blocks(stim_trace, sfreq, threshold_fraction=0.08)
on_start_shift = int(round(ON_WINDOW_S[0] * sfreq))
on_len = int(round((ON_WINDOW_S[1] - ON_WINDOW_S[0]) * sfreq))
late_off_len = int(round((LATE_OFF_WINDOW_S[1] - LATE_OFF_WINDOW_S[0]) * sfreq))


# ============================================================
# 2) ANALYSIS LOOP
# ============================================================
itpc_timecourses = {}  # {intensity: {"raw": ts, "sass": ts, "ssd": ts}}
FIXED_RAW_CH = None

for int_idx, int_label in enumerate(INTENSITIES):
    print(f"\nProcessing {int_label}...")

    # Extract ON/OFF windows
    blk_start = int_idx * BLOCK_CYCLES
    blk_stop = blk_start + BLOCK_CYCLES
    onsets_on = block_onsets[blk_start:blk_stop] + on_start_shift
    offsets_on = block_offsets[blk_start:blk_stop]
    valid = onsets_on + on_len <= offsets_on
    events_on = preprocessing.build_event_array(onsets_on[valid])

    on_raw = np.array([raw_data[:, int(s):int(s) + on_len] for s in events_on[:, 0]], dtype=float)
    gt_on = preprocessing.extract_event_windows(gt_trace, events_on[:, 0], on_len)

    # Late-OFF for SASS
    blk_stop_next = min(blk_stop + 1, len(block_onsets))
    off_full = block_onsets[blk_start:blk_stop_next]
    off_offsets = block_offsets[blk_start:blk_stop_next]
    events_off, _, _ = preprocessing.build_late_off_events(
        off_full, off_offsets, sfreq, LATE_OFF_WINDOW_S[0], LATE_OFF_WINDOW_S[1]
    )
    late_off_raw = np.array([raw_data[:, int(s):int(s) + late_off_len] for s in events_off[:, 0]], dtype=float)

    n_epochs = len(on_raw)
    n_channels = raw_data.shape[0]

    # --- RAW: Lock at 10%, apply to all ---
    if int_idx == 0:
        snrs = [compute_snr(on_raw[:, ch], sfreq, SIGNAL_BAND_HZ, VIEW_BAND_HZ) for ch in range(n_channels)]
        FIXED_RAW_CH = np.argmax(snrs)
        print(f"  Raw locked: {raw_eeg.ch_names[FIXED_RAW_CH]}")

    raw_selected = on_raw[:, FIXED_RAW_CH:FIXED_RAW_CH+1, :]
    raw_itpc_ts = compute_itpc_timecourse(raw_selected, gt_on, sfreq, SIGNAL_BAND_HZ)

    # --- SASS ---
    on_view = preprocessing.filter_signal(on_raw, sfreq, VIEW_BAND_HZ[0], VIEW_BAND_HZ[1])
    off_view = preprocessing.filter_signal(late_off_raw, sfreq, VIEW_BAND_HZ[0], VIEW_BAND_HZ[1])

    on_view_concat = on_view.transpose(1, 0, 2).reshape(n_channels, -1)
    off_view_concat = off_view.transpose(1, 0, 2).reshape(n_channels, -1)

    cov_a = np.cov(on_view_concat)
    cov_b = np.cov(off_view_concat)

    sass_source = sass.sass(on_view_concat, cov_a, cov_b)
    on_sass = sass_source.reshape(n_channels, n_epochs, -1).transpose(1, 0, 2)

    # Rank SASS channels by SNR
    sass_snrs = [
        compute_snr(on_sass[:, ch], sfreq, SIGNAL_BAND_HZ, VIEW_BAND_HZ)
        for ch in range(n_channels)
    ]
    sass_best_ch = np.argmax(sass_snrs)

    sass_selected = on_sass[:, sass_best_ch:sass_best_ch+1, :]
    sass_itpc_ts = compute_itpc_timecourse(sass_selected, gt_on, sfreq, SIGNAL_BAND_HZ)

    # --- SSD ---
    on_signal = preprocessing.filter_signal(on_raw, sfreq, SIGNAL_BAND_HZ[0], SIGNAL_BAND_HZ[1])
    on_view_for_ssd = preprocessing.filter_signal(on_raw, sfreq, VIEW_BAND_HZ[0], VIEW_BAND_HZ[1])

    on_signal_concat = on_signal.transpose(1, 0, 2).reshape(n_channels, -1)
    on_view_for_ssd_concat = on_view_for_ssd.transpose(1, 0, 2).reshape(n_channels, -1)

    cov_signal = np.cov(on_signal_concat)
    cov_view = np.cov(on_view_for_ssd_concat)

    evals, evecs = linalg.eigh(cov_signal, cov_view)
    sort_idx = np.argsort(evals)[::-1]
    evecs_sorted = evecs[:, sort_idx]

    ssd_components = evecs_sorted[:, :N_SSD_COMPONENTS].T @ on_signal_concat
    ssd_components = ssd_components.reshape(N_SSD_COMPONENTS, n_epochs, -1).transpose(1, 0, 2)

    # Rank SSD components by SNR
    ssd_snrs = [
        compute_snr(ssd_components[:, comp_idx], sfreq, SIGNAL_BAND_HZ, VIEW_BAND_HZ)
        for comp_idx in range(N_SSD_COMPONENTS)
    ]
    ssd_best_comp = np.argmax(ssd_snrs)

    ssd_selected = ssd_components[:, ssd_best_comp:ssd_best_comp+1, :]
    ssd_itpc_ts = compute_itpc_timecourse(ssd_selected, gt_on, sfreq, SIGNAL_BAND_HZ)

    itpc_timecourses[int_label] = {
        "raw": raw_itpc_ts,
        "sass": sass_itpc_ts,
        "ssd": ssd_itpc_ts,
    }

    print(f"  Raw: {raw_itpc_ts.mean():.3f} | SASS: {sass_itpc_ts.mean():.3f} | SSD: {ssd_itpc_ts.mean():.3f}")


# ============================================================
# 3) GENERATE FIGURE
# ============================================================
print("\nGenerating ITPC time course figure (5×3 grid)...")

fig, axes = plt.subplots(5, 3, figsize=(14, 12), constrained_layout=True)
fig.suptitle("ON ITPC Time Courses: Raw / SASS / SSD (SNR-selected)\nTime window: 0.3–1.5 s post-stimulation onset",
             fontsize=13, fontweight="bold")

time_s = np.arange(on_len) / sfreq + ON_WINDOW_S[0]

for row_idx, int_label in enumerate(INTENSITIES):
    itpc_data = itpc_timecourses[int_label]

    # Raw
    ax = axes[row_idx, 0]
    ax.plot(time_s, itpc_data["raw"], color=METHOD_COLORS["raw"], lw=2)
    ax.fill_between(time_s, 0, itpc_data["raw"], alpha=0.2, color=METHOD_COLORS["raw"])
    ax.set(ylim=(0, 1.05), ylabel="ITPC")
    if row_idx == 0:
        ax.set_title("Raw (SNR-selected)", fontweight="bold")
    if row_idx == 4:
        ax.set_xlabel("Time (s)")
    ax.text(0.02, 0.95, f"{int_label}\nmean={itpc_data['raw'].mean():.3f}",
            transform=ax.transAxes, va="top", ha="left", fontsize=9,
            bbox={"facecolor": "white", "alpha": 0.7, "pad": 3})
    ax.grid(True, alpha=0.2)

    # SASS
    ax = axes[row_idx, 1]
    ax.plot(time_s, itpc_data["sass"], color=METHOD_COLORS["sass"], lw=2)
    ax.fill_between(time_s, 0, itpc_data["sass"], alpha=0.2, color=METHOD_COLORS["sass"])
    ax.set(ylim=(0, 1.05))
    if row_idx == 0:
        ax.set_title("SASS (SNR-selected)", fontweight="bold")
    if row_idx == 4:
        ax.set_xlabel("Time (s)")
    ax.text(0.02, 0.95, f"{int_label}\nmean={itpc_data['sass'].mean():.3f}",
            transform=ax.transAxes, va="top", ha="left", fontsize=9,
            bbox={"facecolor": "white", "alpha": 0.7, "pad": 3})
    ax.grid(True, alpha=0.2)

    # SSD
    ax = axes[row_idx, 2]
    ax.plot(time_s, itpc_data["ssd"], color=METHOD_COLORS["ssd"], lw=2)
    ax.fill_between(time_s, 0, itpc_data["ssd"], alpha=0.2, color=METHOD_COLORS["ssd"])
    ax.set(ylim=(0, 1.05))
    if row_idx == 0:
        ax.set_title("SSD (SNR-selected)", fontweight="bold")
    if row_idx == 4:
        ax.set_xlabel("Time (s)")
    ax.text(0.02, 0.95, f"{int_label}\nmean={itpc_data['ssd'].mean():.3f}",
            transform=ax.transAxes, va="top", ha="left", fontsize=9,
            bbox={"facecolor": "white", "alpha": 0.7, "pad": 3})
    ax.grid(True, alpha=0.2)

fig.savefig(OUTPUT_PATH, dpi=220, bbox_inches="tight")
print(f"[DONE] Saved: {OUTPUT_PATH}")
plt.close(fig)

print("\nDone!")
