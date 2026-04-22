# High-Level Pseudocode: Correcting SASS/SSD Separation

## File to Change
**`analyze_exp06_run02_on_raw_sass_ssd_plv.py`**

---

## Current State (Wrong)

The script has THREE paths, but SASS path contains SSD:
1. **Path A (Raw):** Select best raw channel by PLV at each intensity
2. **Path B (SASS+SSD hybrid):** Apply SASS → then eigendecompose cleaned data → rank by power ratio
3. **Path C (SSD):** Apply SSD to raw data → rank by power ratio

Problem: Paths B and C both use the second eigendecomposition criterion (power ratio), making them less distinct than they should be.

---

## Desired State (Correct)

1. **Path A (Raw fixed):** Select best raw channel at 10% intensity → use SAME channel for all intensities
2. **Path B (Pure SASS):** Apply SASS → output SASS-cleaned multichannel signal → rank ALL channels by PLV to GT, select best
3. **Path C (Pure SSD):** Apply SSD to raw data → rank top-N components by PLV to GT, select best

All three paths use **PLV to GT** as the final selection criterion (best alignment to ground truth).

---

## Pseudocode Changes per Section

### SECTION 3.4 (Raw Channel Selection)

**Current:**
```
FOR each intensity block:
    FOR each raw channel:
        compute PLV to GT
    SELECT channel with max PLV
```

**Correct:**
```
FOR intensity = 10% ONLY:
    FOR each raw channel:
        compute PLV to GT
    SELECT channel with max PLV → SAVE as REFERENCE_CHANNEL

FOR each remaining intensity block (20%, 30%, 40%, 50%):
    USE REFERENCE_CHANNEL (no re-selection)
    compute PLV to GT for this fixed channel
```

**Why:** Use the same electrode across all intensities to see how artifact contaminates it over increasing dose.

---

### SECTION 3.5 (SASS Path)

**Current:**
```
Apply SASS to ON vs late-OFF view-band data
    → sass_cleaned_concat (multichannel)

FOR each of top-6 eigenvalues of SASS-cleaned signal-band:
    extract component via spatial filter
    compute ON/OFF broadband power ratio
SELECT component with lowest power ratio
```

**Correct:**
```
Apply SASS to ON vs late-OFF view-band data
    → sass_cleaned_concat (multichannel)

FOR each SASS-cleaned channel (all n_channels, not top-6):
    compute PLV to GT
    compute peak frequency (power spectrum)

SELECT channel with max PLV to GT
```

**Why:** SASS outputs cleaned multichannel data. No secondary decomposition. Rank by direct GT correspondence (PLV), same as raw path.

---

### SECTION 3.6 (SSD Path)

**Current:**
```
Fit SSD on raw signal-band vs view-band covariances
    → top-6 components sorted descending

FOR each of top-6 components:
    apply spatial filter to ON raw data
    compute ON/OFF broadband power ratio
SELECT component with lowest power ratio
```

**Correct:**
```
Fit SSD on raw signal-band vs view-band covariances
    → top-6 components sorted descending

FOR each of top-6 components:
    apply spatial filter to ON raw data
    compute PLV to GT
    compute peak frequency (power spectrum)

SELECT component with max PLV to GT
```

**Why:** SSD is a separate pipeline from SASS. Use same selection criterion as both other paths (PLV to GT).

---

## Summary of Changes

| Aspect | Old | New |
|--------|-----|-----|
| **Raw selection** | Best channel per intensity | Best channel at 10%, fixed thereafter |
| **SASS path** | SASS + eigendecomp + power ratio | SASS + channel ranking by PLV |
| **SSD path** | Eigendecomp + power ratio | Eigendecomp + component ranking by PLV |
| **Consistency** | Asymmetric (PLV vs power ratio) | All three use PLV for final selection |

---

## Expected Outputs

For each intensity block, report:
- **Raw:** PLV, peak Hz, phase distribution (fixed channel from 10%)
- **SASS:** PLV, peak Hz, phase distribution (best channel per block)
- **SSD:** PLV, peak Hz, phase distribution (best component per block)
- **GT-vs-STIM:** PLV, peak Hz, phase distribution (reference)

All ranked by **direct GT phase locking**, not artifact suppression proxies.

---

## Code Locations to Modify

1. **Lines 176–229 (Section 3.4):** Add logic to store best channel from 10%, then reuse
2. **Lines 231–294 (Section 3.5):** Remove eigendecomposition; rank all SASS-cleaned channels by PLV instead
3. **Lines 296–346 (Section 3.6):** Change ranking from power ratio to PLV for all top-6 components
4. **Summary reporting (lines 369–400):** Update to reflect which channel/component was selected and why (PLV rank, not power ratio)
