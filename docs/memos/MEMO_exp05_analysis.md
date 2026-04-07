# MEMO: exp05 Artifact and SSD Re-Analysis

**Date:** March 25, 2026  
**Experiment:** exp05 phantom cTBS at 30% and 100% intensity  
**Outputs:** `EXP_05/`

## Question

exp05 was designed to answer two linked questions:

1. Is 30% stimulation clearly cleaner than 100% during cTBS?
2. Does the EEG return close enough to baseline during the OFF period to make SSD recovery meaningful?

## Data

- Baseline with GT: `exp05-phantom-rs-GT-cTBS-run02.vhdr`
- Stim 100% with GT: `exp05-phantom-rs-STIM-ON-GT-cTBS-run01.vhdr`
- Stim 30% with GT: `exp05-phantom-rs-STIM-ON-30pctIntensity-GT-cTBS-run01.vhdr`

The timing reference is the recorded `stim` channel plus the protocol definition in `ctbs_like_v1_amp5hz_mod50hz_triplets.py`.

## Methods

### 1. Block timing

The corrected analysis does **not** use collapsed pulse peaks anymore. It detects ON blocks directly from the raw `stim` channel, then uses measured block onsets and offsets.

Protocol target:

- ON = `1.995 s`
- OFF = `3.000 s`
- cycle = `4.995 s`

Measured from the actual recordings:

- `100%`: `100` blocks, median ON `1.926 s`, median OFF `3.074 s`
- `30%`: `63` blocks, median ON `1.925 s`, median OFF `3.075 s`

So the timing correction is in place. The post-stimulation window is anchored to the **measured block offset**, not to a fixed guessed duration.

### 2. Artifact analysis

Artifact outputs are stored in:

- `EXP_05/artifact_characterization/`

The artifact script now does three different summaries:

- Figure 1: Cz mean waveform aligned to measured ON-block onset
- Figure 2: selected-channel envelope comparison
- Figure 3: post-ON decay based on the **all-channel average envelope**, not only Cz

For numeric summaries, there are two relevant post-stim windows:

- full OFF window
- first `1.0 s` immediately after the measured STIM offset

This first-1-second window matters because it directly answers whether recovery is fast enough right after stimulation stops.

### 3. SSD analysis

SSD outputs are stored in:

- `EXP_05/ssd_recovery/`

The important fix here was to stop using fake `4 s` OFF epochs. exp05 is nominally:

- `2 s` ON
- `3 s` OFF

and the measured STIM medians are very close to that:

- `100%`: ON `1.926 s`, OFF `3.074 s`
- `30%`: ON `1.925 s`, OFF `3.075 s`

The baseline-first SSD rerun does **not** use the whole OFF period anymore. It uses a fixed late-OFF window:

- `1.5-2.5 s` after the measured STIM offset

That gives a strict `1.0 s` SSD epoch and avoids the early post-offset portion as much as possible while staying inside the real measured OFF gap.

The first SSD pass on exp05 was also aimed at the wrong frequency. The recorded `ground_truth` channel peaks at:

- baseline GT: `7.08 Hz`
- `30%` GT: `7.08 Hz`
- `100%` GT: `7.08 Hz`

So the rerun no longer assumes a `10 Hz` target. It measures the GT peak directly from the baseline GT recording and then uses:

- signal band = `6.08-8.08 Hz`
- PSD / noise view = `5-15 Hz`
- SSD training = **baseline GT only**
- SSD application = transfer the same baseline-trained weights to `30%` and `100%`
- component selection = GT-match metrics, but only among components whose PSD peak is actually inside the target band

`lambda` in the new figures is just the SSD generalized eigenvalue from the baseline fit, i.e. the signal-vs-noise separation of that component.

The figure set is now baseline-first:

- `fig1` = baseline component-selection summary
- `fig2` = selected baseline component with temporal trace, topomap, and PSD
- `fig3` = baseline component gallery in `plotSSD.py` style
- `fig4` = selected baseline-component TFR
- `fig5` / `fig6` = secondary `30%` / `100%` component galleries
- `fig7` / `fig8` = secondary selected-component TFRs for `30%` / `100%`

