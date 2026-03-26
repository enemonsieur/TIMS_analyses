import numpy as np
import cocotb
from cocotb.triggers import Timer
from fractions import Fraction
from cocotb.clock import Clock
from config import CONFIG
import matplotlib.pyplot as plt

clk_period = Fraction(1, CONFIG.FPGA_FCLK)
tstart = 10 * clk_period

clk_ticks_per_sample_all = np.arange(256, 513, 64, dtype=np.int32)

num_carrier_periods = 3

SPC = CONFIG.SAMPLES_PER_CARRIER_PERIOD


@cocotb.test()
async def test(dut):
    clock = Clock(dut.clk, clk_period, units="sec")
    dut.rst.value = 1
    cocotb.start_soon(clock.start())

    await Timer(tstart, units='sec')
    dut.rst.value = 0

    for clk_ticks_per_sample in clk_ticks_per_sample_all:
        await Timer(2121*clk_period, units='sec')

        dut.clk_ticks_per_sample.value = int(clk_ticks_per_sample)
        dut.phase_step.value = int(
            2**(CONFIG.FP_NBITS+CONFIG.FP_EXTRA_BITS) /
            (SPC*clk_ticks_per_sample))
        ideal_phase_step = 2**(CONFIG.FP_NBITS) / (SPC*clk_ticks_per_sample)
        await Timer(clk_period, units='sec')

        phases_out = []
        sin_out = []
        cos_out = []
        ideal_phases = []
        sclk_out = []
        for j in range(num_carrier_periods):
            for i in range(clk_ticks_per_sample*SPC):
                await Timer(clk_period, units='sec')
                phases_out.append(int(dut.phase.value))
                sin_out.append(int(dut.sin.value.signed_integer))
                cos_out.append(int(dut.cos.value.signed_integer))
                ideal_phases.append(i*ideal_phase_step)
                sclk_out.append(int(dut.sclk.value))

        sclk_out = np.array(sclk_out)
        ideal_phases = np.array(ideal_phases)
        phases_out = np.array(phases_out)
        sin_out = np.array(sin_out)
        cos_out = np.array(cos_out)

        error = 100 * \
            np.nanmean(np.abs(
                (phases_out[ideal_phases != 0] - ideal_phases[ideal_phases != 0]) / ideal_phases[ideal_phases != 0]))

        print('CLK ticks per sample = %i\t Phase Error = %0.3f%%' %
              (clk_ticks_per_sample, error))

        assert (error < 0.05)

        assert (np.sum(np.diff(sclk_out) == -1) == num_carrier_periods*SPC)

        ref_sin = (np.sin(2*np.pi*ideal_phases /
                          (2**CONFIG.FP_NBITS))*CONFIG.FP_MAX).astype(np.int16)

        ref_cos = (np.cos(2*np.pi*ideal_phases /
                          (2**CONFIG.FP_NBITS))*CONFIG.FP_MAX).astype(np.int16)

        assert (np.all(sin_out[::clk_ticks_per_sample]
                == ref_sin[::clk_ticks_per_sample]))
        assert (np.all(cos_out[::clk_ticks_per_sample]
                == ref_cos[::clk_ticks_per_sample]))
