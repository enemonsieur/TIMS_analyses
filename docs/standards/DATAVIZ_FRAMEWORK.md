# DataViz Framework

Use this when deciding what scientific figure to make, why to make it, and how to edit it so the message is obvious.

## Purpose

- Start with the scientific claim, not the dataset.
- Choose figure types from the reader's task, not from software defaults.
- Build figures that can stand on their own in a paper, slide, poster, or report.
- Default to clarity over decoration. Do not trust defaults.

## Exploratory TIMS/EEG Stage

- In first-pass exploratory TIMS/EEG analysis, the goal is often to inspect signal quality, timing, channel behavior, and obvious anomalies before deciding what the real figure should say.
- At this stage, prefer trusted library-native inspection over custom-designed figures.
- In this repo, exploratory TIMS/EEG plotting should usually begin with MNE-native views such as:
  - raw traces
  - channel inspection
  - epoch images
  - simple evoked views
  - topomaps only when the spatial question is already clear
- Exploratory figures may be plain. Their job is inspection, not polished communication.
- Custom figure design should follow only after the message is stable.

## 1. Start With The Claim

Write one sentence before choosing a figure:

- What should the reader understand immediately?
- What comparison, pattern, mechanism, or tradeoff matters?

Bad:

- "Show the data."
- "Visualize the results."

Good:

- "Condition A produces a larger effect than condition B."
- "Performance improves with depth, but focality worsens."
- "The effect is localized in time and frequency."

Exploratory inspection exists to determine what the valid strong claim actually is.

If you cannot write the claim in one sentence, the figure is not ready.

## 2. Split The Story Into 1 To 3 Figures

Most scientific results need a small figure package, not one overloaded panel.

- Figure 1: orientation
  - setup, task, geometry, anatomy, or pipeline
- Figure 2: primary evidence
  - the main comparison or pattern
- Figure 3: qualification
  - uncertainty, controls, spatial context, or tradeoff

One visual should answer one main question.

## 3. Choose The Chart Family From The Scientific Task

| Scientific task | Best chart families |
|---|---|
| Explain a mechanism or pipeline | Schematic, process diagram, annotated geometry |
| Compare conditions or groups | Dot plot, paired dots, slope plot, box/violin |
| Show change over a continuous axis | Line plot |
| Show a relationship or tradeoff | Scatter plot, fit line, contour |
| Show a spatial pattern | Map, topomap, surface, field map, contour |
| Show multivariate structure | Heatmap, matrix plot |
| Show a full distribution | Histogram, ECDF, swarm, strip, violin |
| Show dynamics or state space | Trajectory plot, phase plot, parameter sweep |

Choose from the task first. Styling comes later.

## 4. Match The Figure To The Data Shape

| Data shape | Usually use |
|---|---|
| Categories | Dot plot, box/violin, paired dots |
| Continuous x-axis | Line plot |
| 2D matrix | Heatmap |
| Spatial coordinates | Map, contour, surface |
| Network | Node-link or adjacency view |
| Trajectories | Path or state-space plot |
| Repeated measures | Paired dots, slope plot, uncertainty bands |

This prevents habit-driven chart choices.

## 5. Choose The Companion Figure Immediately

Many figure types are strong for one job and weak for another. Pair them on purpose.

- Spatial map: good for where, weak for exact comparison
  - pair with ROI summary or profile plot
- Heatmap: good for pattern, weak for precise values
  - pair with a band, window, or region summary
- Line plot: good for time course, weak for spatial context
  - pair with a map, layout, or endpoint summary
- Schematic: good for mechanism, weak for evidence
  - pair with the actual result figure

Do not ask one panel to do every job.

## 6. Draft Before You Polish

Before editing details, answer these five questions:

1. What is the one message?
2. What should the eye see first?
3. What comparison should the reader make?
4. What can be removed without hurting the message?
5. What companion figure is needed?

If these are unclear, revise the figure choice before polishing.

## 7. Edit The Figure With Intent

### Title

- Use a takeaway title, not a topic label.
- Bad: "Results"
- Better: "Condition A increases late activity over posterior sensors"

### Labels

- Label lines, regions, peaks, or groups directly when possible.
- Use legends only when direct labels would be messy.

### Attention

- Highlight the key contrast.
- Keep comparison baselines and context visually quiet.

### Clutter

- Remove unnecessary gridlines, borders, decorative color, 3D effects, and redundant ticks.
- Do not trust defaults from plotting libraries.

### Scale And Ordering

- Use axis limits and scales that make comparisons honest.
- Order categories meaningfully, not alphabetically by habit.

### Uncertainty

- Show uncertainty when it matters to interpretation.
- Make it readable and label what it represents.

### Medium

- Adapt the figure to paper, slide, poster, screen, or grayscale print.
- A figure that works on a laptop can fail on a slide.

### Status

- Make clear whether the figure is conceptual, simulated, or measured.

## 8. Scientific Adequacy Check

Before finalizing, ask:

- Does this figure show the claim, not just the dataset?
- Does it hide variability that matters?
- Does it collapse dimensions the reader needs?
- Is it adapted to the delivery medium?
- Can someone understand it without hearing you explain it live?

## 9. Default Deliverable Pattern

When in doubt, build this package:

- Orientation figure
  - setup, task, pipeline, anatomy, or geometry
- Primary evidence figure
  - the main result using the best chart family for the task
- Qualification figure
  - uncertainty, controls, context, or tradeoff

## References

- Storytelling with Data: claim-first framing, focus, and decluttering
  - https://www.storytellingwithdata.com/books
- From Data to Viz: chart selection from task and data shape
  - https://www.from-data-to-viz.com/
- PLOS "Ten Simple Rules for Better Figures": audience, message, medium, and default skepticism
  - https://journals.plos.org/ploscompbiol/article/file?id=10.1371/journal.pcbi.1003833&type=printable
