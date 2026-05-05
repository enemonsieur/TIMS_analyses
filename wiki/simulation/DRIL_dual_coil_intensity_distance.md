---
type: dril
status: active
updated: 2026-05-01
tags:
  - simnibs
  - dual-coil
  - efield
  - intensity
  - distance-decay
---

# DRIL: Why Dual-Coil E-Field Scales With Current And Falls With Distance

## Goal

Explain two things for the saved Dual-Cz SimNIBS run:

1. Why changing coil current from `75 A` to `10%` current scales `magET` linearly.
2. Why `magET` falls with distance from Cz, and what that falloff looks like in the exported data.

## Why It Matters

The result should not be read as "75 A is just a label." In TMS/TI-style field modeling, the tissue E-field is driven by the **rate of change of current** in the coil. If current is scaled cleanly, the induced E-field scales cleanly too. Distance is different: distance decay is not a simple fixed percent drop, because the two-coil field geometry, coil orientation, tissue shape, and vector cancellation/addition all matter.

## Provenance

Source objects:

- Coil script: `simulation/two_coils.py`
- Combined mesh field: `simulation/sim_results/D60T10L8_dual_cz/combined/combined.msh`
- Extracted ROI/distance outputs: `simulation/sim_results/D60T10L8_dual_cz/combined/coil_midpoint_30mm_gm5mm/`
- Distance table used here: `gm_distance_0_6cm.csv`

Known setup:

- Peak coil current: `75 A`
- Frequency: `20,000 Hz`
- Coil placement: two coils centered on Cz, shifted `+40 mm` and `-40 mm` on local X
- Combined field: `ET = E1 + E2`, with coil 2 sign-flipped in the script before summing
- Reported ROI: 30 mm inward from projected Cz scalp point, snapped to GM, 5 mm GM sphere
- Saved ROI weighted mean: `19.486 V/m`

## Route

The route figure below is a DRIL view of the physics chain. Panels 1-3 are conceptual/numeric from the script parameters; panel 4 uses the measured distance bins exported from `gm_distance_0_6cm.csv`.

![Current scaling drives lower E-field at every distance](../../simulation/sim_results/D60T10L8_dual_cz/combined/coil_midpoint_30mm_gm5mm/dual_cz_dril_current_to_distance.png)

```text
75 A sinusoidal coil current
        |
        v
dI/dt = 2 * pi * current * frequency
        |
        v
changing magnetic field around the coils
        |
        v
induced E-field in tissue
        |
        v
E1 and E2 are vector-added
        |
        v
magET = length of the combined E-field vector
        |
        v
distance table: magET vs distance from projected Cz scalp point
```

## Concept 1: Why Current Has A Linear Relationship To V/m

### Plain Explanation

In this SimNIBS setup, the coil geometry and head model are fixed. The only thing we change is the coil current amplitude. A larger current amplitude creates a proportionally larger changing magnetic field. A proportionally larger changing magnetic field induces a proportionally larger electric field in tissue.

That is the reason `10%` current gives about `10%` E-field.

### Equation

Role: convert sinusoidal coil current into the maximum current-change rate used by SimNIBS.

```text
dI/dt = 2 * pi * I * f
```

Read in words:

`dI/dt` equals `2 pi` times peak current times frequency.

Symbols:

- `dI/dt`: maximum rate of current change, in A/s
- `I`: peak current, in A
- `f`: stimulation frequency, in Hz
- `pi`: 3.14159...

### Execute The Equation: Saved 75 A Run

```text
I = 75 A
f = 20,000 Hz

dI/dt = 2 * pi * 75 * 20,000
      = 9,424,777.96 A/s
```

Term contribution:

- `75 A` sets the amplitude of the current swing.
- `20,000 Hz` sets how fast the current oscillates.
- `2 * pi` converts sinusoidal cycles into angular rate.

### Execute The Equation: 10% Current

```text
10% of 75 A = 7.5 A

dI/dt = 2 * pi * 7.5 * 20,000
      = 942,477.80 A/s
```

Now compare:

```text
942,477.80 / 9,424,777.96 = 0.10
```

So `10%` current gives `10%` `dI/dt`.

