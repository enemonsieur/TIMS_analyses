"""
EXP06 TIMS Artifact Epicenter Analysis: Find the True Artifact Source

Instead of assuming stimulation site is C3, this script:
  1. Identifies which channel has the strongest mean amplitude across all intensities
  2. Uses that channel as the "epicenter" (artifact source)
  3. Computes distances from the epicenter for all channels
  4. Refits the propagation model with epicenter as reference
  5. Compares epicenter location to nominal C3 stimulation site

Pipeline:
  Step 1: Load amplitude data and compute mean amplitude per channel across all intensities
  Step 2: Identify epicenter (strongest channel)
  Step 3: Load electrode positions and compute distances from epicenter
  Step 4: Fit propagation model (distance from epicenter)
  Step 5: Compare epicenter location to C3
  Step 6: Generate comparison figures
"""

import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import mne
from sklearn.linear_model import LinearRegression
from sklearn.metrics import r2_score
import seaborn as sns

# ============================================================================
# SETUP
# ============================================================================

PROJECT_ROOT = r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS"
EXP06_DIR = os.path.join(PROJECT_ROOT, "EXP06")
CSV_PATH = os.path.join(EXP06_DIR, "exp06_run02_on_channel_saturation.csv")

EXCLUDED_CHANNELS = {"TP9", "Fp1", "TP10", "FT9"}
INTENSITY_PCT = [10, 20, 30, 40, 50]
STIM_SITE_NOMINAL = "C3"  # Assumed nominal site

print("[ANALYSIS] EXP06 Artifact Epicenter Detection")
print("=" * 70)

# ============================================================================
# STEP 1: Load amplitude data and find epicenter
# ============================================================================

print("\n[Step 1] Loading amplitude data and finding epicenter...")
amp_df = pd.read_csv(CSV_PATH)

# Melt to long format
intensity_cols = [col for col in amp_df.columns if col != "intensity"]
amp_long = amp_df.melt(
    id_vars=["intensity"],
    value_vars=intensity_cols,
    var_name="channel",
    value_name="mean_abs_amp_uv"
)

# Compute mean amplitude per channel (across all 5 intensities)
channel_mean_amp = amp_long.groupby("channel")["mean_abs_amp_uv"].mean().sort_values(ascending=False)

print(f"\nTop 10 channels by mean amplitude (across all intensities):")
print(channel_mean_amp.head(10))

epicenter_channel = channel_mean_amp.index[0]
epicenter_amplitude = channel_mean_amp.iloc[0]

print(f"\n[EPICENTER IDENTIFIED] {epicenter_channel}")
print(f"  Mean amplitude: {epicenter_amplitude:.2f} uV")
print(f"  Peak amplitude per intensity block:")

for intensity in INTENSITY_PCT:
    subset = amp_long[(amp_long["channel"] == epicenter_channel) &
                      (amp_long["intensity"] == str(intensity) + "%")]
    if not subset.empty:
        amp = subset["mean_abs_amp_uv"].values[0]
        print(f"    {intensity}%: {amp:.2f} uV")

# ============================================================================
# STEP 2: Load electrode positions
# ============================================================================

print("\n[Step 2] Loading electrode positions...")
montage = mne.channels.make_standard_montage("standard_1020")
ch_pos_dict = montage.get_positions()["ch_pos"]

retained_channels = [ch for ch in ch_pos_dict.keys() if ch not in EXCLUDED_CHANNELS]
print(f"  Retained {len(retained_channels)} channels")

# Get positions of epicenter and nominal C3
epicenter_pos = ch_pos_dict[epicenter_channel]
c3_pos = ch_pos_dict[STIM_SITE_NOMINAL]

print(f"\n  {epicenter_channel} position: x={epicenter_pos[0]:.4f}, y={epicenter_pos[1]:.4f}, z={epicenter_pos[2]:.4f} m")
print(f"  {STIM_SITE_NOMINAL} position: x={c3_pos[0]:.4f}, y={c3_pos[1]:.4f}, z={c3_pos[2]:.4f} m")