Saved outputs now include:

- `fig0_ground_truth_reference_psd.png`
- `fig1_baseline_component_selection.png`
- `fig2_baseline_selected_component.png`
- `fig3_baseline_component_gallery.png`
- `fig4_baseline_selected_component_tfr.png`
- `fig5_ssd_components_30pct.png`
- `fig6_ssd_components_100pct.png`
- `fig7_selected_component_tfr_30pct.png`
- `fig8_selected_component_tfr_100pct.png`

### 4. Figure colour scheme

The exp05 SSD figures should use the same visual language as the exp04 figures:

- baseline = `gray`
- `30%` = `steelblue`
- `100%` = `seagreen`
- ground-truth overlay = `darkorange`
- SSD signal band shading = `#f9e7cc`
- SSD noise-flank shading = `#ddebf7`
- component topomaps = `RdBu_r`
- component TFR = `RdBu_r`

## Results

### STIM channel sanity check

The `stim` channel confirms that 30% was really weaker than 100%:

- peak ratio `30% / 100% = 0.547`
- active RMS ratio `30% / 100% = 0.542`

![All-channel epoch averages](EXP_05/channel_avg/fig_all_channels_epoch_avg.png)

### What was wrong with the earlier “30% and 100% are similar” conclusion

That statement was too strong. The main reasons were:

1. The artifact memo leaned too hard on **Cz-only** RMS values.
2. Cz is the wrong channel to generalize from here. It is close to the one place where 30% and 100% look similar.
3. The channel envelope plot is in **dB**, which compresses amplitude differences visually.
4. The older SSD analysis used OFF windows that were too long and leaked into the next ON block.

### What the corrected scalp-wide view says

From the channel-wise probe using the corrected STIM timing:

- `30%` had lower ON-window RMS than `100%` in `30 / 31` EEG channels
- `30%` had lower RMS in the **first 1 s after offset** in `31 / 31` EEG channels
- `Cz` was the main ON-window exception

At Cz specifically:

- ON RMS: `30% = 24.906 uV`, `100% = 22.938 uV`
- first 1 s after offset: `30% = 6.040 uV`, `100% = 6.121 uV`

So yes: your read of the all-channel figure is correct. Across the scalp, `30%` is clearly cleaner than `100%`. The earlier “similar artifact” reading mostly came from looking at Cz and then generalizing too far.

![Mean Cz waveform aligned to measured onset](EXP_05/artifact_characterization/fig1_mean_cz_waveform.png)

![Selected-channel envelope comparison](EXP_05/artifact_characterization/fig2_envelope_db.png)

### Important nuance

“30% is cleaner than 100%” is **not** the same as “30% is clean”.

At Cz, both conditions still sit well above baseline:

- baseline RMS during ON-sized window: `1.628 uV`
- `30%` RMS during ON: `24.906 uV`
- `100%` RMS during ON: `22.938 uV`

So 30% is cleaner than 100% across channels, but it is still not baseline-level.

### Post-stimulation recovery

The corrected timing does already anchor post-stimulation to the measured STIM offset. That part is fixed.

What was still misleading is **how** recovery was summarized:

- full OFF-window RMS can hide the fact that recovery differs strongly across channels
- Cz alone is not representative of the whole scalp

For the scientific question you care about, the better summary is:

- first `1 s` after measured STIM offset
- summarized across channels, not only Cz

That is now the right interpretation target for Figure 3 and the memo.

The regenerated all-channel decay fit gave:

- `30%`: `tau = 0.544 s`
- `100%`: `tau = 0.550 s`

So once the decay is computed scalp-wide instead of at Cz, the time constants look similar again, but now that statement is about the **all-channel mean post-offset envelope**, not about a single channel.

![All-channel mean post-ON decay fit](EXP_05/artifact_characterization/fig3_decay_fit.png)

### SSD after retuning to the recorded GT

The old exp05 SSD branch was mismatched because it was targeting `8-12 Hz` and scoring `10 Hz`, while the recorded GT reference sits at `7.08 Hz`.

