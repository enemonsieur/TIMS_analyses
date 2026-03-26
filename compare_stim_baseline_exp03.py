"""compare_stim_baseline_exp03.py
Overlay processed stim vs baseline: time course, PSD, and ITPC on Cz.

Loads the pre-filtered stim epochs saved by final_postpulse_fixed_channels_exp03,
builds matched baseline epochs from scratch, and compares the two.
"""

from pathlib import Path
import warnings

import matplotlib.pyplot as plt
import mne
import numpy as np
from mne.time_frequency import psd_array_welch
from scipy.signal import hilbert


# ============================================================
# FIXED INPUTS
# ============================================================
STIM_EPOCHS_PATH = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\exp03_postpulse_fixed_channels\epochs_postpulse_hpf-epo.fif")
STIM_VHDR_PATH   = r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\TIMS_data_sync\pilot\doseresp\exp03-phantom-stim-pulse-10hz-GT10s-run03.vhdr"
BASE_VHDR_PATH   = r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\TIMS_data_sync\pilot\doseresp\exp03-phantom-baseline-10hz-GT-fullOFFstim-run01.vhdr"
OUTPUT_DIRECTORY  = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\exp03_postpulse_fixed_channels")
OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)

CHANNELS = ["Fp1", "F3", "FC5", "FC1", "C3", "C4", "FC6", "FC2", "F4", "F8", "Cz"]
HPF_HZ   = 1.0
CZ       = "Cz"
ITPC_BAND = (8, 12)
FIGURE_DPI = 220

# Same fixed-grid timing as final_postpulse script.
FIRST_PULSE_S   = 16.55
PULSE_INTERVAL_S = 10.0


# ============================================================
# 1) LOAD STIM EPOCHS (already processed)
# ============================================================
epochs_stim = mne.read_epochs(str(STIM_EPOCHS_PATH), verbose=False)
sfreq = epochs_stim.info["sfreq"]
tmin, tmax = epochs_stim.times[0], epochs_stim.times[-1]


# ============================================================
# 2) BUILD MATCHING BASELINE EPOCHS
# ============================================================
with warnings.catch_warnings():
    warnings.filterwarnings("ignore", category=RuntimeWarning)
    raw_base = mne.io.read_raw_brainvision(BASE_VHDR_PATH, preload=True, verbose=False)

raw_base_eeg = raw_base.copy().pick(CHANNELS).filter(l_freq=HPF_HZ, h_freq=None, verbose=False)
events_base = mne.make_fixed_length_events(raw_base, id=1, start=FIRST_PULSE_S,
                                           stop=float(raw_base.times[-1]), duration=PULSE_INTERVAL_S)
epochs_base = mne.Epochs(raw_base_eeg, events_base, event_id=1,
                         tmin=tmin, tmax=tmax, baseline=None, preload=True, verbose=False)


# ============================================================
# 3) GROUND TRUTH EPOCHS (for ITPC)
# ============================================================
with warnings.catch_warnings():
    warnings.filterwarnings("ignore", category=RuntimeWarning)
    raw_stim = mne.io.read_raw_brainvision(STIM_VHDR_PATH, preload=True, verbose=False)

events_stim = mne.make_fixed_length_events(raw_stim, id=1, start=FIRST_PULSE_S,
                                           stop=float(raw_stim.times[-1]), duration=PULSE_INTERVAL_S)

def _gt_epochs(raw_full, events):
    """Extract ground_truth epochs, HPF, same window."""
    r = raw_full.copy().pick(["ground_truth"])
    r.set_channel_types({"ground_truth": "eeg"})
    r.filter(l_freq=HPF_HZ, h_freq=None, verbose=False)
    return mne.Epochs(r, events, event_id=1, tmin=tmin, tmax=tmax,
                      baseline=None, preload=True, verbose=False)

gt_stim = _gt_epochs(raw_stim, events_stim)
gt_base = _gt_epochs(raw_base,  events_base)


# ============================================================
# 4) COMPUTE ITPC (Cz vs ground_truth, 8–12 Hz)
# ============================================================
def _itpc(epochs_eeg, epochs_gt, band):
    eeg = epochs_eeg.copy().pick([CZ]).filter(*band, verbose=False).get_data().squeeze()
    gt  = epochs_gt.copy().filter(*band, verbose=False).get_data().squeeze()
    n   = min(eeg.shape[0], gt.shape[0])
    phase_diff = np.angle(hilbert(eeg[:n], axis=-1)) - np.angle(hilbert(gt[:n], axis=-1))
    return np.abs(np.mean(np.exp(1j * phase_diff), axis=0)), n

itpc_stim, n_stim = _itpc(epochs_stim, gt_stim, ITPC_BAND)
itpc_base, n_base = _itpc(epochs_base, gt_base, ITPC_BAND)
chance = 1.0 / np.sqrt(min(n_stim, n_base))


# ============================================================
# 5) FIGURE — 3 subplots
# ============================================================
time_s = epochs_stim.times
fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(12, 10), constrained_layout=True)

# — Subplot 1: time course overlay —
stim_uv  = epochs_stim.get_data(picks=CZ).mean(0).squeeze() * 1e6
base_uv  = epochs_base.get_data(picks=CZ).mean(0).squeeze() * 1e6
ax1.plot(time_s, stim_uv, lw=1.2, color="steelblue", label="Stim (processed)")
ax1.plot(time_s, base_uv, lw=1.2, color="gray",      label="Baseline")
ax1.set(title=f"Trial-averaged time course — {CZ}", xlabel="Time (s)", ylabel="µV")
ax1.legend(); ax1.grid(alpha=0.25)

# — Subplot 2: PSD 5–20 Hz —
n_fft = int(sfreq)  # 1000-pt FFT → 1 Hz resolution
psd_s, freqs = psd_array_welch(epochs_stim.get_data(picks=CZ).squeeze(), sfreq, fmin=5, fmax=40, n_fft=n_fft, verbose=False)
psd_b, _     = psd_array_welch(epochs_base.get_data(picks=CZ).squeeze(), sfreq, fmin=5, fmax=40, n_fft=n_fft, verbose=False)
ax2.plot(freqs, 10*np.log10(psd_s.mean(0)+1e-30), lw=1.5, color="steelblue", label="Stim (processed)")
ax2.plot(freqs, 10*np.log10(psd_b.mean(0)+1e-30), lw=1.5, color="gray",      label="Baseline")
ax2.set(title=f"PSD 5–20 Hz — {CZ}", xlabel="Frequency (Hz)", ylabel="dB")
ax2.legend(); ax2.grid(alpha=0.25)

# — Subplot 3: ITPC —
ax3.plot(time_s, itpc_stim, lw=1.5, color="steelblue", label="Stim vs ground_truth")
ax3.plot(time_s, itpc_base, lw=1.5, color="gray",      label="Baseline vs ground_truth")
ax3.axhline(chance, color="red", ls=":", lw=1, label=f"Chance (1/√n ≈ {chance:.2f})")
ax3.set(title=f"ITPC: {CZ} vs ground_truth ({ITPC_BAND[0]}–{ITPC_BAND[1]} Hz)",
        xlabel="Time (s)", ylabel="ITPC", ylim=(0, 1))
ax3.legend(); ax3.grid(alpha=0.25)

out = OUTPUT_DIRECTORY / "stim_vs_baseline_recovery_Cz.png"
fig.savefig(out, dpi=FIGURE_DPI)
plt.show()
print(f"Saved → {out}")