# Distance between epicenter and nominal C3
dist_epicenter_to_c3 = np.linalg.norm(epicenter_pos - c3_pos)
print(f"\n  Distance {epicenter_channel} -> {STIM_SITE_NOMINAL}: {dist_epicenter_to_c3*100:.2f} cm")

# ============================================================================
# STEP 3: Compute distances from epicenter
# ============================================================================

print("\n[Step 3] Computing distances from epicenter ({})...".format(epicenter_channel))

distances_from_epicenter = {}
distances_from_c3 = {}

for ch in retained_channels:
    ch_pos = ch_pos_dict[ch]
    dist_epicenter = np.linalg.norm(ch_pos - epicenter_pos)
    dist_c3 = np.linalg.norm(ch_pos - c3_pos)
    distances_from_epicenter[ch] = dist_epicenter
    distances_from_c3[ch] = dist_c3

# Create comparison DataFrame
dist_comparison_df = pd.DataFrame({
    "channel": list(distances_from_epicenter.keys()),
    "dist_from_epicenter_m": list(distances_from_epicenter.values()),
    "dist_from_c3_m": list(distances_from_c3.values())
})

dist_comparison_df["dist_from_epicenter_cm"] = dist_comparison_df["dist_from_epicenter_m"] * 100
dist_comparison_df["dist_from_c3_cm"] = dist_comparison_df["dist_from_c3_m"] * 100

print(f"  Distance range from {epicenter_channel}:")
print(f"    Min: {dist_comparison_df['dist_from_epicenter_cm'].min():.2f} cm")
print(f"    Max: {dist_comparison_df['dist_from_epicenter_cm'].max():.2f} cm")

# ============================================================================
# STEP 4: Prepare amplitude data with both distance metrics
# ============================================================================

print("\n[Step 4] Joining amplitude with distance metrics...")

# Convert intensity string to numeric if needed
if isinstance(amp_long["intensity"].iloc[0], str):
    amp_long["intensity_pct"] = amp_long["intensity"].str.rstrip("%").astype(int)
else:
    amp_long["intensity_pct"] = amp_long["intensity"].astype(int)

# Join with distances
feature_df = amp_long.merge(dist_comparison_df, on="channel", how="left")
feature_df = feature_df.dropna(subset=["dist_from_epicenter_m"])

print(f"  Feature matrix: {len(feature_df)} rows × {len(feature_df.columns)} columns")

# ============================================================================
# STEP 5: Fit models with both reference points
# ============================================================================

print("\n[Step 5] Fitting propagation models...")

X_epicenter = feature_df[["dist_from_epicenter_cm", "intensity_pct"]].values
X_c3 = feature_df[["dist_from_c3_cm", "intensity_pct"]].values
y = np.log1p(feature_df["mean_abs_amp_uv"].values)

# Model with epicenter as reference
model_epicenter = LinearRegression().fit(X_epicenter, y)
y_pred_epicenter = model_epicenter.predict(X_epicenter)
r2_epicenter = r2_score(y, y_pred_epicenter)

# Model with C3 as reference (from previous analysis)
model_c3 = LinearRegression().fit(X_c3, y)
y_pred_c3 = model_c3.predict(X_c3)
r2_c3 = r2_score(y, y_pred_c3)

print(f"\nMODEL COMPARISON:")
print(f"\n  Using {epicenter_channel} (Epicenter) as reference:")
print(f"    log(amp) = {model_epicenter.intercept_:.4f} + {model_epicenter.coef_[0]:.4f}·distance + {model_epicenter.coef_[1]:.4f}·intensity")
print(f"    R² = {r2_epicenter:.4f}")

