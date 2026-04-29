"""Measure combined dual-coil magET 30 mm below Cz in a 5 mm GM ROI."""

from pathlib import Path
import csv

import numpy as np
import simnibs


# ============================================================
# CONFIG
# ============================================================

base_directory = Path(r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS")
run_directory = base_directory / r"simulation\sim_results\D60T10L8_dual_cz"
combined_mesh_path = run_directory / r"combined\combined.msh"
eeg_cap_path = base_directory / r"simulation\head_models\m2m_ernie\eeg_positions\EEG10-10_UI_Jurak_2007.csv"
output_directory = run_directory / r"combined\coil_midpoint_30mm_gm5mm"
output_directory.mkdir(parents=True, exist_ok=True)

field_name = "magET"  # norm(E1 + E2), saved by two_coils.py
center_label = "Cz"  # two coils are centered here
ydir_label = "CPz"  # fixes the local coil Y direction
coil_offset_mm = 40.0  # two_coils.py uses +/- 40 mm on local X
coil_distance_mm = 0.001  # current two_coils.py setting
depth_mm = 30.0  # requested 3 cm inward target
roi_radius_mm = 5.0  # local gray-matter neighborhood
top_gm_count = 3000  # context used by the focality plot
visible_field_threshold_v_per_m = 10.0  # hide weak GM field points in the brain map
distance_profile_max_cm = 10.0  # x-axis range for E-field vs distance from Cz


# ============================================================
# FLOW
# ============================================================
#
# combined.msh geometry + EEG cap Cz/CPz
#   -> SimNIBS calc_matsimnibs(Cz, CPz)
#   -> scalp Cz point + 30 mm along inward coil Z axis
#   -> gray-matter centroids
#   -> nearest GM element = snapped target
#   -> 5 mm GM sphere around snapped target
#   -> magET values for ROI, visible whole-GM map, and distance profile
#   -> summary.csv + roi_elements.csv + gm_over_5v.csv + gm_distance_0_6cm.csv
#
# Main method is below in sections 1-4. The helper only reads one binary
# ElementData field because simnibs.read_msh(..., skip_data=False) loads all
# saved fields and is too heavy for this combined mesh.


def read_scalar_element_field(mesh_path, name):
    """Read one scalar ElementData field without loading every saved field."""
    marker = b"$ElementData\n"
    with mesh_path.open("rb") as handle:
        tail = b""
        while True:
            chunk = handle.read(8 * 1024 * 1024)
            if not chunk:
                raise ValueError(f"Missing ElementData field: {name}")
            block = tail + chunk
            index = block.find(marker)
            if index >= 0:
                handle.seek(handle.tell() - len(chunk) - len(tail) + index)
                break
            tail = block[-len(marker):]

        while True:
            if handle.readline() != marker:
                raise ValueError(f"Could not parse ElementData before {name}.")
            names = [handle.readline().decode("ascii").strip().strip('"') for _ in range(int(handle.readline()))]
            for _ in range(int(handle.readline())):
                handle.readline()
            tags = [int(handle.readline()) for _ in range(int(handle.readline()))]
            component_count, row_count = tags[1], tags[2]
            dtype = np.dtype([("id", np.int32), ("value", np.float64, component_count)])

            if names[0] == name:
                if component_count != 1:
                    raise ValueError(f"{name} is not scalar.")
                data = np.fromfile(handle, dtype=dtype, count=row_count)
                return data["value"].ravel()

            handle.seek(row_count * dtype.itemsize, 1)
            handle.readline()  # $EndElementData


# ============================================================
# 1) LOAD GEOMETRY
# ============================================================

# Geometry only. Field values are read later from just the magET ElementData.
mesh = simnibs.read_msh(str(combined_mesh_path), skip_data=True)

# EEG cap CSV -> two named coordinates used by SimNIBS to orient the coil.
with eeg_cap_path.open(newline="") as handle:
    cap_xyz = {row[4]: np.array(row[1:4], dtype=float) for row in csv.reader(handle) if len(row) >= 5}
cz_xyz = cap_xyz[center_label]
cpz_xyz = cap_xyz[ydir_label]

# Cz/CPz -> SimNIBS coil frame.
# matsimnibs[:3, 3] is the scalp point; matsimnibs[:3, 2] is inward.
matsimnibs = mesh.calc_matsimnibs(cz_xyz, cpz_xyz, coil_distance_mm)
surface_xyz = matsimnibs[:3, 3]
target_xyz = surface_xyz + depth_mm * matsimnibs[:3, 2]

# Mesh tetrahedra -> centroids and volumes.
# Centroids define where each element is; volumes weight the ROI mean.
centers = mesh.elements_baricenters().value
volumes = mesh.elements_volumes_and_areas().value
gm_mask = (mesh.elm.tag1 == int(simnibs.ElementTags.GM)) & (mesh.elm.elm_type == 4)
gm_elements = np.flatnonzero(gm_mask) + 1
gm_centers = centers[gm_mask]


# ============================================================
# 2) SNAP TARGET AND BUILD ROI
# ============================================================

# 30 mm target XYZ -> nearest gray-matter centroid.
snap_index = int(np.argmin(np.sum((gm_centers - target_xyz) ** 2, axis=1)))
snapped_element = int(gm_elements[snap_index])
snapped_xyz = gm_centers[snap_index]

# Snapped GM centroid -> 5 mm GM sphere.
distance_to_snap = np.linalg.norm(centers - snapped_xyz, axis=1)
roi_mask = gm_mask & (distance_to_snap <= roi_radius_mm)
if not np.any(roi_mask):
    raise ValueError("No gray-matter elements found inside the 5 mm ROI.")


# ============================================================
# 3) READ FIELD AND SUMMARIZE
# ============================================================

# combined.msh -> one scalar per element: magET in V/m.
field = read_scalar_element_field(combined_mesh_path, field_name)

# ROI mask -> local field distribution around the snapped 30 mm target.
roi_values = field[roi_mask]
roi_centers = centers[roi_mask]
roi_volumes = volumes[roi_mask]
roi_elements = np.flatnonzero(roi_mask) + 1
roi_mean = float(np.average(roi_values, weights=roi_volumes))
roi_std = float(np.sqrt(np.average((roi_values - roi_mean) ** 2, weights=roi_volumes)))
roi_max_index = int(np.argmax(roi_values))

# Whole GM field -> peak context for "where is strongest overall?"
gm_values = field[gm_mask]
gm_max_index = int(np.argmax(gm_values))
gm_max_element = int(gm_elements[gm_max_index])
gm_max_xyz = gm_centers[gm_max_index]

# Whole GM field -> strongest elements for plotting/focality context.
top_count = min(top_gm_count, len(gm_values))
top_index = np.argpartition(gm_values, -top_count)[-top_count:]
top_index = top_index[np.argsort(gm_values[top_index])[::-1]]
top_elements = gm_elements[top_index]

# Whole GM field -> visible brain map.
# This is the "empty every value <5 V/m" step: weak elements are not saved.
visible_gm_mask = gm_mask & (field >= visible_field_threshold_v_per_m)
visible_gm_elements = np.flatnonzero(visible_gm_mask) + 1

# Distance from electrode = Euclidean distance from the SimNIBS-projected Cz
# scalp point to each GM element centroid. Convert mm -> cm for the x-axis.
distance_from_cz_cm = np.linalg.norm(centers - surface_xyz, axis=1) / 10.0
distance_profile_mask = gm_mask & (distance_from_cz_cm <= distance_profile_max_cm)
distance_profile_elements = np.flatnonzero(distance_profile_mask) + 1


# ============================================================
# 4) SAVE TABLES
# ============================================================

points = {
    "surface": surface_xyz,
    "target": target_xyz,
    "snapped": snapped_xyz,
    "roi_max": roi_centers[roi_max_index],
    "whole_gm_max": gm_max_xyz,
}
summary = {
    "mesh": str(combined_mesh_path),
    "field": field_name,
    "center_label": center_label,
    "ydir_label": ydir_label,
    "coil_offset_mm": coil_offset_mm,
    "coil_distance_mm": coil_distance_mm,
    "depth_mm": depth_mm,
    "roi_radius_mm": roi_radius_mm,
    "visible_field_threshold_v_per_m": visible_field_threshold_v_per_m,
    "distance_profile_max_cm": distance_profile_max_cm,
    "roi_element_count": int(len(roi_elements)),
    "roi_volume_mm3": float(np.sum(roi_volumes)),
    "snapped_element": snapped_element,
    "target_to_snap_distance_mm": float(np.linalg.norm(target_xyz - snapped_xyz)),
    "roi_mean_v_per_m": roi_mean,
    "roi_median_v_per_m": float(np.median(roi_values)),
    "roi_weighted_std_v_per_m": roi_std,
    "roi_min_v_per_m": float(np.min(roi_values)),
    "roi_max_v_per_m": float(np.max(roi_values)),
    "roi_max_element": int(roi_elements[roi_max_index]),
    "whole_gm_max_v_per_m": float(gm_values[gm_max_index]),
    "whole_gm_max_element": gm_max_element,
    "distance_snap_to_whole_gm_max_mm": float(np.linalg.norm(snapped_xyz - gm_max_xyz)),
}
for name, xyz in points.items():
    summary.update({f"{name}_{axis}_mm": float(value) for axis, value in zip("xyz", xyz)})

with (output_directory / "summary.csv").open("w", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=list(summary))
    writer.writeheader()
    writer.writerow(summary)

np.savetxt(
    output_directory / "roi_elements.csv",
    np.column_stack((roi_elements, roi_centers, roi_volumes, distance_to_snap[roi_mask], roi_values)),
    delimiter=",",
    header="element_number,centroid_x_mm,centroid_y_mm,centroid_z_mm,volume_mm3,distance_to_snap_mm,magET_v_per_m",
    comments="",
    fmt=["%d", "%.6f", "%.6f", "%.6f", "%.6f", "%.6f", "%.6f"],
)
np.savetxt(
    output_directory / "top_gm_elements.csv",
    np.column_stack((top_elements, centers[top_elements - 1], field[top_elements - 1])),
    delimiter=",",
    header="element_number,centroid_x_mm,centroid_y_mm,centroid_z_mm,magET_v_per_m",
    comments="",
    fmt=["%d", "%.6f", "%.6f", "%.6f", "%.6f"],
)
np.savetxt(
    output_directory / "gm_over_5v.csv",
    np.column_stack((visible_gm_elements, centers[visible_gm_mask], field[visible_gm_mask])),
    delimiter=",",
    header="element_number,centroid_x_mm,centroid_y_mm,centroid_z_mm,magET_v_per_m",
    comments="",
    fmt=["%d", "%.6f", "%.6f", "%.6f", "%.6f"],
)
np.savetxt(
    output_directory / "gm_distance_0_6cm.csv",
    np.column_stack((
        distance_profile_elements,
        centers[distance_profile_mask],
        distance_from_cz_cm[distance_profile_mask],
        field[distance_profile_mask],
    )),
    delimiter=",",
    header="element_number,centroid_x_mm,centroid_y_mm,centroid_z_mm,distance_from_cz_cm,magET_v_per_m",
    comments="",
    fmt=["%d", "%.6f", "%.6f", "%.6f", "%.6f", "%.6f"],
)

(output_directory / "summary.txt").write_text(
    "\n".join([
        "Dual-coil Cz depth E-field extraction",
        f"Coils: centered on {center_label}, +/-{coil_offset_mm:.1f} mm local X, field={field_name}",
        f"Target/snapped GM XYZ: {target_xyz} / {snapped_xyz}",
        f"ROI elements/volume: {len(roi_elements)} / {np.sum(roi_volumes):.3f} mm3",
        f"ROI weighted mean/median/std: {roi_mean:.3f} / {np.median(roi_values):.3f} / {roi_std:.3f} V/m",
        f"ROI min/max: {np.min(roi_values):.3f} / {np.max(roi_values):.3f} V/m",
        f"Whole-GM max: element {gm_max_element}, {gm_values[gm_max_index]:.3f} V/m, XYZ {gm_max_xyz}",
        f"Visible whole-GM map threshold: >= {visible_field_threshold_v_per_m:.1f} V/m",
        f"Distance profile: GM elements within {distance_profile_max_cm:.1f} cm of projected Cz",
    ]) + "\n"
)

print(f"Saved extraction tables: {output_directory}")
print(f"ROI weighted mean {field_name}: {roi_mean:.3f} V/m")
