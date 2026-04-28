---
type: method
status: draft
updated: 2026-04-27
tags:
  - wiki
  - literature
  - research-workflow
---

# Literature Search Framework

This framework turns a research problem into search angles and paper notes. It is general: it can be used for a method, dataset, theory, clinical question, or experimental design problem.

The core idea is simple: do not search for topics. Search for papers that contain useful openings. A useful opening is a result, method, limitation, marker, or mechanism that helps solve the current research problem while respecting current constraints.

## 1. Define Goal, Advantages, And Constraints

Before searching, define the search target. This prevents collecting papers that are interesting but useless.

### 1.1 Goal

The goal is the research problem the literature search must help solve. It should name the real decision, not the papers to be found.

A good goal states what must be understood, tested, chosen, or ruled out. It should be specific enough that irrelevant papers are easy to recognize.

Example:

> The goal is to find a neural or behavioral model that can be tested in one person, so we can decide whether the protocol produces a meaningful effect.

For the current TIMS case:

> The goal is to identify a strong neural or behavioral marker that can show, within one subject or repeated sessions, whether TIMS is doing something interpretable.

### 1.2 Current Advantages

An advantage is any property of the current approach that could solve a limitation in existing work. It can come from the method, dataset, theory, model, population, measurement setup, or analysis strategy.

Do not list advantages as slogans. Translate each advantage into the kind of literature gap it should help find.

To define an advantage, ask two questions: what can the current approach do better or differently, and what limitation in the existing literature would that difference solve?

Advantage types include methodological, dataset, theoretical, mechanistic, and analytical advantages.

Examples:

- Methodological: TIMS may provide stronger rhythmic perturbation than weak-field stimulation. This points toward papers where weak rhythmic stimulation shows partial, variable, or state-dependent effects.
- Dataset: an N=1 repeated-session design may be strong for within-subject dose-response, even if it is weak for group statistics. This points toward papers with trial-rich markers and stable individual effects.
- Mechanistic: a theory may predict that response depends on baseline state. This points toward papers where pre-stimulation state, phase, or endogenous rhythm predicts the effect.

### 1.3 Current Constraints

A constraint is something the current approach cannot do, cannot assume, or cannot interpret safely. Constraints are defined before reading papers. They are not properties of the papers; they are the rules that decide whether a paper can be useful.

Constraints matter because they create second-order consequences. If the experiment cannot use many participants, then useful papers must contain within-subject evidence, repeated measures, strong markers, or large reversible effects. If artifact prevents online recording, useful papers must use post-stimulation windows, behavioral readouts, or markers that survive recovery. If a target is inaccessible, papers about that target may still be mechanistic background, but not direct experiment candidates.

A constraint can also transform the type of evidence to search for. For example, an N=1 constraint does not only mean "find a stable marker." It may also mean "find a response landscape that can be mapped within one subject," such as frequency, dose, phase, timing, task-state, or baseline-state dependencies.

To define a constraint, ask two questions: what can the current approach not do, and what second-order consequences follow from that limit?

Examples:

- Constraint: no large sample. Consequence: prioritize N=1-compatible markers, repeated sessions, dose-response, or clear within-subject state changes.
- Constraint: no reliable online neural recording during artifact. Consequence: prioritize post-stimulation effects, delayed markers, artifact-resistant readouts, or papers with explicit recovery logic.
- Constraint: a method cannot reach a deep target directly. Consequence: retain deep-target papers only if they reveal a mechanism transferable to an accessible target.

## 2. Generate Search Angles

A search angle is a precise sentence or prompt that can be given to an LLM or search engine. It is designed to retrieve papers that are indirectly linked to the goal but directly useful for solving the problem.

This is necessary because direct searches usually fail. If the goal is "find a neural marker for TIMS," a direct search will return broad TMS/tACS marker papers, generic reviews, or paradigms that only work under assumptions TIMS does not satisfy. The search angle must instead encode the first- and second-order consequences of the current advantages and constraints.

