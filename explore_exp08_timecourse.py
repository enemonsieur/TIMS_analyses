"""Plot mean timecourse ±1s around stimulus for 5 channels."""

import matplotlib
import matplotlib.pyplot as plt
import mne
import numpy as np
from pathlib import Path

# ══ CONFIG ══
INTENSITY = 50  # % — modify
N_CH = 5
EPOCH_DIR = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\EXP08")

# ════════════════════════════════════════════════════════════════════════════
# LOAD & PLOT
# ════════════════════════════════════════════════════════════════════════════

epochs = mne.read_epochs(
    str(EPOCH_DIR / f"exp08_epochs_{INTENSITY}pct_on-epo.fif"),
    preload=True, verbose=False
)

data_mean = np.mean(epochs.get_data()[:, :N_CH, :], axis=0)

fig, ax = plt.subplots(figsize=(10, 4))
for i, ch_name in enumerate(epochs.ch_names[:N_CH]):
    ax.plot(epochs.times, data_mean[i], label=ch_name, lw=1)
ax.axvline(0, color="red", linestyle="--", alpha=0.5, label="Stim")
ax.set(xlabel="Time (s)", ylabel="µV", title=f"ON-window ({INTENSITY}%)")
ax.legend(ncol=2, fontsize=9)
ax.grid(alpha=0.2)
fig.tight_layout()
fig.savefig(EPOCH_DIR / f"timecourse_{INTENSITY}pct.png", dpi=150)
plt.close()
print("✓ Saved")
