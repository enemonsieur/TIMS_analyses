import numpy as np
import cocotb
from cocotb.triggers import Timer
from fractions import Fraction
from cocotb.clock import Clock
from config import CONFIG

SPC = CONFIG.SAMPLES_PER_CARRIER_PERIOD
clk_period = Fraction(1, CONFIG.FPGA_FCLK)
tstart = 10 * clk_period

carrier_freq = 40E3
clk_ticks_per_sample = int(CONFIG.FPGA_FCLK / (SPC*carrier_freq))
phase_step = CONFIG.FP_NVALS / (SPC*clk_ticks_per_sample)


@cocotb.test()
async def test(dut):
    duty_cycles = np.linspace(0, 1.0, 20)
    num_periods = 1.65

    clock = Clock(dut.clk, clk_period, units="sec")
    dut.rst.value = 1
    cocotb.start_soon(clock.start())
    await Timer(tstart, units='sec')

    for D in duty_cycles:
        dut.phase_offset.value = 0
        dut.duty_cycle.value = int(D*CONFIG.FP_MAX)
        dut.rst.value = 0

        S1 = []
        S2 = []
        phases = []
        for i in range(int(num_periods*SPC*clk_ticks_per_sample)):
            phase = int(i*phase_step) % CONFIG.FP_NVALS
            dut.ref_phase.value = phase
            phases.append(phase)
            await Timer(clk_period, units='sec')
            S1.append(int(dut.S1.value))
            S2.append(int(dut.S2.value))

        S = np.array(S1)-np.array(S2)

        error = np.abs(np.mean(np.abs(S[-SPC*clk_ticks_per_sample:]))-D)
        print(f'Duty cycle = {D}, error = {error:0.5f}')
        assert error < 0.001

    num_periods = 1.73
    phase_offsets = np.linspace(0, 2*np.pi, 20)
    dut.rst.value = 1
    await Timer(10*clk_period, units='sec')

    for phase_offset in phase_offsets:
        dut.phase_offset.value = int(
            (2**(CONFIG.FP_NBITS)-1)*phase_offset/(2*np.pi))
        dut.duty_cycle.value = int(1.0*CONFIG.FP_MAX)
        dut.rst.value = 0

        S1 = []
        S2 = []
        phases = []
        for i in range(int(num_periods*SPC*clk_ticks_per_sample)):
            phase = int(i*phase_step) % CONFIG.FP_NVALS
            dut.ref_phase.value = phase
            phases.append(phase)
            await Timer(clk_period, units='sec')
            S1.append(int(dut.S1.value))
            S2.append(int(dut.S2.value))

        S = np.array(S1)-np.array(S2)
        phases = np.array(phases).astype(np.float64)/CONFIG.FP_NVALS

        ref_sig = np.sign(np.sin(2*np.pi*phases + phase_offset))
        error = np.mean(np.abs(ref_sig-S))
        print(f'Phase offset = {phase_offset}, error = {error:0.5f}')
        assert (error < 0.005)
