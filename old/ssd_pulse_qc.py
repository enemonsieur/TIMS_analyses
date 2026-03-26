from pathlib import Path
import numpy as np
import mne
from scipy.linalg import eigh
from scipy.signal import find_peaks
import matplotlib.pyplot as plt

# Minimal SSD
def run_ssd(raw, sig, noise, n_comp=6):
    Xs = raw.copy().filter(*sig, verbose=False).get_data()
    Csig = Xs @ Xs.T / Xs.shape[1]
    Xn = np.concatenate([raw.copy().filter(*b, verbose=False).get_data() for b in noise], axis=1)
    Cn = Xn @ Xn.T / Xn.shape[1]
    vals, vecs = eigh(Csig, Cn);
    vecs = vecs[:, vals.argsort()[::-1]]
    W = vecs[:, :n_comp]
    patterns = np.linalg.pinv(W).T
    return W, patterns

p = Path(__file__).parent / 'Experiment_1' / 'processed' / 'STIM_SP_01_notTurnedOff-preproc_raw.fif'
raw = mne.io.read_raw_fif(str(p), preload=True, verbose=False)
sfreq = raw.info['sfreq']
# SSD: signal wideband covering pulse energy, flankers out of band
W, patterns = run_ssd(raw, (0.1, 20), ((0.5, 1.0), (21, 40)), n_comp=4)
X = raw.get_data(); S = W.T @ X
bad = int(np.argmax(S.var(axis=1)))            # heuristic: largest-variance comp
Xc = X - W[:, [bad]] @ S[[bad], :]
rawc = raw.copy(); rawc._data = Xc

# detect pulses from multichannel envelope (peak every ~4s)
env = np.mean(np.abs(X), axis=0)
peaks, _ = find_peaks(env, height=env.mean()+4*env.std(), distance=int(sfreq*3))
peaks = peaks[:6]
ch = 'Cz' if 'Cz' in raw.ch_names else raw.ch_names[0]
ci = raw.ch_names.index(ch)

# plot a few pulse windows (raw vs cleaned)
for pk in peaks:
    i0 = max(0, pk - int(0.5*sfreq)); i1 = min(X.shape[1], pk + int(0.5*sfreq))
    t = (np.arange(i0, i1) - pk) / sfreq
    plt.figure(); plt.plot(t, X[ci, i0:i1], label='raw'); plt.plot(t, Xc[ci, i0:i1], label='cleaned')
    plt.legend(); plt.title(f'Pulse @ {pk/sfreq:.2f}s ({p.name})'); plt.xlabel('s'); plt.show()

# PSD after cleaning only (use raw.compute_psd().plot() for inspection)
rawc.compute_psd(fmin=0.1, fmax=20.0).plot()
plt.show()
print('Removed component:', bad)