print(f"\n  Using C3 (Nominal stim site) as reference:")
print(f"    log(amp) = {model_c3.intercept_:.4f} + {model_c3.coef_[0]:.4f}·distance + {model_c3.coef_[1]:.4f}·intensity")
print(f"    R² = {r2_c3:.4f}")

improvement = (r2_epicenter - r2_c3) / r2_c3 * 100
print(f"\n  Improvement (epicenter vs C3): {improvement:+.1f}%")

# Save comparison
model_comparison = pd.DataFrame({
    "reference": ["Epicenter ({})".format(epicenter_channel), "C3 (Nominal)"],
    "r2": [r2_epicenter, r2_c3],
    "intercept": [model_epicenter.intercept_, model_c3.intercept_],
    "coef_distance": [model_epicenter.coef_[0], model_c3.coef_[0]],
    "coef_intensity": [model_epicenter.coef_[1], model_c3.coef_[1]]
})

output_path = os.path.join(EXP06_DIR, "exp06_run02_epicenter_analysis.csv")
model_comparison.to_csv(output_path, index=False)
print(f"\nSaved comparison: {output_path}")

# ============================================================================
# STEP 6: Generate comparison figures
# ============================================================================

print("\n[Step 6] Generating comparison figures...")

# Figure 1: Channel amplitude ranking with position markers
fig, axes = plt.subplots(2, 1, figsize=(14, 8))

# Top panel: Amplitude ranking
top_n = 15
top_channels = channel_mean_amp.head(top_n)
colors = ['red' if ch == epicenter_channel else 'steelblue' for ch in top_channels.index]

ax1 = axes[0]
ax1.barh(range(len(top_channels)), top_channels.values, color=colors, alpha=0.7, edgecolor='black')
ax1.set_yticks(range(len(top_channels)))
ax1.set_yticklabels(top_channels.index, fontsize=10)
ax1.set_xlabel('Mean Absolute Amplitude (uV)', fontsize=11)
ax1.set_title('Top 15 Channels by Mean Artifact Amplitude\n(Across all 5 intensity levels)',
              fontsize=12, fontweight='bold')
ax1.invert_yaxis()
ax1.grid(axis='x', alpha=0.3)

# Add distance labels
for idx, (ch, amp) in enumerate(top_channels.items()):
    dist_epi = distances_from_epicenter.get(ch, np.nan)
    dist_c3_val = distances_from_c3.get(ch, np.nan)
    label_text = f"{dist_epi*100:.1f}cm ({ch}->{epicenter_channel})"
    ax1.text(amp + 50, idx, label_text, va='center', fontsize=8)

# Bottom panel: Distance comparison
ax2 = axes[1]
dist_for_plot = dist_comparison_df.sort_values("dist_from_epicenter_cm")
x_pos = np.arange(len(dist_for_plot))
width = 0.35

bars1 = ax2.bar(x_pos - width/2, dist_for_plot["dist_from_epicenter_cm"], width,
                label=f"Distance from {epicenter_channel}", color='red', alpha=0.7)
bars2 = ax2.bar(x_pos + width/2, dist_for_plot["dist_from_c3_cm"], width,
                label=f"Distance from C3", color='steelblue', alpha=0.7)

ax2.set_xlabel('Channel', fontsize=11)
ax2.set_ylabel('Distance (cm)', fontsize=11)
ax2.set_title('Electrode Distance Comparison: Epicenter vs. Nominal C3\n(Channels sorted by distance from epicenter)',
              fontsize=12, fontweight='bold')
ax2.set_xticks(x_pos)
ax2.set_xticklabels(dist_for_plot["channel"], rotation=45, ha='right', fontsize=9)
ax2.legend(fontsize=10)
ax2.grid(axis='y', alpha=0.3)

plt.tight_layout()
fig_path = os.path.join(EXP06_DIR, "exp06_run02_epicenter_ranking.png")
plt.savefig(fig_path, dpi=150, bbox_inches='tight')
print(f"  Saved: {fig_path}")
plt.close()

