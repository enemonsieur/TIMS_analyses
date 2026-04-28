---
type: report
title: Wiki Structure & Consistency Lint Report
date: 2026-04-23
scope: All wiki files, especially EXP08
---

# Wiki Lint Report

## Executive Summary

The TIMS wiki has **good structural consistency** across experiment files but suffers from **naming inconsistencies**, **fragmented documentation for EXP08**, and **jargon clarity gaps**. The main blockers are:

1. **MEMO naming convention not enforced** (MEMO_exp06 vs MEMO_EXP06 vs missing MEMO_EXP08)
2. **EXP08 target frequency not prominent in wiki** (hidden in API reference, not in main page)
3. **Method pages lack units and range explanation** (what is "broadband power"? what is ITPC scale?)
4. **Duplicate/fragmented EXP08 documentation** (wiki vs API reference may diverge)

---

## ✅ GOOD: Structural Consistency

### Experiment Wiki Pages
All experiment pages (EXP06, EXP07, EXP08) follow **identical structure**:
- Frontmatter (type, status, updated date, tags)
- Question
- Current Conclusion / What We Did
- Evidence (with links to supporting docs/scripts)
- Conflicts / Caveats
- Next Step(s)
- Relevant Methods (with [[wiki-links]])
- Relevant Papers (with DOI links)

**Verdict:** ✅ Highly consistent; enables easy navigation and understanding

### Method Wiki Pages
Method pages (SNR, ITPC, SSD, SASS, PLV) follow **consistent structure**:
- What It Measures
- Where It Helped
- Known Failure Modes
- TIMS Verdict
- Open Questions
- Relevant Experiments
- Relevant Papers

**Verdict:** ✅ Good; establishes clarity on role, limitations, and open problems

### Wiki Home
`wiki/home.md` provides excellent **narrative context**:
- Current Picture (status of each experiment)
- Biggest Unresolved Contradictions (explicitly acknowledges disagreements)
- Immediate Next Experiments
- Experiment Index
- Method Index

**Verdict:** ✅ Exemplary; prevents readers from landing in a single exp and losing project context

---

## ❌ CRITICAL: Memo Naming Convention Not Enforced

### Finding
Your memory specifies: **use MEMO_EXP## format** (all caps EXP) to keep results together.

### Current State
Files are scattered and inconsistently named:

**Root directory (./):**
- `MEMO_EXP06_pipeline_analysis.md` ✅ correct
- `MEMO_SNR_Selection_Results.md` (data, not EXP-keyed)
- `MEMO_exp06_artifact_propagation_summary.md` ❌ lowercase 'exp'
- `MEMO_exp06_sass_artifact_recovery.md` ❌ lowercase 'exp'
- `MEMO_component_selection_bias.md` (data, not EXP-keyed)

**docs/memos/ directory:**
- `MEMO_exp05_analysis.md` ❌ lowercase 'exp'
- `MEMO_exp05_5_2_ctbs_recovery.md` ❌ lowercase 'exp'
- `MEMO_exp06.md` ❌ lowercase 'exp' (but also referenced as `MEMO_EXP06.md` in wiki/experiments/EXP06.md)
- `MEMO_exp06_working_direction.md` ❌ lowercase 'exp'
- (no MEMO_EXP08.md — **MISSING** per memory inventory)

### Impact
- **Confusion:** EXP06 has both `MEMO_exp06.md` and `MEMO_EXP06.md`; unclear which is authoritative
- **Discoverability:** glob pattern `MEMO_EXP*` won't find lowercase variants
- **Missing:** MEMO_EXP08.md claimed complete in memory (status: completed 2026-04-22) but doesn't exist

### Recommendation
1. **Rename all memos to MEMO_EXP## format** (all caps) and move to standardized location (suggest `docs/memos/`)
   - `MEMO_exp06.md` → `docs/memos/MEMO_EXP06.md`
   - `MEMO_exp05_analysis.md` → `docs/memos/MEMO_EXP05_analysis.md`
   - etc.
2. **Create MEMO_EXP08.md** if the analysis summary exists (currently only have API reference)
3. **Update all wiki links** to point to renamed files
4. **Update memory inventory** to reflect actual file locations and status

---

## ❌ EXP08: Target Frequency Not Prominent in Wiki

