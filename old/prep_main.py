from pathlib import Path

from preprocessing import (
    build_stim_masks,
    detect_stim_onsets,
    epoch_signal,
    filter_signal,
    load_and_extract_signals,
    plot_quick_checks,
)


# User-editable configuration
stim_vhdr_path = r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\TIMS_data_sync\pilot\doseresp\exp02-phantom-stim-pulse-10hz-GT-run02.vhdr"
baseline_vhdr_path = r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\TIMS_data_sync\pilot\doseresp\exp02-phantom-baseline-run01.vhdr"
output_directory = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\exp02_subspace_separation_run02_10s")
bad_channels_to_drop = None  # Example: ["T7", "TP9"]

# Main flow (7 executable lines; imports/comments excluded)
signal_bundle = load_and_extract_signals(stim_vhdr_path, baseline_vhdr_path, reference_channel="Cz", bad_channels_to_drop=bad_channels_to_drop)
preprocessed_reference = filter_signal(signal_bundle["stim_reference"], signal_bundle["sampling_rate_hz"], low_hz=0.5, high_hz=45.0)  # shape: (n_times,)
preprocessed_stim_eeg = filter_signal(signal_bundle["stim_eeg"], signal_bundle["sampling_rate_hz"], low_hz=0.5, high_hz=45.0)  # shape: (n_eeg, n_times)
onsets_samples, median_ioi_seconds, ioi_seconds, onsets_seconds = detect_stim_onsets(signal_bundle["stim_marker"], signal_bundle["sampling_rate_hz"])
stim_masks = build_stim_masks(onsets_samples, total_samples=preprocessed_stim_eeg.shape[1], sampling_rate_hz=signal_bundle["sampling_rate_hz"], on_window_s=(0.0, 1.0), end_window_s=(0.9, 1.05), off_exclusion_window_s=(0.0, 1.05))  # masks shape: (n_times,)
epochs_reference, epoch_time_axis_seconds, valid_onsets_samples = epoch_signal(preprocessed_reference, onsets_samples, signal_bundle["sampling_rate_hz"], window_start_s=-0.25, window_end_s=2.0)  # epochs shape: (n_epochs, n_window_samples)
quick_check_paths = plot_quick_checks(signal_bundle["stim_raw"], preprocessed_reference, signal_bundle["reference_channel_name"], signal_bundle["sampling_rate_hz"], output_directory)

print(f"stim_eeg_shape={preprocessed_stim_eeg.shape}  epochs_shape={epochs_reference.shape}  n_onsets={onsets_samples.size}  n_valid_onsets={valid_onsets_samples.size}")
print(f"median_ioi_seconds={median_ioi_seconds:.3f}  ioi_count={ioi_seconds.size}  first_onset_seconds={onsets_seconds[0]:.3f}")
print(f"mask_on_samples={int(stim_masks['mask_on'].sum())}  mask_off_samples={int(stim_masks['mask_off'].sum())}")
print(f"time_plot={quick_check_paths['time_plot_path']}")
print(f"psd_plot={quick_check_paths['psd_plot_path']}")
