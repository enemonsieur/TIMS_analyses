import numpy as np


def calc_temporal_interference_maximum_modulation(EA, EB):
    magEA = np.linalg.norm(EA, axis=1)
    magEB = np.linalg.norm(EB, axis=1)

    magEA_larger_than_magEB = (magEA > magEB)[:, None]

    E1 = EA * magEA_larger_than_magEB + EB * (1 - magEA_larger_than_magEB)
    E2 = EB * magEA_larger_than_magEB + EA * (1 - magEA_larger_than_magEB)

    magE1 = np.linalg.norm(E1, axis=1)
    magE2 = np.linalg.norm(E2, axis=1)

    cos_alpha = np.sum(E1 * E2, axis=1) / (magE1 * magE2)
    E2[cos_alpha < 0] *= -1
    cos_alpha = np.sum(E1 * E2, axis=1) / (magE1 * magE2)

    magE2_less_than_magE1_cos_alpha = (magE2 < (magE1 * cos_alpha))

    EM = 2 * magE2 * magE2_less_than_magE1_cos_alpha + (2 * np.linalg.norm(np.cross(
        E2, E1-E2), axis=1) / np.linalg.norm(E1-E2, axis=1)) * (1-magE2_less_than_magE1_cos_alpha)

    return EM