### Execute The E-Field Scaling

Rule:

```text
new_E = old_E * new_current / old_current
```

Read in words:

The new E-field equals the old E-field times the current scaling factor.

For the 30 mm ROI:

```text
old_E = 19.486 V/m
new_current / old_current = 7.5 / 75 = 0.10

new_E = 19.486 * 0.10
      = 1.9486 V/m
```

So the expected 10% current ROI mean is:

```text
~1.95 V/m
```

### Minimal Sketch

```text
Current scale:       100%        50%        10%
Current:             75 A       37.5 A      7.5 A
dI/dt scale:         1.00       0.50        0.10
ROI magET:           19.49      9.74        1.95 V/m
```

### Checkpoint

Key takeaway: with fixed geometry and frequency, current intensity scales the E-field linearly.

Most likely confusion: distance decay is not the same thing as current scaling; current scaling changes the amplitude everywhere, while distance changes the spatial sampling of a non-uniform field.

Reformulation menu:

- too abstract
- show exact equation
- give a toy example
- slower / smaller steps
- focus on intuition
- focus on math
- focus on implementation
- rewrite more directly

## Concept 2: Why E-Field Falls With Distance

### Plain Explanation

The coil is a spatial source. Its magnetic field is strongest near the coil windings and weaker farther away. The induced E-field in the brain is therefore strongest close to the scalp area under the coils and weaker deeper or farther away.

But the falloff is not one clean formula like `1 / distance`. In our actual model, the field depends on:

- coil shape and turns,
- two-coil vector addition,
- distance from both coils,
- head/tissue geometry,
- conductivity boundaries,
- whether fields from the two coils add or cancel at a point.

So we do not assume a theoretical decay curve. We read the exported GM element table and summarize what the simulated field does.

### Rule

Role: summarize the exported distance profile.

```text
distance_from_Cz = Euclidean distance from projected Cz scalp point to each GM centroid
bin_mean_E = mean(magET values inside each 1 cm distance bin)
```

Read in words:

Each GM element has a distance from Cz and an E-field magnitude. We group elements by distance and average their `magET`.

Symbols:

- `GM centroid`: center point of one gray-matter mesh element
- `magET`: magnitude of the combined E-field vector, in V/m
- `bin_mean_E`: average E-field magnitude inside a distance bin

### Execute The Distance Summary: 75 A

Measured from `gm_distance_0_6cm.csv`:

| Distance from Cz | GM elements | Mean magET at 75 A | 95th percentile at 75 A |
|---:|---:|---:|---:|
| 2-3 cm | 6,872 | 26.220 V/m | 37.653 V/m |
| 3-4 cm | 20,017 | 15.396 V/m | 26.594 V/m |
| 4-5 cm | 50,777 | 9.815 V/m | 20.928 V/m |
| 5-6 cm | 73,923 | 7.271 V/m | 15.144 V/m |
| 6-7 cm | 89,534 | 7.002 V/m | 14.040 V/m |
| 7-8 cm | 115,722 | 5.922 V/m | 11.743 V/m |
| 8-9 cm | 128,418 | 5.185 V/m | 10.183 V/m |
| 9-10 cm | 179,734 | 4.435 V/m | 8.022 V/m |

The strongest drop happens early:

```text
2-3 cm mean = 26.220 V/m
3-4 cm mean = 15.396 V/m

drop = 26.220 - 15.396
     = 10.824 V/m

relative drop = 10.824 / 26.220
              = 0.413
              = 41.3%
```

From 2-3 cm to 5-6 cm:

```text
2-3 cm mean = 26.220 V/m
5-6 cm mean = 7.271 V/m

ratio = 7.271 / 26.220
      = 0.277
```

So by 5-6 cm, the mean field is about `28%` of the 2-3 cm bin.

### Execute The Same Distance Summary: 10% Current

Because current scaling is linear, each bin scales by `0.10`.

