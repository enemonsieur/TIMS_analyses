
# Standard libraries
import os, shutil, util
import numpy as np
# Custom coil geometry and SimNIBS interface
import coils
import simnibs


# --- Simulation parameters ---
sim_id              = 'dual_cz'  # Identifier for this simulation
head_model          = 'head_models/m2m_ernie'  # Path to head model (precomputed)
rerun_simulation    = True       # If True, rerun SimNIBS for each coil
rerun_superposition = True       # If True, recompute superposition and postprocessing


current             = 75            # A, peak current through coil
frequency           = 20E3          # Hz, stimulation frequency (affects dI/dt)


# --- Coil geometry parameters ---
coil_num_turns      = 10            # Number of turns per layer
coil_num_layers     = 8             # Number of stacked layers
coil_outer_diameter = 60            # mm, total diameter of coil
coil_radial_pitch   = 2.163         # mm, distance between turns (radial direction)
coil_axial_pitch    = 2.450         # mm, distance between layers (axial/vertical)
casing_thickness    = 5             # mm, thickness of coil casing
coil_id             = f'D{coil_outer_diameter}T{coil_num_turns}L{coil_num_layers}'  # Unique coil ID


output_folder       = f'sim_results/{coil_id}_{sim_id}'  # Where results will be saved


# --- Coil positions and orientations (relative to head model) ---
coil_1_rel_posvec   = [40, 0, 0]    # mm, position offset for coil 1
coil_1_rel_rotvec   = [0, 0, 0]     # degrees, rotation for coil 1
coil_2_rel_posvec   = [-40, 0, 0]   # mm, position offset for coil 2
coil_2_rel_rotvec   = [0, 0, 0]     # degrees, rotation for coil 2

# --- Targeting parameters ---
target_center       = 'Cz'          # EEG 10-20 system: target at Cz
target_ydir         = 'CPz'         # Y direction points toward CPz


# Create output directory if it doesn't exist
os.makedirs(output_folder, exist_ok=True)


# Generate the base coil wire path (before positioning)
wire_path = coils.create_coil(
    coil_outer_diameter, 
    coil_num_layers, 
    coil_num_turns, 
    coil_radial_pitch,
    coil_axial_pitch,
    casing_thickness
)


# Position each coil in 3D space
wire_path_1 = coils.position_coil(wire_path, coil_1_rel_posvec, coil_1_rel_rotvec)
wire_path_2 = coils.position_coil(wire_path, coil_2_rel_posvec, coil_2_rel_rotvec)


# Optional: plot the coil wire paths for visualization
coils.plot_wire_paths([wire_path_1, wire_path_2])


# Save coil geometries to .tcd files (SimNIBS coil format)
coil_filepath_1 = coils.save_tcd(wire_path_1, os.path.join(output_folder, 'coil_1.tcd'))
coil_filepath_2 = coils.save_tcd(wire_path_2, os.path.join(output_folder, 'coil_2.tcd'))


# --- Run SimNIBS simulation for each coil ---
for i, coil_filepath in enumerate([coil_filepath_1, coil_filepath_2]):
    sim_dir = os.path.join(output_folder, 'coil_%i'%(i+1))  # Output dir for this coil
    
    S = simnibs.sim_struct.SESSION()  # Create a new SimNIBS session
    S.subpath = head_model            # Set head model

    S.pathfem = sim_dir               # Where to store simulation results
    S.open_in_gmsh = True             # Open in GMSH after simulation
    S.fields = 'E' + 'e' + 'J' + 'j' + 's'  # Compute E-field, J-field, etc.

    tms = S.add_tmslist()             # Add TMS coil to session
    tms.fnamecoil = coil_filepath     # Path to coil geometry
    tms.anisotropy_type = 'vn'        # Use volume-normal anisotropy (main fiber direction)

    pos = tms.add_position()          # Set coil position
    pos.didt = 2 * np.pi * current * frequency  # dI/dt for E-field calculation
    pos.centre = target_center        # Center of coil (Cz)
    pos.pos_ydir = target_ydir        # Y direction (CPz)
    pos.distance = 0.001              # Distance from scalp (1 mm)

    if rerun_simulation:
        if os.path.exists(sim_dir):
            shutil.rmtree(sim_dir)    # Remove old results if rerunning

        simnibs.run_simnibs(S, cpus=16)  # Run simulation (multi-core)


