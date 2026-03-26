import numpy as np
import matplotlib.pyplot as plt


def cordic(x_0, y_0, num_iterations, FP_NBITS):
    atan_table = [int((np.atan(2**(-i))/np.pi)*2**(FP_NBITS-1))
                  for i in range(num_iterations)]
    print(atan_table)

    K_n = np.prod([1.0 / np.sqrt(1 + 2**(-2*i))
                  for i in range(num_iterations)])
    K_n_fixed = int(K_n * 2**(FP_NBITS-1))

    print(K_n_fixed)
    phi = 0

    x = -x_0 if x_0 < 0 else x_0
    y = y_0

    for i in range(num_iterations):
        if y >= 0:   # rotate clockwise
            x_new = x + (y >> i)
            y_new = y - (x >> i)

            phi = phi + atan_table[i]
        else:  # rotate counter-clockwise
            x_new = x - (y >> i)
            y_new = y + (x >> i)

            phi = phi - atan_table[i]

        x, y = x_new, y_new

    x = (x * K_n_fixed) >> (FP_NBITS-1)  # Apply K_n scaling in Q31

    if x_0 < 0:
        if y_0 > 0:
            phi = (2**(FP_NBITS-1)-1) - phi
        else:
            phi = -(2**(FP_NBITS-1)-1) - phi

    print(x, phi)
    return x, phi


cordic(-1000, -2000, 14, 16)
# FP_NBITS = 16
# N = 1000
# min_num_iterations = 10
# max_num_iterations = 50
#
#
# np.random.seed(1233)
# x_0 = np.random.randint(-2**(FP_NBITS-1), 2**(FP_NBITS), size=N)
# y_0 = np.random.randint(-2**(FP_NBITS-1), 2**(FP_NBITS), size=N)
# mag_errors = np.zeros(max_num_iterations-min_num_iterations)
# phase_errors = np.zeros(max_num_iterations-min_num_iterations)
#
# for num_iterations in range(min_num_iterations, max_num_iterations):
#     mag_ref = np.sqrt(x_0**2 + y_0**2)
#     phase_ref = (np.atan2(y_0, x_0)/np.pi)*2**(FP_NBITS-1)
#
#     mag = np.zeros_like(x_0)
#     phase = np.zeros_like(x_0)
#     for i in range(N):
#         mag[i], phase[i] = cordic(x_0[i], y_0[i], num_iterations, FP_NBITS)
#
#     mag_errors[num_iterations - min_num_iterations] = \
#         np.mean(np.abs(mag - mag_ref))
#     phase_errors[num_iterations - min_num_iterations] = \
#         np.mean(np.abs(phase - phase_ref)/mag_ref)
#
# plt.subplot(211)
# plt.plot(np.arange(min_num_iterations, max_num_iterations), mag_errors)
# plt.subplot(212)
# plt.plot(np.arange(min_num_iterations, max_num_iterations), phase_errors)
# plt.show()
