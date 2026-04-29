"""Crop and interpolate TMS artifact from EXP08 epochs using epoch-specific baselines."""

from pathlib import Path
import matplotlib.pyplot as plt
import mne
import numpy as np

OUTPUT_DIR = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\EXP08")

# ════════════════════════════════════════════════════════════════════════════
# CONFIG: Artifact window definition
# ════════════════════════════════════════════════════════════════════════════

ARTIFACT_START_MS = 0      # Crop starts at pulse onset
ARTIFACT_END_MS = 50       # Crop ends 50 ms post-pulse

PRE_BASELINE_START_MS = -100   # Pre-artifact baseline window
PRE_BASELINE_END_MS = -20

POST_BASELINE_START_MS = 100   # Post-artifact baseline window
POST_BASELINE_END_MS = 200

# ════════════════════════════════════════════════════════════════════════════
# LOAD EPOCHS
# ════════════════════════════════════════════════════════════════════════════

ep10 = mne.read_epochs(OUTPUT_DIR / "exp08t_epochs_10pct_on-epo.fif", verbose=False, preload=True)
ep50 = mne.read_epochs(OUTPUT_DIR / "exp08t_epochs_50pct_on-epo.fif", verbose=False, preload=True)
ep100 = mne.read_epochs(OUTPUT_DIR / "exp08t_epochs_100pct_on-epo.fif", verbose=False, preload=True)

epochs_list = [
    (ep10, "10%"),
    (ep50, "50%"),
    (ep100, "100%"),
]

# ════════════════════════════════════════════════════════════════════════════
# FUNCTION: Crop and interpolate artifact
# ════════════════════════════════════════════════════════════════════════════

def crop_and_interpolate(epochs, artifact_start_ms, artifact_end_ms,
                         pre_baseline_start_ms, pre_baseline_end_ms,
                         post_baseline_start_ms, post_baseline_end_ms):
    """
    Apply crop+interpolate artifact removal to epochs using epoch-specific baselines.

    For each epoch and channel:
    1. Extract pre-artifact baseline (mean)
    2. Extract post-artifact baseline (mean)
    3. Linearly interpolate from pre to post to fill artifact region
    4. Replace artifact region with interpolation

    Returns: new epochs object with cleaned data
    """
    epochs_clean = epochs.copy()
    data = epochs_clean.get_data()  # (n_epochs, n_channels, n_times)
    times = epochs_clean.times

    # Convert ms to time indices
    art_start_idx = np.argmin(np.abs(times - artifact_start_ms / 1000))
    art_end_idx = np.argmin(np.abs(times - artifact_end_ms / 1000))
    pre_base_start_idx = np.argmin(np.abs(times - pre_baseline_start_ms / 1000))
    pre_base_end_idx = np.argmin(np.abs(times - pre_baseline_end_ms / 1000))
    post_base_start_idx = np.argmin(np.abs(times - post_baseline_start_ms / 1000))
    post_base_end_idx = np.argmin(np.abs(times - post_baseline_end_ms / 1000))

    # Apply crop+interpolate to each epoch and channel
    for ep_idx in range(data.shape[0]):
        for ch_idx in range(data.shape[1]):
            # Extract baselines for this epoch/channel
            pre_baseline_mean = data[ep_idx, ch_idx, pre_base_start_idx:pre_base_end_idx].mean()
            post_baseline_mean = data[ep_idx, ch_idx, post_base_start_idx:post_base_end_idx].mean()

            # Create linear interpolation
            n_artifact = art_end_idx - art_start_idx
            interp = np.linspace(pre_baseline_mean, post_baseline_mean, n_artifact)

            # Replace artifact region
            data[ep_idx, ch_idx, art_start_idx:art_end_idx] = interp

    # Update epochs object with cleaned data
    epochs_clean._data = data

    return epochs_clean

# ════════════════════════════════════════════════════════════════════════════
# APPLY CROP+INTERPOLATE TO ALL INTENSITIES
# ════════════════════════════════════════════════════════════════════════════