# --- Superimpose results and postprocess ---
if rerun_superposition:
    meshes, geo_filepaths = [], []
    for i in range(2):
        # Find mesh (.msh) and geometry (.geo) files for each coil
        msh_file = [f for f in os.listdir(os.path.join(output_folder, 'coil_%i'%(i+1))) if f.endswith('.msh')][0]
        geo_file = [f for f in os.listdir(os.path.join(output_folder, 'coil_%i'%(i+1))) if f.endswith('.geo')][0]
        
        meshes.append(simnibs.read_msh(os.path.join(output_folder, 'coil_%i'%(i+1), msh_file)))
        geo_filepaths.append(os.path.join(output_folder, 'coil_%i'%(i+1), geo_file))

    # Extract electric and current density fields for both coils
    E1 = meshes[0].field['E'][:]    # Electric field from coil 1
    E2 = -meshes[1].field['E'][:]   # Electric field from coil 2 (negative for superposition)
    ET = E1 + E2                    # Total E-field (superposition)
    J1 = meshes[0].field['J'][:]    # Current density from coil 1
    J2 = -meshes[1].field['J'][:]   # Current density from coil 2

    # max_eig: main direction of conductivity tensor (eigenvector)
    max_eig = meshes[0].field['max_eig'][:]
    n = max_eig / np.linalg.norm(max_eig, axis=1)[:,None]  # Normalize to get direction
    print(n.shape)

    # magEMn: difference in E-field along main conductivity direction
    magEMn = np.abs(np.abs(np.sum((E1 + E2) * n, axis=1)) - np.abs(np.sum((E1 - E2) * n, axis=1)))

    # magEMT: maximum temporal interference modulation (see util.py)
    magEMT = util.calc_temporal_interference_maximum_modulation(E1, E2)

    # cond_iso: isotropic conductivity for each element
    cond_iso = simnibs.utils.cond_utils.cond2elmdata(
        meshes[0], [c.value for c in simnibs.utils.cond_utils.standard_cond()])[:]
    # Qem: heat loss due to RMS current (Joule heating)
    Qem = np.linalg.norm((J1 + J2)/np.sqrt(2), axis=1)**2 / cond_iso

    print('Saving Qem file ...')
    centers = meshes[0].elements_baricenters()[:]  # Element centers (mm)
    Qem = np.concatenate((centers*1e-3, Qem[:,None]), axis=1)  # Convert to meters, append Qem
    np.savetxt(os.path.join(output_folder, 'Qem.csv'), Qem, delimiter=',')
    print('------Done------')

    # Load the head mesh for visualization and add all computed fields
    combined_mesh = simnibs.read_msh(os.path.join(head_model, [f for f in os.listdir(head_model) if f.endswith('.msh')][0]))

    combined_mesh.add_element_field(E1, 'E1')
    combined_mesh.add_element_field(E2, 'E2')
    combined_mesh.add_element_field(ET, 'ET')
    combined_mesh.add_element_field(np.linalg.norm(E1, axis=1), 'magE1')
    combined_mesh.add_element_field(np.linalg.norm(E2, axis=1), 'magE2')
    combined_mesh.add_element_field(np.linalg.norm(ET, axis=1), 'magET')
    combined_mesh.add_element_field(np.abs(np.sum(ET*n, axis=1)), 'magETn')  # E-field along normal
    combined_mesh.add_element_field(magEMn, 'magEMn')
    combined_mesh.add_element_field(magEMT, 'magEMT')
    combined_mesh.add_element_field(Qem, 'Qem')

    # Visualization: show only gray matter surface, display ET field
    v = combined_mesh.view(
        visible_tags=[simnibs.ElementTags.GM_TH_SURFACE.value],  # Gray matter surface
        visible_fields=['ET'],
        cond_list=simnibs.utils.cond_utils.standard_cond())

    # Merge coil geometries for visualization
    v.add_merge(geo_filepaths[0], False)
    v.add_merge(geo_filepaths[1], False)

    # Add vector and colormap views for coil elements
    coil_element_lengths = np.linalg.norm(np.diff(wire_path, axis=0), axis=1)
    v.add_view(VectorType=2, RangeType=2, CenterGlyphs=0, GlyphLocation=2, ShowScale=0,
              CustomMin=coil_element_lengths.min(), CustomMax=coil_element_lengths.max(),
              ArrowSizeMax=30, ArrowSizeMin=30)
    v.add_view(ColormapNumber=8, ColormapAlpha=.3, Visible=0, ShowScale=0)
    v.add_view(VectorType=2, RangeType=2, CenterGlyphs=0, GlyphLocation=2, ShowScale=0,
              CustomMin=coil_element_lengths.min(), CustomMax=coil_element_lengths.max(),
              ArrowSizeMax=30, ArrowSizeMin=30)
    v.add_view(ColormapNumber=8, ColormapAlpha=.3, Visible=0, ShowScale=0)

    # Save combined mesh and visualization options
    if not os.path.exists(os.path.join(output_folder, 'combined')):
        os.mkdir(os.path.join(output_folder, 'combined'))

    simnibs.mesh_tools.mesh_io.write_msh(combined_mesh, os.path.join(output_folder, 'combined', 'combined.msh'))
    v.write_opt(os.path.join(output_folder, 'combined', 'combined.msh'))

# Open the combined mesh in GMSH for visualization
os.system(f"gmsh {os.path.join(output_folder, 'combined', 'combined.msh')}")
