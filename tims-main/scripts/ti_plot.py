import numpy as np
import matplotlib.pyplot as plt

fs = 1E5
fc = 75
tmax = 0.4

t = np.arange(0, tmax, 1.0/fs)

fmods = [1, 3, 5, 8, 10]
amps = [1, 2, 0.5, 2, 0.2]

mod = np.zeros_like(t)
for fmod, amp in zip(fmods, amps):
    mod += amp * np.sin(2*np.pi*fmod*t)

mod -= mod.min()
mod /= mod.max()

relphase = 2 * np.arccos(mod)
s1 = np.sin(2*np.pi*fc*t + relphase/2)
s2 = np.sin(2*np.pi*fc*t - relphase/2)

plt.plot(t, s1, linewidth=1)
plt.plot(t, s2, linewidth=1)
plt.plot(t, (s1+s2), linewidth=2)
plt.plot(t, mod*2, linewidth=3)
plt.axis("off")
plt.savefig("../docs/ti.svg", transparent=True)
plt.show()
