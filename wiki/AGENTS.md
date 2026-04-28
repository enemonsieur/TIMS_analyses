# TIMS Wiki Agent Notes

This wiki is a minimal, LLM-maintained synthesis layer for the TIMS repo.

## Purpose

- Raw sources stay immutable.
- The wiki stores the current interpretation, open conflicts, and next steps.
- Contradictions are handled through a lint workflow, not a special folder.

## Allowed Structure

Only use these wiki surfaces in v1:

- `wiki/home.md`
- `wiki/experiments/` (includes experiment pages and related memos)
- `wiki/methods/`

Do not create `index.md`, `log.md`, `claims/`, `contradictions/`, `comparisons/`, `papers/`, or `dashboard/` unless the user explicitly changes the design later.

## Read Order

Before updating the wiki:

1. Read repo root [`readme.md`](../readme.md).
2. Read the latest relevant memo or summary in `docs/memos/` or the repo root.
3. Read [`home.md`](home.md).
4. Read the affected experiment and method pages.

Follow the repo-root `AGENTS.md` and local memo/script standards. The wiki does not override those repo rules.

## Page Rules

### Experiment Pages

Each page in `wiki/experiments/` should keep these sections:

- `Question`
- `Current Conclusion`
- `Evidence`
- `Conflicts / Caveats`
- `Next Step`
- `Relevant Methods`
- `Relevant Papers`

### Method Pages

Each page in `wiki/methods/` should keep these sections:

- `What It Measures`
- `Where It Helped`
- `Known Failure Modes`
- `TIMS Verdict`
- `Open Questions`
- `Relevant Experiments`
- `Relevant Papers`

## Update Rules

- Update the affected experiment page first.
- Update method pages only if the new source changes the interpretation of a method.
- Update `home.md` only if the current picture, biggest contradiction, or immediate next step changed.
- Keep contradictions inline under `Conflicts / Caveats` or `Known Failure Modes`.
- Do not create a new note type just to store one conflict.
- Prefer links back to repo evidence over copying long result tables into the wiki.
- Keep pages short enough to browse quickly in Obsidian.

## Operations

### Ingest

Use this prompt when a new validated result arrives:

`Ingest [source/result] into the wiki. Create or update method/experiment pages; ensure Query can retrieve it.`

Required reading order:
1. `wiki/home.md` — current picture and blockers
2. Latest relevant memo or `wiki/experiments/EXP##.md`
3. Affected `wiki/methods/*.md` pages

Update sequence:
1. **Create method page** (if new) or **update existing**: add validated pipeline, results table, limitations, operational prompts (Query + Ingest)
2. **Update experiment page**: link to new method, add evidence, update Next Step
3. **Update home.md**: add Status Update (date + one-liner), only if interpretation changed or blocker resolved
4. **Add to memory** (`memory/*.md`): save the validated constraints for next session

Ensure:
- Method page has Query prompt (ready to apply to new target)
- Method page has Ingest prompt (ready to update if result changes)
- Experiment page has Evidence links to repo code/plots
- home.md has link to new method
- Next step in home.md is unambiguous (new blocker or next experiment)

### Query

Use this prompt to apply validated method to new target:

`Answer from wiki/methods/[METHOD].md. Apply to [target]. Report: where it works, what constraints apply, what to do if blocked.`

Required reading order:
1. `wiki/methods/[METHOD].md` — validated pipeline, limitations, operational prompts
2. `wiki/home.md` — current blocker, intensity constraints, etc.
3. Memory (`memory/*.md`) — prior constraints and gotchas
4. Reference script in method page

Report:
- What the method does and why (from wiki)
- Constraints (intensity, channel quality, saturation points)
- Expected results on [target]
- If blocked, suggest next Ingest workflow to resolve

### Lint

Use this prompt for routine health checks:

`Lint the wiki for contradictions, stale conclusions, missing links, unsupported claims, and next experiments.`

Expected behavior:

- Look for contradictions between experiment and method pages.
- Look for stale conclusions superseded by newer memos or analyses.
- Look for unsupported statements that need repo evidence links.
- Look for missing cross-links between experiments and methods.
- Look for open questions that should be promoted to `home.md`.
- Look for literature gaps where a web search would materially help.

### Contradiction Lint

Use this stricter variant when you specifically want conflicts:

`Run a contradiction lint on the wiki. Find places where two pages imply different conclusions, where a metric disagrees with another metric, or where older claims were weakened by newer evidence.`

Expected behavior:

- Surface the conflict in the affected existing pages.
- Update `home.md` only if the conflict is one of the biggest active unresolved issues.

## Literature

- Keep literature inline in the affected experiment or method page.
- Use DOI links or standard markdown links.
- Only create a dedicated paper note later if one paper becomes central across multiple pages.
- If no paper has been linked yet, write `No linked papers yet.` rather than inventing citations.
