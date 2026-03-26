import numpy as np
import cocotb
from cocotb.triggers import Timer
from fractions import Fraction
from cocotb.clock import Clock
from config import CONFIG
import matplotlib.pyplot as plt

clk_period = Fraction(1, CONFIG.FPGA_FCLK)
tstart = 10 * clk_period

latency = 1

SPC = CONFIG.SAMPLES_PER_CARRIER_PERIOD

async def run(dut, modulation):
    dut.modulation.value = int(modulation * CONFIG.FP_MAX)
    dut.input_ready.value = 1
    await Timer(clk_period, 'sec')
    dut.input_ready.value = 0
    await Timer(latency * clk_period, 'sec')
    return np.pi*dut.relative_phase.value / CONFIG.FP_MAX

@cocotb.test()
async def test(dut):
    clock = Clock(dut.clk, clk_period, units="sec")
    dut.rst.value = 1
    dut.input_ready.value = 0
    cocotb.start_soon(clock.start())

    await Timer(tstart, units='sec')
    dut.rst.value = 0

    mod_period = 100*SPC
    num_mod_periods = 1
    num_samples = num_mod_periods * mod_period
    ii = np.arange(num_samples)
    mod = (np.sin(2*np.pi*(ii%mod_period)/mod_period)+1)/2

    relative_phase_out = np.array([await run(dut, m) for m in mod])
    relative_phase_correct = 2 * np.arccos(mod)

    error = np.mean(np.abs(relative_phase_correct - relative_phase_out))
    print(f"Error = {error}")
    assert (error < 0.001)

    s1 = np.sin(2*np.pi*(ii%SPC)/SPC + relative_phase_out/2)
    s2 = np.sin(2*np.pi*(ii%SPC)/SPC - relative_phase_out/2)
    
    plt.plot(mod)
    plt.plot((s1+s2)/2)
    plt.show()
