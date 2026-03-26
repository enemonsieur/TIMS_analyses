from pathlib import Path

import matplotlib.pyplot as plt
import mne

import plot_helpers


# ============================================================
# FIXED INPUTS (EDIT ONLY THIS BLOCK)
# ============================================================
STIM_VHDR_PATH = r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\TIMS_data_sync\pilot\doseresp\exp03-phantom-stim-pulse-10hz-GT10s-run03.vhdr"
BASELINE_VHDR_PATH = r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\TIMS_data_sync\pilot\doseresp\exp03-phantom-baseline-10hz-GT-fullOFFstim-run01.vhdr"

OUTPUT_DIRECTORY = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\exp03_postpulse_fixed_channels")
OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)

# Fixed channels from Step A ranking.
FIXED_RETAINED_CHANNELS = ["Fp1", "F3", "FC5", "FC1", "C3", "C4", "FC6", "FC2", "F4", "F8", "Cz"]

# Pulse timing anchor and periodicity.
FIRST_PULSE_TIME_SECONDS = 16.55
PULSE_INTERVAL_SECONDS = 10.0
EVENT_ID = 1
EVENT_LABEL = "pulse"

# Window used for post-pulse power comparison.
POSTPULSE_WINDOW_START_SECONDS = 0.09
POSTPULSE_WINDOW_END_SECONDS = 2.0

# True evoked setup: pre-stim baseline + post-stim analysis.
EVOKED_EPOCH_START_SECONDS = -0.20
EVOKED_EPOCH_END_SECONDS = 0.50
EVOKED_BASELINE_START_SECONDS = -0.20
EVOKED_BASELINE_END_SECONDS = -0.02
EVOKED_PLOT_START_SECONDS = 0.05
EVOKED_PLOT_END_SECONDS = 0.30

# Filtering and spectral display.
HIGHPASS_FILTER_FREQUENCY_HZ = 1.0
POWER_FREQUENCY_MIN_HZ = 1.0
POWER_FREQUENCY_MAX_HZ = 45.0
FIGURE_DPI = 220


# ============================================================
# 1) LOAD RAW + BUILD FIXED EVENTS
# ============================================================
raw = mne.io.read_raw_brainvision(STIM_VHDR_PATH, preload=True, verbose=False)
baseline_raw = mne.io.read_raw_brainvision(BASELINE_VHDR_PATH, preload=True, verbose=False)
# Required for topomap plots (sensor coordinates).
raw.set_montage("standard_1020", on_missing="ignore", verbose=False)
baseline_raw.set_montage("standard_1020", on_missing="ignore", verbose=False)
raw_fixed_retained_channels = raw.copy().pick(FIXED_RETAINED_CHANNELS)
baseline_fixed_retained_channels = baseline_raw.copy().pick(FIXED_RETAINED_CHANNELS)
events = mne.make_fixed_length_events(
    raw,
    id=EVENT_ID,
    start=FIRST_PULSE_TIME_SECONDS,
    stop=float(raw.times[-1]),
    duration=PULSE_INTERVAL_SECONDS,
)


# ============================================================
# 2) BUILD BEFORE/AFTER RAW STREAMS
# ============================================================
raw_fixed_retained_channels_after_highpass_filter = raw_fixed_retained_channels.copy().filter(
    l_freq=HIGHPASS_FILTER_FREQUENCY_HZ,
    h_freq=None,
    verbose=False,
)
baseline_fixed_retained_channels.filter(1, None, verbose=False)

# ============================================================
# 3) EPOCHS FOR POWER COMPARISON (0.09 TO 2.0 S)
# ============================================================
epochs_postpulse_before_filter = mne.Epochs(
    raw_fixed_retained_channels,
    events=events,
    event_id={EVENT_LABEL: EVENT_ID},
    tmin=POSTPULSE_WINDOW_START_SECONDS,
    tmax=POSTPULSE_WINDOW_END_SECONDS,
    baseline=None,
    preload=True,
    verbose=False,
)
epochs_baseline = mne.Epochs(baseline_fixed_retained_channels, events=events, event_id={EVENT_LABEL: EVENT_ID},
                             tmin=EVOKED_EPOCH_START_SECONDS, tmax=EVOKED_EPOCH_END_SECONDS, 
                             baseline=(EVOKED_BASELINE_START_SECONDS, EVOKED_BASELINE_END_SECONDS), preload=True, verbose=False)
