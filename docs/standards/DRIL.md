# DRIL: Drill-Down Explanation Standard

Use this standard when a result, method, function, equation, figure, or data
transformation is not yet understood well enough to trust.

DRIL means:

- **Define** the exact object and why it matters.
- **Route** the explanation through the right representation.
- **Isolate** one transformation at a time.
- **Loop** with checkpoints until the confusion is gone.

The goal is not a nicer explanation. The goal is to prevent false confidence.

## When To Propose A DRIL

Propose a DRIL when any of these are true:

- A function or method affects interpretation, but its mechanism is unclear.
- A plot shows a surprising result that could be an artifact of processing.
- A metric looks good but may be measuring the wrong thing.
- A helper hides a transformation that changes time, frequency, channel space,
  phase, amplitude, indexing, units, or averaging.
- A result depends on filtering, decomposition, fitting, thresholding,
  interpolation, smoothing, resampling, or baseline correction.
- The user asks "what is happening here?", "why does this happen?", "is this
  real?", or gives a rough explanation that needs correction.

Do not wait for the user to know the word "DRIL". If the situation matches,
offer it directly:

```text
This is a good DRIL candidate: the method transforms the data in a way that
could create the result we are interpreting. I propose we drill the raw input,
the exact equation, one numeric sample, and the before/after plot before using
this output as evidence.
```

If the user asked for an explanation, do the DRIL directly. If the user asked
for a script, analysis decision, or wiki conclusion, first propose the DRIL when
trust is not yet established:

```text
Before I treat this result as evidence, I would run a DRIL on the transformation
that creates it. The risk is that the method itself could generate the pattern.
The drill would use one raw input, one executed equation or rule, one numeric
sample, and one before/after figure. After that we can decide whether to keep,
change, or reject the method.
```

Do not use DRIL as a delay tactic. Use it when it would materially change the
trustworthiness of a result.

## Default DRIL Output Shape

Use this structure unless the user asks for a shorter answer:

```text
Goal
Why it matters
Concept 1
Checkpoint
Concept 2
Checkpoint
Concept 3
Checkpoint
Final summary
```

Keep the answer narrative, not fragmented. Explain one concept at a time. If the
answer becomes dense, stop after one concept and checkpoint before continuing.

Each checkpoint must contain:

```text
Key takeaway in one sentence.
Most likely confusion in one sentence.
Reformulation menu:
  - too abstract
  - show exact equation
  - give a toy example
  - slower / smaller steps
  - focus on intuition
  - focus on math
  - focus on implementation
  - rewrite more directly
```

## Non-Negotiable Rule: Execute The Transformation

For each concept, trace the transformation explicitly. Show how input values
become output values step by step. Do not summarize behavior without computing
it.

Every equation must be executed:

1. State the equation's role.
2. Show the equation.
3. Read it in words.
4. Define every symbol.
5. Compute at least one concrete numerical example.
6. Show each term's contribution.

Every concept must use multiple representations before moving on:

- plain explanation
- equation or rule
- numeric example
- minimal sketch or figure note

No abstraction jump is allowed until all four are present.

## Provenance First

Before explaining a transformation of data, verify what object is entering the
transformation.

Prefer the least-derived object that can answer the question:

1. raw source file and header
2. raw continuous trace
3. explicit slice by sample index
4. epoch
5. filtered array
6. averaged summary
7. metric table

If the lesson is about how a method changes data, do not start from a cached
epoch, processed array, report number, or helper output unless the user
explicitly asks for that representation.

For TIMS EEG/TMS data, state:

- source file or object
- channel(s)
- sample rate
- time window
- whether the signal is raw, filtered, epoched, averaged, or modeled
- what transformations have already happened

## DRIL Figure Rules

If the confusion is visual or temporal, make a figure. Follow
`docs/standards/DATAVIZ_FRAMEWORK.md`.

A DRIL figure should be claim-first and measured when possible:

- title states the mechanism or failure mode
- one panel shows the input
- one panel shows the executed transformation or equation terms
- one panel shows the output
- direct labels beat legends
- provenance note states whether the figure is raw, measured, simulated, or
  conceptual

For method forensics, prefer this package:

```text
Panel 1: measured input
Panel 2: one executed equation / rule / selection step
Panel 3: first transformed output
Panel 4: final output used for interpretation
```

## DRIL For Code

When a function is unclear, do not explain the whole file. Drill the smallest
causal path:

1. What object enters the function?
2. What are its shape, units, and assumptions?
3. What is the first non-trivial transformation?
4. What single row, sample, epoch, or channel can be computed by hand?
5. What object leaves the function?
6. What downstream interpretation depends on that output?

If the function hides a scientific choice, propose a DRIL before reusing it.

Example:

