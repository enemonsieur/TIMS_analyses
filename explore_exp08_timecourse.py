"""Plot mean timecourse ±1s around stimulus for single channel."""

import matplotlib
import matplotlib.pyplot as plt
import mne
import numpy as np
from pathlib import Path
# ══ CONFIG ══
INTENSITY = 50  # % — modify
CHANNEL = "C3"  # modify: "C3", "Cz", "Oz", etc.
EPOCH_DIR = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\EXP08")

# ════════════════════════════════════════════════════════════════════════════
# LOAD & PLOT
# ════════════════════════════════════════════════════════════════════════════

epochs = mne.read_epochs(
    str(EPOCH_DIR / f"exp08_epochs_{INTENSITY}pct_on-epo.fif"),
    preload=True, verbose=False
)

# ── Gentle high-pass filter (0.5 Hz) ──
epochs.filter(l_freq=0.5, h_freq=None, verbose=False)

ch_idx = epochs.ch_names.index(CHANNEL)
data = epochs.get_data()[:, ch_idx, :]  # (n_epochs, n_samples)

# ── Demean per epoch ──
data = data - np.mean(data, axis=1, keepdims=True)

data_mean = np.mean(data, axis=0)*1e6  # convert to µV

fig, ax = plt.subplots(figsize=(10, 4))
ax.plot(epochs.times, data_mean, label=CHANNEL, lw=1.5)
ax.axvline(0, color="red", linestyle="--", alpha=0.5, label="Stim")
ax.set(xlabel="Time (s)", ylabel="µV", title=f"{CHANNEL} ON-window ({INTENSITY}%)")
ax.legend(fontsize=9)
ax.set_ylim(-30, 30)
#ax.grid(alpha=0.2)
fig.tight_layout()
fig.savefig(EPOCH_DIR / f"timecourse_{INTENSITY}pct.png", dpi=150)
plt.close()
print("Saved: timecourse_%dpct.png" % INTENSITY)
