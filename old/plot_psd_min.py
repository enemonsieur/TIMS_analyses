from pathlib import Path
import mne
import matplotlib.pyplot as plt

p = Path(__file__).parent / 'Experiment_1' / 'processed'
for f in sorted(p.glob('*-preproc_raw.fif')):
    print(f"Loading {f.name}...")
    r = mne.io.read_raw_fif(str(f), preload=True, verbose=False)
    r.filter(7,15, verbose=True)
    r.compute_psd(fmin=0.1, fmax=20.0).plot()
    plt.show()
    print(f"Plotted {f.name}")
