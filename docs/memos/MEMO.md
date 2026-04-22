# MEMO Framework for TIMS Experiment Results

## XML Metadata (for reference; actual memos are markdown)

```xml
<memo_framework>
  <document_type>Experiment Results Memos (MEMO_EXP##)</document_type>
  <purpose>
    Report findings from a completed experiment: what was tested, what succeeded/failed, what constraints were revealed.
    Not for: diary entries, vague future work, over-engineered scaffolding.
  </purpose>
</memo_framework>
```

---

## Markdown Skeleton: Experiment Results (MEMO_EXP##)

Follow this structure for all experiment reports.

### Section: # [Title]

**Format:** `# MEMO_EXP##: [Descriptive Title]`

---

### Section: ## Abstract

**Purpose:** State the main finding upfront in 3–4 sentences. Lead with what succeeded/failed and why it matters.

**Structure:**
1. **Sentence 1:** What was tested? (e.g., “We tested whether we can recover a 12.45 Hz oscillation during and after iTBS at varying intensities”)
2. **Sentence 2–3:** What's the main finding? (e.g., “Recovery works in OFF periods at all intensities, but fails during stimulation above 40–50% intensity”)
3. **Sentence 4:** Why does this matter? (e.g., “Artifact saturation is electrode-specific, so a single decay model won't work”)

**Voice:** Terse, direct. Avoid padding. Lead with the result, not the method.

---

### Section: ## Introduction

#### Subsection: ### Background

**Purpose:** Explain what prior work led to this experiment. Reference specific earlier memos (exp03, exp05).

**Rules:**
- If a prior memo covers this background, reference it: “As shown in exp03, we learned that...”
- Do NOT re-explain fundamental concepts (TIMS, TMS, EEG basics) unless this is the first memo on the topic
- State the design change or new question that motivated this experiment

**Typical structure:**
1. What did prior experiments show?
2. Why did we change the approach for this one? (What new frequency, protocol, or question?)
3. One sentence on the transition to this experiment

#### Subsection: ### Why This Matters

**Purpose:** Explain the relevance to the larger research goal (real-brain translation).

**Rules:**
- One paragraph, 2–3 sentences max
- Explain why phantom validation is a prerequisite for human data
- End with the concrete research questions driving the experiment

#### Subsection: ### Research Questions

**Format:** Numbered list of 3 concrete questions.

**Rules:**
- Each question is one sentence, not a multi-part sentence with subquestions
- Use active voice: “Can we recover...?” not “Is it possible to...?”
- Questions should directly map to your Methods and Results sections

**Example:**
```
1. Is our 12.45 Hz signal strong enough and well-localized to use as a target?
2. Can we recover the signal after stimulation stops (OFF windows) across all intensities?
3. Can we recover the signal during active stimulation, and if not, at what intensity does it fail?
```

---

### Section: ## Methods

**Purpose:** Explain what you did, clearly but tersely.

**Rules:**
- Assume reader knows the field; don't explain SSD or ITPC in Methods
- Terse sentences. Avoid step-by-step pedagogy
- Group related methods into subsections (e.g., “Baseline SSD Reference,” “ON-State SSD Fitting”)
- For each subsection, write 2–4 terse sentences + a numbered list of specific steps if necessary

**Voice Example (from MEMO_EXP06):**
```
“In the baseline session, we built a spatial filter to extract the 12.45 Hz signal. 
We used SSD to find a weighted combination of the 28 electrodes that maximized power 
at 12.45 Hz relative to neighboring frequencies. The top five electrodes with the 
strongest natural 12.45 Hz power matched the SSD spatial pattern, validating that 
we isolated the true target signal.”
```

Not:
```
“In the baseline session, the following steps were performed:
1. Data was loaded from the vhdr file
2. Channels were preprocessed
3. A periodogram was computed...
[etc.]”
```

---

### Section: ## Results

**Purpose:** Present data, not interpretation. Let Discussion extract meaning.

#### Subsection Structure: One subsection per research question or major finding

**Rules for each subsection:**

1. **Heading:** Descriptive and decisive (e.g., “ON-State Recovery Fails at High Intensity,” not “ON-State SSD Results”)

2. **Finding sentence(s):** 1–2 sentences stating what you found. Terse.

3. **Table or Figure:** Present the core data
   - **If table:** Self-evident headers, actual units (µV, Hz, not percentages alone), no cryptic abbreviations
   - **Format:** Use markdown tables
   - **Figure caption:** Brief. One sentence on what the figure shows

4. **Interpretation sentence(s):** 1–2 sentences after the table/figure saying what it means
   - **Don't repeat the table; interpret it**
   - Example: “At 10–30% recovery succeeds; spectral peak at 12.45 Hz, ITPC 0.96–0.98. At 40–50%, recovery fails: the peak shifts to 10 Hz (a stimulation harmonic).”
   - **Don't hide assumptions:** “O2 shows high ITPC even at 40–50%, but this measures phase-locking to ground-truth, not spectral dominance. The power spectrum shows 10 Hz artifact dominates, not the 12.45 Hz target.”

5. **Figure placement:** Insert after the interpretation, not before. 
   - Format: `![description](path/to/figure.png)`

**Metrics Rule (Critical for oscillatory data):**
- Always report both **spectral power (PSD)** and **phase-locking (ITPC)**
- Define each metric in one inline sentence where it first appears
- Example: “Phase-locking (ITPC: inter-trial phase coherence) to the ground-truth channel was near ceiling (>0.998)”
- **Why both:** PSD reveals what frequency actually dominates the electrode; ITPC reveals whether phase locks. High ITPC + wrong frequency = failure

**Constraints are woven, not listed:**
- Don't create a “Constraints” section in Results
- Embed constraints naturally: “O2 stays clean through 30% then saturates 180-fold at 40%. O1 grows monotonically. Pz never saturates. After stimulation, clearing times at 40% range from 0.29 s (P4) to 1.34 s (O2)—a 4-fold difference. **Each electrode behaves differently; a single decay constant cannot fit all.**”

---

### Section: ## Discussion

#### Subsection: ### Summary of Findings

**Purpose:** Synthesize results into 2–3 clear, numbered statements.

**Format:** List 2–4 outcomes tied to your research questions
- Example from MEMO_EXP06:
  ```
  1. **Baseline**: Strong recovery (target-vs-flank = 279)
  2. **Late-OFF**: Robust across all intensities (ITPC > 0.998)
  3. **ON-state**: Intensity-dependent failure at 40–50% due to spectral peak shift
  ```

#### Subsection: ### Why [Key Finding]: Mechanism and Implication

**Purpose:** Explain the mechanism behind the primary failure/success.

**Rules:**
- One focused subsection per major constraint revealed
- Explain why the finding happened, not just that it happened
- Connect to implications for next steps
- Example: “At 40–50% ON intensity, SSD fails not because of a spatial masking problem, but because the raw O2 electrode's spectral peak has shifted from 12.45 Hz to 10 Hz. The artifact replaces the target in the raw data—**SSD cannot recover a signal that is no longer present.**”

#### Subsection: ### Constraints on Next Steps

**Purpose:** List 2–3 critical open questions that must be answered before advancing.

**Rules:**
- Use numbered format
- Each question should be answerable (not vague)
- Example:
  ```
  1. Have we tested alternative artifact removal methods (decay models, template subtraction, ICA) at 40–50% intensities?
  2. Is the 0.3 s onset window sufficient, or do transient artifacts linger beyond it in some channels?
  ```

#### Subsection: ### Implications for [Next Phase]

**Purpose:** State what must happen before the work can proceed.

**Rules:**
- Use numbered list of mandatory or high-priority steps
- Start each with a verb: “Artifact removal must...”, “Validate the...”, “Compare...”
- Connect each step to a specific finding or constraint
- Example:
  ```
  1. **Artifact separation before hypothesis testing.** Phantom shows recovery only with strong spatial/temporal constraints.
  2. **Comparison of multiple denoising approaches.** Test decay modeling and template subtraction in parallel.
  3. **Validation of windows.** Confirm 0.3 s adequately excludes transients and 1.5 s respects dynamics.
  ```

---

### Section: ## Conclusions

**Purpose:** Restate findings in 3–4 bullet points + one sentence on the path forward.

**Format:**
- Bullet list of core findings (copy from Summary if needed)
- Final sentence: “These findings justify [mandatory step] as a **prerequisite, not optional**, before [next phase] can advance.”

**Example ending:**
“These findings justify artifact separation modeling as a **prerequisite, not optional step**, before real-brain iTBS claims can be advanced.”

---

### Section: ## References

**Format:** Bulleted list of prior memos, data files, or external references.

**Example:**
```
- exp03 results: Pulse-centered phantom work showing post-pulse recovery
- exp05 results: Artifact separation analysis motivating target frequency redesign
- exp06 data: Two sessions (baseline and run02 with intensity sweep)
```

---

## Style and Voice Rules

### What to Avoid

- **No padding:** Don't explain concepts that are already clear from context. Don't add a standalone section to define metrics inline.
- **No passive voice:** “The signal was recovered” → “We recovered the signal” or “Recovery succeeded”
- **No verbose preambles before tables:** Don't say “Now we ask the harder question...”. Let the table speak.
- **No multi-paragraph interpretations of single tables:** Use 1–2 sentences max
- **No hidden assumptions:** State assumptions when they appear; revisit in Discussion
- **No standalone sections for obvious content:** If you're explaining something the data already shows, delete it

### What to Do

- **Lead with findings:** Abstract → Results → Discussion. Method comes second
- **Use tables for dense data:** Follow with 1-sentence interpretation
- **Explain mechanism, not just outcome:** Don't just say “it failed”; say why (spectral displacement, not spatial masking)
- **Quantify everything:** Use actual units (µV, Hz, seconds), not vague terms
- **Use strong verbs:** “The artifact replaces the target” not “The target is displaced by artifact”
- **Make constraints concrete:** “O2 saturates at 40%, P4 at 40% clears in 0.29 s while O2 takes 1.34 s” not “artifact dynamics are heterogeneous”

---

## Forbidden Patterns

❌ Standalone “Validation Metrics” section explaining PSD and ITPC  
✓ Define each metric inline where it first appears (one sentence)

❌ Lengthy Methods with step-by-step pedagogy  
✓ Terse 2–4 sentence summary + numbered list of key steps only

❌ Bullet-point breakdown of table findings  
✓ One terse summary sentence after each table

❌ “Future work is needed” or “More research would be valuable”  
✓ “Artifact removal is mandatory before real-brain testing” or concrete next step

❌ Re-explaining background from prior memos  
✓ “As shown in exp03...” or assume it's known

❌ Vague constraints like “the artifact is a limitation”  
✓ “O2 saturates at 40%, P4 at 50%—per-electrode removal required”

---

## Complete Example: MEMO_EXP06 Excerpt

This demonstrates the full structure applied:

```markdown
# MEMO_EXP06: Phantom Study on Brain Signal Recovery During Brain Stimulation

## Abstract

We tested whether we can recover a known 12.45 Hz oscillation during and after 
iTBS at varying intensities (10–50%).

**The main finding:** Recovery works in OFF periods (ITPC > 0.998 at all intensities). 
During stimulation, recovery succeeds at 10–30% but fails at 40–50% because the raw 
electrode's spectral peak shifts from 12.45 Hz to 10 Hz (a stimulation harmonic).

Worse, this saturation is electrode-specific: O2 saturates at 40%, O1 at 30%, Pz 
never saturates. Per-electrode artifact removal will be required.

## Introduction

### Background
[Reference exp03, exp05; explain why we changed target frequency to 12.45 Hz]

### Why This Matters
[Explain why phantom validation is prerequisite for human data]

### Research Questions
1. Is our 12.45 Hz signal strong enough and well-localized?
2. Can we recover the signal in OFF periods across all intensities?
3. Can we recover the signal during stimulation, and where does it fail?

## Methods

[Terse 2–4 sentence paragraphs for each method]

## Results

### Baseline SSD Reference is Strong and Posterior-Localized

The baseline SSD recovered the 12.451172 Hz target with peak-to-flank 
ratio 279.33 (power at 12.45 Hz is 279× neighboring frequencies).

[Table]

[Figure]

### ON-State Recovery Fails at High Intensity

Results of ON-state SSD fitting:

| Intensity | Spectral Peak | Peak-to-Flank | SSD ITPC | Raw O2 ITPC |
|-----------|---------------|---------------|----------|------------|
| 10%       | 12.45 Hz ✓    | 1.348         | 0.966    | 0.843      |
| ...       | ...           | ...           | ...      | ...        |
| 40%       | 10 Hz (artifact) | 0.675     | 0.500    | 0.996      |

At 10–30%, recovery succeeds: spectral peak at 12.45 Hz, ITPC 0.96–0.98. 
At 40–50%, recovery fails: the spectral peak shifts to 10 Hz (a stimulation harmonic), 
replacing the target. The high raw O2 ITPC (0.996–0.9995) is misleading—it measures 
phase-locking to ground-truth, not spectral dominance.

[Figure]

### Raw Artifact Is Spatially Heterogeneous

O2 stays clean through 30% then saturates 180-fold at 40%. O1 grows monotonically. 
Pz never saturates. Clearing times at 40% range from 0.29 s (P4) to 1.34 s (O2)—
a 4-fold difference. **Each electrode behaves differently; a single decay constant 
cannot fit all.**

## Discussion

### Summary of Findings
1. **Baseline**: Strong recovery (peak-to-flank = 279)
2. **OFF-state**: Robust at all intensities (ITPC > 0.998)
3. **ON-state**: Fails at 40–50% due to spectral peak shift from 12.45 Hz to 10 Hz

### Why SSD Fails at 40–50%: Spectral Displacement, Not Spatial Masking

SSD fails not because of spatial masking, but because the raw O2 spectral peak 
has shifted from 12.45 Hz to 10 Hz. The artifact replaces the target in the raw data—
**SSD cannot recover a signal that is no longer present.**

The high raw O2 ITPC is misleading: it measures phase-locking to ground-truth, 
not what frequency dominates the electrode. The power spectral density shows 10 Hz 
artifact dominates. **This is precisely why artifact removal must happen before 
real-brain testing.**

### The Artifact Is Spatially Heterogeneous

Different electrodes have different saturation thresholds, growth curves, and 
settling rates. No single decay constant can model all. Per-electrode artifact 
removal is necessary.

### Constraints on Next Steps

1. Have we tested alternative artifact removal methods (decay models, template 
   subtraction, ICA) at 40–50% intensities?
2. Is the 0.3 s onset window sufficient, or do transient artifacts linger beyond it?

### Implications for Human Brain Translation

1. **Artifact separation before hypothesis testing.** Phantom shows recovery only 
   with strong spatial/temporal constraints.
2. **Comparison of multiple denoising approaches.** Test decay modeling and template 
   subtraction in parallel.
3. **Validation of windows.** Confirm 0.3 s adequately excludes transients and 1.5 s 
   respects dynamics.

## Conclusions

- Baseline and OFF-state support robust recovery across all intensities
- ON-state recovery fails at 40–50% due to spectral peak shift to 10 Hz harmonic
- Artifact is spatially heterogeneous; per-electrode removal required

These findings justify artifact separation modeling as a **prerequisite, not optional 
step**, before real-brain iTBS claims can be advanced.

## References

- exp03: Pulse-centered phantom work showing post-pulse recovery
- exp05: Artifact separation analysis motivating frequency redesign
- exp06 data: Two sessions (baseline + intensity sweep)
```

---

## Checklist for Experiment Memos

Before finalizing:

- [ ] Abstract states main finding upfront (not just “we tested...”)
- [ ] Research questions are 3 concrete, numbered, 1-sentence each
- [ ] Methods are terse (2–4 sentences per subsection, no pedagogy)
- [ ] Each Results subsection has: heading + finding + table/figure + 1–2 sentence interpretation
- [ ] Metrics defined inline (PSD and ITPC both present, one sentence each)
- [ ] Constraints woven into findings, not listed separately
- [ ] Discussion explains mechanism, not just outcome
- [ ] “Constraints on Next Steps” section is 2–3 numbered questions
- [ ] Implications section starts with mandatory next steps (not “future work”)
- [ ] Conclusions are 3–4 bullets + one sentence on path forward
- [ ] No standalone sections explaining obvious concepts
- [ ] No padding, no passive voice, no verbose preambles
- [ ] All units stated explicitly (µV, Hz, seconds, not percentages alone)
