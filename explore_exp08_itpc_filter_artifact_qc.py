"""Plot whether EXP08 80 Hz and 13 Hz filters reshape one artremoved Oz epoch."""

import os
from pathlib import Path

os.environ["QT_API"] = "pyqt6"
os.environ["MPLBACKEND"] = "qtagg"
os.environ.setdefault("_MNE_FAKE_HOME_DIR", r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\.mne")

import matplotlib
matplotlib.use("QtAgg", force=True)
import matplotlib.pyplot as plt
import mne
import numpy as np
from scipy.signal import butter, sosfilt


# ============================================================
# CONFIG
# ============================================================

epoch_directory = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\EXP08")

intensity_pct = 100  # edit to 10, 20, ..., 100
channel_name = "Oz"  # edit to any retained EEG channel

display_window_s = (-0.5, 2.0)  # wide enough to see pulse-adjacent ringing and later drift
artifact_check_window_s = (-0.1, 0.8)  # ranks epochs by pulse-adjacent residual size
lowpass_hz = 80.0  # broad cleanup tested before the phase-band filter
signal_band_hz = (11.0, 14.0)  # less aggressive phase-view band than 12.5-13.5 Hz


# ============================================================
# 1) LOAD AND BUILD FILTER VIEWS
# ============================================================

# 1.1 Load one artremoved epoch set
epochs = mne.read_epochs(epoch_directory / f"exp08_epochs_{intensity_pct}pct_on_artremoved-epo.fif", preload=True, verbose=False)
times_s, sampling_rate_hz = np.asarray(epochs.times, dtype=float), float(epochs.info["sfreq"])

# 1.2 Extract and demean Oz per epoch
# Demeaning removes slow offset/ramp before comparing filter-induced shape changes.
raw_v = epochs.get_data(picks=[channel_name])[:, 0, :]
raw_v = raw_v - raw_v.mean(axis=1, keepdims=True)

# 1.3 Apply causal 80 Hz low-pass
# Causal filtering should not smear pulse energy backward before t=0.
lowpass_epochs = epochs.copy().pick([channel_name]).filter(
    None, lowpass_hz, method="iir", iir_params=dict(order=4, ftype="butter"), phase="forward", verbose=False
)
lowpass_v = lowpass_epochs.get_data()[:, 0, :]
lowpass_v = lowpass_v - lowpass_v.mean(axis=1, keepdims=True)

# 1.4 Apply simple causal 10-16 Hz phase-view filter
# Order 2 and wider passband reduce resonator ringing compared with 12.5-13.5 Hz.
phase_v = sosfilt(butter(2, signal_band_hz, btype="bandpass", fs=sampling_rate_hz, output="lfilter"), lowpass_v, axis=-1)
phase_v = phase_v - phase_v.mean(axis=1, keepdims=True)


# ============================================================
# 2) PICK ONE BAD EPOCH AND PLOT
# ============================================================

# 2.1 Pick worst residual epoch
# Select from the unfiltered demeaned trace so filtering cannot hide the artifact.
display_mask = (times_s >= display_window_s[0]) & (times_s <= display_window_s[1]); artifact_mask = (times_s >= artifact_check_window_s[0]) & (times_s <= artifact_check_window_s[1])
worst_epoch = int(np.argmax(np.max(np.abs(raw_v[:, artifact_mask]), axis=1)))

# 2.2 Plot worst epoch and mean trace
fig, axes = plt.subplots(1, 1, figsize=(11, 7), sharex=True)
axes.plot(times_s[display_mask], raw_v[worst_epoch, display_mask] * 1e6, label=" worst epoch")
axes.plot(times_s[display_mask], lowpass_v[worst_epoch, display_mask] * 1e6, label="LPass 80 Hz")
axes.plot(times_s[display_mask], phase_v[worst_epoch, display_mask] * 1e6, label=" +BPass")
#axes[0].set_title(f"{intensity_pct}% {channel_name}: worst residual epoch {worst_epoch}")

# axes[1].plot(times_s[display_mask], raw_v.mean(axis=0)[display_mask] * 1e6, label="mean demeaned artremoved")
# axes[1].plot(times_s[display_mask], lowpass_v.mean(axis=0)[display_mask] * 1e6, label="mean causal 80 Hz")
# axes[1].plot(times_s[display_mask], phase_v.mean(axis=0)[display_mask] * 1e6, label="mean 80 Hz + causal 10-16 Hz order2")
# axes[1].set_title(f"{intensity_pct}% {channel_name}: mean over epochs")

#for axis in axes:
axes.axvline(0.0, color="black", lw=0.8, ls="--")
axes.set_ylabel("uV")
axes.grid(alpha=0.2)
axes.legend(frameon=False)
axes.set_xlabel("Time relative to pulse (s)")
fig.tight_layout(); plt.show(); input("Inspect plot, then press Enter to finish...")
