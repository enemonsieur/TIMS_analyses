import numpy as np
from simnibs.simulation.tms_coil.tms_coil import TmsCoil

from simnibs.simulation.tms_coil.tms_coil_element import LineSegmentElements
from simnibs.simulation.tms_coil.tms_stimulator import TmsStimulator

from scipy.spatial.transform import Rotation

import matplotlib.pyplot as plt


def create_coil(
        outer_diameter,
        num_radial_turns,
        num_axial_turns,
        radial_pitch,
        axial_pitch,
        casing_thickness,
        spiral_step=2*np.pi/100):

    pr = radial_pitch
    pa = axial_pitch
    r = outer_diameter/2-pr/2-(num_radial_turns-1)*pr

    wire_path = []
    for i in range(num_radial_turns):
        wire_path.append(np.array([[
            (r + i * pr) * np.cos(s),
            (r + i * pr) * np.sin(s),
            (pa * s / (2*np.pi)) if i % 2 == 0 else (pa *
                                                     num_axial_turns - pa * s / (2*np.pi))
        ]
            for s in np.arange(0, 2*np.pi*(num_axial_turns-1), spiral_step)]))

        wire_path.append(np.array([[
            (r + i * pr + pr * s/(2*np.pi)) * np.cos(s),
            (r + i * pr + pr * s/(2*np.pi)) * np.sin(s),
            (pa * (num_axial_turns-1) + pa * s / (2*np.pi)) if i % 2 == 0 else (pa - pa * s / (2*np.pi))
        ]
            for s in np.arange(0, 2*np.pi, spiral_step)]))

    wire_path.append(np.array(
        [[r + pr*num_radial_turns, 0, pa * num_axial_turns]]))
    wire_path.append(np.array(
        [[r + pr*num_radial_turns, 0, pa * (num_axial_turns + 1)]]))
    wire_path.append(
        np.array([[r - pr, 0, pa * (num_axial_turns + 1)]]))
    wire_path.append(np.array([[r - pr, 0, 0]]))

    wire_path = np.concatenate(wire_path)

    wire_path[:, 2] += casing_thickness + pa/2

    return wire_path


def position_coil(wire_path, posvec, rotvec):
    return posvec + wire_path @ Rotation.from_rotvec(rotvec, degrees=True).as_matrix()


def save_tcd(
        wire_path,
        file_path,
        name="TIMS",
        field_infinity_dist=300,
        field_resolution=1,
        max_current=150,
        max_frequency=50E3):

    wire_path = np.copy(wire_path)
    wire_path[:, 2] *= -1

    D = field_infinity_dist
    limits = [[-D, D], [-D, D], [-D, D]]
    resolution = [field_resolution, field_resolution, field_resolution]
    max_di_dt = 2 * np.pi * max_frequency * max_current

    stimulator = TmsStimulator(name=name, max_di_dt=max_di_dt)

    line_element = LineSegmentElements(stimulator, wire_path)

    tms_coil = TmsCoil(
        [line_element], limits=limits, resolution=resolution
    )

    tms_coil.write(file_path)

    return file_path


def plot_wire_paths(paths, head_radius=90):
    ax = plt.figure().add_subplot(projection='3d')

    for wire_path in paths:
        ax.plot(wire_path[:, 0], wire_path[:, 1], wire_path[:, 2])

    u = np.linspace(0, 2 * np.pi, 100)
    v = np.linspace(0, np.pi, 100)
    x = head_radius * np.outer(np.cos(u), np.sin(v))
    y = head_radius * np.outer(np.sin(u), np.sin(v))
    z = head_radius * np.outer(np.ones(np.size(u)), np.cos(v)) - head_radius
    ax.plot_surface(x, y, z, color='k', rstride=5, cstride=5, alpha=0.3)

    ax.set_box_aspect((np.diff(ax.get_xlim3d())[0], np.diff(
        ax.get_ylim3d())[0], np.diff(ax.get_zlim3d())[0]))

    ax.set_xlabel('X (mm)')
    ax.set_ylabel('Y (mm)')
    ax.set_zlabel('Z (mm)')

    plt.show()


if __name__ == '__main__':
    coil_path = create_coil(60, 8, 10, 2.163, 2.45, 5)
    plot_wire_paths([coil_path])
