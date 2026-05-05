# Claude Code Guidelines for TIMS Project

## Collaboration Style
**Always work back and forth with the user — share open questions and outlines before writing implementation plans.**

Do not assume implementation details. Ask clarifying questions first to understand:
- What the user wants to accomplish and why
- Any ambiguous terminology or technical choices
- Existing patterns or conventions in the codebase that might apply

This prevents wasted effort on incorrect implementations and ensures alignment on approach.

## When Asking Questions
- Be specific and concrete (reference actual code, files, or parameters)
- Ask one or two focused questions at a time
- Explain what information you need and why it matters to the implementation

## When Writing Plans
- Share the plan (even if brief) before implementing
- Reference specific files, functions, and code locations
- Call out any assumptions or design decisions that could have alternatives

## Code Style for Analysis Scripts

- **Hard-code over parametrize.** If a value is fixed for the analysis (component index, channel name, frequency band), write it as a literal in the script. Do not introduce a constant, parameter, or selection function for it.
- **No "select best by reference metric" helpers.** Picking a component by its score against the very reference you are scoring against is circular and inflates the metric. Pick by definition (SASS = skip artifact components; SSD = take the largest eigenvalue component).
- **Inline scipy / numpy directly.** Do not wrap two-line operations (filter, flatten, hilbert, PLV, ITPC, SNR) in named helpers unless they are reused in three or more places.
- **Never use `filter_signal` from `preprocessing.py` in new scripts.** Use `scipy.signal.butter(..., output='sos')` + `sosfiltfilt` directly.
- **One helper per spatial-filter method, max.** SASS and SSD each get one tiny function that returns the demixing matrix; everything else (filtering, flattening, applying weights, scoring) is inline.
- **Plots are inline with `plt.show()`,** three lines max for the plot itself (comments don't count).
- **Target ≤ 100 non-comment lines** for analysis scripts.
