import numpy as np
import matplotlib.pyplot as plt

fc = 100
spc = 32
tmax = 6/fc
fs = spc*fc

ref_mag = 0.75
ref_phase = np.pi/4

t = np.arange(0, tmax, 1/fs)
samples = ref_mag * np.sin(2*np.pi*fc*t+ref_phase)

def dft(samples):
    ref_sin = np.sin(2*np.pi*np.arange(spc, dtype=np.float64)/spc)
    ref_cos = np.cos(2*np.pi*np.arange(spc, dtype=np.float64)/spc)
    mag = np.zeros_like(samples)
    phase = np.zeros_like(samples)
    for i in range(len(samples)):
        sum_sin = np.sum(samples[max(i-spc+1, 0):i+1] * ref_sin[:min(spc, i)+1])/(spc/2)
        sum_cos = np.sum(samples[max(i-spc+1, 0):i+1] * ref_cos[:min(spc, i)+1])/(spc/2)
        mag[i] = np.sqrt(sum_cos**2+sum_sin**2)
        phase[i] = np.arctan2(sum_sin, sum_cos)

    return mag, phase
        
mag, phase = dft(samples)
plt.plot(t, samples)
plt.plot(t, mag)
plt.plot(t, phase)
plt.show()


