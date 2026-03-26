import numpy as np
from scipy.signal import hilbert, butter, sosfiltfilt, find_peaks
import mne, warnings
warnings.filterwarnings('ignore')

STIM = r'C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\TIMS_data_sync\pilot\doseresp\exp02-phantom-stim-pulse-10hz-GT-run02.vhdr'
raw = mne.io.read_raw_brainvision(STIM, preload=True, verbose=False)
fs = int(raw.info['sfreq'])

# pick channels
stim_ch = next(c for c in raw.ch_names if 'stim' in c.lower())
marker = raw.copy().pick([stim_ch]).get_data()[0]
cz = raw.copy().pick(['Cz']).get_data()[0]
cz = sosfiltfilt(butter(4,[0.5,45],btype='bandpass',fs=fs,output='sos'), cz)

# detect onsets
env_m = np.abs(hilbert(marker))
prom = max(3*np.std(env_m), np.percentile(env_m,95)-np.percentile(env_m,50))
cand,_=find_peaks(env_m,prominence=prom,distance=int(0.05*fs))
d=np.diff(cand/fs); d2=d[d>0.5]; med_ioi=float(np.median(d2)) if len(d2) else 10.
mnd=int(max(0.6*med_ioi*fs,1.5*fs)); kept=[]; last=-10**9
for i in cand:
    if i-last>=mnd: kept.append(i); last=i
    elif env_m[i]>env_m[last]: kept[-1]=i; last=i
onsets = np.array(kept,dtype=int)

# epoch envelopes over one IOI
ioi_n = int(med_ioi * fs)
valid = [o for o in onsets if o + ioi_n < len(cz)]
if len(valid) == 0:
    print('NO_VALID_EPOCHS'); raise SystemExit

envs = np.stack([np.abs(hilbert(cz[o:o+ioi_n])) for o in valid])  # shape (n_epochs, ioi_n)

# baseline floor
env_base = np.abs(hilbert(sosfiltfilt(butter(4,[0.5,45],btype='bandpass',fs=fs,output='sos'), raw.copy().pick(['Cz']).get_data()[0])))
base_p75 = np.percentile(env_base, 75)
base_p95 = np.percentile(env_base, 95)

ratio = envs / base_p75  # dimensionless

# global minima
global_min = ratio.min()
min_idx = np.unravel_index(np.argmin(ratio), ratio.shape)
min_epoch, min_sample = int(min_idx[0]), int(min_idx[1])
min_time_s = min_sample / fs

# median envelope minima (as previously reported)
med_env = np.median(envs, axis=0)
med_min_ratio = (med_env / base_p75).min()
med_min_time_s = float(np.argmin(med_env)) / fs

# fractions
frac_samples_below_2 = float(np.mean(ratio <= 2.0))
frac_epochs_with_0p5s_below_2 = 0
win = int(0.5 * fs)
for ep in range(ratio.shape[0]):
    r = ratio[ep] <= 2.0
    # find any run >= win
    if np.any(np.convolve(r.astype(int), np.ones(win, dtype=int), mode='valid') >= win):
        frac_epochs_with_0p5s_below_2 += 1
frac_epochs_with_0p5s_below_2 = frac_epochs_with_0p5s_below_2 / ratio.shape[0]

# print concise results
print(f'n_epochs={len(valid)}  IOI_s={med_ioi:.2f}')
print(f'baseline p75={base_p75*1e6:.3f} µV  p95={base_p95*1e6:.3f} µV')
print(f'global_min_ratio={global_min:.3f}  at epoch={min_epoch}  t={min_time_s:.3f}s  (µV={(envs[min_epoch,min_sample]*1e6):.1f})')
print(f'median_min_ratio={med_min_ratio:.3f} at t={med_min_time_s:.3f}s')
print(f'fraction of all epoch-samples <= 2× baseline p75: {frac_samples_below_2:.6f}')
print(f'fraction of epochs with ≥0.5s continuous <=2× baseline p75: {frac_epochs_with_0p5s_below_2:.3f}')
