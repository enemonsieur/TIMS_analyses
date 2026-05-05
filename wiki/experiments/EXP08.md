---
type: experiment
status: active
updated: 2026-04-28
tags:
  - exp08
  - phantom
  - single-pulse
  - dose-response
  - 10-to-100-percent
---

# EXP08

## Question

Can a single-pulse dose-response protocol (10–100% intensity, 20 pulses per level) produce clean, repeatable on-demand signal recovery without the complexity of continuous iTBS modulation?

## Current Conclusion

**Data extraction and spatial filtering complete.** 200 pulses detected across 10 intensity levels (10%–100%), grouped into per-intensity epoch files (20 epochs each, 28 EEG channels). Spatial filter comparison (Raw/SASS/SSD) shows **SSD maintains SNR>6 µV² even at 100% intensity** where raw collapses to 0.385 µV². **Critical observation:** Baseline ITPC with GT (pre-pulse, no stim) is 0.76 ± 0.23 (high coherence), but drops 3× to 0.25–0.48 across stimulated intensities, even in quiet OFF-window. This stimulation-induced phase loss persists despite spatial filtering, suggesting genuine GT/frequency disruption, not artifact masking alone. **⚠️ Caveat (2026-04-28):** Causal bandpass filter (12.5–13.5 Hz, Q=13) produces forward ringing for 2+ s post-pulse; ITPC/PLV computed on filtered signal may conflate artifact phase locking with true coherence, especially at 100% intensity. Filtering methodology is under investigation; see [[experiments/MEMO_EXP08|MEMO_EXP08 §5]] for forensics and planned approach.

**Filter forensics update (2026-04-28):** `filtfilt` is not acceptable for pulse-adjacent interpretation because it mirrors artifact ringing into the pre-pulse window. A causal 10-16 Hz filter is more interpretable than `filtfilt` because it preserves temporal direction (pre-pulse RMS 1.67 uV causal vs. 151.38 uV `filtfilt` on one raw Oz 100% pulse), but it still rings forward after the pulse. See [[methods/Filter_Impulse_Response|Filter impulse response]].

## Evidence

**Extraction & Data:**
- [`explore_exp08_pulses.py`](../../explore_exp08_pulses.py): pulse detection and epoch extraction, SKRIPT.md compliant.
- [`exp08_epoch_summary.txt`](../../EXP08/exp08_epoch_summary.txt): timing summary with per-intensity epoch counts and window definitions.
- [`exp08_block_timing_by_intensity.png`](../../EXP08/exp08_block_timing_by_intensity.png): visualization of all 200 pulses marked by intensity level.
- Epoch files: 4 unified files with GT+STIM embedded, event_id 1–10 per intensity: `exp08_all_on_artremoved-epo.fif`, `exp08_all_on_signal-epo.fif`, `exp08_all_on_noise-epo.fif`, `exp08_all_lateoff_noise-epo.fif`.

**Pulse Artifact Removal + Epoch Saving (2026-05-02):**
- **Correction:** Single-pulse cleanup must use raw run01 (`exp08-STIM-pulse_run01_10-100.vhdr`). Do not use `exp08t_*_artremoved`; those belong to triplet run02.
- [`exp08_preprocessing.py`](../../exp08_preprocessing.py): raw run01 → dual-threshold find_peaks artifact removal → 4 pre-filtered epoch FIF files with GT+STIM embedded, event_id 1–10.
- 4 unified output files (PRIMARY — use for all downstream analysis): `exp08_all_on_artremoved-epo.fif`, `exp08_all_on_signal-epo.fif` (12–14 Hz), `exp08_all_on_noise-epo.fif` (4–20 Hz), `exp08_all_lateoff_noise-epo.fif` (4–20 Hz, +2 to +4 s).
- [`exp08_pulse_artremoved_qc.png`](../../EXP08/exp08_pulse_artremoved_qc.png): QC heatmaps showing artifact recovery duration per channel/epoch, plus before/after Oz overlays at 100% intensity.
- [`exp08_artremoved_dataviz.png`](../../EXP08/exp08_artremoved_dataviz.png): all-intensity Oz before/after overview, explicitly sourced from run01.
- [`exp08_run01_pulse_artifact_summary.txt`](../../EXP08/exp08_run01_pulse_artifact_summary.txt): run01 pulse schedule, thresholds, and artifact-duration table.