### Finding
**Situation:** EXP08 uses 13 Hz as target frequency (not the 12.45 Hz from EXP06)

**Location of clarity:**
- ✅ **EXP08_API_REFERENCE.md** (Section 3.1, Notes): "Ground-truth frequency is 13 Hz (updated from 12 Hz)"
- ✅ **EXP08_API_REFERENCE.md** (Section 3.1): Signal band 12.5–13.5 Hz
- ❌ **wiki/experiments/EXP08.md**: No explicit mention of 13 Hz target

### Why This Matters
- Methods pages reference 12.45 Hz (e.g., SNR.md: "typically `12.45 Hz +/- 0.5 Hz`")
- Readers of the main EXP08 page won't know the target frequency
- Potential for confusion with EXP06 (12.45 Hz) vs EXP08 (13 Hz)

### Recommendation
Add to **wiki/experiments/EXP08.md**, early in the "Current Conclusion" section:

```markdown
## Current Conclusion

...existing text...

**Key Parameters:**
- **Target frequency:** 13 Hz (updated from 12.45 Hz in EXP06)
- **Signal band:** 12.5–13.5 Hz
- **View band:** 4–20 Hz (for SNR and SSD baseline)
```

---

## ❌ Methods: Jargon Not Explained with Units

### SNR.md
**Issue:** "broadband power" mentioned without units or explicit definition

**Current:**
> In the current TIMS wiki, SNR means target-band power divided by broadband power, typically `12.45 Hz +/- 0.5 Hz` over `4-20 Hz`.

**Better:**
> In the current TIMS wiki, SNR is the ratio of **power in the target band (µV²/Hz) to power in the broadband view band (µV²/Hz)**, computed via Welch PSD. Typical target band: `12.45 Hz ± 0.5 Hz`; view band: `4–20 Hz`. SNR > 2 indicates clean signal; SNR < 1 indicates artifact dominance.

### ITPC.md
**Issue:** No mention of scale or expected values

**Current:**
> Inter-trial phase coherence summarizes how consistently phase aligns across repeated events...

**Better:**
> Inter-trial phase coherence (ITPC) ranges from **0 (random phase) to 1 (perfect phase locking)** and quantifies how consistently phase aligns across repeated events. Values > 0.8 indicate strong phase locking; < 0.5 suggest artifact or noise contamination.

### SNR.md and other method pages
**Issue:** "artifact saturation" and "settle" used without defining the mechanism

**Better:** Add a brief note explaining what happens:
> **Artifact saturation** occurs when the stimulus-evoked artifact grows faster than linearly with stimulus intensity, eventually dominating the signal band and making SNR collapse (EXP06 shows this above 40% intensity).

---

## ⚠️ WARNING: EXP08 Documentation Fragmentation

### Finding
EXP08 documentation split across two files with different purposes:
- **wiki/experiments/EXP08.md** — narrative summary (400 words)
- **EXP08/EXP08_API_REFERENCE.md** — technical reference (435 lines)

### Risk
- Changes to one may not propagate to the other
- Readers may miss critical info (e.g., 13 Hz target) because it's only in the reference
- Reference is too long and technical for quick lookup; wiki is too brief for implementation

### Recommendation
Keep both but add a **forward link** in EXP08.md:
```markdown
## Detailed API Reference

For detailed information on available epoch files, function signatures, configuration, and quick-start templates, see [`EXP08_API_REFERENCE.md`](../EXP08/EXP08_API_REFERENCE.md).
```

And add a **back link** in API_REFERENCE.md header:
```markdown
For experiment design and high-level findings, see [`wiki/experiments/EXP08.md`](../../wiki/experiments/EXP08.md).
```

---

## ✅ GOOD: Cross-References and Links

### Strengths
- Wiki links use consistent `[[category/page|display text]]` format
- All experiment pages reference relevant methods
- Method pages link back to experiments where they apply
- Home page provides roadmap to all experiments and methods
- Evidence sections cite actual script filenames and paths

**Verdict:** ✅ Navigation is excellent

---

## ⚠️ WATCH: Contradictions Explicitly Documented

### Finding
wiki/home.md explicitly lists "Biggest Unresolved Contradictions":
- PLV vs SNR rankings (bias under synchronized artifact)
- SASS vs SSD relative story (selection-rule dependent)
- 30% intensity cleaner but not "clean"
- EXP04 sits between biology, fatigue, and residual artifact

