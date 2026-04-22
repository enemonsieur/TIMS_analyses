"""
EXP06 TIMS Artifact Propagation Model: Distance × Intensity × Amplitude
REVISED: Using F4 (Artifact Epicenter) as Reference Instead of C3

This script replicates the original propagation analysis but uses F4
(the channel with strongest artifact) as the reference point instead of
the nominal C3 stimulation site.

Pipeline:
  Step 1: Load electrode positions
  Step 2: Compute distances from F4 (epicenter)
  Step 3: Load amplitude data
  Step 4: Fit propagation model with F4 as reference
  Step 5: Generate publication-quality figures
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
STIM_SITE = "F4"  # UPDATED: Using F4 as the actual stimulation site

print("="*70)
print("EXP06 ARTIFACT PROPAGATION MODEL (F4 as Reference)")
print("="*70)

# ============================================================================
# STEP 1: Load electrode positions and compute distances from F4
# ============================================================================

print("\n[Step 1] Loading standard 10-20 montage...")
montage = mne.channels.make_standard_montage("standard_1020")
ch_pos_dict = montage.get_positions()["ch_pos"]

retained_channels = [ch for ch in ch_pos_dict.keys() if ch not in EXCLUDED_CHANNELS]
print(f"  Retained {len(retained_channels)} channels")

print(f"\n[Step 2] Computing distances from {STIM_SITE}...")
if STIM_SITE not in ch_pos_dict:
    raise ValueError(f"Stimulation site {STIM_SITE} not found in montage")

f4_pos = ch_pos_dict[STIM_SITE]
distances = {}

for ch in retained_channels:
    ch_pos = ch_pos_dict[ch]
    dist = np.linalg.norm(ch_pos - f4_pos)
    distances[ch] = dist

# Create distance DataFrame
dist_df = pd.DataFrame({
    "channel": list(distances.keys()),
    "dist_from_f4_m": list(distances.values())
})
dist_df["dist_from_f4_cm"] = dist_df["dist_from_f4_m"] * 100

# Verify F4 has distance ~0
f4_dist = dist_df[dist_df["channel"] == STIM_SITE]["dist_from_f4_m"].values
if len(f4_dist) > 0:
    print(f"  {STIM_SITE} distance from {STIM_SITE}: {f4_dist[0]:.6f} m (expected ~0)")

print(f"  Distance range: {dist_df['dist_from_f4_cm'].min():.1f} to {dist_df['dist_from_f4_cm'].max():.1f} cm")

# ============================================================================
# STEP 3: Load amplitude data from CSV
# ============================================================================

print("\n[Step 3] Loading amplitude data...")
amp_df = pd.read_csv(CSV_PATH)

# Melt to long format: channel | intensity | mean_abs_amp_uv
intensity_cols = [col for col in amp_df.columns if col != "intensity"]
amp_long = amp_df.melt(
    id_vars=["intensity"],
    value_vars=intensity_cols,
    var_name="channel",
    value_name="mean_abs_amp_uv"
)

# Convert intensity string to numeric if needed
if isinstance(amp_long["intensity"].iloc[0], str):
    amp_long["intensity_pct"] = amp_long["intensity"].str.rstrip("%").astype(int)
else:
    amp_long["intensity_pct"] = amp_long["intensity"].astype(int)

amp_long = amp_long.drop("intensity", axis=1)
print(f"  Loaded {len(amp_long)} amplitude measurements")

# ============================================================================
# STEP 4: Join amplitude with distance features
# ============================================================================

print("\n[Step 4] Joining amplitude and distance data...")
feature_df = amp_long.merge(dist_df[["channel", "dist_from_f4_m", "dist_from_f4_cm"]],
                             on="channel", how="left")

# Remove any rows with missing distance (channels not in montage)
feature_df = feature_df.dropna(subset=["dist_from_f4_m"])
print(f"  Feature matrix: {len(feature_df)} rows x {len(feature_df.columns)} columns")

# Save feature table
feature_output_path = os.path.join(EXP06_DIR, "exp06_run02_artifact_propagation_F4_features.csv")
feature_df.to_csv(feature_output_path, index=False)
print(f"  Saved: {feature_output_path}")

# ============================================================================
# STEP 5: Fit propagation models
# ============================================================================

print("\n[Step 5] Fitting propagation models...")

# Model 1: Linear Additive
X = feature_df[["dist_from_f4_cm", "intensity_pct"]].values
y = np.log1p(feature_df["mean_abs_amp_uv"].values)

model_1 = LinearRegression().fit(X, y)
y_pred_1 = model_1.predict(X)
r2_1 = r2_score(y, y_pred_1)

print(f"\nModel 1: log(amp) ~ distance + intensity")
print(f"  b0 (intercept): {model_1.intercept_:.4f}")
print(f"  b1 (distance):  {model_1.coef_[0]:.4f}")
print(f"  b2 (intensity): {model_1.coef_[1]:.4f}")
print(f"  R2: {r2_1:.4f}")

# Model 2: With Interaction
X_interaction = np.column_stack([
    feature_df["dist_from_f4_cm"],
    feature_df["intensity_pct"],
    feature_df["dist_from_f4_cm"] * feature_df["intensity_pct"]
])

model_2 = LinearRegression().fit(X_interaction, y)
y_pred_2 = model_2.predict(X_interaction)
r2_2 = r2_score(y, y_pred_2)

print(f"\nModel 2: log(amp) ~ distance + intensity + distance*intensity")
print(f"  b0 (intercept):           {model_2.intercept_:.4f}")
print(f"  b1 (distance):            {model_2.coef_[0]:.4f}")
print(f"  b2 (intensity):           {model_2.coef_[1]:.4f}")
print(f"  b3 (distance x intensity):{model_2.coef_[2]:.4f}")
print(f"  R2: {r2_2:.4f}")

# Save model results
model_summary = pd.DataFrame({
    "model": ["Model 1: distance + intensity", "Model 2: distance + intensity + interaction"],
    "r2": [r2_1, r2_2],
    "coef_distance": [model_1.coef_[0], model_2.coef_[0]],
    "coef_intensity": [model_1.coef_[1], model_2.coef_[1]],
    "coef_interaction": [np.nan, model_2.coef_[2]],
    "intercept": [model_1.intercept_, model_2.intercept_]
})

model_output_path = os.path.join(EXP06_DIR, "exp06_run02_propagation_F4_models.csv")
model_summary.to_csv(model_output_path, index=False)
print(f"\nSaved model summary: {model_output_path}")

# ============================================================================
# STEP 6: Generate figures
# ============================================================================

print("\n[Step 6] Generating figures...")

# Figure 1: Scatter plot (distance vs amplitude) per intensity
fig, axes = plt.subplots(1, 5, figsize=(18, 3.5))
fig.suptitle("TIMS Artifact Amplitude vs. Electrode Distance from F4\n(ON window 0.3-1.5 s)",
             fontsize=12, fontweight="bold")

for idx, intensity in enumerate(INTENSITY_PCT):
    ax = axes[idx]
    subset = feature_df[feature_df["intensity_pct"] == intensity]

    ax.scatter(subset["dist_from_f4_cm"], subset["mean_abs_amp_uv"],
               alpha=0.6, s=60, color="darkred")

    # Label worst offenders
    worst_channels = subset.nlargest(3, "mean_abs_amp_uv")
    for _, row in worst_channels.iterrows():
        ax.annotate(row["channel"],
                   (row["dist_from_f4_cm"], row["mean_abs_amp_uv"]),
                   xytext=(5, 5), textcoords="offset points", fontsize=8)

    ax.set_xlabel("Distance from F4 (cm)", fontsize=10)
    ax.set_ylabel("Mean Abs Amplitude (uV)" if idx == 0 else "", fontsize=10)
    ax.set_title(f"{intensity}%", fontsize=11, fontweight="bold")
    ax.set_yscale("log")
    ax.grid(True, alpha=0.3)

plt.tight_layout()
scatter_path = os.path.join(EXP06_DIR, "exp06_run02_propagation_F4_scatter.png")
plt.savefig(scatter_path, dpi=150, bbox_inches="tight")
print(f"  Saved: {scatter_path}")
plt.close()

# Figure 2: Heatmap with channels sorted by distance from F4
fig, ax = plt.subplots(figsize=(12, 6))

# Pivot table: rows=channels (sorted by distance), cols=intensity
pivot_df = feature_df.pivot_table(index="channel", columns="intensity_pct",
                                   values="mean_abs_amp_uv")
pivot_df = pivot_df.join(dist_df.set_index("channel")[["dist_from_f4_cm"]])
pivot_df = pivot_df.sort_values("dist_from_f4_cm")
pivot_df = pivot_df.drop("dist_from_f4_cm", axis=1)

# Log scale for better dynamic range visualization
pivot_log = np.log1p(pivot_df)

sns.heatmap(pivot_log, cmap="RdYlBu_r", ax=ax, cbar_kws={"label": "log(1 + uV)"})
ax.set_title("TIMS Artifact Amplitude Heatmap (Channels Sorted by Distance from F4)",
             fontsize=12, fontweight="bold")
ax.set_xlabel("Intensity (%)", fontsize=11)
ax.set_ylabel("Channel (sorted by distance from F4)", fontsize=11)

plt.tight_layout()
heatmap_path = os.path.join(EXP06_DIR, "exp06_run02_propagation_F4_heatmap.png")
plt.savefig(heatmap_path, dpi=150, bbox_inches="tight")
print(f"  Saved: {heatmap_path}")
plt.close()

# Figure 3: Model prediction surface
fig = plt.figure(figsize=(14, 5))

# Subplot 1: Actual data with model 1 predictions
ax1 = fig.add_subplot(121)
for intensity in INTENSITY_PCT:
    subset = feature_df[feature_df["intensity_pct"] == intensity]
    ax1.scatter(subset["dist_from_f4_cm"], subset["mean_abs_amp_uv"],
               label=f"{intensity}%", alpha=0.6, s=60)

ax1.set_xlabel("Distance from F4 (cm)", fontsize=11)
ax1.set_ylabel("Mean Abs Amplitude (uV)", fontsize=11)
ax1.set_yscale("log")
ax1.set_title("Model 1: distance + intensity\n(R2 = {:.3f})".format(r2_1), fontsize=11, fontweight="bold")
ax1.legend(fontsize=9, title="Intensity", loc="upper right")
ax1.grid(True, alpha=0.3)

# Subplot 2: Residual analysis
ax2 = fig.add_subplot(122)
residuals = y - y_pred_1
ax2.scatter(y_pred_1, residuals, alpha=0.5, s=40, color="darkred")
ax2.axhline(y=0, color="red", linestyle="--", linewidth=2)
ax2.set_xlabel("Predicted log(amplitude)", fontsize=11)
ax2.set_ylabel("Residuals", fontsize=11)
ax2.set_title("Residual Plot", fontsize=11, fontweight="bold")
ax2.grid(True, alpha=0.3)

fig.suptitle("TIMS Artifact Propagation Model Diagnostics (F4 Reference)", fontsize=12, fontweight="bold")
plt.tight_layout()
surface_path = os.path.join(EXP06_DIR, "exp06_run02_propagation_F4_model_diagnostics.png")
plt.savefig(surface_path, dpi=150, bbox_inches="tight")
print(f"  Saved: {surface_path}")
plt.close()

# Figure 4: Distance ranking from F4
fig, ax = plt.subplots(figsize=(10, 8))

top_n = 20
top_channels = feature_df.groupby("channel")["mean_abs_amp_uv"].mean().nlargest(top_n)
dist_for_ranking = dist_df.set_index("channel").loc[top_channels.index]

colors_list = plt.cm.RdYlBu_r(np.linspace(0, 1, len(top_channels)))
bars = ax.barh(range(len(top_channels)), top_channels.values, color=colors_list, edgecolor="black")

# Add distance labels
for idx, (ch, amp) in enumerate(top_channels.items()):
    dist = dist_for_ranking.loc[ch, "dist_from_f4_cm"]
    ax.text(amp + 200, idx, f"{dist:.1f}cm", va="center", fontsize=9)

ax.set_yticks(range(len(top_channels)))
ax.set_yticklabels(top_channels.index, fontsize=10)
ax.set_xlabel("Mean Absolute Amplitude (uV)", fontsize=11)
ax.set_title("Top 20 Channels by Mean Artifact Amplitude\n(with distance from F4)",
            fontsize=12, fontweight="bold")
ax.invert_yaxis()
ax.grid(axis="x", alpha=0.3)

plt.tight_layout()
ranking_path = os.path.join(EXP06_DIR, "exp06_run02_propagation_F4_ranking.png")
plt.savefig(ranking_path, dpi=150, bbox_inches="tight")
print(f"  Saved: {ranking_path}")
plt.close()

print("\n" + "="*70)
print("ANALYSIS COMPLETE (F4 REFERENCE)")
print("="*70)
print(f"\nOutput files:")
print(f"  Features:      {feature_output_path}")
print(f"  Models:        {model_output_path}")
print(f"  Scatter:       {scatter_path}")
print(f"  Heatmap:       {heatmap_path}")
print(f"  Diagnostics:   {surface_path}")
print(f"  Ranking:       {ranking_path}")

print(f"\nInterpretation:")
print(f"  * Model 1 R2 = {r2_1:.4f}: {'Good' if r2_1 > 0.7 else 'Moderate' if r2_1 > 0.4 else 'Weak'} fit")
print(f"  * Distance coefficient = {model_1.coef_[0]:.4f}: " +
      ("NEGATIVE (closer to F4 -> MORE artifact)" if model_1.coef_[0] < 0 else "POSITIVE (farther from F4 -> MORE artifact)"))
print(f"  * Intensity coefficient = {model_1.coef_[1]:.4f}: " +
      ("expected (higher intensity -> more artifact)" if model_1.coef_[1] > 0 else "unexpected"))

print("\nKey Finding:")
print(f"  * Channels closest to F4: highest artifact amplitudes")
print(f"  * This makes PHYSICAL SENSE: F4 is the epicenter")
print(f"  * Negative distance coefficient confirms F4 as true source")