cleaned_epochs = {}
for epochs, intensity_label in epochs_list:
    print(f"Processing {intensity_label} intensity...")
    epochs_clean = crop_and_interpolate(
        epochs,
        ARTIFACT_START_MS, ARTIFACT_END_MS,
        PRE_BASELINE_START_MS, PRE_BASELINE_END_MS,
        POST_BASELINE_START_MS, POST_BASELINE_END_MS
    )
    cleaned_epochs[intensity_label] = epochs_clean
    print(f"  OK Cleaned {len(epochs_clean)} epochs")

# ════════════════════════════════════════════════════════════════════════════
# SAVE CLEANED EPOCHS
# ════════════════════════════════════════════════════════════════════════════

for intensity_label, epochs_clean in cleaned_epochs.items():
    filename = OUTPUT_DIR / f"exp08t_epochs_{intensity_label.replace('%', 'pct')}_on_cleaned-epo.fif"
    epochs_clean.save(filename, overwrite=True, verbose=False)
    print(f"Saved: {filename.name}")

# ════════════════════════════════════════════════════════════════════════════
# VISUALIZATION: Before/After Comparison (Oz channel)
# ════════════════════════════════════════════════════════════════════════════

fig, axes = plt.subplots(3, 2, figsize=(14, 10))
fig.suptitle("Crop+Interpolate Artifact Removal: Before/After Comparison (Oz channel)",
             fontsize=14, fontweight='bold')

for row, (intensity_label, epochs_clean) in enumerate(cleaned_epochs.items()):
    epochs_orig = [ep for ep, label in epochs_list if label == intensity_label][0]

    # Get Oz channel
    ch_idx = epochs_orig.ch_names.index("Oz")
    t = epochs_orig.times

    # Plot: BEFORE
    ax_before = axes[row, 0]
    data_before = epochs_orig.get_data()[:, ch_idx, :] * 1e6
    for epoch in data_before:
        ax_before.plot(t, epoch, alpha=0.2, linewidth=0.5, color='gray')
    ax_before.axvline(0, color='red', linestyle='--', linewidth=1, alpha=0.5, label='Pulse onset')
    ax_before.axvspan(ARTIFACT_START_MS / 1000, ARTIFACT_END_MS / 1000,
                      alpha=0.2, color='red', label='Artifact region')
    ax_before.set_xlabel("Time (s)")
    ax_before.set_ylabel("Oz voltage (uV)")
    ax_before.set_title(f"{intensity_label} — BEFORE crop+interp")
    ax_before.grid(True, alpha=0.2)
    ax_before.legend(fontsize=8)

    # Plot: AFTER
    ax_after = axes[row, 1]
    data_after = epochs_clean.get_data()[:, ch_idx, :] * 1e6
    for epoch in data_after:
        ax_after.plot(t, epoch, alpha=0.2, linewidth=0.5, color='blue')
    ax_after.axvline(0, color='red', linestyle='--', linewidth=1, alpha=0.5, label='Pulse onset')
    ax_after.axvspan(ARTIFACT_START_MS / 1000, ARTIFACT_END_MS / 1000,
                     alpha=0.2, color='green', label='Interpolated region')
    ax_after.set_xlabel("Time (s)")
    ax_after.set_ylabel("Oz voltage (uV)")
    ax_after.set_title(f"{intensity_label} — AFTER crop+interp")
    ax_after.grid(True, alpha=0.2)
    ax_after.legend(fontsize=8)

fig.tight_layout()
fig.savefig(OUTPUT_DIR / "exp08_crop_interpolate_before_after.png", dpi=150)
plt.close()
print("\nSaved: exp08_crop_interpolate_before_after.png")

print("\n" + "="*70)
print("CROP+INTERPOLATE ARTIFACT REMOVAL COMPLETE")
print("="*70)
print(f"Artifact window: {ARTIFACT_START_MS} to {ARTIFACT_END_MS} ms")
print(f"Pre-baseline: {PRE_BASELINE_START_MS} to {PRE_BASELINE_END_MS} ms")
print(f"Post-baseline: {POST_BASELINE_START_MS} to {POST_BASELINE_END_MS} ms")
print(f"\nCleaned epochs saved:")
for label in cleaned_epochs.keys():
    pct_label = label.replace('%', 'pct')
    print(f"  exp08t_epochs_{pct_label}_on_cleaned-epo.fif")
