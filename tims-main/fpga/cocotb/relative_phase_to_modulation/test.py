import numpy as np
import cocotb
from cocotb.triggers import Timer
from fractions import Fraction
from cocotb.clock import Clock
from config import CONFIG
import matplotlib.pyplot as plt

clk_period = Fraction(1, CONFIG.FPGA_FCLK)
tstart = 10 * clk_period

latency = 22
SPC = CONFIG.SAMPLES_PER_CARRIER_PERIOD

async def run(dut, phase1, phase2, mag1, mag2):
    dut.phase1.value = int((phase1/np.pi) * CONFIG.FP_MAX)
    dut.phase2.value = int((phase2/np.pi) * CONFIG.FP_MAX)
    dut.mag1.value = int(mag1 * CONFIG.FP_MAX)
    dut.mag2.value = int(mag2 * CONFIG.FP_MAX)
    dut.input_ready.value = 1
    await Timer(clk_period, 'sec')
    dut.input_ready.value = 0
    await Timer(latency * clk_period, 'sec')
    mod = float(dut.modulation.value) / CONFIG.FP_MAX
    return mod

@cocotb.test()
async def test(dut):
    clock = Clock(dut.clk, clk_period, unit="sec")
    dut.rst.value = 1
    dut.input_ready.value = 0
    cocotb.start_soon(clock.start())

    await Timer(tstart, 'sec')
    dut.rst.value = 0

    mod_period = 100*SPC
    num_mod_periods = 1
    mag1, mag2 = 0.7, 0.9
    num_samples = num_mod_periods * mod_period
    ii = np.arange(num_samples)
    mod_unscaled_correct = (np.sin(2*np.pi*(ii%mod_period)/mod_period)+1)/2
    mod_correct = (mag1 + mag2)/2 * mod_unscaled_correct

    relphase = 2 * np.arccos(mod_unscaled_correct)
    phase1 = relphase/2
    phase2 = -relphase/2

    mod_out = np.array([await run(dut, p1, p2, mag1, mag2) for (p1, p2) in zip(phase1, phase2)])

    error = np.mean(np.abs(mod_correct - mod_out))
    print(f"Error = {error}")
    assert (error < 0.002)

    plt.plot(mod_correct)
    plt.plot(mod_out)
    plt.show()
