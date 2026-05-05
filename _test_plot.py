import matplotlib
matplotlib.use('QtAgg')
import matplotlib.pyplot as plt
plt.ion()
import mne
from pathlib import Path

ep_path = Path(r'EXP08/exp08_epochs_10pct_on_artremoved-epo.fif')
epochs = mne.read_epochs(str(ep_path), preload=True, verbose=False)
evoked = epochs.average(picks='all')

fig = evoked.plot(show=True)
plt.pause(15)  # pump event loop for 15s — window should stay open
print('done')