| Distance from Cz | Mean magET at 75 A | Expected mean magET at 10% |
|---:|---:|---:|
| 2-3 cm | 26.220 V/m | 2.622 V/m |
| 3-4 cm | 15.396 V/m | 1.540 V/m |
| 4-5 cm | 9.815 V/m | 0.982 V/m |
| 5-6 cm | 7.271 V/m | 0.727 V/m |
| 6-7 cm | 7.002 V/m | 0.700 V/m |
| 7-8 cm | 5.922 V/m | 0.592 V/m |
| 8-9 cm | 5.185 V/m | 0.519 V/m |
| 9-10 cm | 4.435 V/m | 0.444 V/m |

### Minimal Sketch

```text
75 A:
2-3 cm  | ########################## 26.2 V/m
3-4 cm  | ###############            15.4 V/m
4-5 cm  | ##########                  9.8 V/m
5-6 cm  | #######                     7.3 V/m
9-10 cm | ####                        4.4 V/m

10% current:
2-3 cm  | ##                          2.6 V/m
3-4 cm  | #                           1.5 V/m
4-5 cm  | #                           1.0 V/m
5-6 cm  | .                           0.7 V/m
9-10 cm | .                           0.4 V/m
```

### Important Plot Consequence

Our current whole-GM plot removes elements below `5 V/m`.

At 75 A:

```text
many GM elements are >= 5 V/m
```

At 10% current:

```text
all values are expected to be 10x smaller
```

So a `>= 5 V/m` threshold would hide nearly everything. For a 10% current visualization, use a threshold closer to:

```text
0.5 V/m or 1.0 V/m
```

### Checkpoint

Key takeaway: distance decay is measured from the simulated GM element table, and it falls steeply between about 2-6 cm from Cz.

Most likely confusion: the distance bins are Euclidean distance from projected Cz to GM centroids, not depth along the coil axis.

Reformulation menu:

- too abstract
- show exact equation
- give a toy example
- slower / smaller steps
- focus on intuition
- focus on math
- focus on implementation
- rewrite more directly

## Concept 3: What Does Not Change At 10%

### Plain Explanation

If both coils are scaled together from `75 A` to `7.5 A`, the field pattern should stay the same shape. Every vector field value is scaled by the same factor. The hot spots stay in the same anatomical places, but their values become 10x smaller.

### Rule

```text
E1_10pct = 0.10 * E1_75A
E2_10pct = 0.10 * E2_75A

ET_10pct = E1_10pct + E2_10pct
         = 0.10 * E1_75A + 0.10 * E2_75A
         = 0.10 * (E1_75A + E2_75A)
         = 0.10 * ET_75A
```

Read in words:

If both coil fields are multiplied by the same factor before summing, the combined field is just the original combined field multiplied by that factor.

### Numeric Example

Suppose one GM element has:

```text
E1 contribution = 12 V/m
E2 contribution = 8 V/m
combined value = 20 V/m
```

At 10%:

```text
E1 contribution = 1.2 V/m
E2 contribution = 0.8 V/m
combined value = 2.0 V/m
```

Same location, same addition logic, 10x smaller magnitude.

### Checkpoint

Key takeaway: if both coils scale together, the spatial pattern stays the same and the values shrink by the current factor.

Most likely confusion: if only one coil is scaled or the phase/sign changes, the spatial pattern can change because `E1 + E2` changes directionally.

Reformulation menu:

- too abstract
- show exact equation
- give a toy example
- slower / smaller steps
- focus on intuition
- focus on math
- focus on implementation
- rewrite more directly

## Final Summary

```text
75 A at 20 kHz:
  dI/dt = 9.425e6 A/s
  30 mm ROI weighted mean = 19.486 V/m

10% current:
  current = 7.5 A
  dI/dt = 9.425e5 A/s
  expected 30 mm ROI weighted mean = 1.949 V/m

Distance:
  2-3 cm mean = 26.220 V/m at 75 A
  5-6 cm mean = 7.271 V/m at 75 A
  9-10 cm mean = 4.435 V/m at 75 A

At 10%:
  multiply those by 0.10.
```

Operational rule:

```text
To estimate any 10% current field from the saved 75 A run:
  new_magET = saved_magET * 0.10

To estimate any current fraction:
  new_magET = saved_magET * fraction
```

Main caveat:

This works when both coils are scaled together and frequency, coil geometry, coil position, tissue model, and phase/sign convention stay unchanged.
