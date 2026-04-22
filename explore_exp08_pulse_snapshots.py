"""Plot raw pulse snapshots (first epoch) for each intensity level (10–100%), single channel."""

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import mne
import numpy as np

# ============================================================
# CONFIG
# ============================================================

EXP08_DIR = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\EXP08")
INTENSITY_LEVELS = [0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90, 1.00]
INTENSITY_LABELS = ["10%", "20%", "30%", "40%", "50%", "60%", "70%", "80%", "90%", "100%"]

CHANNEL = "C3"
WINDOW_TMIN_S = -0.1
WINDOW_TMAX_S = 0.5

OUTPUT_PATH = EXP08_DIR / "exp08_pulse_snapshots_c3.png"

# ════════════════════════════════════════════════════════════════════════════
# PIPELINE OVERVIEW
# ════════════════════════════════════════════════════════════════════════════
#
# Epoch Files (exp08_epochs_*pct-epo.fif, 10 files)
# ├─ Load: each intensity file
# ├─ Extract: first epoch (first pulse), C3 channel only
# ├─ Demean: per-channel baseline
# │
# └─ Visualize: 10 stacked subplots (raw timecourse, one per intensity)
#    └─ OUTPUT: exp08_pulse_snapshots_c3.png

# ============================================================
# 1) LOAD FIRST EPOCH, GET METADATA
# ============================================================

# ══ 1.1 Load 10% epochs ══
epochs_10pct_path = EXP08_DIR / "exp08_epochs_10pct-epo.fif"
epochs_10pct = mne.read_epochs(str(epochs_10pct_path), preload=True, verbose=False)
sfreq = float(epochs_10pct.info["sfreq"])
n_samples = len(epochs_10pct.times)
time_s = np.arange(n_samples) / sfreq + WINDOW_TMIN_S

print(f"Sampling rate: {sfreq:.0f} Hz")
print(f"Channel: {CHANNEL}")
print(f"Window: {WINDOW_TMIN_S:.2f}–{WINDOW_TMAX_S:.2f} s ({n_samples} samples)")

# ============================================================
# 2) EXTRACT FIRST PULSE PER INTENSITY
# ============================================================

panel_rows = []

for i, (intensity_level, label) in enumerate(zip(INTENSITY_LEVELS, INTENSITY_LABELS)):
    intensity_pct = int(intensity_level * 100)

    # 2.1 Load intensity-specific epoch file
    epochs_path = EXP08_DIR / f"exp08_epochs_{intensity_pct}pct-epo.fif"
    epochs = mne.read_epochs(str(epochs_path), preload=True, verbose=False)

    # 2.2 Extract first epoch, C3 channel, convert to µV
    data_uv = epochs[0].copy().pick([CHANNEL]).get_data().squeeze() * 1e6
    # → (600,) µV

    # 2.3 Demean
    data_uv -= data_uv.mean()

    # 2.4 Store
    panel_rows.append({
        "label": label,
        "data_uv": data_uv,
    })

    print(f"  {label}: {data_uv.min():.1f}–{data_uv.max():.1f} µV")

# ============================================================
# 3) PLOT 10 STACKED SUBPLOTS
# ============================================================

# ══ 3.1 Create figure ══
fig, axes = plt.subplots(len(panel_rows), 1, figsize=(10, 16),
                         constrained_layout=True, sharex=True, sharey=False)

# ══ 3.2 Plot each intensity ══
for ax, row in zip(np.atleast_1d(axes), panel_rows):
    ax.plot(time_s, row["data_uv"], color='#08519c', linewidth=1.0)
    ax.set_ylabel(f"{CHANNEL} (µV)", fontsize=10)
    ax.set_title(row["label"], fontsize=11)
    ax.grid(True, alpha=0.3)

# ══ 3.3 Set shared labels ══
axes = np.atleast_1d(axes)
axes[-1].set_xlabel("Time within ON window (s)")
fig.suptitle(f"EXP08 Raw Pulse Snapshots: {CHANNEL} (first pulse per intensity)", fontsize=12)

# ============================================================
# 4) SAVE & REPORT
# ============================================================

fig.savefig(OUTPUT_PATH, dpi=220)
plt.close()

print(f"\nSaved: {OUTPUT_PATH.name}")