```text
Before trusting compute_itpc_timecourse(), we should DRIL one raw epoch through
the filter, Hilbert transform, phase extraction, and ITPC equation. The risk is
that high phase consistency may be filter ringing rather than recovery.
```

## DRIL For Scripts

Mirror this standard in script design when an analysis script contains a
load-bearing method. For full script rules, see `SKRIPT.md`.

A script-side DRIL should:

- answer one narrow question
- use explicit `Path(r"...")` inputs and explicit output directory
- read raw source data when the question is about transformations
- keep intermediate arrays needed for inspection
- save a claim-first figure and a numeric summary
- compare any manual implementation to the library implementation when possible

Use a script DRIL when:

- the method has memory, state, fitting, optimization, or hidden defaults
- the output could be created by preprocessing
- the result changes an experiment conclusion

Do not turn every analysis into a DRIL. Use it when trust is the problem.

## DRIL For Databases Or Tables

Mirror this standard in database work when a table, query, join, aggregation, or
derived field is not understood. For table-specific checks, see `DATABASE.md`.

A database DRIL should:

- name the source table and row count
- show one representative row before the transformation
- execute the join, filter, aggregation, or derived-field calculation on that row
- show the exact output row
- state what records are dropped, duplicated, or changed at each step
- check row counts after each join/filter/aggregation
- check whether join keys are unique on the side that is assumed to be unique
- test one edge case

Example:

```text
Before trusting this aggregate, DRIL one subject through the join and grouping
logic. Show the raw rows, the join keys, the grouped rows, and the final summary
value. Also show row counts before and after the join so duplicate keys or
silent record loss cannot hide.
```

## DRIL For Filtering And Signal Processing

Filtering is a default DRIL candidate because filters have memory.

For a filter DRIL, show:

1. the raw input trace
2. the filter equation or rule
3. one executed sample
4. the impulse response or equivalent ringing behavior
5. the final filtered signal
6. whether the filtered signal could have been generated by the artifact alone

Required interpretation check:

```text
Could the method have created the structure I am about to interpret?
```

If yes, the filtered output is not evidence yet. It is an object needing
validation.

EXP08 example:

```text
The 100% pulse is a sharp raw artifact. A narrow 11-14 Hz bandpass behaves like
a tuned resonator. The previous-output terms dominate the next output, so the
artifact rings after a forward pass. filtfilt runs the same resonator backward
and flips back, so ringing appears before and after the pulse.
```

## Quality Bar

A DRIL is good enough when a reader can answer:

- What exact object entered?
- What exact operation happened?
- Which input values produced which output values?
- Which term or rule did most of the work?
- What changed in the interpretation?
- What should no longer be trusted without validation?

A DRIL is not good enough if it only says:

- "the method smooths the data"
- "the filter removes noise"
- "the model fits the artifact"
- "the helper computes the metric"
- "the plot shows recovery"

Those are labels, not explanations.

## Self-Test Protocol For New DRIL Prompts

Before adding a DRIL prompt or rule to the repo, test it on three cases:

1. a signal-processing case, such as filtering or Hilbert phase
2. a script/function case, such as a helper with hidden assumptions
3. a table/database case, such as a join or aggregate

For each test, ask:

- Did the answer verify provenance first?
- Did it execute at least one equation or transformation numerically?
- Did it isolate one concept before moving on?
- Did it include a checkpoint?
- Did it identify what can no longer be trusted?

Revise the prompt until all three tests pass.

### Minimal Acceptance Examples

Signal-processing pass:

```text
The answer starts from raw source provenance, identifies the filter as the
transformation, executes one sample of the filter equation, shows which term
dominates, and states whether the filtered output can be trusted as evidence.
```

Script/function pass:

```text
The answer names the exact function and input object, follows one sample/channel
through the first non-trivial transformation, avoids explaining unrelated file
structure, and states what downstream conclusion depends on the function output.
```

Database/table pass:

```text
The answer names the source tables, row counts, join keys, one representative
input row, the exact joined or aggregated output row, row-count changes, duplicate
key checks, and one edge case.
```

## Drop-In Prompt Block

Use this block when asking an LM to do a DRIL:

```text
Apply DRIL.

Goal:
Explain the mechanism well enough that we can decide whether to trust the
output.

Rules:
- Verify provenance first. Start from the least-derived object that can answer
  the question.
- Explain one concept at a time.
- For each concept, show plain explanation, equation or rule, numeric example,
  and minimal sketch or figure note.
- Execute every equation or transformation with concrete values.
- Show how input values become output values step by step.
- Do not summarize behavior without computing it.
- If a method could create the result being interpreted, say that explicitly.
- End each concept with a checkpoint:
  Key takeaway; most likely confusion; reformulation menu.

Checkpoint reformulation menu:
- too abstract
- show exact equation
- give a toy example
- slower / smaller steps
- focus on intuition
- focus on math
- focus on implementation
- rewrite more directly
```
