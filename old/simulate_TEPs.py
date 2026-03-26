# simulate_TEPs.py


# -----------------------
# Parameters 
# -----------------------
SEED = 7
SFREQ = 1000.0          # Hz
TMIN, TMAX = -0.1, 0.3  # seconds (the epoch window)
INTENSITIES = (20, 40, 80, 100)  # %MSO
N_TRIALS_PER_INTENSITY = 50
NOISE_SD = 1.2          # microV of noise additive noise
ART_T0, ART_T1 = -0.002, 0.015  # artifact window (s) to interpolate over
POST_SCALE = 1.0        # multiply template in post block (set !=1 to emulate effect)
# Whatthe fuck is the 

