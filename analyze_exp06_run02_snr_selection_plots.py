"""Generate run02 PLV/ITPC summary figures using SNR-based component selection.

QUESTION: How do raw/SASS/SSD methods compare when selected by signal-to-noise ratio
instead of phase locking? Do SNR-selected components reveal clearer artifact patterns?

KEY CHANGE: Components selected by SNR (signal-band power / broadband power) rather than
PLV (phase locking value). Raw channel locked at 10%, SASS/SSD adapt per intensity.

OUTPUT FIGURES:
  - exp06_run02_on_raw_sass_ssd_plv_summary.png (PLV trend across intensities)
  - exp06_run02_on_raw_sass_ssd_phase_grid.png (Phase distributions per method/intensity)
  - exp06_run02_sass_itpc_per_intensity.png (ITPC time courses per intensity)
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

SUMMARY_PATH = OUTPUT_DIR / "exp06_run02_on_raw_sass_ssd_plv_summary.png"
PHASE_GRID_PATH = OUTPUT_DIR / "exp06_run02_on_raw_sass_ssd_phase_grid.png"
ITPC_PATH = OUTPUT_DIR / "exp06_run02_sass_itpc_per_intensity.png"
MANIFEST_PATH = OUTPUT_DIR / "exp06_run02_snr_selection_manifest.txt"


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
# 2) ANALYSIS LOOP: SNR-BASED SELECTION
# ============================================================
summary_rows = []
FIXED_RAW_CH = None
sass_itpc_per_intensity = {}

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

    raw_selected = on_raw[:, FIXED_RAW_CH, :]
    raw_metrics = preprocessing.compute_epoch_plv_summary(raw_selected, gt_on, sfreq, SIGNAL_BAND_HZ, TARGET_HZ)

    # --- SASS: SNR-select per intensity ---
    on_view = preprocessing.filter_signal(on_raw, sfreq, VIEW_BAND_HZ[0], VIEW_BAND_HZ[1])
    off_view = preprocessing.filter_signal(late_off_raw, sfreq, VIEW_BAND_HZ[0], VIEW_BAND_HZ[1])

    on_view_concat = on_view.transpose(1, 0, 2).reshape(n_channels, -1)
    off_view_concat = off_view.transpose(1, 0, 2).reshape(n_channels, -1)

    cov_a = np.cov(on_view_concat)
    cov_b = np.cov(off_view_concat)
    sass_clean = sass.sass(on_view_concat, cov_a, cov_b)
    on_sass = sass_clean.reshape(n_channels, n_epochs, -1).transpose(1, 0, 2)

    # SASS ITPC computation (for ITPC per intensity figure)
    sass_filtered = preprocessing.filter_signal(on_sass, sfreq, SIGNAL_BAND_HZ[0], SIGNAL_BAND_HZ[1])
    gt_filtered = preprocessing.filter_signal(gt_on, sfreq, SIGNAL_BAND_HZ[0], SIGNAL_BAND_HZ[1])

    sass_phase = np.angle(signal.hilbert(sass_filtered, axis=-1))
    gt_phase = np.angle(signal.hilbert(gt_filtered, axis=-1))

    # Average ITPC across channels
    itpc_per_channel = []
    for ch in range(n_channels):
        phase_diff = sass_phase[:, ch, :] - gt_phase
        itpc_ts = np.abs(np.mean(np.exp(1j * phase_diff), axis=0))
        itpc_per_channel.append(itpc_ts)

    itpc_mean = np.mean(itpc_per_channel, axis=0)
    sass_itpc_per_intensity[int_label] = itpc_mean

    # Select best SASS channel by SNR
    sass_snrs = [compute_snr(on_sass[:, ch], sfreq, SIGNAL_BAND_HZ, VIEW_BAND_HZ) for ch in range(n_channels)]
    sass_ch = np.argmax(sass_snrs)
    sass_selected = on_sass[:, sass_ch, :]
    sass_metrics = preprocessing.compute_epoch_plv_summary(sass_selected, gt_on, sfreq, SIGNAL_BAND_HZ, TARGET_HZ)

    print(f"  SASS selected: {raw_eeg.ch_names[sass_ch]} (SNR={sass_snrs[sass_ch]:.3f})")

    # --- SSD: SNR-select per intensity ---
    on_sig = preprocessing.filter_signal(on_raw, sfreq, SIGNAL_BAND_HZ[0], SIGNAL_BAND_HZ[1])
    on_view_ssd = preprocessing.filter_signal(on_raw, sfreq, VIEW_BAND_HZ[0], VIEW_BAND_HZ[1])

    on_sig_concat = on_sig.transpose(1, 0, 2).reshape(n_channels, -1)
    on_view_ssd_concat = on_view_ssd.transpose(1, 0, 2).reshape(n_channels, -1)

    cov_sig = np.cov(on_sig_concat)
    cov_view = np.cov(on_view_ssd_concat)

    try:
        evals, evecs = linalg.eigh(cov_sig, cov_view)
        evals = np.maximum(evals, 0)
        idx_sort = np.argsort(evals)[::-1]
        evecs = evecs[:, idx_sort]
    except:
        evecs = np.linalg.svd(cov_sig)[0]

    ssd_comps = []
    ssd_snrs = []
    for comp_idx in range(min(N_SSD_COMPONENTS, n_channels)):
        comp_epochs = np.array([on_raw[e].T.dot(evecs[:, comp_idx]) for e in range(n_epochs)])
        ssd_comps.append(comp_epochs)
        ssd_snrs.append(compute_snr(comp_epochs, sfreq, SIGNAL_BAND_HZ, VIEW_BAND_HZ))

    ssd_comp_idx = np.argmax(ssd_snrs)
    ssd_selected = np.asarray(ssd_comps[ssd_comp_idx], dtype=float)
    ssd_metrics = preprocessing.compute_epoch_plv_summary(ssd_selected, gt_on, sfreq, SIGNAL_BAND_HZ, TARGET_HZ)

    print(f"  SSD selected: Component {ssd_comp_idx} (SNR={ssd_snrs[ssd_comp_idx]:.3f})")

    # --- STIM vs GT reference ---
    stim_metrics = preprocessing.compute_epoch_plv_summary(stim_on, gt_on, sfreq, SIGNAL_BAND_HZ, TARGET_HZ)

    # Compute peak frequencies
    raw_sig = preprocessing.filter_signal(raw_selected, sfreq, VIEW_BAND_HZ[0], VIEW_BAND_HZ[1])
    raw_psd = np.mean(np.abs(np.fft.rfft(raw_sig, axis=-1)) ** 2, axis=0)
    freqs = np.fft.rfftfreq(raw_sig.shape[-1], 1 / sfreq)
    raw_peak_hz = freqs[np.argmax(raw_psd)]

    sass_sig = preprocessing.filter_signal(sass_selected, sfreq, VIEW_BAND_HZ[0], VIEW_BAND_HZ[1])
    sass_psd = np.mean(np.abs(np.fft.rfft(sass_sig, axis=-1)) ** 2, axis=0)
    sass_peak_hz = freqs[np.argmax(sass_psd)]

    ssd_sig = preprocessing.filter_signal(ssd_selected, sfreq, VIEW_BAND_HZ[0], VIEW_BAND_HZ[1])
    ssd_psd = np.mean(np.abs(np.fft.rfft(ssd_sig, axis=-1)) ** 2, axis=0)
    ssd_peak_hz = freqs[np.argmax(ssd_psd)]

    summary_rows.append({
        "label": int_label,
        "intensity_pct": int(int_label.replace("%", "")),
        "event_count": n_epochs,
        "raw_ch_name": raw_eeg.ch_names[FIXED_RAW_CH],
        "raw_ch_idx": FIXED_RAW_CH,
        "raw_peak_hz": raw_peak_hz,
        "raw_plv": raw_metrics["plv"],
        "raw_p_value": raw_metrics.get("p_value", 1.0),
        "raw_phase_samples": raw_metrics.get("phase_samples", np.array([])),
        "sass_ch_name": raw_eeg.ch_names[sass_ch],
        "sass_ch_idx": sass_ch,
        "sass_peak_hz": sass_peak_hz,
        "sass_plv": sass_metrics["plv"],
        "sass_p_value": sass_metrics.get("p_value", 1.0),
        "sass_phase_samples": sass_metrics.get("phase_samples", np.array([])),
        "ssd_comp_idx": ssd_comp_idx,
        "ssd_peak_hz": ssd_peak_hz,
        "ssd_plv": ssd_metrics["plv"],
        "ssd_p_value": ssd_metrics.get("p_value", 1.0),
        "ssd_phase_samples": ssd_metrics.get("phase_samples", np.array([])),
        "stim_plv": stim_metrics["plv"],
        "stim_p_value": stim_metrics.get("p_value", 1.0),
        "stim_phase_samples": stim_metrics.get("phase_samples", np.array([])),
    })


# ============================================================
# 3) GENERATE FIGURES
# ============================================================
print("\nGenerating figures...")

# Figure 1: PLV Summary across intensities
intensities_pct = np.array([row["intensity_pct"] for row in summary_rows])
raw_plv = np.array([row["raw_plv"] for row in summary_rows])
sass_plv = np.array([row["sass_plv"] for row in summary_rows])
ssd_plv = np.array([row["ssd_plv"] for row in summary_rows])
stim_plv = np.array([row["stim_plv"] for row in summary_rows])

plot_helpers.save_plv_method_summary_figure(
    x_values=intensities_pct,
    event_counts=np.array([row["event_count"] for row in summary_rows]),
    method_series=[
        {"label": "Raw (SNR-selected)", "values": raw_plv, "color": METHOD_COLORS["raw"], "linewidth": 2.0},
        {"label": "SASS (SNR-selected)", "values": sass_plv, "color": METHOD_COLORS["sass"], "linewidth": 2.2},
        {"label": "SSD (SNR-selected)", "values": ssd_plv, "color": METHOD_COLORS["ssd"], "linewidth": 2.2},
        {"label": "GT vs STIM", "values": stim_plv, "color": METHOD_COLORS["stim"], "linewidth": 1.8},
    ],
    output_path=SUMMARY_PATH,
    title="run02 ON PLV: raw/SASS/SSD (SNR-based selection) vs GT-STIM reference",
)
print(f"Saved: {SUMMARY_PATH}")

# Figure 2: Phase grid (polar histograms)
phase_grid_rows = []
for row in summary_rows:
    phase_grid_rows.append([
        {
            "title": f"{row['label']} Raw {row['raw_ch_name']}\nPLV={row['raw_plv']:.2f}",
            "phases": row["raw_phase_samples"] if row["raw_phase_samples"].size else np.array([0.0]),
            "plv": row["raw_plv"],
            "p_value": row["raw_p_value"],
            "color": METHOD_COLORS["raw"],
        },
        {
            "title": f"{row['label']} SASS {row['sass_ch_name']}\nPLV={row['sass_plv']:.2f}",
            "phases": row["sass_phase_samples"],
            "plv": row["sass_plv"],
            "p_value": row["sass_p_value"],
            "color": METHOD_COLORS["sass"],
        },
        {
            "title": f"{row['label']} SSD comp{row['ssd_comp_idx']}\nPLV={row['ssd_plv']:.2f}",
            "phases": row["ssd_phase_samples"],
            "plv": row["ssd_plv"],
            "p_value": row["ssd_p_value"],
            "color": METHOD_COLORS["ssd"],
        },
        {
            "title": f"{row['label']} STIM vs GT\nPLV={row['stim_plv']:.2f}",
            "phases": row["stim_phase_samples"],
            "plv": row["stim_plv"],
            "p_value": row["stim_p_value"],
            "color": METHOD_COLORS["stim"],
        },
    ])

plot_helpers.save_phase_histogram_grid(
    phase_grid_rows=phase_grid_rows,
    output_path=PHASE_GRID_PATH,
    title="Phase Distributions: SNR-based component selection",
)
print(f"Saved: {PHASE_GRID_PATH}")

# Figure 3: SASS ITPC per intensity
fig, axes = plt.subplots(5, 1, figsize=(10, 10))
fig.suptitle("SASS ITPC vs GT (SNR-selected channel, time course per intensity)",
             fontsize=12, fontweight="bold")

colors = ["#c6dbef", "#9ecae1", "#6baed6", "#3182bd", "#08519c"]
time_s = np.arange(on_len) / sfreq

for idx, (int_label, ax) in enumerate(zip(INTENSITIES, axes)):
    itpc_ts = sass_itpc_per_intensity[int_label]
    mean_itpc = np.mean(itpc_ts)

    ax.plot(time_s, itpc_ts, color=colors[idx], linewidth=2, label=f"ITPC = {mean_itpc:.3f}")
    ax.fill_between(time_s, 0, itpc_ts, alpha=0.3, color=colors[idx])
    ax.set_ylim([0, 1])
    ax.set_ylabel("ITPC", fontsize=9)
    ax.set_title(f"{int_label}: SASS phase locking to GT", fontsize=10)
    ax.legend(loc="upper right", fontsize=8)
    ax.grid(True, alpha=0.3)

axes[-1].set_xlabel("Time (s)", fontsize=9)
plt.tight_layout()
plt.savefig(ITPC_PATH, dpi=150, bbox_inches="tight")
plt.close()
print(f"Saved: {ITPC_PATH}")


# ============================================================
# 4) SAVE MANIFEST
# ============================================================
manifest = "SNR-BASED COMPONENT SELECTION ANALYSIS MANIFEST\n"
manifest += "="*70 + "\n"
manifest += f"Data: {STIM_VHDR}\n"
manifest += f"Selection method: SNR = power(12.45 Hz ± 0.5 Hz) / power(4-20 Hz)\n"
manifest += f"Raw: Locked at 10% ({summary_rows[0]['raw_ch_name']}), applied to all intensities\n"
manifest += f"SASS/SSD: Adaptive per intensity\n\n"

manifest += "Intensity | Raw PLV | SASS PLV | SSD PLV | STIM PLV\n"
manifest += "-"*70 + "\n"
for row in summary_rows:
    manifest += f"{row['label']:10} | {row['raw_plv']:7.4f} | {row['sass_plv']:8.4f} | {row['ssd_plv']:7.4f} | {row['stim_plv']:8.4f}\n"

manifest += "\n" + "="*70 + "\nComponent selections:\n"
for row in summary_rows:
    manifest += f"{row['label']}: Raw={row['raw_ch_name']}, SASS={row['sass_ch_name']}, SSD=comp{row['ssd_comp_idx']}\n"

with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
    f.write(manifest)

print(f"Saved: {MANIFEST_PATH}")
print("\nDone!")
