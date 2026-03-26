import mne 

import os
import pathlib
import matplotlib.pyplot as plt
import numpy as np
BAD_CHANNELS = ['F8', 'FT10', 'T8', 'TP10', 'P7', 'TP9', 'FT9', 'F7','Fp2','C3','Fz','CP1'] #'Fz','FC1','CP1','F3','CP5',
input_path = "C:\\Users\\njeuk\\OneDrive\\Documents\\Charite Berlin\\TIMS\\TIMS_data_sync\\pilot\\doseresp"
exp04_stim_path = os.path.join(input_path, "exp04-sub01-stim-mod-50hz-pulse-run01.vhdr")
exp04_rsPreStim = os.path.join(input_path, "exp04-sub01-baseline-fullOFFstim-run01.vhdr")
exp04_rsPostStim = os.path.join(input_path, "exp04-sub01-baseline-after--fullOFFstim-run02.vhdr")

# load first the resting states and viz activity
# raw_rsPre = mne.io.read_raw_brainvision(exp04_rsPreStim, preload=True)
# raw_rsPost = mne.io.read_raw_brainvision(exp04_rsPostStim, preload=True)
raw_stim = mne.io.read_raw_brainvision(exp04_stim_path, preload=True)
# Drop non-EEG channels

# raw_rsPre.pick_types(eeg=True).drop_channels(BAD_CHANNELS)
# raw_rsPost.pick_types(eeg=True).drop_channels(BAD_CHANNELS)
raw_stim.pick_types(eeg=True).drop_channels(BAD_CHANNELS)
# raw_rsPre.plot(duration=10, n_channels=30, remove_dc=True)
# raw_rsPost.plot(duration=10, n_channels=30, remove_dc=True)

## Try to plot the psd
# raw_rsPre.compute_psd().plot()

# raw_stim.compute_psd().plot()
# raw_rsPost.compute_psd().plot()

# Let's build epochs arround stim onsets. 

# Detect onsets from one of the channels. First let's plot 1 EEG channel
# raw_stim.plot(duration=19, n_channels=1)
# plt.show()

# now we see that CP6 has a relatively linear time course without DC, we can now use it to detect onset
# we isolate CP6, demean it, use a supra-physiological threshold and taeke the first  idx > onset, then increase 4s, and repeat
# This gives onset of the 1s desynch stimulation, which we know the last 1/50 s is the stim pulse. 

cp6_data = raw_stim.copy().pick_channels(['CP6']).get_data()[0]
print(type(cp6_data))
## ========== ONSET DETECTION ===========
cp6_data_demeaned = cp6_data - np.mean(cp6_data[0:int(10*raw_stim.info['sfreq'])]) # demean using the first 10s that has no stimulation. 
diff_btwIdx = np.diff(cp6_data_demeaned)
jump_threshold = 0.01
candidate_onsets = np.where(np.abs(diff_btwIdx) > jump_threshold)[0] + 1
print(f"structure of candidate onsets is: {candidate_onsets[0:10]}, shape is: {candidate_onsets.shape}")
skip_time = int(1.2 * 1000) 
stim_onsets_samples = [candidate_onsets[0]]
for s in candidate_onsets[1:]:
    if s - stim_onsets_samples[-1]> skip_time:
        stim_onsets_samples.append(s)
stim_onsets_samples = np.array(stim_onsets_samples)
stim_pulse_onsets_events = stim_onsets_samples + int(1.008 * 1000)

print(f"Detected {len(stim_pulse_onsets_events)} stimulation blocks from CP6 channel.")

# Lets plot the Pulses
# time axis for the whole trace
sfreq = raw_stim.info['sfreq']
times = np.arange(len(cp6_data_demeaned)) / sfreq
pulse_vals = cp6_data_demeaned[stim_onsets_samples]
# and the corresponding times
pulse_times = stim_pulse_onsets_events / sfreq