epochs_postpulse_after_highpass_filter = mne.Epochs(
    raw_fixed_retained_channels_after_highpass_filter,
    events=events,
    event_id={EVENT_LABEL: EVENT_ID},
    tmin=POSTPULSE_WINDOW_START_SECONDS,
    tmax=POSTPULSE_WINDOW_END_SECONDS,
    baseline=None,
    preload=True,
    verbose=False,
)


# ============================================================
# 4) PIPELINE STEP SUBPLOT — Cz
# ============================================================
plot_helpers.plot_cz_pipeline_steps(
    stage_epochs={
        "01  Post-pulse raw (0.09–2.0 s)": epochs_postpulse_before_filter,
        "02  After HPF 1.0 Hz": epochs_postpulse_after_highpass_filter,
    },
    channel="Cz",
    output_path=OUTPUT_DIRECTORY / "pipeline_steps_Cz.png",
)
print(f"Saved → {OUTPUT_DIRECTORY / 'pipeline_steps_Cz.png'}")

# Save processed epochs for downstream comparison scripts.
epochs_postpulse_after_highpass_filter.save(
    OUTPUT_DIRECTORY / "epochs_postpulse_hpf-epo.fif", overwrite=True, verbose=False
)
print(f"Saved → {OUTPUT_DIRECTORY / 'epochs_postpulse_hpf-epo.fif'}")

# ============================================================
# (OLD) TRUE MNE EVOKED POTENTIALS — commented out
# ============================================================
# epochs_evoked_before_filter = mne.Epochs(
#     raw_fixed_retained_channels,
#     events=events,
#     event_id={EVENT_LABEL: EVENT_ID},
#     tmin=EVOKED_EPOCH_START_SECONDS,
#     tmax=EVOKED_EPOCH_END_SECONDS,
#     baseline=(EVOKED_BASELINE_START_SECONDS, EVOKED_BASELINE_END_SECONDS),
#     preload=True,
#     verbose=False,
# )
# epochs_baseline_before_filter = mne.Epochs(
#     baseline_fixed_retained_channels,
#     events=events,
#     event_id={EVENT_LABEL: EVENT_ID},
#     tmin=EVOKED_EPOCH_START_SECONDS,
#     tmax=EVOKED_EPOCH_END_SECONDS,
#     baseline=(EVOKED_BASELINE_START_SECONDS, EVOKED_BASELINE_END_SECONDS),
#     preload=True,
#     verbose=False,
# )
# epochs_evoked_after_highpass_filter = mne.Epochs(
#     raw_fixed_retained_channels_after_highpass_filter,
#     events=events,
#     event_id={EVENT_LABEL: EVENT_ID},
#     tmin=EVOKED_EPOCH_START_SECONDS,
#     tmax=EVOKED_EPOCH_END_SECONDS,
#     baseline=(EVOKED_BASELINE_START_SECONDS, EVOKED_BASELINE_END_SECONDS),
#     preload=True,
#     verbose=False,
# )
# evoked_before_filter = epochs_evoked_before_filter[EVENT_LABEL].average().crop(tmin=EVOKED_PLOT_START_SECONDS, tmax=EVOKED_PLOT_END_SECONDS)
# evoked_after_highpass_filter = epochs_evoked_after_highpass_filter[EVENT_LABEL].average().crop(tmin=EVOKED_PLOT_START_SECONDS, tmax=EVOKED_PLOT_END_SECONDS)
# baseline_evoked = epochs_baseline_before_filter[EVENT_LABEL].average().crop(tmin=EVOKED_PLOT_START_SECONDS, tmax=EVOKED_PLOT_END_SECONDS)
#
# (5) EVOKED PLOTS, (6) POWER PLOTS, (7) SUMMARY all removed — see git history.