The point is to find papers where existing work reveals an opening: a stable marker that is underused, a promising effect that is too weak, a strong effect that is confounded, a method that fails for an informative reason, or a mechanism that suggests how to avoid the current constraints.

The framework user or FMK must research before finalizing angles. First scan enough papers, abstracts, reviews, and methods sections to understand the real gaps and opportunities. Then ask the user targeted questions to refine the angle. Do up to three back-and-forth rounds, or stop earlier when the goal, advantages, constraints, marker type, exclusion rules, and useful paper patterns are clear.

An angle must preserve the full research context, not just keywords. It should carry the proof question, the usable marker type, the constraints that remove attractive but unusable papers, and the specific kind of failure or opportunity that makes a paper useful. If the search sentence can be reduced to "find papers about this marker," it is not yet an angle.

### 2.1 Build The Angle

Build the angle by moving from the goal to indirect search logic:

1. State the decision the literature must help with.
2. Identify which advantage could solve a known limitation.
3. Translate each constraint into filters and consequences.
4. Look for papers where existing methods almost solve the problem but fail in a way that matters.
5. Formulate a search sentence that asks for both the useful effect and the limitation.

6. Validate the angle against a small online or database scan before treating it as final.
   - If the scan retrieves broad topic papers, revise the angle.
   - If it retrieves papers that violate constraints, add filters.
   - If it retrieves only failures with no useful mechanism, change the gap pattern.
   - If it retrieves one useful paper type, ask whether to narrow or broaden.

7. Ask the user refinement questions.
   - Round 1: confirm goal, proof target, and hard constraints.
   - Round 2: confirm marker families, paper types, and exclusions.
   - Round 3: confirm whether early scan results are useful enough to lock the angle.

Example for the current TIMS case:

Goal: find a marker that can show in one subject whether stimulation has an interpretable effect.

Advantage: TIMS may be stronger than weak rhythmic electric stimulation and less pulse-like than TMS.

Constraint: the marker must not require large-N behavior, suprathreshold MEPs, or clean online EEG during artifact.

Search angle:

> Find papers where rhythmic stimulation or perturbation shows a neural marker that is stable within subjects, but existing methods are limited by weak effects, sensory confounds, poor network fit, or state-dependence.

This angle should retrieve papers with indirect value: not "best neural markers for stimulation," but papers where the marker and method limitation together suggest a usable opening.

An alternative angle may search for an under-mapped response landscape rather than a stable marker:

> Find papers where rhythmic stimulation, sensory drive, or oscillatory perturbation reveals a neural marker whose response depends on frequency, phase, dose, baseline state, task epoch, or individual resonance, but where the response landscape is still incompletely mapped.

### 2.2 Angle Template

Use a causal template:

> Find papers where [method/intervention] manipulates [input], producing [specific marker/output] under [specific contrast], but interpretation or usefulness is limited by [gap], creating an opening for [current advantage] under [current constraints].

Generic example:

> Find papers where rhythmic stimulation manipulates frequency, phase, dose, or timing, producing a specific neural response under a sham, frequency, phase, state, or dose contrast, but interpretation or usefulness is limited by weak effects, variability, or incomplete response mapping.

Under-mapped response example:

> Find papers where a neural response is not simply present or absent, but depends on a controllable parameter such as dose, phase, state, timing, or individual resonance, making it useful for designing a within-subject response-mapping experiment.

### 2.3 Angle Quality Check

A good angle should retrieve papers that contain:

- A concrete effect, marker, method, task, or mechanism.
- A limitation or unresolved problem in the existing approach.
- A reason the current advantage is relevant.
- A constraint-aware filter.
- Searchable terms and paper categories.
- A route to either a stable marker or a map-able response landscape.

Reject the angle if it retrieves only broad topic papers, generic reviews, papers requiring impossible constraints, or papers with no interpretable marker or mechanism.

Bad retrieval patterns:

