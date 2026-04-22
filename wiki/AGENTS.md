# TIMS Wiki Agent Notes

This wiki is a minimal, LLM-maintained synthesis layer for the TIMS repo.

## Purpose

- Raw sources stay immutable.
- The wiki stores the current interpretation, open conflicts, and next steps.
- Contradictions are handled through a lint workflow, not a special folder.

## Allowed Structure

Only use these wiki surfaces in v1:

- `wiki/home.md`
- `wiki/experiments/`
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

Use this prompt when a new source arrives:

`Ingest this source into the wiki. Update the affected experiment page, affected method pages, and home only if the current picture changed.`

Expected behavior:

- Read the source.
- Decide which experiment page owns it.
- Update method pages only if the source changes method interpretation.
- Add or revise evidence links.
- Preserve older conclusions only as caveats if they are now weakened.

### Query

Use this prompt for normal exploration:

`Answer this question from the wiki first, then pull in repo evidence and papers as needed. File back only durable conclusions.`

Expected behavior:

- Read the relevant wiki pages first.
- Pull in repo evidence only where needed.
- If the answer changes the durable interpretation, write it back into an existing page.
- Do not create a new page by default for one-off answers.

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
