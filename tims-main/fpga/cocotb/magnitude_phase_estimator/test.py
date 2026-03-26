import numpy as np
import cocotb
from cocotb.triggers import Timer
from fractions import Fraction
from cocotb.clock import Clock
from config import CONFIG
import matplotlib.pyplot as plt
from scipy import signal

clk_period = Fraction(1, CONFIG.FPGA_FCLK)
tstart = 10 * clk_period

SPC = CONFIG.SAMPLES_PER_CARRIER_PERIOD
FP_MAX = 2**(CONFIG.FP_NBITS-1)-1

max_latency = SPC + CONFIG.FB_LOWPASS_FILTER_NTAPS + 6

min_samples = SPC + CONFIG.FB_LOWPASS_FILTER_NTAPS

plot = True


async def run(dut, samples_mag, samples_phase, noise_ac=0.0, noise=0.0):
    dut.sample_ready.value = 0
    dut.rst.value = 1
    await Timer(tstart, units='sec')
    dut.rst.value = 0

    num_samples = len(samples_mag)
    ref_phase = 2 * np.pi * (np.arange(num_samples) % SPC)/SPC

    samples = samples_mag*np.sin(ref_phase + samples_phase)
    ref_sin = np.sin(ref_phase)
    ref_cos = np.cos(ref_phase)

    mag = np.zeros_like(samples_mag)
    phase = np.zeros_like(samples_mag)
    for i in range(num_samples):
        s = samples[i] + noise * np.random.randn()
        s = max(min(s, 1.0), -1)

        dut.sample.value = int(s*FP_MAX)
        dut.ref_sin.value = int(ref_sin[i]*FP_MAX)
        dut.ref_cos.value = int(ref_cos[i]*FP_MAX)
        dut.sample_ready.value = 1
        await Timer(clk_period, units='sec')
        dut.sample_ready.value = 0
        await Timer(max_latency*clk_period, units='sec')
        mag[i] = int(dut.mag.value)/FP_MAX
        phase[i] = 2*np.pi*int(dut.phase.value)/(2**CONFIG.FP_NBITS)

    reconstruction = mag*np.sin(ref_phase + phase)

    return mag, phase, samples, reconstruction


@cocotb.test()
async def simple_test(dut):
    clock = Clock(dut.clk, clk_period, units="sec")
    cocotb.start_soon(clock.start())

    r = 0.3
    theta = 0.2*np.pi

    num_samples = min_samples + SPC*32
    samples_mag = r * np.ones(num_samples)
    samples_phase = theta * np.ones(num_samples)

    mag, phase, samples, reconstruction = await run(
        dut, samples_mag, samples_phase, noise=0.005)

    print(np.std((phase-samples_phase)[min_samples:]))

    if plot:
        plt.figure()
        plt.plot(samples)
        plt.plot(reconstruction)
        plt.plot(mag)
        plt.plot(phase)
        plt.show()


@cocotb.test()
async def static_estimation_test(dut):
    clock = Clock(dut.clk, clk_period, units="sec")
    cocotb.start_soon(clock.start())

    num_samples = min_samples + SPC
    num_points = 10
    mag_errors = []
    phase_errors = []
    for r in np.linspace(0.0, 1.0, num_points):
        for theta in np.linspace(0, 2*np.pi, 20):
            samples_mag = r * np.ones(num_samples)
            samples_phase = theta * np.ones(num_samples)

            mag, phase, samples, reconstruction = await run(dut, samples_mag, samples_phase)
            mag_errors.append(np.mean(np.abs(samples_mag-mag)[min_samples:]))
            phase_errors.append(
                np.mean(np.abs(np.angle(np.exp((samples_phase - phase)*1j)))[min_samples:]))
            assert (mag_errors[-1] < 0.005)
            if r > 0:
                assert (phase_errors[-1] < 0.005)


@cocotb.test()
async def amplitude_modulation_test(dut):
    clock = Clock(dut.clk, clk_period, units="sec")
    cocotb.start_soon(clock.start())

    mod_period = 100*SPC
    num_mod_periods = 1

    ii = np.arange(mod_period*num_mod_periods)
    samples_mag = (1.0+np.sin(2*np.pi*(ii % mod_period)/mod_period))/2
    samples_phase = 0.687 * np.ones_like(ii)

    mag, phase, samples, reconstruction = await run(dut, samples_mag, samples_phase)

    mag_error = np.mean(np.abs(samples_mag - mag)[min_samples:])
    phase_error = np.mean(
        np.abs(np.angle(np.exp((samples_phase - phase)*1j)))[min_samples:])

    print(f'Magnitude error = {mag_error}')
    print(f'Phase error = {phase_error}')

    if plot:
        plt.plot(samples)
        plt.plot(reconstruction)
        plt.plot(mag)
        plt.show()
    assert (mag_error < 0.05)
    assert (phase_error < 0.05)


@cocotb.test()
async def phase_modulation_test(dut):
    clock = Clock(dut.clk, clk_period, units="sec")
    cocotb.start_soon(clock.start())

    mod_period = 100*SPC
    num_mod_periods = 1

    ii = np.arange(mod_period*num_mod_periods)
    mod = (np.sin(2*np.pi*(ii % mod_period)/mod_period)+1)/2
    samples_phase = 2 * np.arccos(mod)
    samples_mag = 1.0 * np.ones_like(samples_phase)

    mag, phase, samples, reconstruction = await run(dut, samples_mag, samples_phase)

    mag_error = np.mean(np.abs(samples_mag - mag)[min_samples:])
    phase_error = np.mean(
        np.abs(np.angle(np.exp((samples_phase - phase)*1j)))[min_samples:])

    print(f'Magnitude error = {mag_error}')
    print(f'Phase error = {phase_error}')
    if plot:
        plt.plot(samples)
        plt.plot(reconstruction)
        plt.plot(mag)
        plt.show()
    assert (mag_error < 0.01)
    assert (phase_error < 0.075)
