import numpy as np
import matplotlib.pyplot as plt
import pytims

# Initialize protocol and enable channel A
protocol = pytims.Protocol()
protocol.enable_channel(pytims.Channel.A)

# Set intensity as fraction of maximum stimulator output
protocol.set_stimulation_intensity(1.0)

# Set duration in seconds
# Must be set before adding any arbitrary signals
protocol.set_session_duration(60.0)

# Get the required sampling rate and number of samples
sampling_rate = protocol.get_sampling_rate()
num_samples = protocol.get_num_samples()

# Make a time vector
t = np.arange(num_samples, dtype=np.float64) / sampling_rate

# Make an simple repeating on-off signal
on_duration = 3.0
off_duration = 7.0
period = on_duration + off_duration
on_off_samples = (t % period <= on_duration).astype(np.float64)

# Make a multi-frequency sine wave
freqs = [3.0, 5.0, 10.0, 17.0]
amps = [0.8, 0.3, 0.4, 0.1]
multi_freq_sine_samples = np.sum(
    [a * np.sin(2 * np.pi * f * t) for (a, f) in zip(freqs, amps)],
    axis=0
)

# Scale it to 0-1 range
multi_freq_sine_samples -= multi_freq_sine_samples.min()
multi_freq_sine_samples /= multi_freq_sine_samples.max()

# Plot arbitrary signals
plt.plot(t, on_off_samples)
plt.plot(t, multi_freq_sine_samples)
plt.show()

# Add signals to protocol
on_off = protocol.add_arbitrary_signal(on_off_samples)
multi_freq_sine = protocol.add_arbitrary_signal(multi_freq_sine_samples)

# Wire them to to get on-off temporal inteference stimulation with
# multi-frequency sine wave modulation
protocol.set_amplitude_source(pytims.Coil.A1, index=on_off)
protocol.set_amplitude_source(pytims.Coil.A2, index=on_off)
protocol.set_modulation_source(pytims.Channel.A, index=multi_freq_sine)

# Save the protocol file
protocol.save("arbitrary-signals.tims")