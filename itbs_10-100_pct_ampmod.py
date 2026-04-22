"""Generate a single `.tims` file with iTBS dose-response blocks (10–100%), pure amplitude modulation."""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pytims

# ===== Config =================================================================

SHOW_PLOT_PREVIEW = True

# Ordered amplitude blocks for the dose-response sweep: 10% to 100% in 10% steps.
AMPLITUDE_LEVELS = [0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90, 1.00]

# Standard iTBS timing:
# - bursts repeat at 5 Hz
# - each burst contains three pulses at 50 Hz
# - the active window lasts 2 s, followed by 4 s OFF
BURST_RATE_HZ = 5.0
TRIPLET_RATE_HZ = 50.0
TRIPLETS_PER_BURST = 3
ON_DURATION_S = 2.0
OFF_DURATION_S = 4.0

# One iTBS block contains 5 ON cycles:
# 5 cycles x (2 s ON + 4 s OFF) = 30 s per block
# 5 cycles x 10 bursts per ON x 3 pulses per burst = 150 pulses per block
CYCLES_PER_BLOCK = 5
PULSES_PER_BLOCK = 150
BLOCK_DURATION_S = 30.0

# Pulses are half-sine waves at 50 Hz: 10 ms duration (half of 20 ms period).
EVENT_WIDTH_S = 0.010

OUTPUT_TIMS_PATH = Path(
    r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\itbs_10-100_pct_ampmod_1s.tims"
)


# ===== Protocol setup ==========================================================

protocol = pytims.Protocol()
protocol.enable_channel(pytims.Channel.A)

# Keep protocol-level stimulator intensity fixed.
# The dose-response is encoded by scaling the amplitude signal directly.
protocol.set_stimulation_intensity(1.0)
protocol.set_session_duration(len(AMPLITUDE_LEVELS) * BLOCK_DURATION_S)

sampling_rate = protocol.get_sampling_rate()
num_samples = protocol.get_num_samples()
t = np.arange(num_samples, dtype=np.float64) / sampling_rate


# ===== Session construction ====================================================

# Single amplitude array encodes: block dose × ON/OFF gate × triplet pulse structure.
amplitude_samples = np.zeros_like(t)

block_starts_s = np.arange(len(AMPLITUDE_LEVELS), dtype=np.float64) * BLOCK_DURATION_S
cycle_duration_s = ON_DURATION_S + OFF_DURATION_S 
bursts_per_on = int(ON_DURATION_S * BURST_RATE_HZ)
pulse_offsets_s = np.arange(TRIPLETS_PER_BURST, dtype=np.float64) / TRIPLET_RATE_HZ

for block_index, amplitude_level in enumerate(AMPLITUDE_LEVELS):
    block_start_s = block_starts_s[block_index]
    block_start_sample = int(round(block_start_s * sampling_rate))
    block_stop_sample = int(round((block_start_s + BLOCK_DURATION_S) * sampling_rate))

    for cycle_index in range(CYCLES_PER_BLOCK):
        cycle_start_s = block_start_s + cycle_index * cycle_duration_s
        cycle_start_sample = int(round(cycle_start_s * sampling_rate))

        # Each ON window contains 10 bursts at 5 Hz.
        for burst_index in range(bursts_per_on):
            burst_start_s = cycle_start_s + burst_index / BURST_RATE_HZ

            # Each burst is a 50 Hz triplet at 0, 20, and 40 ms.
            for pulse_offset_s in pulse_offsets_s:
                pulse_start_s = burst_start_s + pulse_offset_s
                pulse_start_sample = int(round(pulse_start_s * sampling_rate))
                pulse_stop_sample = int(round((pulse_start_s + EVENT_WIDTH_S) * sampling_rate))
                amplitude_samples[pulse_start_sample:pulse_stop_sample] = amplitude_level

# Create constant modulation signal set to 1.0 for entire session
modulation_samples = np.ones_like(t)


# ===== Validation ==============================================================

pulse_count_total = (
    len(AMPLITUDE_LEVELS) * CYCLES_PER_BLOCK * bursts_per_on * TRIPLETS_PER_BURST
)   
assert pulse_count_total == len(AMPLITUDE_LEVELS) * PULSES_PER_BLOCK
assert amplitude_samples.max() == max(AMPLITUDE_LEVELS)


# ===== Optional preview ========================================================

if SHOW_PLOT_PREVIEW:
    preview_samples = int(2 * BLOCK_DURATION_S * sampling_rate)
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))
    ax1.plot(t[:preview_samples], amplitude_samples[:preview_samples], label="Amplitude (A1/A2)")
    ax1.set_xlabel("Time (s)")
    ax1.set_ylabel("Amplitude")
    ax1.set_title("Amplitude signal (iTBS 10–100% dose-response)")
    ax1.legend()
    ax2.plot(t[:preview_samples], modulation_samples[:preview_samples], label="Modulation (Channel A)", color='orange')
    ax2.set_xlabel("Time (s)")
    ax2.set_ylabel("Modulation")
    ax2.set_ylim([0, 1.1])
    ax2.set_title("Modulation signal (should be 1.0 everywhere)")
    ax2.legend()
    plt.tight_layout()
    plt.show()


# ===== Save ===================================================================
amp_idx = protocol.add_arbitrary_signal(amplitude_samples.astype(np.float64))
mod_idx = protocol.add_arbitrary_signal(modulation_samples.astype(np.float64))
protocol.set_amplitude_source(pytims.Coil.A1, index=amp_idx)
protocol.set_amplitude_source(pytims.Coil.A2, index=amp_idx)
protocol.set_modulation_source(pytims.Channel.A, index=mod_idx)
protocol.save(str(OUTPUT_TIMS_PATH))

print(f"saved={OUTPUT_TIMS_PATH}")
print(f"duration_s={len(AMPLITUDE_LEVELS) * BLOCK_DURATION_S:.1f}")
print(f"blocks={len(AMPLITUDE_LEVELS)} pulses_total={pulse_count_total}")
