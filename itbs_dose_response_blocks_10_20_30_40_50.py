"""Generate a single `.tims` file with ordered iTBS dose-response blocks."""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pytims

# ===== Config =================================================================

SHOW_PLOT_PREVIEW = False

# Ordered amplitude blocks for the dose-response sweep.
AMPLITUDE_LEVELS = [0.10, 0.20, 0.30, 0.40, 0.50]

# Standard iTBS timing:
# - bursts repeat at 5 Hz
# - each burst contains three pulses at 50 Hz
# - the active window lasts 2 s, followed by 4 s OFF
BURST_RATE_HZ = 5.0
TRIPLET_RATE_HZ = 50.0
TRIPLETS_PER_BURST = 3
ON_DURATION_S = 2.0
OFF_DURATION_S = 4.0

# One iTBS block contains 20 ON cycles:
# 20 cycles x (2 s ON + 4 s OFF) = 120 s per block
# 20 cycles x 10 bursts per ON x 3 pulses per burst = 600 pulses per block
CYCLES_PER_BLOCK = 20
PULSES_PER_BLOCK = 600
BLOCK_DURATION_S = 120.0

# Pulses are written as short square events in the modulation signal.
EVENT_WIDTH_S = 0.005

OUTPUT_TIMS_PATH = Path(
    r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\itbs_dose_response_blocks_10_20_30_40_50.tims"
)


# ===== Protocol setup ==========================================================

protocol = pytims.Protocol()
protocol.enable_channel(pytims.Channel.A)

# Keep protocol-level stimulator intensity fixed.
# The dose-response is encoded by scaling the arbitrary amplitude signal.
protocol.set_stimulation_intensity(1.0)
protocol.set_session_duration(len(AMPLITUDE_LEVELS) * BLOCK_DURATION_S)

sampling_rate = protocol.get_sampling_rate()
num_samples = protocol.get_num_samples()
t = np.arange(num_samples, dtype=np.float64) / sampling_rate


# ===== Session construction ====================================================

# One array holds the amplitude scaling for each block.
block_scale_samples = np.zeros_like(t)

# One array gates the active iTBS ON windows inside each block.
itbs_gate_samples = np.zeros_like(t)

# One array holds the sparse 3-pulse triplets that define each burst.
triplet_modulation_samples = np.zeros_like(t)

block_starts_s = np.arange(len(AMPLITUDE_LEVELS), dtype=np.float64) * BLOCK_DURATION_S
cycle_duration_s = ON_DURATION_S + OFF_DURATION_S
bursts_per_on = int(ON_DURATION_S * BURST_RATE_HZ)
pulse_offsets_s = np.arange(TRIPLETS_PER_BURST, dtype=np.float64) / TRIPLET_RATE_HZ

for block_index, amplitude_level in enumerate(AMPLITUDE_LEVELS):
    block_start_s = block_starts_s[block_index]
    block_start_sample = int(round(block_start_s * sampling_rate))
    block_stop_sample = int(round((block_start_s + BLOCK_DURATION_S) * sampling_rate))

    # Fill the entire block with its dose level.
    block_scale_samples[block_start_sample:block_stop_sample] = amplitude_level

    for cycle_index in range(CYCLES_PER_BLOCK):
        cycle_start_s = block_start_s + cycle_index * cycle_duration_s
        cycle_start_sample = int(round(cycle_start_s * sampling_rate))
        cycle_stop_sample = int(round((cycle_start_s + ON_DURATION_S) * sampling_rate))

        # Mark the 2 s active window inside the 10 s iTBS cycle.
        itbs_gate_samples[cycle_start_sample:cycle_stop_sample] = 1.0

        # Each ON window contains 10 bursts at 5 Hz.
        for burst_index in range(bursts_per_on):
            burst_start_s = cycle_start_s + burst_index / BURST_RATE_HZ

            # Each burst is a 50 Hz triplet at 0, 20, and 40 ms.
            for pulse_offset_s in pulse_offsets_s:
                pulse_start_s = burst_start_s + pulse_offset_s
                pulse_start_sample = int(round(pulse_start_s * sampling_rate))
                pulse_stop_sample = int(round((pulse_start_s + EVENT_WIDTH_S) * sampling_rate))
                triplet_modulation_samples[pulse_start_sample:pulse_stop_sample] = 1.0


# ===== Signal assembly =========================================================

# Amplitude is the block dose level, gated to the active ON windows.
amplitude_samples = block_scale_samples * itbs_gate_samples

# Modulation is only present during the active iTBS windows.
triplet_modulation_samples *= itbs_gate_samples

pulse_count_total = len(AMPLITUDE_LEVELS) * CYCLES_PER_BLOCK * bursts_per_on * TRIPLETS_PER_BURST
assert pulse_count_total == len(AMPLITUDE_LEVELS) * PULSES_PER_BLOCK
assert amplitude_samples.max() == max(AMPLITUDE_LEVELS)


# ===== Optional preview ========================================================

if SHOW_PLOT_PREVIEW:
    preview_samples = int(2 * BLOCK_DURATION_S * sampling_rate)
    plt.figure(figsize=(12, 5))
    plt.plot(t[:preview_samples], block_scale_samples[:preview_samples], label="Block amplitude")
    plt.plot(t[:preview_samples], amplitude_samples[:preview_samples], label="A1/A2 amplitude")
    plt.plot(t[:preview_samples], triplet_modulation_samples[:preview_samples], label="Channel A modulation")
    plt.xlabel("Time (s)")
    plt.ylabel("Amplitude")
    plt.title("iTBS dose-response blocks")
    plt.legend()
    plt.tight_layout()
    plt.show()


# ===== Save ===================================================================

amp_idx = protocol.add_arbitrary_signal(amplitude_samples.astype(np.float64))
mod_idx = protocol.add_arbitrary_signal(triplet_modulation_samples.astype(np.float64))
protocol.set_amplitude_source(pytims.Coil.A1, index=amp_idx)
protocol.set_amplitude_source(pytims.Coil.A2, index=amp_idx)
protocol.set_modulation_source(pytims.Channel.A, index=mod_idx)
protocol.save(str(OUTPUT_TIMS_PATH))

print(f"saved={OUTPUT_TIMS_PATH}")
print(f"duration_s={len(AMPLITUDE_LEVELS) * BLOCK_DURATION_S:.1f}")
print(f"blocks={len(AMPLITUDE_LEVELS)} pulses_total={pulse_count_total}")
