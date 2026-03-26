from pathlib import Path

import numpy as np
import mne

MUST_KEEP = ['C3', 'Cz', 'FC2', 'F4']
EXPDIR = Path(__file__).parent / 'Experiment_1'

# find a built-in 32-channel montage
montage = None
for name in mne.channels.get_builtin_montages():
    try:
        m = mne.channels.make_standard_montage(name)
        if len(m.ch_names) == 32:
            montage = (name, m)
            break
    except Exception:
        pass

def detect_and_remove_bad_channels(raw, std_factor=5.0, flat_thresh=1e-12, max_bad_frac=0.30, drop=True, verbose=True):
    """Detect flat channels and high-variance outliers (EEG-only).
    Marks `raw.info['bads']` and optionally drops them from `raw`.
    Returns list of bad channel names.
    """
    eeg_picks = mne.pick_types(raw.info, eeg=True, meg=False)
    if len(eeg_picks) == 0:
        if verbose:
            print("detect_and_remove_bad_channels: no EEG channels found")
        return []
    ch_names = [raw.ch_names[p] for p in eeg_picks]
    data = raw.get_data(picks=eeg_picks)
    ch_std = np.std(data, axis=1)
    median_std = np.median(ch_std)

    flat_mask = ch_std < flat_thresh
    high_var_mask = ch_std > (median_std * std_factor)
    bads = [ch for i, ch in enumerate(ch_names) if flat_mask[i] or high_var_mask[i]]

    bad_frac = len(bads) / max(1, len(ch_names))
    if bad_frac > max_bad_frac:
        if verbose:
            print(f"detect_and_remove_bad_channels: flagged {len(bads)}/{len(ch_names)} channels (> {max_bad_frac*100:.0f}%), skipping automatic removal.")
        return []

    raw.info['bads'] = bads
    if drop and bads:
        raw.drop_channels(bads)
    if verbose:
        print(f"detect_and_remove_bad_channels: marked bads = {bads}")
    return bads

outdir = EXPDIR / 'processed'
outdir.mkdir(exist_ok=True)

for vhdr in EXPDIR.glob('*.vhdr'):
    raw = mne.io.read_raw_brainvision(str(vhdr), preload=True, verbose=False)
    # drop non-EEG
    eegs = {raw.ch_names[i] for i in mne.pick_types(raw.info, eeg=True, meg=False)}
    non_eeg = [ch for ch in raw.ch_names if ch not in eegs]
    if non_eeg:
        raw.drop_channels(non_eeg)
    # keep only wanted EEG channels if present
    present = [ch for ch in MUST_KEEP if ch in raw.ch_names]
    if present:
        to_drop = [ch for ch in raw.ch_names if ch not in present]
        if to_drop:
            raw.drop_channels(to_drop)
    # filters
    raw.notch_filter([50.0], notch_widths=2, verbose=False)
    raw.filter(0.1, 50.0, verbose=False)

    # detect and remove bad channels (variance + flat)
    bads = detect_and_remove_bad_channels(raw, std_factor=5.0, flat_thresh=1e-12, max_bad_frac=0.30, drop=True, verbose=True)
    if bads:
        print(f"  Auto-detected bad channels: {bads}")

    # set montage if found
    if montage:
        raw.set_montage(montage[1], on_missing='warn')
    # save and print summary
    out = outdir / (vhdr.stem + '-preproc_raw.fif')
    raw.save(str(out), overwrite=True)
    print(f"{vhdr.name}: sfreq={raw.info['sfreq']:.0f}, channels={raw.ch_names}, montage={montage[0] if montage else 'none'}")
