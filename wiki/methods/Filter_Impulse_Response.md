---
type: method
status: active
updated: 2026-04-28
tags:
  - filtering
  - impulse-response
  - artifact
  - dril
---

# Filter Impulse Response

## Operational Prompts

**Query (use this to apply to new target):**
```text
Answer from wiki/methods/Filter_Impulse_Response.md. Before trusting filtered
pulse-adjacent data, verify raw provenance, compute the filter impulse response,
compare causal vs zero-phase behavior, and report whether the filter could have
created the structure being interpreted.
```

**Ingest (use this if a new filter result changes interpretation):**
```text
Ingest into wiki. Update the affected experiment page, method page, and home if
the filtering result changes what can be trusted.
```

## What It Measures

Filter impulse-response analysis measures how much temporal structure a filter
itself creates after a sharp artifact. In TIMS pulse data, the relevant question
is not only "does the filter pass 13 Hz?", but "could the filter turn the pulse
artifact into the apparent 13 Hz signal?"

## Where It Helped

- [[experiments/EXP08|EXP08]]: one raw Oz 100% pulse was passed through the same
  Butterworth 10-16 Hz order-4 filter using causal `sosfilt` and zero-phase
  `sosfiltfilt`. Causal filtering kept pre-pulse RMS low (`1.67 uV`,
  -0.25 to -0.02 s), while `filtfilt` created large backward ringing
  (`151.38 uV` pre-pulse RMS).
- The same DRIL showed the wider 10-16 Hz band has lower Q
  (`Q = 13 / 6 = 2.17`) than the previous 1 Hz-wide 13 Hz filter
  (`Q = 13`), so its memory is shorter. It still rings after the pulse.

Evidence:
- Script: [`explore_exp08_causal_10_16_vs_filtfilt_dril.py`](../../explore_exp08_causal_10_16_vs_filtfilt_dril.py)
- Figure: [`exp08_causal_10_16_vs_filtfilt_dril_oz_100pct.png`](../../EXP08/exp08_causal_10_16_vs_filtfilt_dril_oz_100pct.png)
- Summary: [`exp08_causal_10_16_vs_filtfilt_dril_oz_100pct.txt`](../../EXP08/exp08_causal_10_16_vs_filtfilt_dril_oz_100pct.txt)

## Known Failure Modes

- **Zero-phase is not artifact-free:** `filtfilt` cancels phase delay by running
  the filter forward and backward. For pulse artifacts, this can smear artifact
  energy into the pre-pulse period.
- **Causal is not clean:** causal filtering avoids backward contamination, but
  still spreads artifact energy forward after the pulse.
- **Wider is not safe by itself:** a wider bandpass lowers Q and shortens memory,
  but the filtered output can still be dominated by filter memory.
- **Post-hoc masking can be insufficient:** masking only the visible pulse
  interval does not remove ringing that extends beyond the mask.

## TIMS Verdict

For EXP08 pulse-adjacent high-intensity data, causal 10-16 Hz filtering is more
interpretable than `filtfilt` because it preserves temporal direction: artifact
ringing remains after the pulse instead of being mirrored into the pre-pulse
period. It is not a cleanup method by itself. Any ITPC, PLV, or SNR computed on
filtered post-pulse data still needs impulse-response validation.

## Open Questions

- How long must the post-pulse exclusion window be for causal 10-16 Hz filtering
  at each intensity?
- Does the same causal 10-16 Hz result hold across all 20 pulses at 100%, not
  just the first 100% pulse?
- Should phase metrics be computed only after subtracting or modeling the raw
  pulse artifact rather than filtering it?
- Can Morlet/wavelet approaches reduce temporal contamination without creating a
  new impulse-response problem?

## Relevant Experiments

- [[experiments/EXP08|EXP08]]

## Relevant Papers

No linked papers yet.

