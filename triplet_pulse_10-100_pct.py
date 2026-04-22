"""Generate a single `.tims` file with triplet-pulse dose-response blocks (10–100%).

Each event is one 50 Hz triplet (3 half-sine pulses at 0, 20, 40 ms), repeated
every 5 s for 20 events per intensity level, 10 levels total = 1000 s.
"""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pytims

# ===== Config =================================================================

SHOW_PLOT_PREVIEW = True

# Amplitude sweep: 10% to 100% in 10% steps.
AMPLITUDE_LEVELS = [0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90, 1.00]

# Triplet structure: 3 pulses at 50 Hz → offsets at 0, 20, 40 ms.
TRIPLET_RATE_HZ = 50.0
TRIPLETS_PER_BURST = 3

# One event = one triplet burst, then a 5 s wait (onset-to-onset interval).
INTER_EVENT_INTERVAL_S = 5.0
EVENTS_PER_LEVEL = 20

# Half-sine pulse: 10 ms (half of 20 ms period at 50 Hz).
PULSE_WIDTH_S = 0.010

WARMUP_S = 5.0

LEVEL_DURATION_S = EVENTS_PER_LEVEL * INTER_EVENT_INTERVAL_S   # 100 s per level
TOTAL_DURATION_S = WARMUP_S + len(AMPLITUDE_LEVELS) * LEVEL_DURATION_S    # 1005 s total

OUTPUT_TIMS_PATH = Path(
    r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\triplet_pulse_10-100_pct.tims"
)


# ===== Protocol setup ==========================================================

protocol = pytims.Protocol()
protocol.enable_channel(pytims.Channel.A)

protocol.set_stimulation_intensity(1.0)
protocol.set_session_duration(TOTAL_DURATION_S)

sampling_rate = protocol.get_sampling_rate()
num_samples = protocol.get_num_samples()
t = np.arange(num_samples, dtype=np.float64) / sampling_rate


# ===== Session construction ====================================================

amplitude_samples = np.zeros_like(t)

pulse_width_samples = int(round(PULSE_WIDTH_S * sampling_rate))
half_sine_template = np.sin(np.pi * np.arange(pulse_width_samples) / pulse_width_samples)

# Pulse offsets within each triplet: 0, 20, 40 ms.
pulse_offsets_s = np.arange(TRIPLETS_PER_BURST, dtype=np.float64) / TRIPLET_RATE_HZ

for level_index, amplitude_level in enumerate(AMPLITUDE_LEVELS):
    level_start_s = WARMUP_S + level_index * LEVEL_DURATION_S

    for event_index in range(EVENTS_PER_LEVEL):
        triplet_start_s = level_start_s + event_index * INTER_EVENT_INTERVAL_S

        # Three half-sine pulses at 0, 20, 40 ms.
        for pulse_offset_s in pulse_offsets_s:
            pulse_start_s = triplet_start_s + pulse_offset_s
            pulse_start_sample = int(round(pulse_start_s * sampling_rate))
            pulse_stop_sample = pulse_start_sample + pulse_width_samples
            amplitude_samples[pulse_start_sample:pulse_stop_sample] = amplitude_level * half_sine_template

# Modulation fixed at 1.0 for entire session.
modulation_samples = np.ones_like(t)


# ===== Validation ==============================================================

pulse_count_total = len(AMPLITUDE_LEVELS) * EVENTS_PER_LEVEL * TRIPLETS_PER_BURST


# ===== Optional preview ========================================================

if SHOW_PLOT_PREVIEW:
    preview_s = 2 * LEVEL_DURATION_S
    preview_samples = int(preview_s * sampling_rate)
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 6))
    ax1.plot(t[:preview_samples], amplitude_samples[:preview_samples], label="Amplitude (A1/A2)")
    ax1.set_xlabel("Time (s)")
    ax1.set_ylabel("Amplitude")
    ax1.set_title("Triplet-pulse amplitude signal (10–100% dose-response, first 2 levels)")
    ax1.legend()
    ax2.plot(t[:preview_samples], modulation_samples[:preview_samples], label="Modulation (Channel A)", color="orange")
    ax2.set_xlabel("Time (s)")
    ax2.set_ylabel("Modulation")
    ax2.set_ylim([0, 1.1])
    ax2.set_title("Modulation signal (constant 1.0)")
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
print(f"duration_s={TOTAL_DURATION_S:.1f}")
print(f"levels={len(AMPLITUDE_LEVELS)}  events_per_level={EVENTS_PER_LEVEL}  pulses_total={pulse_count_total}")