### Verdict
✅ **Good:** Prevents readers from treating uncertainties as settled facts. However, consider adding version dates to each method's verdict, since the PLV/SNR contradiction suggests the wiki may evolve.

---

## Minor Issues

### Wiki Home — Outdated Reference
Line 17 references `MEMO_SNR_Selection_Results.md` at root level. This file exists but conflicts with the MEMO_EXP## naming convention. Once renamed, update the link.

### EXP07.md — Ground Truth Availability
Caveat notes: "Need to verify that ground_truth channel is present and aligned in the epochs file; if not, extract it separately from raw VHDR."

**Status:** Is this resolved? If so, remove or update. If not, flag as a blocker.

### Method Pages — Frequency Updates
SNR.md still references 12.45 Hz. Should explicitly note that EXP08 uses 13 Hz and the choice depends on experiment. Example:
> Typical band for EXP06: `12.45 Hz ± 0.5 Hz`. EXP08 uses `13 Hz ± 0.5 Hz` (ground-truth frequency). Always check the experiment page for the actual target frequency.

---

## Compliance with Memory Guidelines

### Memo Naming Convention ❌
**Rule:** use MEMO_EXP## format

**Status:** Not enforced. Multiple variants exist.

**Action:** Rename all memos, update links in wiki and memory inventory

### Clarity in Technical Writing ⚠️
**Rule:** explain jargon with concrete examples; use actual units

**Status:** Partially compliant. Wiki is clear on narrative flow but methods pages lack units/scales.

**Action:** Add units (µV, µV²/Hz, Hz) and expected ranges to methods pages

### Validation Metrics ✅
**Rule:** use both PSD and ITPC together; neither alone is sufficient

**Status:** Compliant. SNR.md and ITPC.md both note failure modes; home page recommends SNR + secondary ITPC.

### SKRIPT.md Code Standards ✅
**Rule:** follow SKRIPT.md hierarchy for analysis scripts

**Status:** Not directly evaluated (no SKRIPT.md linting done). EXP07 and EXP08 pages reference compliant scripts.

---

## Action Items (Priority Order)

### HIGH PRIORITY
- [ ] **Rename all MEMO files to MEMO_EXP## format** (uppercase), consolidate to `docs/memos/`
- [ ] **Create MEMO_EXP08.md** with analysis summary (or remove from memory inventory)
- [ ] **Add target frequency (13 Hz) to wiki/experiments/EXP08.md** main content
- [ ] **Update all wiki links** to memos after renaming

### MEDIUM PRIORITY
- [ ] **Add units and scales to methods pages** (SNR: µV²/Hz; ITPC: 0–1 scale)
- [ ] **Add forward/back links** between wiki/experiments/EXP08.md and EXP08/EXP08_API_REFERENCE.md
- [ ] **Update memory inventory** to reflect actual memo locations and status
- [ ] **Add version dates to method verdicts** (if wiki will evolve with contradictions resolved)

### LOW PRIORITY
- [ ] Resolve EXP07 ground-truth caveat (is it a blocker or resolved?)
- [ ] Update SNR.md to explicitly note EXP06 (12.45 Hz) vs EXP08 (13 Hz) choice
- [ ] Consider consolidating EXP08 documentation (wiki summary + API reference) into single unified document

---

## Summary Table

| Issue | Severity | Category | Status |
|---|---|---|---|
| MEMO naming inconsistency | HIGH | Naming/Organization | ❌ Broken |
| MEMO_EXP08.md missing | HIGH | Inventory | ❌ Missing |
| EXP08 target frequency not in wiki | MEDIUM | Clarity | ❌ Fragmented |
| Methods lack units/scales | MEDIUM | Clarity | ⚠️ Partial |
| EXP08 doc fragmentation | MEDIUM | Organization | ⚠️ Risk |
| EXP07 ground-truth caveat unresolved | LOW | Blocker | ⚠️ Unknown |
| Experiment wiki structure | - | Structure | ✅ Excellent |
| Method wiki structure | - | Structure | ✅ Good |
| Cross-references and links | - | Navigation | ✅ Excellent |
| Contradictions documented | - | Transparency | ✅ Good |

