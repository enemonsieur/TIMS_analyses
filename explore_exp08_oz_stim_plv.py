# Print Pearson r between mean evoked Oz and mean evoked STIM per intensity (no filtering).
# Answers: does the artifact shape in Oz track the STIM pulse shape, and at which intensities?

import os
from pathlib import Path
import warnings
import mne
import numpy as np

os.environ.setdefault("_MNE_FAKE_HOME_DIR", str(Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS")))
warnings.filterwarnings("ignore")

EPOCH_DIR   = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\EXP08")
INTENSITIES = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
WINDOW_S    = (0.020, 0.3)  # post-pulse window; skip interpolated region (0 to 20 ms)

# No bandpass — raw evoked correlation shows whether artifact shape tracks STIM shape

print(f"\n{'Intensity':>10}  {'Pearson r':>10}  {'Oz peak (uV)':>13}  {'note'}")
print("-" * 50)

for pct in INTENSITIES:
    epochs_on = mne.read_epochs(str(EPOCH_DIR / f"exp08_epochs_{pct}pct_on_artremoved-epo.fif"), preload=True, verbose=False)
    stim_on   = mne.read_epochs(str(EPOCH_DIR / f"exp08_stim_epochs_{pct}pct_on-epo.fif"),       preload=True, verbose=False)

    t = epochs_on.times
    mask = (t >= WINDOW_S[0]) & (t <= WINDOW_S[1])

    oz_idx = epochs_on.ch_names.index("Oz")
    oz_evoked   = epochs_on.get_data()[:, oz_idx, :].mean(axis=0)[mask]   # mean across trials
    stim_evoked = stim_on.get_data()[:, 0, :].mean(axis=0)[mask]

    r = np.corrcoef(oz_evoked, stim_evoked)[0, 1]
    oz_peak_uv = np.max(np.abs(oz_evoked)) * 1e6

    note = "** HIGH" if abs(r) > 0.7 else ("* mid" if abs(r) > 0.4 else "")
    print(f"  {pct:>6}%    {r:>9.3f}    {oz_peak_uv:>11.2f}    {note}")

print()
