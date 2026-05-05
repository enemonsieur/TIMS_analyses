from pathlib import Path

import matplotlib.pyplot as plt
import mne
import numpy as np


stim_vhdr_path = r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\TIMS_data_sync\pilot\doseresp\exp03-phantom-stim-pulse-10hz-GT10s-run03.vhdr"
output_directory = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\exp03_find_best_channels")
output_directory.mkdir(parents=True, exist_ok=True)

candidate_eeg_channels = ["Fp1", "F3", "FC5", "FC1", "C3", "C4", "FC6", "FC2", "F4", "F8", "Fp2", "Cz"]
first_pulse_time_seconds = 16.55
pulse_interval_seconds = 10.0
postpulse_window_start_seconds = 0.09
postpulse_window_end_seconds = 2.0
highpass_filter_frequency_hz = 1.0
power_frequency_min_hz = 1.0
power_frequency_max_hz = 45.0
channels_to_keep_count = 4


raw = mne.io.read_raw_brainvision(stim_vhdr_path, preload=True, verbose=False)
raw_candidate_channels = raw.copy().pick(candidate_eeg_channels)

events = mne.make_fixed_length_events(
    raw,
    id=1,
    start=first_pulse_time_seconds,
    stop=float(raw.times[-1]),
    duration=pulse_interval_seconds,
)

epochs_postpulse_before_filter = mne.Epochs(
    raw_candidate_channels,
    events=events,
    event_id=1,
    tmin=postpulse_window_start_seconds,
    tmax=postpulse_window_end_seconds,
    baseline=None,
    preload=True,
    verbose=False,
)

raw_candidate_channels_after_highpass_filter = raw_candidate_channels.copy().filter(
    l_freq=highpass_filter_frequency_hz,
    h_freq=None,
    verbose=False,
)

epochs_postpulse_after_highpass_filter = mne.Epochs(
    raw_candidate_channels_after_highpass_filter,
    events=events,
    event_id=1,
    tmin=postpulse_window_start_seconds,
    tmax=postpulse_window_end_seconds,
    baseline=None,
    preload=True,
    verbose=False,
)

power_spectrum_before_filter = epochs_postpulse_before_filter.compute_psd(
    fmin=power_frequency_min_hz,
    fmax=power_frequency_max_hz,
)
power_spectrum_after_highpass_filter = epochs_postpulse_after_highpass_filter.compute_psd(
    fmin=power_frequency_min_hz,
    fmax=power_frequency_max_hz,
)

power_before_filter = power_spectrum_before_filter.get_data().mean(axis=0)
power_after_highpass_filter = power_spectrum_after_highpass_filter.get_data().mean(axis=0)
power_change_decibel = 10.0 * np.log10((power_after_highpass_filter + 1e-30) / (power_before_filter + 1e-30))
channel_change_score = np.mean(np.abs(power_change_decibel), axis=1)
channel_order_from_best_to_worst = np.argsort(channel_change_score)

ordered_channel_names = np.asarray(candidate_eeg_channels)[channel_order_from_best_to_worst]
ordered_channel_scores = channel_change_score[channel_order_from_best_to_worst]
ordered_channel_mean_change_decibel = power_change_decibel.mean(axis=1)[channel_order_from_best_to_worst]

recommended_fixed_channels = ordered_channel_names[:channels_to_keep_count].tolist()

csv_output_path = output_directory / "channel_scores.csv"
csv_rows = np.column_stack(
    [
        ordered_channel_names.astype(str),
        ordered_channel_scores.astype(float).astype(str),
        ordered_channel_mean_change_decibel.astype(float).astype(str),
    ]
)
csv_header = "channel_name,change_score_abs_delta_db,mean_delta_db"
np.savetxt(csv_output_path, csv_rows, delimiter=",", fmt="%s", header=csv_header, comments="")

figure_channel_scores, axis_channel_scores = plt.subplots(figsize=(10, 4), constrained_layout=True)
axis_channel_scores.bar(ordered_channel_names, ordered_channel_scores, color="steelblue")
axis_channel_scores.set_title("Channel ranking by postpulse power change")
axis_channel_scores.set_xlabel("Channel")
axis_channel_scores.set_ylabel("Mean absolute delta power (dB)")
axis_channel_scores.tick_params(axis="x", rotation=45)
figure_channel_scores.savefig(output_directory / "channel_scores_barplot.png", dpi=220)

print(f"recommended_fixed_channels={recommended_fixed_channels}")
print(f"events_count={events.shape[0]}")
print(f"epochs_shape_before={epochs_postpulse_before_filter.get_data().shape}")
print(f"epochs_shape_after={epochs_postpulse_after_highpass_filter.get_data().shape}")

plt.show()

