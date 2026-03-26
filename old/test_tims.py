import mne 

import os
import pathlib
import matplotlib.pyplot as plt
import numpy as np
BAD_CHANNELS = ['F8', 'FT10', 'T8', 'TP10', 'P7', 'TP9', 'FT9', 'F7']
input_path = "C:\\Users\\njeuk\\OneDrive\\Documents\\Charite Berlin\\TIMS\\TIMS_data_sync\\pilot\\doseresp"
exp04_stim_path = os.path.join(input_path, "exp04-sub01-stim-mod-50hz-pulse-run01.vhdr")
exp04_rsPreStim = os.path.join(input_path, "exp04-sub01-baseline-fullOFFstim-run01.vhdr")
exp04_rsPostStim = os.path.join(input_path, "exp04-sub01-baseline-after--fullOFFstim-run02.vhdr")

# load first the resting states and viz activity
raw_rsPre = mne.io.read_raw_brainvision(exp04_rsPreStim, preload=True)
raw_rsPost = mne.io.read_raw_brainvision(exp04_rsPostStim, preload=True)
raw_stim = mne.io.read_raw_brainvision(exp04_stim_path, preload=True)
# Drop non-EEG channels

raw_rsPre.pick_types(eeg=True).drop_channels(BAD_CHANNELS)
raw_rsPost.pick_types(eeg=True).drop_channels(BAD_CHANNELS)
raw_stim.pick_types(eeg=True).drop_channels(BAD_CHANNELS)
# raw_rsPre.plot(duration=10, n_channels=30, remove_dc=True)
# raw_rsPost.plot(duration=10, n_channels=30, remove_dc=True)

## Try to plot the psd
# raw_rsPre.compute_psd().plot()

# raw_stim.compute_psd().plot()
# raw_rsPost.compute_psd().plot()

# Let's build epochs arround stim onsets. 

# Detect onsets from one of the channels. First let's plot 1 EEG channel
#raw_stim.plot(duration=10, n_channels=1)
#plt.show()

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
skip_time = int(0.8 * 1000) 
stim_onsets_samples = [candidate_onsets[0]]
for s in candidate_onsets[1:]:
    if s - stim_onsets_samples[-1]> skip_time:
        stim_onsets_samples.append(s)
stim_onsets_samples = np.array(stim_onsets_samples)
print(f"Detected {len(stim_onsets_samples)} stimulation blocks from CP6 channel.")
# scheneurkel
# plt.plot(np.arange(len(cp6_data_demeaned))/raw_stim.info['sfreq'], cp6_data_demeaned)
# plt.show()

## ========== EPOCHING ===========
# Now we have the onsets, we can epoch the data around the onsets. We know the last 1/50 s of each 1s period is the stim pulse, so we can epoch from -2s to +1s around the onset, and then we can look at the last 1/50 s of each epoch to see the stimulation effect.
# first lets change stim onsets to real pulse time, which is 1/50 s after the detected onset.
stim_pulse_onsets_events = stim_onsets_samples + int(1/50 * 1000)
# now we create fake events for MNE, which requires a 3-column array: [sample, 0, event_id]
events = np.array([[s, 0, 1] for s in stim_pulse_onsets_events], dtype=int)
print(f"structure of events is: {events[0:10]}, shape is: {events.shape}")