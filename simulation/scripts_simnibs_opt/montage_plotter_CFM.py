# montage_plotter_CFM.py
"""Helper functions to load Starstim montages and visualize 2‑D electrode layouts using proven code logic.

Features:
1. Build a DigMontage directly from Starstim CSV positions (mm → m).
2. Direct 2D plotting that preserves channel order, intensity normalization, and colormap.
3. Exportable figure handles for saving or further customization.
"""
from __future__ import annotations
from pathlib import Path
from typing import Sequence, Tuple
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib import cm, colors as mcolors
import mne



def build_starstim_montage(
    csv_path: Path,
    coord_frame: str = "head",
) -> mne.channels.DigMontage:
    """
    Create a DigMontage from a Starstim CSV file:
    CSV columns: tag,x,y,z,name (mm)

    Returns
    -------
    montage : DigMontage in metres
    """
    df = pd.read_csv(csv_path, header=None,
                     names=["tag","x","y","z","name"] )
    # Convert mm → m
    ch_pos = {row.name: (row.x/1000, row.y/1000, row.z/1000)
              for row in df.itertuples()}
    return mne.channels.make_dig_montage(ch_pos=ch_pos,
                                         coord_frame=coord_frame)


# montage_plotter_CFM.py
"""Helper functions to load Starstim montages and visualize 2‑D electrode layouts using proven code logic.

Features:
1. Build a DigMontage directly from Starstim CSV positions (mm → m).
2. Direct 2D plotting that preserves channel order, intensity normalization, and colormap.
3. Exportable figure handles for saving or further customization.
"""


def build_starstim_montage(
    csv_path: Path,
    coord_frame: str = "head",
) -> mne.channels.DigMontage:
    """
    Create a DigMontage from a Starstim CSV file:
    CSV columns: tag,x,y,z,name (mm)

    Returns
    -------
    montage : DigMontage in metres
    """
    df = pd.read_csv(csv_path, header=None,
                     names=["tag","x","y","z","name"] )
    # Convert mm → m
    ch_pos = {row.name: (row.x/1000, row.y/1000, row.z/1000)
              for row in df.itertuples()}
    return mne.channels.make_dig_montage(ch_pos=ch_pos,
                                         coord_frame=coord_frame)

def plot_montage_topo(
    montage: mne.channels.DigMontage,
    names: Sequence[str],
    values: Sequence[float],
    norm: mcolors.Normalize,
    cmap: cm.Colormap,
    threshold: float = 0.005,
    figsize: Tuple[float, float] = (6, 6),
    font_size: int = 7,
    marker_size: int = 120,
    show: bool = True,
) -> Tuple[plt.Figure, plt.Axes]:
    """
    Plot a cleaned 2D topomap using MNE's layout, overlaying value-based intensities.

    Parameters
    ----------
    montage : mne DigMontage with .get_positions()['ch_pos']
    names   : List of electrode names to highlight
    values  : List of values corresponding to `names`
    norm    : Matplotlib normalization (e.g. TwoSlopeNorm)
    cmap    : Colormap (e.g. cm.seismic)
    threshold : Float, values below are greyed
    figsize : Tuple, figure size
    font_size : Int, size of text labels
    marker_size : Int, size of electrode dots
    show : Bool, whether to call plt.show()

    Returns
    -------
    fig, ax : Matplotlib figure and axis
    """
    fig = plt.figure(figsize=figsize)
    ax = fig.add_subplot(111)

    # Plot base montage to access projection geometry
    mne.viz.plot_montage(
        montage, kind="topomap", show_names=False,
        axes=ax, show=False
    )

    # Remove default visuals
    ax = fig.axes[0]
    for coll in list(ax.collections):
        coll.remove()
    for txt in list(ax.texts):
        txt.remove()

    # Build lookup from montage
    pos = montage.get_positions()['ch_pos']
    positions = {ch: coords for ch, coords in pos.items() if len(coords) == 3}

    value_dict = dict(zip(names, values))

    # Overlay electrodes
    for ch_name, (x, y, z) in positions.items():
        if ch_name in value_dict:
            val = value_dict[ch_name]
            color = cmap(norm(val))
            text_color = "black"
            if abs(val) < threshold:
                color = (0, 0, 0, 0.1)
                text_color = (0, 0, 0, 0.0)
            ax.scatter(x, y+0.015, color=color, s=marker_size)
            ax.text(x, y + 0.02, ch_name, fontsize=font_size,
                    ha="center", color=text_color, zorder=10)
        else:
            ax.scatter(x, y, color=(0, 0, 0, 0), s=marker_size)

    # Colorbar
    sm = cm.ScalarMappable(norm=norm, cmap=cmap)
    fig.colorbar(sm, ax=ax, shrink=0.7, label="Intensity (mA)")

    ax.set_aspect("equal")
    ax.axis("off")
    if show:
        plt.show()

    return fig, ax