- Sensory-confound papers with no usable marker.
- Broad marker reviews with no experiment structure.
- Abstract-only papers presented as retained evidence.
- Papers where the marker cannot transfer to the current method, dataset, or target.
- Papers that explain cleanup, artifact suppression, or preprocessing but do not identify an experimental readout.

## 3. Structure Paper Outputs

The paper output should make the paper auditable. It should show why the paper is useful, what the authors actually did, what they found, and what limitation or mechanism matters for the search angle.

Do not lead with personal interpretation. Preserve the author's formulation first. Then state what the paper contributes to the search framework.

### 3.1 Paper Entry Fields

| Field | Purpose |
|---|---|
| Paper | Citation and link |
| Read status | Full text read, abstract only, methods checked, or result checked |
| Immediate relevance | Why the finding, method, or failure mode matters for the current goal |
| Key methodology | The minimal methodological details needed to judge the claim |
| Causal chain | What was manipulated, what changed, what marker captured it, and what contrast made it interpretable |
| Specificity check | The contrast showing whether the result means what the authors claim |
| Author result | The result as the authors state it, with metrics where available |
| Author limitation | What remains weak, variable, confounded, null, or unresolved |
| Author mechanism | The explanation proposed by the authors |
| Search angle supported | The angle this paper strengthens or weakens |
| Decision | Retain, background, or reject |

### 3.2 Immediate Relevance

Immediate relevance should explain why the paper belongs in the search result.

It should be based on the evidence structure, not the topic label.

Write this as three to four sentences. The block must explain which current goal the paper could help answer, why the paper's method/result structure matters, and what gap or opportunity it exposes. If relevance cannot be explained without hand-waving, reject or demote the paper.

Good:

> The paper is relevant because it uses a high-SNR recording method to test whether a weak external intervention produces a measurable physiological response.

Bad:

> The paper is relevant because it studies a famous brain region.

### 3.3 Key Methodology

Key methodology is not a methods summary. It is the set of design facts needed to judge whether the result is interpretable.

Write this as three to four sentences. Describe the causal setup in plain order: intervention or input first, recording/readout second, contrast third, and the design feature that makes the result interpretable or questionable fourth.

Include:

- What was manipulated.
- What was measured.
- When it was measured.
- What comparison made the result specific.
- What artifact, confound, or design limitation matters.

### 3.4 Causal Chain And Specificity

The causal chain replaces a loose marker/output label. It should state what was manipulated, what was measured, what changed, and why the contrast supports or weakens the claim.

The specificity check tells whether the marker supports the claim.

Ask:

- Is the output tied to the hypothesized mechanism?
- Is it frequency-, region-, timing-, dose-, task-, or state-specific?
- Did the intended marker change, or only a broad/non-specific signal?
- Is the result different from sham, baseline, control condition, or alternative model?

If specificity is absent, write that directly.

### 3.5 Author Result, Limitation, And Mechanism

Keep these separate:

- **Author result**: what happened.
- **Author limitation**: what did not work, remained uncertain, or weakened interpretation.
- **Author mechanism**: how the authors explain the result.

Write each as a three to four sentence block when the paper is retained. Embed short full-sentence excerpts or pinpointed sentences inside the block rather than listing isolated fragments. If only the abstract is available, label the entry `abstract only`; do not summarize it as retained evidence. If the paper looks highly relevant but the full text is missing, ask for the PDF.

### 3.6 Decision

Retain a paper if it improves at least one of these:

- the search angle,
- the marker choice,
- the experiment design,
- the constraint logic,
- the mechanistic model,
- the reject rules.

Reject or demote a paper if it is only topically related, only abstract-level, too generic, behavior-only without mechanism, or impossible to adapt under the current constraints.

Reject or demote a paper if it explains an artifact-control method but does not provide a usable experimental marker. A confound paper is useful only when the confound limits an otherwise relevant effect, not when the paper's main contribution is cleanup.
