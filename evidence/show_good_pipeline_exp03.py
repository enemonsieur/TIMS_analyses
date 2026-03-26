"""show_good_pipeline_exp03.py
Step-by-step view of the pipeline that successfully recovers the ERP.

The key insight shown here: cropping to the post-pulse window (Stage 3)
discards the unstable pre-pulse context entirely — no ICA needed.
HPF applied after crop operates only on clean, stationary signal.

Subplot rows (all on channel Cz):
  01  Raw epoch (−2 to +1 s)          — full epoch showing the dual-pulse structure
  02  Zero stim gap + dual demean       — −1 to 0 s zeroed, pre/post centred to 0 µV
  03  Crop to post-pulse (0.08–1.0 s)  — pre-pulse context discarded entirely
  04  HPF 0.5 Hz on cropped signal     — clean ERP ready for analysis
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

# Full epoch window — same as failure scripts so stages 1–2 are directly comparable.
EPOCH_TMIN_S = -2.0
EPOCH_TMAX_S =  1.0

# Artifact zeroing windows — identical to show_tesa_ica_failure_exp03.py.
ARTIFACT_BLOCK_WINDOW_S      = (-1.000, 0.05)  # entire stim gap
ARTIFACT_PRECENTER_WINDOW_S  = (-1.90, -1.10)  # stable pre-gap window for demeaning
ARTIFACT_POSTCENTER_WINDOW_S = ( 0.06,  0.40)  # stable post-gap window for demeaning

# Post-pulse crop and filter — mirrors main_analysis_exp03.py final stage.
POSTPULSE_CROP_TMIN_S = 0.08
POSTPULSE_CROP_TMAX_S = 1.00
HPF_HZ                = 0.5

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
# 2) PIPELINE STAGES
# ============================================================

# Stage 1 — raw epoch, no processing.
epochs_raw = mne.Epochs(
    raw, events, event_id=1,
    tmin=EPOCH_TMIN_S, tmax=EPOCH_TMAX_S,
    baseline=None, preload=True, verbose=False,
)

# Stage 2 — zero out the entire stim gap and independently demean pre/post
# segments so both sit around 0 µV. Identical to the failure script stage 2.
data_zeroed, _ = preprocessing.replace_block_with_zero_after_dual_center(
    epochs_raw.get_data(), epochs_raw.times,
    artifact_block_window_s=ARTIFACT_BLOCK_WINDOW_S,
    pre_center_window_s=ARTIFACT_PRECENTER_WINDOW_S,
    post_center_window_s=ARTIFACT_POSTCENTER_WINDOW_S,
)
epochs_blockzero = mne.EpochsArray(
    data_zeroed, epochs_raw.info, tmin=EPOCH_TMIN_S, baseline=None, verbose=False
)

# Stage 3 — crop to post-pulse window only.
# This is the decisive step: by discarding everything before 0.08 s we remove
# the unstable pre-pulse context that breaks ICA and ringing-based filters.
epochs_postpulse = epochs_blockzero.copy().crop(
    tmin=POSTPULSE_CROP_TMIN_S, tmax=POSTPULSE_CROP_TMAX_S
)

# Stage 4 — HPF on the clean, cropped signal.
# Operating on a stationary post-pulse window, the filter no longer sees
# the DC baseline steps and produces a clean result.
epochs_final = epochs_postpulse.copy().filter(
    l_freq=HPF_HZ, h_freq=None,
    method="iir", iir_params={"order": 4, "ftype": "butter"},
    verbose=False,
)


# ============================================================
# 3) SUBPLOT FIGURE — one row per stage, channel Cz
# ============================================================
plot_helpers.plot_cz_pipeline_steps(
    stage_epochs={
        "01  Raw epoch (−2 to +1 s)": epochs_raw,
        "02  Zero stim gap −1→0 s (dual-demeaned)": epochs_blockzero,
        "03  Crop to post-pulse (0.08–1.0 s)": epochs_postpulse,
        "04  HPF 0.5 Hz — clean ERP": epochs_final,
    },
    channel=CHANNEL_TO_PLOT,
    output_path=OUTPUT_DIRECTORY / "good_pipeline_steps_Cz.png",
)

print(f"Saved → {OUTPUT_DIRECTORY / 'good_pipeline_steps_Cz.png'}")
