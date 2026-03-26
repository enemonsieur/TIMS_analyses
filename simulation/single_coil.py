import os, shutil
import numpy as np
import coils
import simnibs

sim_id              = 'single_cz'
head_model          = 'head_models/m2m_ernie'
rerun_simulation    = False

current             = 75            # A, peak
frequency           = 20E3          # Hz

coil_num_turns      = 10
coil_num_layers     = 8
coil_outer_diameter = 60            # mm
coil_radial_pitch   = 2.163         # mm
coil_axial_pitch    = 2.450         # mm
casing_thickness    = 5             # mm
coil_id             = f'D{coil_outer_diameter}T{coil_num_turns}L{coil_num_layers}'

output_folder       = f'sim_results/{coil_id}_{sim_id}'

coil_1_rel_posvec   = [50, 0, 0]    # mm
coil_1_rel_rotvec   = [0, 0, 0]     # degrees

coil_2_rel_posvec   = [-50, 0, 0]   # mm
coil_2_rel_rotvec   = [0, 0, 0]     # degrees

target_center       = 'Cz'
target_ydir         = 'CPz'

os.makedirs(output_folder, exist_ok=True)

wire_path = coils.create_coil(
    coil_outer_diameter, 
    coil_num_layers, 
    coil_num_turns, 
    coil_radial_pitch,
    coil_axial_pitch,
    casing_thickness
)

coils.plot_wire_paths([wire_path])

coil_filepath = coils.save_tcd(wire_path, os.path.join(output_folder, 'coil.tcd'))

sim_dir = os.path.join(output_folder, 'sim')

S = simnibs.sim_struct.SESSION()
S.subpath = head_model

S.pathfem = sim_dir
S.open_in_gmsh = True
S.fields = 'E' + 'e' + 'J' + 'j' + 's'


tms = S.add_tmslist()
tms.fnamecoil = coil_filepath
tms.anisotropy_type = 'vn'

pos = tms.add_position()
pos.didt = 2 * np.pi * current * frequency
pos.centre = target_center
pos.pos_ydir = target_ydir
pos.distance = 0.001

if rerun_simulation:
    if os.path.exists(sim_dir):
        shutil.rmtree(sim_dir)
    simnibs.run_simnibs(S, cpus=16)
else:
    os.system(f"gmsh {os.path.join(sim_dir, '*.msh')}")
