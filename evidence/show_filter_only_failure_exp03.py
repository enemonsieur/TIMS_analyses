"""show_filter_only_failure_exp03.py
Evidence that filtering alone cannot recover a clean signal from the double-
pulse dataset.

The slow post-pulse baseline drift behaves like a DC step. High-pass filters
respond to such steps with Gibbs ringing — the steeper the filter cutoff, the
worse the ringing. This script shows that problem across four HPF cutoffs.

Subplot rows (all on channel Cz):
  01  Raw epoch      — unfiltered reference
  02  HPF 0.1 Hz     — very gentle, minimal ringing
  03  HPF 0.5 Hz     — standard TESA/EEGLAB default
  04  HPF 1.0 Hz     — moderate
  05  HPF 8.0 Hz     — aggressive (used to suppress slow artifact)
"""

from pathlib import Path
import warnings

import mne
import numpy as np

import plot_helpers
import preprocessing


# ============================================================
# FIXED INPUTS  (edit only this block)
# ============================================================
STIM_VHDR_PATH = r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\TIMS_data_sync\pilot\doseresp\exp03-phantom-stim-pulse-10hz-GT10s-run03.vhdr"
OUTPUT_DIRECTORY = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\exp03_pipeline_failure_evidence")
OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)

FIXED_RETAINED_CHANNELS = ["Fp1", "F3", "FC5", "FC1", "C3", "C4", "FC6", "FC2", "F4", "F8", "Cz"]

# Epoch window: long enough to expose the pre-pulse drift.
EPOCH_TMIN_S = -2.0
EPOCH_TMAX_S =  1.0

# HPF cutoffs to compare.  Filter is applied to the continuous raw signal so
# the filter impulse response sees the full baseline drift between pulses.
HPF_CUTOFFS_HZ = [0.1, 0.5, 1.0, 8.0]

CHANNEL_TO_PLOT = "Cz"


# ============================================================
# 1) LOAD RAW + DETECT ACTUAL PULSE ONSETS FROM STIM CHANNEL
# ============================================================
with warnings.catch_warnings():
    warnings.filterwarnings("ignore", category=RuntimeWarning)
    raw = mne.io.read_raw_brainvision(STIM_VHDR_PATH, preload=True, verbose=False)

# Detect onsets from the stim channel BEFORE dropping it.
sfreq = float(raw.info["sfreq"])
stim_marker = raw.copy().pick(["stim"]).get_data()[0]
stim_onsets_samples, _, _, _ = preprocessing.detect_stim_onsets(
    stim_marker=stim_marker, sampling_rate_hz=sfreq
)
events = np.c_[
    stim_onsets_samples,
    np.zeros_like(stim_onsets_samples),
    np.ones_like(stim_onsets_samples),
].astype(int)

print(f"Detected {len(stim_onsets_samples)} pulses from stim channel.")
raw.pick(FIXED_RETAINED_CHANNELS)


# ============================================================
# 2) BUILD STAGE EPOCHS
# ============================================================

# Stage 1 — raw epoch, no filter.
epochs_raw = mne.Epochs(
    raw, events, event_id=1,
    tmin=EPOCH_TMIN_S, tmax=EPOCH_TMAX_S,
    baseline=None, preload=True, verbose=False,
)

# Stages 2–5 — one per HPF cutoff. Filter continuous raw first, then epoch,
# so the filter sees the DC baseline steps between pulses (not just the epoch).
stage_epochs = {"01  Raw (no filter)": epochs_raw}

for cutoff_hz in HPF_CUTOFFS_HZ:
    raw_filt = raw.copy().filter(l_freq=cutoff_hz, h_freq=None, verbose=False)
    label = f"{len(stage_epochs) + 1:02d}  HPF {cutoff_hz} Hz"
    stage_epochs[label] = mne.Epochs(
        raw_filt, events, event_id=1,
        tmin=EPOCH_TMIN_S, tmax=EPOCH_TMAX_S,
        baseline=None, preload=True, verbose=False,
    )


# ============================================================
# 3) SUBPLOT FIGURE — one row per stage, channel Cz
# ============================================================
plot_helpers.plot_cz_pipeline_steps(
    stage_epochs=stage_epochs,
    channel=CHANNEL_TO_PLOT,
    output_path=OUTPUT_DIRECTORY / "filter_steps_Cz.png",
)

print(f"Saved → {OUTPUT_DIRECTORY / 'filter_steps_Cz.png'}")
