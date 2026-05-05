"""Tiny EXP08 artremoved epoch vs reference sanity plot."""

from pathlib import Path
import os

os.environ.setdefault("_MNE_FAKE_HOME_DIR", str(Path(__file__).resolve().parent / ".mne"))
import numpy as np
import matplotlib
import scipy.signal
#matplotlib.use("Agg", force=True)

import matplotlib.pyplot as plt
import mne

EPOCH_DIRECTORY = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\EXP08")
QC_PCT = 100
QC_EPOCH = 0
QC_CHANNEL = "Oz"
QC_WINDOW_S = (-0.05, 0.50)
OUTPUT_PATH = EPOCH_DIRECTORY / f"qc_exp08_artremoved_vs_reference_{QC_PCT}pct.png"

clean_epochs = mne.read_epochs(EPOCH_DIRECTORY / f"exp08_epochs_{QC_PCT}pct_on_artremoved-epo.fif", preload=True, verbose=False)
stim_epochs = mne.read_epochs(EPOCH_DIRECTORY / f"exp08_stim_epochs_{QC_PCT}pct_on-epo.fif", preload=True, verbose=False)
gt_epochs = mne.read_epochs(EPOCH_DIRECTORY / f"exp08_gt_epochs_{QC_PCT}pct_on-epo.fif", preload=True, verbose=False)
reference_epochs = stim_epochs  # Switch this to gt_epochs to compare against GT.
channel_idx = clean_epochs.ch_names.index(QC_CHANNEL)
plot_mask = (clean_epochs.times >= QC_WINDOW_S[0]) & (clean_epochs.times <= QC_WINDOW_S[1])

artremoved_trace = clean_epochs.get_data()[QC_EPOCH, channel_idx, :] * 1e6

#let's normalize the reference trace y-values from 0 
plt.figure(figsize=(6, 3))
plt.plot(clean_epochs.times[plot_mask], artremoved_trace[plot_mask], label="artremoved")
#plt.plot(reference_epochs.times[plot_mask], reference_trace[plot_mask], label="STIM/GT")
plt.axvspan(0.0, 0.1, color="red", alpha=0.15)
plt.legend(frameon=False)
plt.tight_layout()
plt.show()
plt.savefig(OUTPUT_PATH, dpi=160)
print(f"Saved {OUTPUT_PATH}")
