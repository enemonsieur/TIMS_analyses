# Answer style guide for coding responses

These instructions define the preferred answer structure and tone for coding-related responses in this repo.

## Core principle
- Lead with the answer.
- Keep reasoning short and relevant.
- Show concrete code or exact changes when useful.
- End with a short caveat, verification note, or next step.

## Good style
- Be direct, not chatty.
- Be structured, but not stiff.
- Prefer concrete guidance over theory.
- Keep fluff and repeated framing out.
- Give the reader something actionable fast.

## Default answer shapes

### Coding question or explanation
Use this when the user asks how something works, why something happens, or what a piece of code means.

```md
[Direct answer in 1-3 sentences]

[Brief explanation of the key reason or mechanism]

```language
[Minimal code example only if it helps]
```

[Short note: caveat, verification, or next step]
```

### Bug or traceback explanation
Use this when the user shows an error and wants the cause or fix.

```md
The error happens because `[root cause]`.

Fix:
```language
[Exact replacement line or block]
```

Why this works:
- [Short explanation]

Check next:
- [Concrete check 1]
- [Concrete check 2]
```

### Implementation request
Use this when the user asks for a feature, refactor, or new code path.

```md
Approach:
- [High-level structure]
- [Key decision or constraint]

Implementation:
```language
[Final code, patch, or the essential part]
```

Validation:
- [How to test]
- [Expected behavior]
```

### Code review
Use this when the user asks for a review or asks whether code is correct.

```md
Findings:
1. [Most important bug or risk]
2. [Next issue]
3. [Next issue]

Suggested fix:
```language
[Targeted patch or example]
```

Residual risks:
- [Untested area or assumption]
```

## Canonical template
When no more specific shape is a better fit, mirror this pattern.

```md
Short answer: [direct answer].

Why:
- [reason 1]
- [reason 2]

What to change:
```language
[minimal relevant code]
```

Notes:
- [edge case or caveat]
- [how to verify]
```

## Scope
- These rules apply to response structure and tone.
- They do not replace repo-specific implementation rules in `AGENTS.md`.
- If there is a conflict, follow `AGENTS.md`.
