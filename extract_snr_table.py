"""Extract SNR values for selected components across intensities and show in table."""

import os
from pathlib import Path
import warnings
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

INTENSITIES = ["10%", "20%", "30%", "40%", "50%"]
BLOCK_CYCLES = 20
ON_WINDOW_S = (0.3, 1.5)
LATE_OFF_WINDOW_S = (1.5, 3.2)
EXCLUDED_CH = {"TP9", "Fp1", "TP10"}

TARGET_HZ = 12.451172
SIGNAL_BAND_HZ = (TARGET_HZ - 0.5, TARGET_HZ + 0.5)
VIEW_BAND_HZ = (4.0, 20.0)
N_SSD_COMPONENTS = 6


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
# LOAD & PREPARE
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

block_onsets, block_offsets = preprocessing.detect_stim_blocks(stim_trace, sfreq, threshold_fraction=0.08)
on_start_shift = int(round(ON_WINDOW_S[0] * sfreq))
on_len = int(round((ON_WINDOW_S[1] - ON_WINDOW_S[0]) * sfreq))
late_off_len = int(round((LATE_OFF_WINDOW_S[1] - LATE_OFF_WINDOW_S[0]) * sfreq))


# ============================================================
# ANALYSIS LOOP: COLLECT SNR VALUES
# ============================================================
snr_table = []
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
        raw_snr = snrs[FIXED_RAW_CH]
        print(f"  Raw locked: {raw_eeg.ch_names[FIXED_RAW_CH]} (SNR={raw_snr:.4f})")
    else:
        # Recompute SNR for the same fixed channel at other intensities
        raw_snr = compute_snr(on_raw[:, FIXED_RAW_CH], sfreq, SIGNAL_BAND_HZ, VIEW_BAND_HZ)
        print(f"  Raw (fixed): {raw_eeg.ch_names[FIXED_RAW_CH]} (SNR={raw_snr:.4f})")

    # --- SASS: SNR-select per intensity ---
    on_view = preprocessing.filter_signal(on_raw, sfreq, VIEW_BAND_HZ[0], VIEW_BAND_HZ[1])
    off_view = preprocessing.filter_signal(late_off_raw, sfreq, VIEW_BAND_HZ[0], VIEW_BAND_HZ[1])

    on_view_concat = on_view.transpose(1, 0, 2).reshape(n_channels, -1)
    off_view_concat = off_view.transpose(1, 0, 2).reshape(n_channels, -1)

    cov_a = np.cov(on_view_concat)
    cov_b = np.cov(off_view_concat)
    sass_clean = sass.sass(on_view_concat, cov_a, cov_b)
    on_sass = sass_clean.reshape(n_channels, n_epochs, -1).transpose(1, 0, 2)

    # Select best SASS channel by SNR
    sass_snrs = [compute_snr(on_sass[:, ch], sfreq, SIGNAL_BAND_HZ, VIEW_BAND_HZ) for ch in range(n_channels)]
    sass_ch = np.argmax(sass_snrs)
    sass_snr = sass_snrs[sass_ch]
    print(f"  SASS selected: {raw_eeg.ch_names[sass_ch]} (SNR={sass_snr:.4f})")

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
    ssd_snr = ssd_snrs[ssd_comp_idx]
    print(f"  SSD selected: Component {ssd_comp_idx} (SNR={ssd_snr:.4f})")

    # Also show all SSD component SNRs
    print(f"    All SSD components SNRs: {[f'{s:.4f}' for s in ssd_snrs]}")

    # Store row
    snr_table.append({
        "Intensity": int_label,
        "Raw SNR": raw_snr,
        "SASS SNR": sass_snr,
        "SSD SNR": ssd_snr,
    })


# ============================================================
# PRINT TABLE
# ============================================================
print("\n" + "="*70)
print("SNR TABLE: Selected Components Across Intensities")
print("="*70)
print(f"{'Intensity':<12} {'Raw SNR':<15} {'SASS SNR':<15} {'SSD SNR':<15}")
print("-"*70)
for row in snr_table:
    print(f"{row['Intensity']:<12} {row['Raw SNR']:<15.4f} {row['SASS SNR']:<15.4f} {row['SSD SNR']:<15.4f}")
print("="*70)

# Save to text file
output_txt = OUTPUT_DIR / "exp06_snr_selected_components.txt"
with open(output_txt, "w") as f:
    f.write("SNR TABLE: Selected Components Across Intensities\n")
    f.write("="*70 + "\n")
    f.write(f"{'Intensity':<12} {'Raw SNR':<15} {'SASS SNR':<15} {'SSD SNR':<15}\n")
    f.write("-"*70 + "\n")
    for row in snr_table:
        f.write(f"{row['Intensity']:<12} {row['Raw SNR']:<15.4f} {row['SASS SNR']:<15.4f} {row['SSD SNR']:<15.4f}\n")
    f.write("="*70 + "\n")

print(f"\nSaved: {output_txt}")
