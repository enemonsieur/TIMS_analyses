# MEMO: exp06 Run02 Late-OFF Artifact Filtering

## Context

### Latest Shared Information
- Latest relevant memo: [`MEMO_exp06_working_direction.md`](/mnt/c/Users/njeuk/OneDrive/Documents/Charite%20Berlin/TIMS/docs/memos/MEMO_exp06_working_direction.md)
- Inherited from that memo:
  - exp06 should be treated as a baseline-trained SSD recoverability test before broader interpretation
  - timing and transfer should be checked only after baseline SSD strength is established
  - spectral validity should be checked before support metrics such as phase-locking
- New relative to that memo:
  - the baseline-trained SSD filter was transferred into the measured late-OFF windows of `exp06-STIM-iTBS_run02.vhdr`
  - run02 contains five measured dose blocks when the STIM detector threshold is lowered from `0.10` to `0.08`, which is required to recover the first low-amplitude block
  - the transferred SSD component keeps the baseline `12.451172 Hz` peak across all five run02 dose blocks

### Goal
- Determine whether the saved baseline SSD filter remains spectrally valid in run02 late-OFF windows.
- Record whether the transferred SSD is more GT-locked than raw `O2` once spectral validity is confirmed.

### New Information
- The run02 STIM trace yields `100` measured ON blocks at `threshold_fraction=0.08`, corresponding to five `20`-cycle dose blocks.
- The transferred SSD component peak stays fixed at `12.451172 Hz` in all five run02 late-OFF blocks.
- Mean GT-locking is slightly higher for SSD than for raw `O2` in every run02 block:
  - `10%`: `0.998332` vs `0.997338`
  - `20%`: `0.998953` vs `0.997475`
  - `30%`: `0.999249` vs `0.997831`
  - `40%`: `0.999353` vs `0.997705`
  - `50%`: `0.999526` vs `0.998539`

## Constraint

### Key Constraints
- Constraint 1: `signal` the first run02 dose block is weaker than the later blocks, so the default global STIM threshold misses it and undercounts the run.
- Constraint 2: `metric` the phase-locking values are near ceiling for both raw `O2` and SSD, so the SSD advantage is real but numerically small.
- Constraint 3: `sequence` spectral validity still has to carry the main recoverability claim; GT-locking should only support that claim.

### Decision Space
- Current input state:
  - baseline SSD component 1 was already accepted as a strong `12.45 Hz` baseline reference
  - run02 contains the higher-intensity stimulation sweep with recorded `stim` and `ground_truth`
- Target output state:
  - a memo-backed decision on whether run02 late-OFF transfer supports the exp06 recoverability path
- What blocks the path from input to output:
  - if the first run02 block is missed, the dose structure is wrong before any transfer metric is interpreted
  - if the transferred component drifts out of band, phase metrics would become ambiguous again
- Which assumptions are currently load-bearing:
  - `threshold_fraction=0.08` is the correct run02 detector setting because it recovers the visually obvious first block without merging adjacent cycles
  - the run02 five-block order is the intended `10-20-30-40-50%` sweep

### Actions Implemented

#### Action 1: Recover the full run02 block timing
- Question:
  - Does the recorded run02 STIM trace really contain five measurable dose blocks?
- Input:
  - `exp06-STIM-iTBS_run02.vhdr`
  - recorded `stim` channel
- Transformation:
  - detect ON blocks directly from the raw STIM trace
  - lower the detector threshold from `0.10` to `0.08`
  - rebuild the late-OFF windows from the measured offsets
- Output:
  - `EXP06/exp06_run02_art_filtering_timing_windows.png`
- Key parameters / assumptions:
  - detector threshold fraction: `0.08`
  - late-OFF window: `1.5-3.2 s` after measured offset
  - cycle count per block: `20`
- Figure:
  - `EXP06/exp06_run02_art_filtering_timing_windows.png`
- Result:
  - run02 yields `100` measured ON blocks, or five `20`-cycle dose blocks
  - the final block contributes `19` valid late-OFF windows because the recording ends after the last ON block
- Local interpretation:
  - the earlier four-block readout was a detector-threshold artifact, not a property of the recording

#### Action 2: Check transferred spectral validity in run02 late-OFF
- Question:
  - Does the saved baseline SSD component stay centered on the baseline target frequency after transfer into run02 late-OFF?
