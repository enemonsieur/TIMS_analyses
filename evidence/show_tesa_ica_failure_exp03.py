"""show_tesa_ica_failure_exp03.py
Evidence that TESA-style ICA cleaning fails on the double-pulse dataset.

The TESA pipeline assumes the signal around the removed artifact window is
stable. With our slow post-pulse baseline drift it is not, so ICA
reconstruction introduces distortions instead of isolating neural components.

Even with the standard TESA cut-and-interpolate step, the massive artifact
window still leaves an unstable baseline context on both sides — ICA then
reconstructs against that drift and distorts the signal further.

Subplot rows (all on channel Cz):
  01  Raw epoch                        — signal before any processing
  02  Zero stim gap + dual demean      — full −1 to 0 s gap removed, pre/post centred to 0 µV
  03  HPF 0.5 Hz                       — standard pre-ICA filter
  04  After ICA                        — note distortion vs HPF row
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

# ICA settings.
HPF_PRE_ICA_HZ          = 0.5     # standard TESA pre-ICA filter
ICA_N_COMPONENTS         = 0.99  # fraction → MNE picks the max valid component count
ICA_RANDOM_STATE         = 42
# Update these indices after visual inspection of ICA components.
ICA_EXCLUDE_COMPONENTS   = [0, 1]

# Full stimulation gap to zero out, plus stable windows used to demean
# the pre- and post-segments independently so both sit around 0 µV.
ARTIFACT_BLOCK_WINDOW_S      = (-1.000, 0.05)  # entire stim gap
ARTIFACT_PRECENTER_WINDOW_S  = (-1.90, -1.10)   # stable pre-gap window for demeaning
ARTIFACT_POSTCENTER_WINDOW_S = ( 0.06,  0.40)   # stable post-gap window for demeaning

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

# Stage 2 — zero out the entire stim gap (−1 to 0 s) and independently demean
# the pre- and post-segments so both hover around 0 µV. This is the most
# generous possible artifact removal — and ICA still fails on the context.
data_zeroed, _ = preprocessing.replace_block_with_zero_after_dual_center(
    epochs_raw.get_data(), epochs_raw.times,
    artifact_block_window_s=ARTIFACT_BLOCK_WINDOW_S,
    pre_center_window_s=ARTIFACT_PRECENTER_WINDOW_S,
    post_center_window_s=ARTIFACT_POSTCENTER_WINDOW_S,
)
epochs_interp = mne.EpochsArray(
    data_zeroed, epochs_raw.info, tmin=EPOCH_TMIN_S, baseline=None, verbose=False
)

# Stage 3 — standard TESA pre-ICA high-pass filter applied to the interpolated
# epochs. The unstable baseline drift between pulses is still very much present.
# IIR avoids the FIR filter-length issue on short (~3 s) epochs.
epochs_hpf = epochs_interp.copy().filter(
    l_freq=HPF_PRE_ICA_HZ, h_freq=None,
    method="iir", iir_params={"order": 4, "ftype": "butter"},
    verbose=False,
)

# Stage 4 — fit ICA on the HPF epochs and apply exclusion.
# ICA assumes epoch context around the removed window is stable —
# with our drifting baseline this assumption is violated.
ica = mne.preprocessing.ICA(
    n_components=ICA_N_COMPONENTS,
    random_state=ICA_RANDOM_STATE,
    max_iter="auto",
    verbose=False,
)
ica.fit(epochs_hpf, verbose=False)
ica.exclude = ICA_EXCLUDE_COMPONENTS

epochs_ica = epochs_hpf.copy()
ica.apply(epochs_ica, verbose=False)


# ============================================================
# 3) SUBPLOT FIGURE — one row per stage, channel Cz
# ============================================================
plot_helpers.plot_cz_pipeline_steps(
    stage_epochs={
        "01  Raw epoch (−2 to +1 s)": epochs_raw,
        "02  Zero stim gap −1→0 s (dual-demeaned)": epochs_interp,
        "03  After HPF 0.5 Hz (pre-ICA)": epochs_hpf,
        "04  After ICA — note distortion vs HPF row": epochs_ica,
    },
    channel=CHANNEL_TO_PLOT,
    output_path=OUTPUT_DIRECTORY / "tesa_ica_steps_Cz.png",
)

print(f"Saved → {OUTPUT_DIRECTORY / 'tesa_ica_steps_Cz.png'}")
