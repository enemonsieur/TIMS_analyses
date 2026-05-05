import numpy as np
import matplotlib.pyplot as plt
import pytims

SHOW_PLOT_PREVIEW = False

# -----------------------------------
# 1) Protocol setup
# -----------------------------------
protocol = pytims.Protocol()
protocol.enable_channel(pytims.Channel.A)

# Fraction of max stimulator output
protocol.set_stimulation_intensity(1.0)

# cTBS-like total duration
session_duration = 500.0  # seconds
protocol.set_session_duration(session_duration)

sampling_rate = protocol.get_sampling_rate()
num_samples = protocol.get_num_samples()
t = np.arange(num_samples, dtype=np.float64) / sampling_rate

# -----------------------------------
# 2) Smooth 5 Hz amplitude envelope
# Assigned to BOTH A1 and A2
# Range: 0..1
# -----------------------------------
amp_5hz = 0.5 * (1.0 + np.sin(2 * np.pi * 5.0 * t))

# Optional: make the envelope less close to zero if needed
# amp_5hz = 0.2 + 0.8 * amp_5hz

# -----------------------------------
# 3) TBS burst modulation signal
# 3 events at 50 Hz => 0 ms, 20 ms, 40 ms
# Bursts repeat every 200 ms => 5 Hz
# Bursts run for 2 s, then pause for 3 s
#
# This is the MODULATION source.
# It is sparse and only "active" during burst events.
# -----------------------------------
mod_tbs = np.zeros_like(t)

burst_period = 0.200  # 200 ms -> 5 Hz burst repetition
triplet_times = [0.000, 0.020, 0.040]  # 50 Hz within burst
event_width = 0.005  # 5 ms trigger width, adjustable
on_duration_s = 2.0 -0.005 # last 5 Hz trough at 1.95 s, stop just after drop
off_duration_s = 3.0
cycle_duration_s = on_duration_s + off_duration_s
on_off_mask = ((t % cycle_duration_s) < on_duration_s).astype(np.float64)

amp_5hz *= on_off_mask

burst_starts = np.arange(0.0, session_duration, burst_period)

for bs in burst_starts:
    for dt in triplet_times:
        start = bs + dt
        end = start + event_width
        mod_tbs[(t >= start) & (t < end)] = 1.0

mod_tbs *= on_off_mask

# -----------------------------------
# 4) Plot sanity check (optional)
# -----------------------------------
if SHOW_PLOT_PREVIEW:
    plot_duration = 5.0
    plot_n = int(plot_duration * sampling_rate)

    plt.figure(figsize=(12, 5))
    plt.plot(t[:plot_n], amp_5hz[:plot_n], label="A1/A2 amplitude envelope (5 Hz, gated)")
    plt.plot(t[:plot_n], on_off_mask[:plot_n], label="Burst gate (2 s ON / 3 s OFF)")
    plt.plot(t[:plot_n], mod_tbs[:plot_n], label="Modulation source (50 Hz triplets, gated)")
    plt.xlabel("Time (s)")
    plt.ylabel("Amplitude")
    plt.title("TIMS cTBS-like control signals")
    plt.legend()
    plt.tight_layout()
    plt.show()

# -----------------------------------
# 5) Add signals to protocol
# -----------------------------------
amp_idx = protocol.add_arbitrary_signal(amp_5hz.astype(np.float64))
mod_idx = protocol.add_arbitrary_signal(mod_tbs.astype(np.float64))

# -----------------------------------
# 6) Route signals
# BOTH coils get the same 5 Hz amplitude envelope
# The channel gets the TBS-like modulation source
# -----------------------------------
protocol.set_amplitude_source(pytims.Coil.A1, index=amp_idx)
protocol.set_amplitude_source(pytims.Coil.A2, index=amp_idx)
protocol.set_modulation_source(pytims.Channel.A, index=mod_idx)

# -----------------------------------
# 7) Save protocol
# -----------------------------------
protocol.save("ctbs_like_v1_amp5hz_mod50hz_triplets.tims")
