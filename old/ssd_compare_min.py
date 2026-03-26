from pathlib import Path
import mne, numpy as np
from scipy.linalg import eigh
import matplotlib.pyplot as plt

# Minimal SSD implementation
def run_ssd_continuous_simple(raw, signal_band, noise_bands, n_components=6):
    l_sig, h_sig = map(float, signal_band)
    X_sig = raw.copy().filter(l_sig, h_sig, verbose=False).get_data()
    cov_sig = (X_sig @ X_sig.T) / X_sig.shape[1]
    (l_nl, h_nl), (l_nr, h_nr) = noise_bands
    X_nl = raw.copy().filter(float(l_nl), float(h_nl), verbose=False).get_data()
    X_nr = raw.copy().filter(float(l_nr), float(h_nr), verbose=False).get_data()
    X_noise = np.concatenate((X_nl, X_nr), axis=1)
    cov_noise = (X_noise @ X_noise.T) / X_noise.shape[1]
    eigvals, eigvecs = eigh(cov_sig, cov_noise)
    idx = np.argsort(eigvals)[::-1]
    eigvecs = eigvecs[:, idx]
    n_comp = min(n_components, eigvecs.shape[1])
    filters = eigvecs[:, :n_comp]              # W (channels x comps)
    patterns = np.linalg.pinv(filters).T        # mixing patterns
    return None, patterns, eigvals[idx][:n_comp], filters, list(raw.ch_names)

p = Path(__file__).parent / 'Experiment_1' / 'processed'
for f in sorted(p.glob('*-preproc_raw.fif')):
    print('Loading', f.name)
    raw = mne.io.read_raw_fif(str(f), preload=True, verbose=False)

    # PSD of raw (0.1-20 Hz)
    raw.compute_psd(fmin=0.1, fmax=20.0).plot(); plt.show()

    # run SSD on 0.1-20 Hz vs flankers
    _, patterns, eigs, W, chs = run_ssd_continuous_simple(raw, (0.w, 20), ((0.5, 1.0), (21, 40)), n_components=4)

    # plot first 3 component topographies
    for i in range(min(3, patterns.shape[1])):
        mne.viz.plot_topomap(patterns[:, i], raw.info, show=True)
        plt.title(f'{f.name} comp {i}'); plt.show()

    # reject the component with largest variance (simple heuristic)
    X = raw.get_data()
    S = W.T @ X
    bad = int(np.argmax(S.var(axis=1)))
    Xc = X - W[:, [bad]] @ S[[bad], :]
    rawc = raw.copy(); rawc._data = Xc
    rawc.compute_psd(fmin=0.1, fmax=20.0).plot(); plt.show()
    print(f"{f.name}: removed component {bad}")