**Analysis & Findings:**
- [`explore_exp08_timecourse_100pct.py`](../../explore_exp08_timecourse_100pct.py): 5-channel timecourse + ITPC + stimulus visualization at 100% intensity.
- [`exp08_timecourse_100pct_overlay.png`](../../EXP08/exp08_timecourse_100pct_overlay.png): 6-panel figure (5 channels + ITPC at 100% intensity).
- [`explore_exp08_coherence_to_gt.py`](../../explore_exp08_coherence_to_gt.py): Multi-intensity ITPC analysis with 0% baseline comparison (heatmap + trend plot).
- [`exp08_coherence_to_gt_heatmap.png`](../../EXP08/exp08_coherence_to_gt_heatmap.png): Heatmap (channels × intensities) + trend line showing 3× ITPC drop from baseline.
- **Filter forensics (2026-04-28):**
  - [`explore_exp08_oz_13hz_sanity.py`](../../explore_exp08_oz_13hz_sanity.py): 11–14 Hz filtered Oz vs GT timecourse at 10% and 100% to visualize artifact ringing.
  - [`exp08_oz_13hz_sanity.png`](../../EXP08/exp08_oz_13hz_sanity.png): Side-by-side comparison showing 100+ µV artifact ringing in Oz at 100% intensity.
  - [`explore_exp08_stim_pulse_shape.py`](../../explore_exp08_stim_pulse_shape.py): Raw STIM channel pulse shape (single trial + average).
  - [`explore_exp08_causal_10_16_vs_filtfilt_dril.py`](../../explore_exp08_causal_10_16_vs_filtfilt_dril.py): raw-VHDR DRIL comparing causal 10-16 Hz vs. `filtfilt` on one Oz 100% pulse.
  - [`exp08_causal_10_16_vs_filtfilt_dril_oz_100pct.png`](../../EXP08/exp08_causal_10_16_vs_filtfilt_dril_oz_100pct.png): measured figure showing causal filtering avoids backward ringing but not post-pulse ringing.
- [[experiments/MEMO_EXP08|MEMO_EXP08]]: detailed spatial filter comparison (Raw/SASS/SSD), multi-intensity ITPC findings, and filter artifact forensics (§5).

## Conflicts / Caveats