# plt.figure()
# plt.plot(times, cp6_data_demeaned, color='k')          # full trace
# plt.plot(pulse_times, pulse_vals, 'r*', markersize=10)
# plt.show()

## ========== EPOCHING ===========
# Now we have the onsets, we can epoch the data around the onsets. We know the last 1/50 s of each 1s period is the stim pulse, so we can epoch from -2s to +1s around the onset, and then we can look at the last 1/50 s of each epoch to see the stimulation effect.
# first lets change stim onsets to real pulse time, which is 1/50 s after the detected onset.
# now we create fake events for MNE, which requires a 3-column array: [sample, 0, event_id]
events = np.array([[s, 0, 1] for s in stim_pulse_onsets_events], dtype=int)
epochs_stim = mne.Epochs(raw_stim, events, event_id=1, tmin=-2.0, tmax=2.5, baseline=None, preload=True)
# epochs_pre= mne.Epochs(raw_rsPre, events, event_id=1, tmin=-2.0, tmax=2.5, baseline=None, preload=True)
# epochs_post= mne.Epochs(raw_rsPost, events, event_id=1, tmin=-2.0, tmax=2.5, baseline=None, preload=True)
#epochs_stim.plot()

print(f"Epochs shape is: {epochs_stim.get_data().shape}, which is (n_epochs, n_channels, n_times)")

# Now we can look at the last 1/50 s of each epoch to see the stimulation effect. We can also compare the pre and post resting states to see if there are any changes in the brain activity after the stimulation.
# plot average of epochs  at our times but before, we wanna demean it using time points -2 to -1.5s , before stim starts
print (f"good channels are: {epochs_stim.ch_names}")
epochs_stim_demeaned = epochs_stim.copy().apply_baseline(baseline=(-1.9, -1.3)) #

# # I'mm forced to use that to notch filter withoiut artifacts.
# data = epochs_stim_demeaned.get_data()

# data = mne.filter.notch_filter(
#     data,
#     Fs=epochs_stim_demeaned.info['sfreq'],
#     freqs=50
# )
# == SUBPLOT of ERP of 10 Channels ==
import scipy
# == FIT CURVE ===

epochs_clean = epochs_stim_demeaned.copy().crop(tmin=0.08, tmax=2.3).filter(None,42)
evoked = epochs_clean.average()
evoked.plot(picks='CP6')

t = evoked.times
mask = t > 0.02

for ch_idx, ch_name in enumerate(evoked.ch_names):
    y = evoked.data[ch_idx]

    popt, _ = scipy.optimize.curve_fit(
        lambda tt, A, tau, C: A * np.exp(-tt / tau) + C,
        t[mask], y[mask],
        maxfev=10000
    )

    decay = popt[0] * np.exp(-t / popt[1]) + popt[2]

    # subtract this channel's fitted decay from that channel in every epoch
    epochs_clean._data[:, ch_idx, :] -= decay[np.newaxis, :]
epochs_clean.average().plot()
#epochs_clean.compute_psd().plot()
plt.show()
schnerkel 
# how many channels we actually have
ch_names = epochs_stim_demeaned.ch_names
nch = len(ch_names)
 
# compute integer number of rows (ceil so the last row may be half‑filled)
nrows = int(np.ceil(nch / 2))
fig, axes = plt.subplots(nrows=nrows, ncols=2,
                         figsize=(16, 3 * nrows),  # bigger figure
                         sharex=True, sharey=False,
                         squeeze=False)
# flatten the grid for easy zipping
axes_flat = axes.flat
for ax, ch in zip(axes_flat, ch_names):
    print(f"Plotting channel {ch}")
    evoked.plot(picks=ch, axes=ax, show=False)
    ax.set_title(ch, fontsize=10)

# if nch is odd, hide the unused subplot(s)
for ax in axes_flat[nch:]:
    ax.set_visible(False)

plt.tight_layout()
plt.show()