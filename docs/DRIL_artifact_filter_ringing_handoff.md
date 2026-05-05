# DRIL Handoff: Why a Butterworth Filter Can Turn a Pulse Artifact Into Ringing

## Goal

Understand why a sharp TMS/EEG artifact can become a large oscillatory-looking signal after filtering.

This note is intentionally code-independent. It records the stable mechanism and the interpretation rules so the conversation can continue without relying on any specific script version.

## Core Mechanism

A causal IIR Butterworth filter does not compute each output sample from the current input alone.

Each new output depends on:

- the current input sample
- previous input samples
- previous output samples

That last part is the key. The filter has memory. A large artifact can enter the filter at one moment, then keep affecting later samples through the previous-output terms.

The practical consequence is:

> A sharp pulse can inject energy into the filter, and the filter can release that energy as ringing at the filter's preferred frequency.

For the 13 Hz bandpass case, the filter behaves like a resonator around 13 Hz. A huge pulse is not a 13 Hz brain rhythm, but after the filter it can produce a 13 Hz-looking waveform.

## The Filter Equation

For one second-order-section of an IIR filter, the causal recurrence can be written as:

```text
y[n] = b0*x[n] + b1*x[n-1] + b2*x[n-2] - a1*y[n-1] - a2*y[n-2]
```

Read in words:

> The current output equals weighted current/past inputs plus weighted previous outputs.

Symbols:

- `x[n]`: current input sample
- `x[n-1]`, `x[n-2]`: previous input samples
- `y[n]`: current output sample
- `y[n-1]`, `y[n-2]`: previous output samples
- `b0`, `b1`, `b2`: input coefficients
- `a1`, `a2`: feedback coefficients

The feedback terms are why the filter can keep ringing after the original artifact has passed.

SciPy's SOS implementation uses an equivalent state form:

```text
y[n] = b0*x[n] + z0
z0_next = b1*x[n] - a1*y[n] + z1
z1_next = b2*x[n] - a2*y[n]
```

This is the same idea: the filter carries state forward from one sample to the next.

## Left-To-Right Causal Processing

A causal filter processes samples left to right.

At processing step `n`:

- samples `0..n` have been transformed into output `y[0..n]`
- samples `n+1..end` have not been touched yet
- future samples cannot affect the present output

So causal filtering cannot create true pre-pulse ringing from a future pulse. It can only propagate pulse energy forward in time.

By contrast, a zero-phase forward-backward filter such as `filtfilt` runs the filter forward and backward. That can make pulse-driven ringing appear both after and before the pulse.

## Why Artifact Size Matters

The filter is approximately linear for these signals:

```text
filter(background + artifact) = filter(background) + filter(artifact)
```

So if the artifact gets bigger, the artifact-generated filtered output also gets bigger.

This is the important trust problem:

> If a large filtered oscillation scales with artifact size, it may be filter-created artifact, not neural signal.

In the DRIL run using the measured EXP08 artifact shape, the same 13 Hz filter was applied to three versions of the input:

```text
no artifact  = cleaned signal + 0% artifact residual
mid artifact = cleaned signal + 25% artifact residual
huge artifact = cleaned signal + 100% artifact residual
```

The filtered output scaled strongly with artifact size:

```text
no artifact:   filtered post-pulse peak about 37 uV
mid artifact:  filtered post-pulse peak about 1446 uV
huge artifact: filtered post-pulse peak about 5686 uV
```

The exact numbers depend on the selected raw pulse and cleaning parameters, but the mechanism does not change.

## What The DRIL Figures Were Showing

The most useful visual framing was:

1. Show the raw or cleaned input with the artifact region highlighted.
2. Show the filter's impulse response.
3. Show the output after SOS section 1.
4. Show the output after SOS section 2.
5. Freeze the causal filter at several sample indices:
   - left side already transformed into output
   - right side still raw future input
6. Keep y-limits around `-10..+10 uV` when the goal is to inspect non-artifact scale.

The point of clipping or zooming the y-axis is not to hide the artifact. It is to see what the filter is doing to the physiological-scale signal after the huge artifact has dominated the full scale.

## What Can And Cannot Be Trusted

Can trust:

- the filter has memory
- a sharp artifact can drive post-pulse ringing
- a narrow bandpass can make artifact energy look oscillatory
- a larger artifact can produce a larger filtered oscillation
- causal filtering only propagates the artifact forward in time

Cannot trust without validation:

- a post-pulse 13 Hz filtered waveform as neural evidence
- amplitude recovery after filtering if it scales with artifact size
- pre-pulse ringing from a zero-phase filter as physiological
- any filtered output unless an artifact-only or artifact-scaled control has been checked

## Interpretation Rule

Before interpreting a filtered post-pulse rhythm, ask:

```text
Could the filter have created this structure from the artifact alone?
```

If yes, the filtered signal is not evidence yet. It is an object requiring validation.

## Recommended DRIL Language

Use this framing in future discussion:

> The 13 Hz Butterworth bandpass is a causal IIR system with memory. A pulse artifact enters as a large sharp transient. The recurrence keeps part of that transient in the filter state. Because the filter is tuned around 13 Hz, the stored energy is released as a damped 13 Hz oscillation. If the artifact amplitude is increased while the background is held fixed, the filtered 13 Hz output also increases. Therefore a large filtered post-pulse oscillation can be created by artifact size and filter memory alone.

## Minimal Checkpoint

Key takeaway:

> A Butterworth IIR filter can convert a short high-amplitude artifact into a longer oscillatory output because previous outputs feed into future outputs.

Most likely confusion:

> The filter is not "finding" a real 13 Hz rhythm. It is applying a recurrence that can make artifact energy ring at the passband frequency.

Reformulation menu:

- show exact equation
- show one numeric sample
- show left-to-right causal processing
- compare no/mid/huge artifact inputs
- compare causal vs `filtfilt`
- focus on intuition
- focus on math
- focus on implementation
