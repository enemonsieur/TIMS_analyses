# Interactive Matplotlib Plotting Problem in explore_exp08_art_filtering.py

## Goal
Show an interactive MNE evoked plot for each intensity level during the loading loop,
pause for inspection, then continue to the next intensity.

## Symptom
Running `python explore_exp08_art_filtering.py` from the VS Code terminal produces:

```
UserWarning: FigureCanvasAgg is non-interactive, and thus cannot be shown
  (fig or plt).show(**kwargs)   # from mne/viz/utils.py:158
UserWarning: FigureCanvasAgg is non-interactive, and thus cannot be shown
  plt.pause(0.5)                # from the script itself
```

No window appears. The script runs to completion without ever showing a plot.

## Environment
- Python: `C:\Program Files\Python310\python.exe` (3.10.4)
- MNE: `C:\Users\njeuk\AppData\Roaming\Python\Python310\site-packages\mne`
- PyQt6: installed at same user site-packages location (`PyQt6\__init__.py` resolves correctly)
- PyQt5: NOT installed
- Available Qt backends for matplotlib: `qtagg`, `qt5agg` (no `qt6agg` string — it goes through `qtagg`)
- Terminal: VS Code integrated terminal

## What was confirmed working in isolation
Running this snippet directly in the terminal prints `backend: QtAgg`, `interactive: True`,
`canvas: FigureCanvasQTAgg` — i.e., the Qt stack is correctly wired up:

```python
import os
os.environ['QT_API'] = 'pyqt6'
import matplotlib
matplotlib.use('QtAgg')
import matplotlib.pyplot as plt
plt.ion()
import mne
print('backend:', plt.get_backend())        # QtAgg
print('interactive:', matplotlib.is_interactive())  # True
print('canvas:', type(plt.figure().canvas).__name__)  # FigureCanvasQTAgg
```

## What the script currently does (top of file)
```python
import os
from pathlib import Path
import warnings

os.environ.setdefault("QT_API", "pyqt6")  # noqa: E402
os.environ.setdefault("MPLBACKEND", "qtagg")  # noqa: E402
import matplotlib
matplotlib.use('QtAgg')
import matplotlib.pyplot as plt
plt.ion()

MNE_CONFIG_ROOT = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS")
(MNE_CONFIG_ROOT / ".mne").mkdir(parents=True, exist_ok=True)
os.environ.setdefault("_MNE_FAKE_HOME_DIR", str(MNE_CONFIG_ROOT))
import mne
```

And the plot call in the loading loop:
```python
epochs_on_all[intensity_pct].average(picks='all').plot(show=True)
plt.pause(0.5)
input(f"  [{label}] Inspect plot, then press Enter to continue...")
```

## Hypothesis
Despite the backend resolving to `QtAgg` and the canvas being `FigureCanvasQTAgg` in
isolation, the `mne.Evoked.plot()` call internally creates its own figure in a way that
bypasses the already-set interactive backend — possibly because:

1. MNE's `plot()` calls `mne.viz.utils.plt_show()` which checks `matplotlib.get_backend()`
   at call time and sees `Agg` — suggesting something between script start and the `.plot()`
   call is resetting the backend.
2. The VS Code terminal may inject a `MPLBACKEND=Agg` or `matplotlib_inline` setting via
   its Python extension after the process starts (but before the plot call), overriding our
   `setdefault`.
3. The `# noqa: E402` comments do not prevent the isort linter from reordering imports on
   save — the linter occasionally moves the `os.environ` lines to after the matplotlib import,
   breaking the ordering guarantee. This has been observed multiple times in this session.

## What to try
1. **Add `matplotlib.rcParams['backend'] = 'QtAgg'` after `plt.ion()`** — this is a
   second-layer override that persists through rcParams and is harder to reset.
2. **Check backend immediately before the `.plot()` call** by adding:
   ```python
   print("backend at plot time:", matplotlib.get_backend())
   ```
   to confirm whether the backend is being reset between import and the loop.
3. **Use `mne.viz.set_browser_backend('matplotlib')` if relevant** — some MNE versions
   route epoch/evoked plots through a separate browser backend.
4. **Try `epochs_on.average().plot(show=False); plt.show(block=False); plt.pause(0.5)`**
   — separating figure creation from display.
5. **Try running with `MPLBACKEND=qtagg python explore_exp08_art_filtering.py`** from
   a plain PowerShell window (outside VS Code) to rule out VS Code terminal interference.

## Working Strategy Used In `explore_exp08_pulse_artifact_removal.py`

Use plain Matplotlib for inline sanity plots:

```python
import matplotlib.pyplot as plt

fig, (ax1, ax2) = plt.subplots(2, 1, sharex=True)
ax1.plot(t, eeg_trace_uv)
ax2.plot(t, stim_trace)
plt.show()
```

Rules:
- Do not force `matplotlib.use("Agg")` in scripts that need visible windows.
- Do not use MNE `.plot(show=True)` for this quick sanity check; draw the arrays yourself.
- Put `plt.show()` immediately after the tiny sanity plot so the script pauses there.
- If a backend must be forced on this Windows setup, use `TkAgg` before importing `pyplot`.
