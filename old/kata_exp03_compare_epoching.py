from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import mne


stim_vhdr_path = r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\TIMS_data_sync\pilot\doseresp\exp03-phantom-stim-pulse-10hz-GT10s-run03.vhdr"
output_directory = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\exp03_kata_outputs_run03")
output_directory.mkdir(parents=True, exist_ok=True)
CANDIDATE_EEG_PICKS = ["Fp1", "F3", "FC5", "FC1", "C3", "C4", "FC6", "FC2", "F4", "F8", "Fp2", "Cz"]

focus_channel = "FC1"
start_s = 16.55
pulse_interval_s = 10.0
epoch_tmin = 0.09
epoch_tmax = 2.0
pre_window_s = (4.0, 12.0)
psd_fmin = 1.0
psd_fmax = 45.0


### 1) Load raw recording
raw = mne.io.read_raw_brainvision(stim_vhdr_path, preload=True, verbose=False)
recording_end_s = float(raw.times[-1])
raw.filter(l_freq=1, h_freq=None, verbose=False)  # gentle bandpass to clean up for epoching
### 2) Build pulse events every 10 s from manual first pulse time
events = mne.make_fixed_length_events(
    raw,
    id=1,
    start=start_s,
    stop=recording_end_s,
    duration=pulse_interval_s,
)

### 3) Build post-pulse epochs (no filtering, no baseline)
epochs_raw = mne.Epochs(
    raw,
    events=events,
    event_id=1,
    tmin=epoch_tmin,
    tmax=epoch_tmax,
    baseline=None,
    preload=True,
    verbose=False,
)

### 4) Build post-pulse epochs after gentle HPF at 0.1 Hz
raw_hpf01 = raw.copy().filter(l_freq=1, h_freq=None, verbose=False)
epochs_hpf01 = mne.Epochs(
    raw_hpf01,
    events=events,
    event_id=1,
    tmin=epoch_tmin,
    tmax=epoch_tmax,
    baseline=None,
    preload=True,
    verbose=False,
)

### 5) Build post-pulse epochs with baseline correction only
epochs_baseline = epochs_raw.copy().apply_baseline((0.09, 0.20))

### 6) Plot post-pulse time course and power for each step (save manually if needed)
# fig_raw_time = epochs_raw.average().plot(picks=[focus_channel], show=False)
# fig_raw_psd = epochs_raw.compute_psd(fmin=psd_fmin, fmax=psd_fmax).plot(picks=[focus_channel], show=False)

# fig_hpf_time = epochs_hpf01.average().plot(picks=[focus_channel], show=False)
# fig_hpf_psd = epochs_hpf01.compute_psd(fmin=psd_fmin, fmax=psd_fmax).plot(picks=[focus_channel], show=False)


fig_base_time = epochs_baseline.average().plot(picks=[focus_channel], show=False)
fig_base_psd = epochs_baseline.compute_psd(fmin=psd_fmin, fmax=psd_fmax).plot(picks=[focus_channel], show=False)

### 7) Compare continuous pre-pulse vs post-pulse power
raw_pre = raw.copy().crop(tmin=pre_window_s[0], tmax=pre_window_s[1])
raw_pre.apply_function(lambda x: x - x.mean(), picks="eeg", channel_wise=True)
raw_pre.filter(l_freq=1, h_freq=None, verbose=False)

raw_post = raw.copy().crop(tmin=start_s, tmax=None)

#fig_pre_psd = raw_pre.compute_psd(fmin=psd_fmin, fmax=psd_fmax).plot(picks=[focus_channel], show=False)

# raw_pre.plot(
#     picks=[focus_channel], n_channels=1, duration=6.0, start=0.0,
#     scalings=dict(eeg=15e-6), remove_dc=True,
#     highpass=0.5, lowpass=40.0, filtorder=2,
#     bgcolor="white", color="black", butterfly=False,
#     show_scrollbars=True, show_scalebars=True, time_format="float"
# )
plt.show()

#fig_post_psd = raw_post.compute_psd(fmin=psd_fmin, fmax=psd_fmax).plot(picks=[focus_channel], show=False)

### 8) Print quick summary and open figures
print(f"events_n={events.shape[0]}")
print(f"epochs_raw_shape={epochs_raw.get_data().shape}")
print(f"epochs_hpf01_shape={epochs_hpf01.get_data().shape}")
print(f"epochs_baseline_shape={epochs_baseline.get_data().shape}")
print(f"recording_end_s={recording_end_s:.3f}")
print("Figures created: raw/hpf/baseline timecourse + raw/hpf/baseline PSD + pre/post continuous PSD")
print("Save any figure manually with e.g. fig_raw_time.savefig(output_directory / 'my_name.png', dpi=200)")
