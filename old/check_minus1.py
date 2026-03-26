import numpy as np
from scipy.signal import hilbert, butter, sosfiltfilt, find_peaks
import mne, warnings
warnings.filterwarnings('ignore')

STIM = r'C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\TIMS_data_sync\pilot\doseresp\exp02-phantom-stim-pulse-10hz-GT-run02.vhdr'
raw = mne.io.read_raw_brainvision(STIM, preload=True, verbose=False)
fs = int(raw.info['sfreq'])

stim_ch = next(c for c in raw.ch_names if 'stim' in c.lower())
marker = raw.copy().pick([stim_ch]).get_data()[0]
cz = raw.copy().pick(['Cz']).get_data()[0]
cz = sosfiltfilt(butter(4,[0.5,45],btype='bandpass',fs=fs,output='sos'), cz)

# detect onsets
env_m = np.abs(hilbert(marker))
prom = max(3*np.std(env_m), np.percentile(env_m,95)-np.percentile(env_m,50))
cand,_=find_peaks(env_m,prominence=prom,distance=int(0.05*fs))
d=np.diff(cand/fs);d2=d[d>0.5];med_ioi=float(np.median(d2)) if len(d2) else 10.
mnd=int(max(0.6*med_ioi*fs,1.5*fs));kept=[];last=-10**9
for i in cand:
    if i-last>=mnd: kept.append(i); last=i
    elif env_m[i]>env_m[last]: kept[-1]=i; last=i
onsets = np.array(kept,dtype=int)

# prepare epochs that include -1s
pre = int(1.2*fs); post = int(2.0*fs)
valid = [o for o in onsets if o>=pre and o+post < len(cz)]
if len(valid)==0:
    print('NO_VALID_EPOCHS')
    raise SystemExit

# compute envelopes
envs = np.stack([np.abs(hilbert(cz[o-pre:o+post])) for o in valid])
idx_minus1 = int(pre - 1.0*fs)
vals_minus1 = envs[:, idx_minus1] * 1e6  # µV

# baseline stats
env_base = np.abs(hilbert(sosfiltfilt(butter(4,[0.5,45],btype='bandpass',fs=fs,output='sos'), raw.copy().pick(['Cz']).get_data()[0])))
p75 = np.percentile(env_base, 75) * 1e6
p95 = np.percentile(env_base, 95) * 1e6

print(f'n_epochs={len(valid)}  med_ioi_s={med_ioi:.2f}')
print(f'Baseline Cz env: p75={p75:.3f} µV  p95={p95:.3f} µV')
print(f'Median envelope at t=-1.0s: {np.median(vals_minus1):.3f} µV  (mean={np.mean(vals_minus1):.3f} µV, sd={np.std(vals_minus1):.3f})')
print(f'Ratio median(-1s)/p75 = {np.median(vals_minus1)/p75:.2f}x')
frac_above_2 = np.mean(vals_minus1 > 2*p75)
print(f'Fraction of epochs with envelope > 2× baseline p75 at -1s: {frac_above_2:.3f}')