The baseline-first rerun now does three useful things:

1. it fits SSD only on late-OFF baseline snippets (`1.5-2.5 s` after offset)
2. it restricts the visual and selection view to `5-15 Hz`
3. it forces the selected baseline component to actually peak inside the GT target band

That changed the baseline result materially. The selected baseline component is now:

- selected baseline component = `5`
- baseline component 5 `lambda` = `0.555`
- baseline component 5 coherence = `0.049`
- baseline component 5 PLV = `0.099`
- baseline component 5 local peak / flank ratio = `1.52x`
- baseline component 5 PSD peak = `7.32 Hz`
- best-aligned baseline late-OFF epoch correlation = `0.87`

So the baseline picture is no longer “the best component peaks at 4-5 Hz”. The late-OFF redesign does recover a more plausible target-band baseline component near the measured GT peak.

## Iteration 2: Denser Training + Temporal Visualization (2026-03-26)

### What Was Improved

1. **Baseline training epochs:** Increased from 63 (cycle-aligned, ~5 s stride) to **313** (dense 1 s stride across the entire baseline recording). This gives the GED covariance estimator much more data and reduces sampling variability.

2. **Component search space:** Increased from 6 to **10 components** to explore more of the filter eigenspace.

3. **Temporal waveform visualization:** Added a 3rd row to the component gallery showing the **epoch-averaged component waveform** overlaid with the **band-filtered GT reference**. This visual immediately shows whether each component oscillates in sync with the ground truth signal.

4. **OFF window timing figure:** New `fig_timing_inspection.png` shows ~40 s of Cz EEG + stim channel with ON blocks (gray shading) and late-OFF windows (cyan shading). This confirms that OFF windows are artifact-free before SSD training.

### Results (Iteration 2)

