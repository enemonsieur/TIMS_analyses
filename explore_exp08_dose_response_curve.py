"""Plot dose-response curve: max envelope amplitude vs. intensity (10–100%)."""

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import mne
import numpy as np
from scipy.signal import hilbert

# ============================================================
# CONFIG
# ============================================================

EXP08_DIR = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\EXP08")
INTENSITY_LEVELS = [0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90, 1.00]
INTENSITY_LABELS = ["10%", "20%", "30%", "40%", "50%", "60%", "70%", "80%", "90%", "100%"]
EPOCHS_PER_INTENSITY = 20

# Best channel detected in exp08_on_state_by_intensity.py
BEST_CHANNEL = "C3"

# Pre-post window definition
WINDOW_TMIN_S = -0.1
WINDOW_TMAX_S = 0.5

OUTPUT_PATH = EXP08_DIR / "exp08_dose_response_curve.png"

# ════════════════════════════════════════════════════════════════════════════
# PIPELINE OVERVIEW
# ════════════════════════════════════════════════════════════════════════════
#
# Epoch Files (exp08_epochs_*pct-epo.fif, 10 files)
# ├─ Load: each intensity file
# ├─ Extract: best channel (C3), compute mean timecourse
# ├─ Compute: envelope via Hilbert transform
# ├─ Measure: max envelope amplitude per intensity
# │
# └─ Plot: dose-response curve (intensity % vs. max envelope µV)
#    └─ OUTPUT: exp08_dose_response_curve.png

# ============================================================
# 1) LOAD FIRST EPOCH TO GET METADATA
# ============================================================

# ══ 1.1 Load 10% intensity epochs for sfreq ══
epochs_10pct_path = EXP08_DIR / "exp08_epochs_10pct-epo.fif"
epochs_10pct = mne.read_epochs(str(epochs_10pct_path), preload=True, verbose=False)
sfreq = float(epochs_10pct.info["sfreq"])
n_samples = len(epochs_10pct.times)

print(f"Sampling rate: {sfreq:.0f} Hz")
print(f"Samples per epoch: {n_samples}")

# ============================================================
# 2) EXTRACT MEAN ENVELOPE PER INTENSITY
# ============================================================

# ══ 2.1 Time axis for reference ══
time_s = np.arange(n_samples) / sfreq + WINDOW_TMIN_S

# ══ 2.2 Compute max envelope per intensity ══
max_envelopes = []

for intensity_level, label in zip(INTENSITY_LEVELS, INTENSITY_LABELS):
    intensity_pct = int(intensity_level * 100)

    # 2.2.1 Load intensity-specific epoch file
    epochs_path = EXP08_DIR / f"exp08_epochs_{intensity_pct}pct-epo.fif"
    epochs = mne.read_epochs(str(epochs_path), preload=True, verbose=False)

    # 2.2.2 Extract best channel and convert to µV
    data_uv = epochs.copy().pick([BEST_CHANNEL]).get_data()[:, 0, :] * 1e6
    # → (20, 600) µV

    # 2.2.3 Demean each epoch
    data_uv -= data_uv.mean(axis=1, keepdims=True)

    # 2.2.4 Compute mean timecourse
    mean_uv = data_uv.mean(axis=0)
    # → (600,) mean timecourse

    # 2.2.5 Compute envelope via Hilbert transform
    analytic = hilbert(mean_uv)
    envelope = np.abs(analytic)

    # 2.2.6 Find max envelope amplitude
    max_env = np.max(envelope)
    max_envelopes.append(max_env)

    print(f"  {label}: max envelope = {max_env:.2f} µV")

# ============================================================
# 3) PLOT DOSE-RESPONSE CURVE
# ============================================================

# ══ 3.1 Prepare intensity percentages for x-axis ══
intensity_pcts = [int(level * 100) for level in INTENSITY_LEVELS]

# ══ 3.2 Create figure ══
fig, ax = plt.subplots(figsize=(8, 5))

# ══ 3.3 Plot dose-response ══
ax.plot(intensity_pcts, max_envelopes, marker='o', markersize=8, linewidth=2.5, color='#08519c')
ax.scatter(intensity_pcts, max_envelopes, s=100, color='#08519c', zorder=5)

# ══ 3.4 Format axes ══
ax.set_xlabel("Intensity (%)", fontsize=12, fontweight="bold")
ax.set_ylabel("Max Envelope Amplitude (µV)", fontsize=12, fontweight="bold")
ax.set_title(f"EXP08 Dose-Response Curve: {BEST_CHANNEL} Channel", fontsize=13, fontweight="bold")
ax.grid(True, alpha=0.3)
ax.set_xlim(0, 105)

# ============================================================
# 4) SAVE & REPORT
# ============================================================

# ══ 4.1 Save figure ══
fig.tight_layout()
fig.savefig(OUTPUT_PATH, dpi=220, bbox_inches="tight")
plt.close()

# ══ 4.2 Print summary ══
print(f"\nDose-response summary:")
print(f"  10%:  {max_envelopes[0]:.2f} µV")
print(f"  100%: {max_envelopes[-1]:.2f} µV")
print(f"  Fold increase: {max_envelopes[-1] / max_envelopes[0]:.1f}×")
print(f"\nSaved: {OUTPUT_PATH.name}")
