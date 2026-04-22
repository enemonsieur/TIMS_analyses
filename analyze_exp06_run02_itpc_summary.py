"""Generate run02 ITPC summary figure: all methods on one plot, averaged across all channels.

QUESTION: How do raw/SASS/SSD methods compare when ranked by average ITPC (not PLV)?
Does ITPC-based ranking reveal artifact patterns more clearly than phase-locking value?

KEY METRIC CHANGE: Average ITPC per method/intensity (time-averaged, channel-averaged)
replaces PLV. ITPC is more robust to artifact because it measures phase coherence at each
time point, immune to the PLV bias where both GT and STIM lock to 12.45 Hz artifact.

OUTPUT FIGURES:
  - exp06_run02_on_raw_sass_ssd_itpc_summary.png (ITPC trend, all methods, no fill, single plot)
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
    "stim": "darkorange",
}

OUTPUT_PATH = OUTPUT_DIR / "exp06_run02_on_raw_sass_ssd_itpc_summary.png"


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


def compute_average_itpc(sig_epochs, ref_epochs, sfreq, signal_band):
    """
    Compute average ITPC across all channels and time points.

    sig_epochs: (n_epochs, n_channels, n_samples)
    ref_epochs: (n_epochs, n_samples)

    Returns: scalar ITPC value (0 to 1)
    """
    sig_filtered = preprocessing.filter_signal(sig_epochs, sfreq, signal_band[0], signal_band[1])
    ref_filtered = preprocessing.filter_signal(ref_epochs, sfreq, signal_band[0], signal_band[1])

    sig_phase = np.angle(signal.hilbert(sig_filtered, axis=-1))
    ref_phase = np.angle(signal.hilbert(ref_filtered, axis=-1))

    # ITPC per channel and time point
    n_channels = sig_epochs.shape[1] if sig_epochs.ndim == 3 else 1

    if sig_epochs.ndim == 3:
        # Multi-channel: average over channels first
        itpc_per_time = []
        for t in range(sig_filtered.shape[-1]):
            phase_diff = sig_phase[:, :, t] - ref_phase[:, t:t+1]
            itpc_at_t = np.abs(np.mean(np.exp(1j * phase_diff), axis=(0, 1)))
            itpc_per_time.append(itpc_at_t)
        avg_itpc = np.mean(itpc_per_time)
    else:
        # Single channel
        phase_diff = sig_phase - ref_phase
        avg_itpc = np.abs(np.mean(np.exp(1j * phase_diff)))

    return avg_itpc


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
# 2) ANALYSIS LOOP: SNR-BASED SELECTION, ITPC COMPUTATION
# ============================================================
summary_rows = []
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
    stim_on = preprocessing.extract_event_windows(stim_trace, events_on[:, 0], on_len)

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
        print(f"  Raw locked: {raw_eeg.ch_names[FIXED_RAW_CH]} (SNR={snrs[FIXED_RAW_CH]:.3f})")

    raw_selected = on_raw[:, FIXED_RAW_CH:FIXED_RAW_CH+1, :]
    raw_itpc = compute_average_itpc(raw_selected, gt_on, sfreq, SIGNAL_BAND_HZ)

    # --- SASS: SNR-select per intensity ---
    on_view = preprocessing.filter_signal(on_raw, sfreq, VIEW_BAND_HZ[0], VIEW_BAND_HZ[1])
    off_view = preprocessing.filter_signal(late_off_raw, sfreq, VIEW_BAND_HZ[0], VIEW_BAND_HZ[1])

    on_view_concat = on_view.transpose(1, 0, 2).reshape(n_channels, -1)
    off_view_concat = off_view.transpose(1, 0, 2).reshape(n_channels, -1)

    cov_a = np.cov(on_view_concat)
    cov_b = np.cov(off_view_concat)

    # SASS returns cleaned data in channel space as a single synthetic source
    sass_source = sass.sass(on_view_concat, cov_a, cov_b)  # Shape: (n_channels, n_samples)
    # Reshape to (n_epochs, n_channels, n_samples)
    on_sass = sass_source.reshape(n_channels, n_epochs, -1).transpose(1, 0, 2)

    # Now extract a single source component: use PCA-like approach to find the most signal-rich direction
    # Rank channels by SNR in signal band
    sass_snrs = [
        compute_snr(on_sass[:, ch], sfreq, SIGNAL_BAND_HZ, VIEW_BAND_HZ)
        for ch in range(n_channels)
    ]
    sass_best_ch = np.argmax(sass_snrs)

    # Use the best SASS-cleaned channel as the synthetic source
    sass_selected = on_sass[:, sass_best_ch:sass_best_ch+1, :]
    sass_itpc = compute_average_itpc(sass_selected, gt_on, sfreq, SIGNAL_BAND_HZ)

    # --- SSD: SNR-select per intensity ---
    on_signal = preprocessing.filter_signal(on_raw, sfreq, SIGNAL_BAND_HZ[0], SIGNAL_BAND_HZ[1])
    on_view_for_ssd = preprocessing.filter_signal(on_raw, sfreq, VIEW_BAND_HZ[0], VIEW_BAND_HZ[1])

    on_signal_concat = on_signal.transpose(1, 0, 2).reshape(n_channels, -1)
    on_view_for_ssd_concat = on_view_for_ssd.transpose(1, 0, 2).reshape(n_channels, -1)

    cov_signal = np.cov(on_signal_concat)
    cov_view = np.cov(on_view_for_ssd_concat)

    # Generalized eigendecomposition
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
    ssd_itpc = compute_average_itpc(ssd_selected, gt_on, sfreq, SIGNAL_BAND_HZ)

    # --- STIM vs GT (reference) ---
    stim_itpc = compute_average_itpc(stim_on.reshape(n_epochs, 1, -1), gt_on, sfreq, SIGNAL_BAND_HZ)

    summary_rows.append({
        "intensity_pct": int(int_label.rstrip("%")),
        "event_count": n_epochs,
        "raw_itpc": raw_itpc,
        "sass_itpc": sass_itpc,
        "ssd_itpc": ssd_itpc,
        "stim_itpc": stim_itpc,
    })

    print(f"  Raw ITPC: {raw_itpc:.3f} | SASS ITPC: {sass_itpc:.3f} | SSD ITPC: {ssd_itpc:.3f} | STIM ITPC: {stim_itpc:.3f}")


# ============================================================
# 3) GENERATE SUMMARY FIGURE
# ============================================================
print("\nGenerating ITPC summary figure...")

intensities_pct = np.array([row["intensity_pct"] for row in summary_rows])
raw_itpc_vals = np.array([row["raw_itpc"] for row in summary_rows])
sass_itpc_vals = np.array([row["sass_itpc"] for row in summary_rows])
ssd_itpc_vals = np.array([row["ssd_itpc"] for row in summary_rows])
stim_itpc_vals = np.array([row["stim_itpc"] for row in summary_rows])
event_counts = np.array([row["event_count"] for row in summary_rows])

# Simple line plot: all methods, no fill, single plot
fig, ax = plt.subplots(figsize=(10, 6), constrained_layout=True)

ax.plot(intensities_pct, raw_itpc_vals, color=METHOD_COLORS["raw"], lw=2.5,
        marker="o", ms=7, label="Raw (SNR-selected)", zorder=3)
ax.plot(intensities_pct, sass_itpc_vals, color=METHOD_COLORS["sass"], lw=2.5,
        marker="s", ms=7, label="SASS (SNR-selected)", zorder=3)
ax.plot(intensities_pct, ssd_itpc_vals, color=METHOD_COLORS["ssd"], lw=2.5,
        marker="^", ms=7, label="SSD (SNR-selected)", zorder=3)
ax.plot(intensities_pct, stim_itpc_vals, color=METHOD_COLORS["stim"], lw=2.0,
        marker="D", ms=6, label="GT vs STIM (reference)", zorder=2)

# Add event count labels
for x, max_y, n in zip(intensities_pct,
                        np.maximum(raw_itpc_vals, np.maximum(sass_itpc_vals, np.maximum(ssd_itpc_vals, stim_itpc_vals))),
                        event_counts):
    ax.text(x, min(0.99, float(max_y) + 0.03), f"n={n}", ha="center", va="bottom", fontsize=8)

ax.set(
    xlabel="Run02 stimulation block (%)",
    ylabel="Average ITPC (all channels, all time points)",
    xticks=intensities_pct,
    ylim=(0.0, 1.05),
    title="run02 ON ITPC: raw/SASS/SSD (SNR-based selection) vs GT-STIM reference\n(Channel-averaged, time-averaged, bias-free metric)",
)
ax.legend(frameon=False, loc="lower left", fontsize=10)
ax.grid(True, alpha=0.2, linestyle="--", linewidth=0.7)
ax.set_axisbelow(True)

fig.savefig(OUTPUT_PATH, dpi=220, bbox_inches="tight")
print(f"[DONE] Saved: {OUTPUT_PATH}")
plt.close(fig)

print("\nDone!")
