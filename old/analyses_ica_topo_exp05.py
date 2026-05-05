"""Visualize topographic distribution of cTBS artifact at 30% via ICA."""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import mne
import numpy as np

import preprocessing


# ============================================================
# FIXED INPUTS
# ============================================================
DATA_DIR = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\TIMS_data_sync\pilot\doseresp")
STIM_30_VHDR = DATA_DIR / "exp05-phantom-rs-STIM-ON-30pctIntensity-GT-cTBS-run01.vhdr"
OUTPUT_DIRECTORY = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\EXP05_ica_30pct")
OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)

N_ICA = 15
ON_DURATION_S = 2.0
ARTIFACT_RATIO_THRESHOLD = 2.0  # ON/OFF RMS ratio to flag a component as artifact


# ============================================================
# 1) LOAD + PREPROCESS FOR ICA
# ============================================================
raw = mne.io.read_raw_brainvision(str(STIM_30_VHDR), preload=True, verbose=False)
sfreq = float(raw.info["sfreq"])

# Extract stim marker before dropping non-EEG channels
stim_marker = raw.copy().pick(["stim"]).get_data()[0]

# EEG-only, highpass at 1 Hz (ICA requirement), notch 50 Hz
non_eeg = [ch for ch in raw.ch_names if ch.lower() in ("stim", "ground_truth") or ch.startswith("STI")]
raw.drop_channels(non_eeg)
raw.filter(l_freq=1.0, h_freq=None, verbose=False)
raw.notch_filter([50.0], verbose=False)

# Standard 10-20 montage for topoplots
montage = mne.channels.make_standard_montage("standard_1020")
raw.set_montage(montage, on_missing="warn")
n_eeg = len(raw.ch_names)
print(f"EEG channels: {n_eeg}  |  sfreq: {sfreq}")


# ============================================================
# 2) DETECT ON-BLOCK ONSETS + BUILD ON/OFF MASKS
# ============================================================
all_onsets, _, _, _ = preprocessing.detect_stim_onsets(stim_marker, sfreq)
block_onsets = [int(all_onsets[0])]
for o in all_onsets[1:]:
    if (o - block_onsets[-1]) / sfreq > 3.0:
        block_onsets.append(int(o))
block_onsets = np.array(block_onsets, dtype=int)

n_times = raw.n_times
mask_on = np.zeros(n_times, dtype=bool)
for o in block_onsets:
    end = min(n_times, o + int(ON_DURATION_S * sfreq))
    mask_on[o:end] = True
mask_off = ~mask_on

print(f"ON-blocks: {len(block_onsets)}  |  ON samples: {mask_on.sum()}  |  OFF samples: {mask_off.sum()}")


# ============================================================
# 3) FIT ICA
# ============================================================
n_components = min(N_ICA, n_eeg - 1)
ica = mne.preprocessing.ICA(n_components=n_components, random_state=42, method="fastica")
ica.fit(raw, verbose=False)
print(f"ICA fitted: {n_components} components")

# Get continuous source time series
sources = ica.get_sources(raw).get_data()  # (n_components, n_times)


# ============================================================
# 4) IDENTIFY ARTIFACT COMPONENTS: ON/OFF RMS RATIO
# ============================================================
rms_on  = np.sqrt(np.mean(sources[:, mask_on]  ** 2, axis=1))
rms_off = np.sqrt(np.mean(sources[:, mask_off] ** 2, axis=1))
on_off_ratio = rms_on / (rms_off + 1e-12)

artifact_comps = np.where(on_off_ratio > ARTIFACT_RATIO_THRESHOLD)[0]
print(f"Artifact components (ON/OFF ratio > {ARTIFACT_RATIO_THRESHOLD}): {artifact_comps.tolist()}")
for ic in artifact_comps:
    print(f"  IC{ic:02d}  ON/OFF ratio = {on_off_ratio[ic]:.2f}")

# Channels most affected: top 3 weights per artifact component
mixing = ica.get_components()  # (n_channels, n_components)
for ic in artifact_comps:
    weights = np.abs(mixing[:, ic])
    top3_idx = np.argsort(weights)[-3:][::-1]
    top3_chs = [raw.ch_names[i] for i in top3_idx]
    print(f"  IC{ic:02d}  top channels: {top3_chs}")


# ============================================================
# 5) FIGURE 1: ICA COMPONENT TOPOMAPS
# ============================================================
fig1 = ica.plot_components(picks=range(n_components), show=False)
if isinstance(fig1, list):
    for i, f in enumerate(fig1):
        path = OUTPUT_DIRECTORY / f"fig1_ica_topos_{i}.png"
        f.savefig(path, dpi=200)
        print(f"Saved -> {path}")
        plt.close(f)
else:
    fig1.savefig(OUTPUT_DIRECTORY / "fig1_ica_topos.png", dpi=200)
    print(f"Saved -> {OUTPUT_DIRECTORY / 'fig1_ica_topos.png'}")
    plt.close(fig1)


# ============================================================
# 6) FIGURE 2: ON/OFF RATIO BAR CHART + THRESHOLD LINE
# ============================================================
fig2, ax2 = plt.subplots(figsize=(10, 4))
colors = ["C3" if r > ARTIFACT_RATIO_THRESHOLD else "C0" for r in on_off_ratio]
ax2.bar(range(n_components), on_off_ratio, color=colors, alpha=0.7)
ax2.axhline(ARTIFACT_RATIO_THRESHOLD, color="gray", ls="--", lw=1, label=f"threshold = {ARTIFACT_RATIO_THRESHOLD}")
ax2.set_xlabel("ICA component")
ax2.set_ylabel("ON / OFF RMS ratio")
ax2.set_title("exp05 (30%): ICA component artifact ratio")
ax2.legend(fontsize=9)
fig2.tight_layout()
fig2.savefig(OUTPUT_DIRECTORY / "fig2_artifact_ratio.png", dpi=200)
print(f"Saved -> {OUTPUT_DIRECTORY / 'fig2_artifact_ratio.png'}")
plt.close(fig2)
