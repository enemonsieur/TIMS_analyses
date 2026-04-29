# DATABASE: Table And Query Trust Standard

Use this standard when working with CSVs, spreadsheets, database tables, joins,
aggregations, or derived fields.

The core rule is the same as `DRIL.md`: if a table operation could create the
result being interpreted, drill one representative record through the operation
before trusting the summary.

## When To Propose A Table DRIL

Propose a table DRIL when:

- a join changes row counts
- a key is assumed unique but not checked
- filtering removes records used in a conclusion
- aggregation hides subject-level or trial-level variability
- a derived field changes units, bins, labels, or thresholds
- missing values are filled, dropped, or silently coerced
- the output looks plausible but the transformation path is unclear

Use this proposal:

```text
This is a good table DRIL candidate. Before trusting the aggregate, I should
trace one representative row through the join/filter/grouping logic, check row
counts, check duplicate keys, and show the exact output row.
```

## Required Checks

For each table transformation, state:

- source table names
- row count before the step
- key columns used
- whether the key is unique where uniqueness is assumed
- row count after the step
- records dropped, duplicated, or changed
- one representative input row
- the exact output row
- one edge case

## Minimum Table DRIL Shape

```text
Goal
Why it matters
Source tables and row counts
Concept 1: one row before the transformation
Checkpoint
Concept 2: execute the join/filter/aggregation
Checkpoint
Concept 3: show the output row and trust decision
Checkpoint
Final summary
```

## Trust Decision

End with one of:

- **Trust for this purpose**: row counts, keys, and edge cases are consistent.
- **Trust with limitation**: the operation is clear, but a known assumption
  remains.
- **Do not trust yet**: row loss, duplication, missingness, or unit conversion
  could explain the result.

Do not summarize a table result as evidence until this decision is explicit.

