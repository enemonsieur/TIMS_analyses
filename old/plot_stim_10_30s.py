import numpy as np
import matplotlib.pyplot as plt
import mne

# ---- config ----
baseline_vhdr = r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\TIMS_data_sync\pilot\doseresp\exp03-phantom-baseline-10hz-GT-fullOFFstim-run01.vhdr"
stim_vhdr_path = r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\TIMS_data_sync\pilot\doseresp\exp03-phantom-stim-pulse-10hz-GT10s-run03.vhdr"
#candidate_eeg_picks = ["Fp1", "F3", "FC5", "FC1", "C3", "C4", "FC6", "FC2", "F4", "F8", "Fp2", "Cz"]

T0, T1 = 10, 15.0          # plot window (seconds)
EEG_PICKS = ['Fp1', 'Cz', 'FC1',"F3", "FC5",  "C3", "C4", "FC6", "FC2"]   # channels to show 'F4', 'FC6', 'F8', 'Fp2',, 'C4',  'F3', 'FC2',
# run 03: Fp2, Fp1, C4, C3, 
# ---- load ----

raw = mne.io.read_raw_brainvision(baseline_vhdr, preload=True, verbose=False)
events = mne.make_fixed_length_events(raw, duration=2.0)
epochs = mne.Epochs(raw, events, tmin=0, tmax=2.0, baseline=None, preload=True, verbose=False)
epochs.filter(1,45)
epochs.average().plot(picks="Cz", spatial_colors=True)
#epochs.plot(picks=EEG_PICKS, n_epochs=10, title="2 s epochs time course")
plt.show()

sfreq = raw.info['sfreq']
i0, i1 = int(T0 * sfreq), int(T1 * sfreq)
#raw.filter(0.5, 45, verbose=False)
# ---- pick channels that actually exist ----
eeg_chs     = [c for c in EEG_PICKS if c in raw.ch_names]
stim_ch     = next((c for c in raw.ch_names if 'stim'         in c.lower()), None)
gt_ch       = next((c for c in raw.ch_names if 'ground_truth' in c.lower() or c.lower() == 'gt'), None)
aux_chs     = [c for c in (stim_ch, gt_ch) if c is not None]

# ---- extract data slice ----
t   = np.arange(i0, i1) / sfreq
eeg = raw.copy().pick(eeg_chs).get_data()[:, i0:i1] * 1e6          # → µV
aux = {c: raw.copy().pick([c]).get_data()[0, i0:i1] for c in aux_chs}

# ---- plot ----
n_eeg   = len(eeg_chs)
n_rows  = n_eeg + len(aux_chs)
fig, axes = plt.subplots(n_rows, 1, figsize=(14, 2.0 * n_rows),
                         sharex=True, constrained_layout=True)
axes = np.atleast_1d(axes)

for i, (ch, sig) in enumerate(zip(eeg_chs, eeg)):
    axes[i].plot(t, sig, lw=0.8, color='steelblue')
    axes[i].set_ylabel(ch, fontsize=8, rotation=0, labelpad=28, va='center')
    axes[i].grid(True, alpha=0.2)

for j, ch in enumerate(aux_chs):
    ax = axes[n_eeg + j]
    color = 'C3' if 'stim' in ch.lower() else 'C2'
    ax.plot(t, aux[ch], lw=0.8, color=color)
    ax.set_ylabel(ch, fontsize=8, rotation=0, labelpad=28, va='center')
    ax.grid(True, alpha=0.2)

axes[-1].set_xlabel('Time (s)')
fig.suptitle(f'Stimulation recording: {T0}–{T1} s', fontsize=12, fontweight='bold')
plt.savefig('stim_10_30s.png', dpi=200)
plt.show()
print('Saved stim_10_30s.png')