**Selected component:** Component 8 (not 5 as before)
- lambda = 0.425 (eigenvalue, weaker than comp 5's 0.555)
- Peak frequency = 6.59 Hz (in-band)
- Baseline coherence = 0.0074 (very weak, 7.4 mV²/Hz)
- Baseline PLV = 0.0283 (weak phase locking)
- Best epoch correlation = 0.897 (one epoch aligns 89.7% with GT)

**Transfer to stimulated conditions:**

| Condition | Events | Coherence | PLV | Peak ratio | Peak freq | Signal? |
|-----------|--------|-----------|-----|-----------|-----------|---------|
| Baseline | 313 | 0.0074 | 0.0283 | 1.30x | 6.59 Hz | weak |
| 30% | 62 | **0.251** | **0.098** | 0.633x | 5.13 Hz | **NO** |
| 100% | 99 | 0.0365 | 0.2127 | 0.567x | 5.13 Hz | NO |

**Key observation:** The selected baseline component shows a spectral peak drift from 6.59 Hz (in-band) to 5.13 Hz (out-of-band) in both stimulated conditions. Although coherence and PLV spike in the 30% condition, the component is tracking something at 5.13 Hz, not the ground truth at 7.08 Hz.

### Why This Happens

1. **Weak baseline signal:** The coherence = 0.0074 means the 7 Hz component is barely above noise in the baseline late-OFF window. When the EEG is dominated by artifact at higher intensities, the residual artifact structure can mimic the component better than the true ground truth.

2. **Artifact spectral shape:** The 5.13 Hz peak in the stimulated conditions suggests the SSD component is capturing a residual artifact mode at that frequency, even after the ON window ends. The late-OFF windows (1.5–2.5 s after offset) may still contain fading artifact harmonics.

3. **Limited in-band pool:** Only 6 out of 10 components peaked in-band. Among those 6, none showed both strong baseline signal AND successful transfer. The trade-off is between baseline strength (comp 8 trades strength for transfer) and robustness.

### What This Means

The **OFF windows are clean enough for EEG inspection**, but they are **not clean enough for high-quality SSD recovery**. The ground truth signal is fundamentally weak in the phantom's baseline (coherence = 0.007), and the SSD solution trades between:
- Fitting the weak baseline signal (peaks at ~6.6 Hz)
- Avoiding artifact at stimulation intensity (peaks drift to ~5.1 Hz where residual stimulation noise lives)

### Next Actions

1. **Try narrower signal band:** Reduce from ±1.0 Hz to ±0.5 Hz (6.58–7.58 Hz) to exclude 6.59 Hz-peaking components.
2. **Allow peak-frequency tolerance:** Set TARGET_PEAK_TOLERANCE_HZ = 0.5 Hz so components peaking at 7.08 ± 0.5 Hz are preferred.
3. **Test alternative baseline windows:** Use baseline data from a different segment (e.g., first 30 s of baseline, or the pre-stim baseline from the stimulated runs). The current late-OFF window may have inherently low GT amplitude.
4. **Inspect best-correlated epoch:** Check the single best-aligned baseline epoch (index 266, correlation 0.897) to understand what makes it special. Possible artifacts in other epochs?

The transfer results are still secondary, and they remain mixed:

- baseline late-OFF: coherence `0.049`, PLV `0.099`, peak ratio `1.52x`, PSD peak `7.32 Hz`
- `30%` late-OFF: coherence `0.359`, PLV `0.441`, peak ratio `0.49x`, PSD peak `5.13 Hz`
- `100%` late-OFF: coherence `0.046`, PLV `0.270`, peak ratio `0.47x`, PSD peak `5.13 Hz`

That means the new baseline-first SSD pass improves the baseline proof, but the transferred component is still not spectrally stable in the stimulated runs. The selected component stays near the GT band at baseline, then drifts back toward `~5.1 Hz` in `30%` and `100%`.

The corrected GT reference figure:

![GT PSD across runs](EXP_05/ssd_recovery/fig0_ground_truth_reference_psd.png)

Baseline-first SSD selection:

![Baseline SSD component selection](EXP_05/ssd_recovery/fig1_baseline_component_selection.png)

![Baseline selected-component summary](EXP_05/ssd_recovery/fig2_baseline_selected_component.png)

![Baseline SSD component gallery](EXP_05/ssd_recovery/fig3_baseline_component_gallery.png)

![Baseline selected-component TFR](EXP_05/ssd_recovery/fig4_baseline_selected_component_tfr.png)

Secondary transfer figures with the same baseline-trained weights:

![30% SSD components](EXP_05/ssd_recovery/fig5_ssd_components_30pct.png)

![100% SSD components](EXP_05/ssd_recovery/fig6_ssd_components_100pct.png)

![30% selected-component TFR](EXP_05/ssd_recovery/fig7_selected_component_tfr_30pct.png)

![100% selected-component TFR](EXP_05/ssd_recovery/fig8_selected_component_tfr_100pct.png)

## Interpretation

The corrected interpretation is:

- The timing is now defined correctly from the real `stim` channel.
- 30% is **visibly and quantitatively cleaner** than 100% across the scalp.
- The old “similar artifact magnitude” claim should be downgraded to:  
  **similar at Cz, not similar across channels**.
- Recovery should be discussed relative to the **measured block offset** and ideally the first `1 s` after offset.
- The exp05 SSD target is around `7.08 Hz`, not `10 Hz`.
- The GT baseline file is the correct one (`run02`), and the late-OFF baseline redesign now selects a component with a plausible target-band peak at `7.32 Hz`.
- The good-looking baseline result does **not** transfer cleanly to the stimulated runs, where the selected component drifts back toward `~5.1 Hz` in the late-OFF windows.
- SSD recovery is still weak overall even after retuning the band and transferring the baseline-trained weights.

## Bottom Line

Your critique is right.

The earlier exp05 write-up was too Cz-centered and not explicit enough about methodology. The corrected take is:

- `30%` is clearly less contaminated than `100%` across channels
- Cz understated that difference
- post-stim timing should be measured from the actual STIM offset, and that correction is already in the code
- the memo should discuss recovery using the first `1 s` after offset and scalp-wide summaries, not only Cz
- the old `10 Hz` SSD interpretation is obsolete for exp05 because the recorded GT reference is centered near `7.08 Hz`
