"""Raw Oz pulse shape at 100% — single trial + average."""

from pathlib import Path
import matplotlib.pyplot as plt
import mne

# ============================================================
# CONFIG
# ============================================================

EPOCH_DIR   = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\EXP08")
CROP_WINDOW = (-0.5, 0.3)
CHANNEL     = "stim"
PCT         = 100

# ============================================================
# PLOT
# ============================================================

epochs = mne.read_epochs(
    str(EPOCH_DIR / f"exp08_stim_epochs_{PCT}pct_on-epo.fif"),
    preload=True, verbose=False,
)
epochs.crop(*CROP_WINDOW)
data_uv = epochs.get_data()[:, 0, :] * 1e6   # -> (n_epochs, n_samples) uV (stim channel)
time_s  = epochs.times

fig, axes = plt.subplots(2, 1, figsize=(10, 7), sharex=True)

axes[0].plot(time_s, data_uv[0], color="steelblue", linewidth=0.8)
axes[0].set_title("Single trial (epoch 0)", fontsize=11)

axes[1].plot(time_s, data_uv.mean(axis=0), color="navy", linewidth=1.2)
axes[1].set_title(f"Mean across {len(data_uv)} epochs", fontsize=11)

for ax in axes:
    ax.axvline(0, color="gray", linestyle="--", linewidth=0.8)
    ax.set_ylabel(f"{CHANNEL} (uV)")
    ax.grid(True, alpha=0.2)

axes[-1].set_xlabel("Time relative to pulse (s)")
fig.suptitle(f"EXP08 — {CHANNEL} raw pulse shape at {PCT}%", fontsize=12)
fig.tight_layout()
plt.show()