- Input:
  - `EXP06/exp06_baseline_ssd_component1_weights.npz`
  - run02 late-OFF windows from the measured block timing
- Transformation:
  - epoch the run02 EEG in the `4-20 Hz` view band
  - apply the saved SSD filter directly to each late-OFF window
  - compute mean PSDs for GT, raw `O2`, and SSD
  - read the transferred SSD peak frequency inside the view band
- Output:
  - `EXP06/exp06_run02_art_filtering_psd_panels.png`
- Key parameters / assumptions:
  - signal band: `12.0-13.0 Hz`
  - view band: `4.0-20.0 Hz`
  - no SSD refit; the baseline weights are reused unchanged
- Figure:
  - `EXP06/exp06_run02_art_filtering_psd_panels.png`
- Result:
  - recovered SSD peak frequency is `12.451172 Hz` in `10%`, `20%`, `30%`, `40%`, and `50%`
- Local interpretation:
  - the transferred component is spectrally stable across run02 late-OFF instead of drifting away from the target band

#### Action 3: Compare GT-locking for raw `O2` and transferred SSD
- Question:
  - Once spectral validity is confirmed, is the transferred SSD more GT-locked than raw `O2` in run02 late-OFF?
- Input:
  - run02 late-OFF epochs for GT, raw `O2`, and transferred SSD
- Transformation:
  - band-pass all three signals in `12.0-13.0 Hz`
  - compute analytic phase with the Hilbert transform
  - compute time-resolved GT-locking from the phase difference
  - reduce each block to one mean GT-locking value
- Output:
  - `EXP06/exp06_run02_art_filtering_itpc_summary.png`
  - `EXP06/exp06_run02_art_filtering_summary.txt`
- Key parameters / assumptions:
  - GT-locking is treated as a support metric, not as the primary validity test
  - raw comparison channel: `O2`
- Figure:
  - `EXP06/exp06_run02_art_filtering_itpc_summary.png`
- Result:
  - SSD mean GT-locking is higher than raw `O2` in all five run02 blocks
  - the SSD-minus-raw advantage ranges from `0.000987` to `0.001648`
- Local interpretation:
  - SSD improves alignment with the recorded target, but the effect size is small because both signals are already near ceiling

## Trade-Off

### General Interpretation / Discussion
- This is the first positive transfer result in exp06 that stays interpretable under the memo sequence.
- The main reason it is interpretable is not the ITPC gain by itself. The main reason is that the transferred SSD component stays exactly on the baseline `12.45 Hz` target across all run02 late-OFF blocks.
- That means the small GT-locking advantage is not being earned by a spectrally wrong mode, which was the main failure pattern in the earlier exp05 transfer work.
- The remaining caution is effect size. Raw `O2` is already extremely GT-locked in run02 late-OFF, so the SSD improvement is consistent but modest. This supports artifact filtering, but it is not a dramatic separation result.

### Options / Next Actions
- Option 1: accept run02 late-OFF transfer as a positive recoverability result.
  - Why it helps:
    - it gives exp06 a memo-backed baseline-to-transfer success case
  - Trade-off:
    - the result is late-OFF only and does not yet address ON-window recovery
- Option 2: add one run02 ON-window transfer check next.
  - Why it helps:
    - it tests the harder artifact-filtering case directly
  - Trade-off:
    - ON interpretation is riskier because timing and artifact contamination are stronger
- Option 3: tighten the transfer memo around spectral stability as the primary claim.
  - Why it helps:
    - it keeps the exp06 claim aligned with the established memo sequence
  - Trade-off:
    - it intentionally downplays the near-ceiling ITPC result even though it is positive

## Decision

### Decision Needed
- Accept run02 late-OFF transfer as positive evidence that the saved baseline SSD filter remains spectrally valid and slightly improves GT recovery across the exp06 run02 dose sweep.

### Precise Questions for Review
1. Should exp06 treat this run02 late-OFF result as sufficient evidence to proceed to an ON-window artifact-filtering check?
2. Should the exp06 transfer claim be phrased primarily as spectral stability with supporting GT-locking, rather than as a phase-locking result?
3. Should the run02 detector threshold `0.08` now be treated as the fixed timing setting for exp06 stimulation runs, or should that still be revalidated per run?
