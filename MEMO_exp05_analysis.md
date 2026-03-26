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

The corrected SSD script starts OFF epochs at:

- measured block offset + `0.5 s`

and limits each OFF epoch so it stays inside the real measured OFF gap. Because the shortest measured OFF gap is `2.955 s`, the usable SSD OFF epoch becomes:

- `2.454 s`

The first SSD pass on exp05 was also aimed at the wrong frequency. The recorded `ground_truth` channel peaks at:

- baseline GT: `7.08 Hz`
- `30%` GT: `7.08 Hz`
- `100%` GT: `7.08 Hz`

So the rerun no longer assumes a `10 Hz` target. It measures the GT peak directly from the baseline GT recording and then uses:

- signal band = `6.08-8.08 Hz`
- PSD / noise view = `4-25 Hz`
- SSD training = **baseline GT only**
- SSD application = transfer the same baseline-trained weights to `30%` and `100%`

The SSD script also saves component-inspection figures that mirror the `plotSSD.py` layout:

- top row = SSD component 2D scalp pattern
- bottom row = mean component PSD across OFF epochs on a **log y-axis**
- `30%` and `100%` PSD panels also overlay the transferred **baseline reference PSD**
- separate TFR figures = **absolute log-power** inside the OFF epoch, cropped to the Morlet-safe time range

Figure 3 was also changed. It now shows:

- continuous coherence to GT
- local peak / flank ratio around the GT band
- component PSD peak frequency
- circular PLV plots from one sampled phase difference per GT cycle

Saved outputs now include:

- `fig0_ground_truth_reference_psd.png`
- `fig1_ssd_eigenvalues.png`
- `fig2_ssd_vs_gt.png`
- `fig3_recovery_metrics.png`
- `fig4_ssd_components_baseline.png`
- `fig5_ssd_components_30pct.png`
- `fig6_ssd_components_100pct.png`
- `fig7_ssd_component_tfr_baseline.png`
- `fig8_ssd_component_tfr_30pct.png`
- `fig9_ssd_component_tfr_100pct.png`

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

The rerun therefore does four things differently:

1. it centers the SSD around the measured GT peak (`6.08-8.08 Hz`)
2. it trains SSD once on the GT baseline and transfers those weights to `30%` and `100%`
3. it scores baseline on the full continuous GT-baseline run, and `30%` / `100%` on the measured OFF samples only
4. it replaces the old broad-band SNR with a **local peak / flank ratio**

The baseline-trained component selection stayed weak even after that correction:

- selected baseline component = `2`
- baseline component 2 coherence = `0.007`
- baseline component 2 PLV = `0.040`
- baseline component 2 local peak / flank ratio = `0.79x`
- baseline component 2 broad-view PSD peak = `4.15 Hz`

So this is **not** a wrong-baseline-file problem. The script is already using the correct GT baseline (`run02`), but the scalp projection of that GT is still weak.

Transferred OFF-window recovery metrics:

- baseline coherence `0.007`, PLV `0.040`, peak ratio `0.79x`, PSD peak `4.15 Hz`
- `30%` coherence `0.056`, PLV `0.223`, peak ratio `0.92x`, PSD peak `4.15 Hz`
- `100%` coherence `0.004`, PLV `0.283`, peak ratio `1.19x`, PSD peak `4.64 Hz`

So the retuned analysis changes the story in two ways:

- the old `10 Hz` SSD numbers should not be used anymore
- the transferred SSD still does **not** yield a clean scalp component that peaks near the GT band in the broad `4-25 Hz` view

That last point matters. The corrected TFRs are now absolute log-power, not baseline-normalized change maps, and they still do **not** show a convincing sustained `7 Hz` ridge. So the negative conclusion is real:

- the weak exp05 baseline SSD is not a plotting artifact
- it is not a wrong-baseline-file problem
- the recorded GT is simply not recovering as a strong scalp component here

The corrected GT reference figure:

![GT PSD across runs](EXP_05/ssd_recovery/fig0_ground_truth_reference_psd.png)

Baseline SSD selection and transferred recovery:

![Baseline SSD component selection](EXP_05/ssd_recovery/fig1_ssd_eigenvalues.png)

![Baseline-trained SSD source vs GT during OFF windows](EXP_05/ssd_recovery/fig2_ssd_vs_gt.png)

![Baseline-trained SSD recovery metrics](EXP_05/ssd_recovery/fig3_recovery_metrics.png)

Component PSD + topomap inspection with baseline-trained weights:

![Baseline SSD components](EXP_05/ssd_recovery/fig4_ssd_components_baseline.png)

![30% SSD components](EXP_05/ssd_recovery/fig5_ssd_components_30pct.png)

![100% SSD components](EXP_05/ssd_recovery/fig6_ssd_components_100pct.png)

Absolute-power OFF-epoch TFR inspection:

![Baseline SSD component TFR](EXP_05/ssd_recovery/fig7_ssd_component_tfr_baseline.png)

![30% SSD component TFR](EXP_05/ssd_recovery/fig8_ssd_component_tfr_30pct.png)

![100% SSD component TFR](EXP_05/ssd_recovery/fig9_ssd_component_tfr_100pct.png)

## Interpretation

The corrected interpretation is:

- The timing is now defined correctly from the real `stim` channel.
- 30% is **visibly and quantitatively cleaner** than 100% across the scalp.
- The old “similar artifact magnitude” claim should be downgraded to:  
  **similar at Cz, not similar across channels**.
- Recovery should be discussed relative to the **measured block offset** and ideally the first `1 s` after offset.
- The exp05 SSD target is around `7.08 Hz`, not `10 Hz`.
- The GT baseline file is the correct one (`run02`), but the selected component still peaks around `4-5 Hz` in the broad PSD view.
- The corrected absolute-power TFRs still do not show a strong sustained `7 Hz` band, so exp05 SSD recovery remains weak even after the rerun.
- SSD recovery is still weak overall even after retuning the band and transferring the baseline-trained weights.

## Bottom Line

Your critique is right.

The earlier exp05 write-up was too Cz-centered and not explicit enough about methodology. The corrected take is:

- `30%` is clearly less contaminated than `100%` across channels
- Cz understated that difference
- post-stim timing should be measured from the actual STIM offset, and that correction is already in the code
- the memo should discuss recovery using the first `1 s` after offset and scalp-wide summaries, not only Cz
- the old `10 Hz` SSD interpretation is obsolete for exp05 because the recorded GT reference is centered near `7.08 Hz`
