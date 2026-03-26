import numpy as np
import matplotlib.pyplot as plt
from scipy import signal

num_taps = 64

coeffs = signal.firwin(num_taps, cutoff=[0.5,1.5], pass_zero=False, fs=32)

w, h = signal.freqz(coeffs, worN=8000, fs=32)
plt.plot(w, np.angle(h), linewidth=2)
print(coeffs)
plt.show()

plt.plot(coeffs)
plt.show()
