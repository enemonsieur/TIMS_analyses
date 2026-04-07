# MEMO: exp06 Baseline SSD Intensity Check

## Context

### Latest Shared Information
- Latest relevant memo: none yet for exp06
- Inherited from repo-level decision context:
  - exp06 currently has QC-style exploratory outputs rather than a memo-backed decision chain
  - the baseline recording contains a visible narrowband target near 12.5 Hz
- New relative to that context:
  - a baseline-only SSD check was run to test whether the retained EEG channels support a strong 12.5 Hz separation
  - the selected SSD component aligns with the same posterior channels that dominate the raw 12.0-13.0 Hz channel ranking

### Goal
- Determine whether the exp06 baseline contains a strong enough narrowband oscillatory structure to justify SSD-based extraction.
- Record whether the selected SSD component is spatially consistent with the dominant raw channels.

### New Information
- The baseline-only SSD intensity check selected component 1 with peak frequency `12.451172 Hz`.
- The selected component has `target_vs_flank_ratio=279.330007`, which is a very strong within-band separation for this baseline recording.
- The top raw target-band channels and top SSD topography channels are the same five channels: `O2`, `P8`, `Oz`, `P4`, `O1`.

## Constraint

### Key Constraints
- Constraint 1: signal this memo is based on baseline only, not on transfer into stimulation or recovery windows.
- Constraint 2: metric the reported ratio compares the target band against flanks inside the `4-20 Hz` view band, so it should be read as a narrowband separation metric, not as a universal SNR.
- Constraint 3: method the current result comes from an exploratory script and should not yet be treated as a finalized component-selection policy for later exp06 analyses.

### Decision Space
- Current input state:
  - baseline BrainVision recording `exp06-baseline-gt_12hz_noSTIM_run01.vhdr`
  - retained EEG channels after excluding `stim`, `ground_truth`, `TP9`, `Fp1`, and `TP10`
- Target output state:
  - a clear decision on whether baseline SSD is promising enough to keep for exp06
- What blocks the path from input to output:
  - no memo-backed transfer test yet for non-baseline exp06 conditions
  - no explicit decision yet on whether future selection should prioritize target-band power, flank contrast, or GT agreement
- Which assumptions are currently load-bearing:
  - fixed `1.0 s` baseline windows are representative of the narrowband baseline rhythm
  - the posterior topography reflects the same baseline source seen in the raw channel ranking

### Actions Implemented

#### Action 1: Baseline channel scout around the target band
- Question: Which retained raw EEG channels carry the strongest baseline `12.0-13.0 Hz` power?
- Input: `exp06-baseline-gt_12hz_noSTIM_run01.vhdr`
- Transformation: compute raw-channel PSD in `4-20 Hz`, then rank channels by mean PSD in `12.0-13.0 Hz`
- Output: `EXP06/exp06_baseline_raw_channel_target_band_ranking.png`
- Key parameters / assumptions:
  - excluded channels: `TP9`, `Fp1`, `TP10`, plus `stim` and `ground_truth`
  - target band: `12.0-13.0 Hz`
  - view band: `4.0-20.0 Hz`
- Figure: `EXP06/exp06_baseline_raw_channel_target_band_ranking.png`
- Result:
  - top raw channels near the target band are `O2`, `P8`, `Oz`, `P4`, `O1`
- Local interpretation:
  - the baseline target rhythm is not diffuse; it is dominated by a posterior channel cluster

#### Action 2: Baseline SSD intensity check
- Question: Does SSD produce a component with strong 12.5 Hz concentration from the same baseline recording?
- Input: the same baseline recording, split into `319` fixed `1.0 s` windows spanning `2.0-321.0 s`
- Transformation:
  - build pseudo-events from fixed baseline windows
  - fit SSD with signal band `12.0-13.0 Hz` inside view band `4.0-20.0 Hz`
  - project component epochs and score components by mean target-band PSD
- Output:
  - `EXP06/exp06_baseline_ssd_intensity_component.png`
  - `EXP06/exp06_baseline_ssd_intensity_summary.txt`
- Key parameters / assumptions:
  - baseline window duration: `1.0 s`
  - first window start: `2.0 s`
  - stride: `1.0 s`
  - coverage: `319.0 s`, or `99.3%` of the recording
- Figure: `EXP06/exp06_baseline_ssd_intensity_component.png`
- Result:
  - selected component: `1`
  - selected peak frequency: `12.451172 Hz`
  - selected target mean PSD: `1.944161e-26 V^2/Hz`
  - selected flank mean PSD: `6.960087e-29 V^2/Hz`
  - selected target-vs-flank ratio: `279.330007`
  - top SSD topography channels: `O2`, `P8`, `Oz`, `P4`, `O1`
- Local interpretation:
  - the baseline SSD solution is strong, narrowband, and spatially consistent with the strongest raw target-band channels

## Trade-Off

### General Interpretation / Discussion
- This is a genuinely positive baseline result. The selected SSD component shows very strong 12.5 Hz concentration and does not look like an arbitrary spatial mixture detached from the raw data.
- The exact match between the top raw target-band channels and the top SSD topography channels supports the idea that SSD is recovering the same posterior baseline source rather than inventing a different channel pattern.
- The main caution is interpretation scope. This memo supports the statement that exp06 baseline SSD is promising. It does not yet support the stronger statement that SSD will remain equally clean or stable when transferred to stimulation or post-stimulation windows.

### Options / Next Actions
- Option 1: keep SSD as the baseline reference method for exp06.
  - Why it helps: the baseline separation is already strong and spatially coherent.
  - Trade-off: this still leaves transfer validity untested.
- Option 2: run one transfer check from baseline-trained SSD into the next exp06 condition of interest.
  - Why it helps: it answers whether the strong baseline component remains interpretable outside baseline.
  - Trade-off: requires choosing a condition and a component-selection rule before expanding scope.
- Option 3: tighten the scoring rule before transfer.
  - Why it helps: selection could combine target-band PSD with flank contrast or GT agreement.
  - Trade-off: adds method complexity before it is clear that the simple baseline result is insufficient.

## Decision

### Decision Needed
- Accept the exp06 baseline SSD result as strong enough to justify keeping SSD in the exp06 analysis path, while explicitly limiting the claim to baseline-only evidence.

### Precise Questions for Review
1. Should exp06 treat this baseline SSD result as sufficient justification to proceed with SSD-based transfer checks?
2. For the next exp06 step, should component selection remain based on target-band PSD alone, or should it require an additional contrast or GT-match criterion?
3. Should the next exp06 memo focus on one transfer condition, or stay baseline-only until the selection rule is finalized?