# Figure 2: Distance vs. Amplitude (epicenter vs C3) - 2D comparison
fig, axes = plt.subplots(1, 2, figsize=(14, 5))

# Left: Using epicenter as reference
ax1 = axes[0]
for intensity in INTENSITY_PCT:
    subset = feature_df[feature_df["intensity_pct"] == intensity]
    ax1.scatter(subset["dist_from_epicenter_cm"], subset["mean_abs_amp_uv"],
               label=f"{intensity}%", alpha=0.6, s=60)

ax1.set_xlabel(f'Distance from {epicenter_channel} (cm)', fontsize=11)
ax1.set_ylabel('Mean Abs Amplitude (uV)', fontsize=11)
ax1.set_yscale('log')
ax1.set_title(f'Distance vs Amplitude\n(Reference: {epicenter_channel}, R² = {r2_epicenter:.3f})',
             fontsize=11, fontweight='bold')
ax1.legend(fontsize=9, title='Intensity', loc='upper left')
ax1.grid(True, alpha=0.3)

# Right: Using C3 as reference
ax2 = axes[1]
for intensity in INTENSITY_PCT:
    subset = feature_df[feature_df["intensity_pct"] == intensity]
    ax2.scatter(subset["dist_from_c3_cm"], subset["mean_abs_amp_uv"],
               label=f"{intensity}%", alpha=0.6, s=60)

ax2.set_xlabel('Distance from C3 (cm)', fontsize=11)
ax2.set_ylabel('Mean Abs Amplitude (uV)', fontsize=11)
ax2.set_yscale('log')
ax2.set_title(f'Distance vs Amplitude\n(Reference: C3, R² = {r2_c3:.3f})',
             fontsize=11, fontweight='bold')
ax2.legend(fontsize=9, title='Intensity', loc='upper left')
ax2.grid(True, alpha=0.3)

fig.suptitle('EXP06 Artifact Propagation: Epicenter Detection Comparison',
            fontsize=12, fontweight='bold', y=1.02)

plt.tight_layout()
fig_path = os.path.join(EXP06_DIR, "exp06_run02_epicenter_vs_c3_comparison.png")
plt.savefig(fig_path, dpi=150, bbox_inches='tight')
print(f"  Saved: {fig_path}")
plt.close()

# Figure 3: Topomap showing amplitude distribution and marked epicenter
try:
    print("  Generating topomap with epicenter marked...")
    fig, axes = plt.subplots(1, 5, figsize=(16, 3.5))
    fig.suptitle(f'TIMS Artifact Topography (Epicenter: {epicenter_channel})',
                fontsize=12, fontweight='bold')

    for idx, intensity in enumerate(INTENSITY_PCT):
        ax = axes[idx]
        subset = feature_df[feature_df["intensity_pct"] == intensity].copy()

        ch_names = list(retained_channels)
        subset_dict = dict(zip(subset["channel"], subset["mean_abs_amp_uv"]))
        data = np.array([subset_dict.get(ch, np.nan) for ch in ch_names])
        data = np.log1p(data)

        info = mne.create_info(ch_names, 1000, ch_types="eeg")
        info.set_montage(montage)

        mne.viz.plot_topomap(data, info, cmap="RdYlBu_r", show=False, axes=ax)

        # Mark epicenter with a star
        epicenter_idx = ch_names.index(epicenter_channel) if epicenter_channel in ch_names else -1
        if epicenter_idx >= 0:
            ax.plot(0, 0, '*', markersize=20, color='white', markeredgecolor='black',
                   markeredgewidth=2, label=epicenter_channel, zorder=10)

        ax.set_title(f"{intensity}%", fontsize=11, fontweight='bold')

    plt.tight_layout()
    fig_path = os.path.join(EXP06_DIR, "exp06_run02_epicenter_topomap.png")
    plt.savefig(fig_path, dpi=150, bbox_inches='tight')
    print(f"  Saved: {fig_path}")
    plt.close()