- On-window definition (−0.1 to 0.5 s post-pulse) differs from [[experiments/EXP06|EXP06]] and [[experiments/EXP07|EXP07]] (0.3–1.5 s). Single pulses are much shorter (~15 ms) than iTBS blocks (~2 s ON), so the post-pulse response window is necessarily compressed.
- Pulses are delivered at 5 s inter-pulse spacing, leaving 4.98 s of OFF-state between pulses. This differs from iTBS cycles and may reveal different artifact settling dynamics.
- **CRITICAL:** Low ITPC in stimulated OFF-window is NOT artifact masking (baseline pre-pulse shows 0.76 ITPC). Rather, stimulation itself appears to disrupt phase coherence, even after artifact settles. Suggests frequency shift, GT reference mismatch, or phantom GT disruption at high fields.
- **FILTER ARTIFACT SPREADING (2026-04-28):** The 1 Hz-wide bandpass filter (12.5–13.5 Hz, Q≈13) rings for ~2–2.5 s after an impulsive artifact. At 100%, the raw artifact (~5000 µV) is filtered into a fake 13 Hz oscillation that dominates the entire ITPC window, creating artificial phase locking on every trial. This may inflate apparent ITPC coherence at high intensities. See [[experiments/MEMO_EXP08#5-filter-artifact-spreading-temporal-contamination-2026-04-28|MEMO_EXP08 §5]] for forensics evidence and recommendations (wider bandwidth, Morlet wavelet, or artifact subtraction).
- **TEP decay removal limitation:** Exponential decay model A·exp(−t/τ)+C does not fit all channels adequately. Even after removal, some channels (P7, F4, P3) retain large DC offsets. "Good" channels (Oz, P4, F3) show minimal residual offset but are still not zero. Suggests artifact is multi-component or non-exponential; exponential subtraction alone is insufficient.

- **CAUSAL 10-16 HZ UPDATE (2026-04-28):** The wider causal filter lowers Q to 2.17 and avoids backward contamination (1.67 uV pre-pulse RMS vs. 151.38 uV for `filtfilt`), but post-pulse ringing remains large (260.61 uV causal post-pulse RMS). Filtered post-pulse metrics are not evidence until the filter impulse response is validated.

## TEP Analysis (2026-04-23)

**TMS-evoked potentials** extracted across 6 intensities (10%, 20%, 30%, 40%, 50%, 100%) using PRE (−0.8 to −0.3 s, pre-pulse control) and POST (0.020–0.5 s, post-pulse response) windows.

### Channel Quality Issues (2026-04-23)

Initial QC identified 13 channels with extreme amplitudes (>±8 µV) in POST window across all intensities, which were dropped. Remaining 15 channels still show quality problems:

**Channel dropout procedure:**
- Screened all 28 channels for amplitude > ±8 µV in POST window (0.020–0.5 s)
- 10% intensity: 13 bad channels identified
- Dropped BAD_CHANNELS: ['F7', 'FT9', 'FC5', 'FC1', 'C3', 'T7', 'Pz', 'O1', 'O2', 'CP6', 'T8', 'FT10', 'FC2']
- **Remaining 15 channels**: ['F3', 'CP5', 'CP1', 'P3', 'P7', 'Oz', 'P4', 'P8', 'CP2', 'Cz', 'C4', 'FC6', 'F4', 'F8', 'Fp2']

**Decay removal investigation (20% intensity, POST window):**
Exponential decay removal A·exp(−t/τ)+C was applied to remaining 15 channels. Baseline offset measured as mean(evoked POST trace) per channel.

*Before baseline correction (decay only):*
- **GOOD channels**: Oz (0.02 µV), P4 (0.03 µV), F3 (0.04 µV)
- **BAD channels**: P7 (10,162 µV), F4 (1.05 µV), P3 (0.32 µV)

**Critical finding:** Channel P7 catastrophic residual DC offset (10K+ µV) after decay removal. Decay model does not fit this channel.

**Solution applied (2026-04-23): Explicit DC centering via PRE-window baseline correction**
After decay removal, applied `.apply_baseline((-0.8, -0.3))` to demean each epoch using pre-stimulus window as reference. This centers all channels around zero before filtering.

*After decay removal + baseline correction:*
- **GOOD channels** (offset <0.2 µV): Fp2 (0.03 µV), P8 (0.11 µV), CP2 (0.05 µV), Cz (0.06 µV), FC6 (0.08 µV)
- **PROBLEMATIC channels** (offset 3–11 µV): P4 (3.08 µV), F4 (4.19 µV), P7 (11.23 µV)

**Interpretation:** Exponential decay model insufficient for all channels. P7, F4 exhibit slow drift + non-exponential baseline components not captured by A·exp(−t/τ)+C. Baseline correction helps normalize to common reference but cannot fix inherently unstable baseline characteristics in POST window.

**Next investigation:** High-pass filter (0.3 Hz) on clean PRE region to remove slow drift components, then apply to POST window as additional cleanup before final averaging.

### TEP Pipeline

**Scripts**: [`explore_exp08_tep.py`](../../explore_exp08_tep.py) (main), [`explore_exp08_tep_qc_raw.py`](../../explore_exp08_tep_qc_raw.py) (raw inspection), [`explore_exp08_tep_decay_inspection.py`](../../explore_exp08_tep_decay_inspection.py) (decay QC).

1. Load ON epochs (28 EEG channels, 20 epochs per intensity)
2. Drop known bad channels (13 outliers by amplitude threshold)
3. Exponential decay removal (per-channel fit A·exp(−t/τ)+C from 20 ms onward)
4. Explicit DC centering (demean all channels to zero after decay removal)
5. Lowpass filter 42 Hz
6. Extract PRE and POST evoked averages
7. plot_joint at 3 topomap times (PRE: −0.75, −0.60, −0.45 s; POST: 0.03, 0.10, 0.20 s)

**Output**: 12 PNGs in `EXP08/TEPs/` (6 intensities × 2 windows). Files 10-20% are ~400K–1.6M (viewable); 30%+ grow to 1.7–3.9M due to artifact-induced GFP scaling.

## Artifact Removal Pipeline (2026-04-28)

**PREREQUISITE**: All downstream analyses (ITPC, SNR, TEP, PLV, etc.) must use **artremoved epochs**, not raw epochs.

**Run01 correction:** `exp08t_*_artremoved` files are triplet-run02 products and are invalid for the single-pulse EXP08 conclusion. Use only the 4 unified files generated from raw run01.

Pulse artifact removal completed from raw run01 via dual-threshold find_peaks + linear interpolation:
- `exp08_preprocessing.py` — Restructured 2026-05-02 (saves 4 unified FIF files)
- Output files: `exp08_all_on_artremoved-epo.fif`, `exp08_all_on_signal-epo.fif`, `exp08_all_on_noise-epo.fif`, `exp08_all_lateoff_noise-epo.fif`
- QC plot: `exp08_pulse_artremoved_qc.png` (artifact end times per channel/epoch, before/after overlays)
- Dataviz plot: `exp08_artremoved_dataviz.png` (all-intensity Oz before/after)
- Summary: `exp08_run01_pulse_artifact_summary.txt`
- Method details: wiki/methods/TEP_Preprocessing.md § "Pulse Artifact Removal"

**Key results**:
- Run01 single-pulse timing: 200 pulses total, 20 pulses per intensity, 5.0 s spacing.
- Artifact-duration summaries are regenerated in `exp08_run01_pulse_artifact_summary.txt` with all 10 intensities; current acute removal is -10 to +20 ms for nearly all channels.
- 100% Oz acute-window validation: raw abs max 93,340.8 uV -> cleaned abs max 6,781.2 uV.
- Current artifact end table:

| Intensity | Mean end ms | Std | Min | Max | Mean threshold uV |
|-----------|------------:|----:|----:|----:|------------------:|
| 10% | 20.0 | 0.0 | 20 | 20 | 10.8 |
| 20% | 20.0 | 0.4 | 20 | 29 | 32.0 |
| 30% | 20.0 | 0.0 | 20 | 20 | 83.0 |
| 40% | 20.0 | 0.0 | 20 | 20 | 157.3 |
| 50% | 20.0 | 0.0 | 20 | 20 | 320.9 |
| 60% | 20.0 | 0.0 | 20 | 20 | 519.5 |
| 70% | 20.0 | 0.0 | 20 | 20 | 712.9 |
| 80% | 20.0 | 0.0 | 20 | 20 | 875.9 |
| 90% | 20.0 | 0.0 | 20 | 20 | 1005.9 |
| 100% | 20.0 | 0.0 | 20 | 20 | 1132.1 |

**Why pulse-level per-channel?** At 100%, baseline is bimodal (±315 µV) and residual offsets vary by channel and pulse. Global batch cropping fails; the run01 cleanup adapts to each pulse/channel before rebuilding the single-pulse epochs.

## Next Steps

### Filtering & ITPC Methodology Investigation (2026-04-28+)

**Core Problem:** Causal sosfilt bandpass (12.5–13.5 Hz, Q=13) causes forward ringing for 2+ s post-pulse. ITPC/PLV computed on filtered signal may measure artifact phase locking, not true signal recovery. **NOW PARTLY SOLVED by artifact removal: artremoved epochs have cleaner baselines and less residual artifact for the filter to ring on.**

**Investigation Plan (updated for post-artifact-removal era):**

1. **Retry TEP extraction on artremoved epochs**: Run `explore_exp08_tep.py` on `*_artremoved-epo.fif`. Expected: POST window baseline should now be much cleaner (<100 µV instead of 1.4K–17K µV), decay-removal model should work better.

2. **Window expansion**: Expand analysis window from ±0.5 s to ±0.6 s (symmetric, captures full post-pulse settling).

3. **ITPC computation method**: Test **Option D (hybrid approach)** — compute ITPC on filtered signal but mask artifact-dominated regions (0–0.1 s post-pulse), reporting only off-window phase coherence. Avoids forward ringing contamination while preserving component selection on full filtered bandwidth.

3b. **Updated ITPC filtering rule (2026-04-28):** Do not use `filtfilt` for pulse-adjacent ITPC/PLV. If filtering is needed, prefer causal 10-16 Hz only after impulse-response validation and define the usable post-pulse window from measured ringing. Artifact removal reduces (but does not eliminate) filter ringing artifacts.

4. **Filtering method optimization** (ongoing learning): Test alternative filter designs (bandwidth trade-offs, notch effectiveness), and validate SNR/ITPC stability across intensities on artremoved epochs. Should see significant improvement over raw-epoch filtering.

5. **Replace ITPC visualization with PLV** (if applicable): Test PLV (phase locking value) as alternative summary metric; decide which to prioritize based on stability across intensities on cleaned data.

6. **Archive redundant visualization scripts**: Keep only one simple raw-plot script (`explore_exp08_raw_pulse.py` — quick-and-dirty, hardcoded, `plt.show()` for sanity checks). Archive: `explore_exp08_coherence_to_gt.py`, `explore_exp08_timecourse_100pct.py`, `explore_exp08_oz_13hz_sanity.py`, `explore_exp08_stim_pulse_shape.py`, `explore_exp08_raw_pulse_view.py`.

## Relevant Methods

- [[methods/SNR|SNR]]
- [[methods/ITPC|ITPC]]
- [[methods/SSD|SSD]]
- [[methods/Post_Pulse_Windowing|Post-pulse windowing]]
- [[methods/Filter_Impulse_Response|Filter impulse response]]

## Relevant Papers

- No linked papers yet.