except Exception as e:
    print(f"  Warning: Could not generate topomap: {e}")

# Figure 4: Distance distribution comparison
fig, ax = plt.subplots(figsize=(10, 6))

bins = np.linspace(0, 20, 20)
ax.hist(dist_comparison_df["dist_from_epicenter_cm"], bins=bins, alpha=0.6,
        label=f"Distance from {epicenter_channel}", color='red', edgecolor='black')
ax.hist(dist_comparison_df["dist_from_c3_cm"], bins=bins, alpha=0.6,
        label="Distance from C3", color='steelblue', edgecolor='black')

ax.axvline(0, color='red', linestyle='--', linewidth=2, alpha=0.7)
ax.axvline(dist_epicenter_to_c3*100, color='green', linestyle='--', linewidth=2, alpha=0.7,
          label=f"Distance {epicenter_channel} -> C3 ({dist_epicenter_to_c3*100:.1f} cm)")

ax.set_xlabel('Distance from Reference (cm)', fontsize=11)
ax.set_ylabel('Number of Channels', fontsize=11)
ax.set_title(f'Distance Distribution: {epicenter_channel} vs. C3',
            fontsize=12, fontweight='bold')
ax.legend(fontsize=10)
ax.grid(True, alpha=0.3)

plt.tight_layout()
fig_path = os.path.join(EXP06_DIR, "exp06_run02_epicenter_distance_distribution.png")
plt.savefig(fig_path, dpi=150, bbox_inches='tight')
print(f"  Saved: {fig_path}")
plt.close()

# ============================================================================
# STEP 7: Summary and interpretation
# ============================================================================

print("\n" + "="*70)
print("EPICENTER ANALYSIS COMPLETE")
print("="*70)

print(f"\nKEY FINDINGS:")
print(f"  1. Artifact Epicenter: {epicenter_channel}")
print(f"     Mean amplitude: {epicenter_amplitude:.2f} uV")
print(f"     Location: ({epicenter_pos[0]:.4f}, {epicenter_pos[1]:.4f}, {epicenter_pos[2]:.4f}) m")

print(f"\n  2. Epicenter vs. Nominal C3:")
print(f"     Distance: {dist_epicenter_to_c3*100:.2f} cm")
print(f"     C3 location: ({c3_pos[0]:.4f}, {c3_pos[1]:.4f}, {c3_pos[2]:.4f}) m")

print(f"\n  3. Model Fit Quality:")
print(f"     Using {epicenter_channel}: R² = {r2_epicenter:.4f}")
print(f"     Using C3:       R² = {r2_c3:.4f}")
print(f"     Improvement: {improvement:+.1f}%")

if improvement > 0:
    print(f"\n   EPICENTER ({epicenter_channel}) is a BETTER predictor than C3!")
    print(f"    This suggests the actual artifact source is offset from nominal C3.")
else:
    print(f"\n   C3 is still a slightly better predictor than {epicenter_channel}.")
    print(f"    Nominal C3 may be closer to the actual artifact source than the")
    print(f"    highest-amplitude channel location.")

print(f"\nTop 5 channels by distance from {epicenter_channel}:")
farthest = dist_comparison_df.nlargest(5, "dist_from_epicenter_cm")
for idx, row in farthest.iterrows():
    print(f"  {row['channel']:>4}: {row['dist_from_epicenter_cm']:.2f} cm")

print(f"\nTop 5 channels closest to {epicenter_channel}:")
closest = dist_comparison_df.nsmallest(5, "dist_from_epicenter_cm")
for idx, row in closest.iterrows():
    if row['channel'] != epicenter_channel:  # Don't list the epicenter itself
        print(f"  {row['channel']:>4}: {row['dist_from_epicenter_cm']:.2f} cm")

print("\n" + "="*70)
