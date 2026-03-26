import numpy as np
import cocotb
from cocotb.triggers import Timer
from fractions import Fraction
from cocotb.clock import Clock
from config import CONFIG

clk_period = Fraction(1, CONFIG.FPGA_FCLK)
tstart = 10 * clk_period

SPC = CONFIG.SAMPLES_PER_CARRIER_PERIOD
FP_MAX = 2**(CONFIG.FP_NBITS-1)-1

filter_coefficients = np.sin(2*np.pi/SPC*np.arange(SPC))
CONFIG.write_memfile(
    'filter.mem', (FP_MAX*filter_coefficients).astype(np.int32), 16)


@cocotb.test()
async def test(dut):
    clock = Clock(dut.clk, clk_period, units="sec")
    cocotb.start_soon(clock.start())

    num_samples = int(10.231*SPC)
    ii = np.arange(num_samples)
    for r in np.linspace(0, 1.0, 20):
        dut.rst.value = 1
        dut.sample_ready.value = 0
        await Timer(tstart, 'sec')
        dut.rst.value = 0

        samples = r*np.sin(2*np.pi*(ii % SPC)/SPC+0.2)
        for i in ii:
            dut.sample.value = int(FP_MAX * samples[i])
            dut.sample_ready.value = 1
            await Timer(clk_period, 'sec')
            dut.sample_ready.value = 0

            await Timer(100*clk_period, 'sec')
            out = dut.out.value.signed_integer/FP_MAX
            ref_out = 0
            if i >= SPC-1:
                ref_out = np.sum(filter_coefficients *
                                 samples[i-SPC+1:i+1])/(SPC/2)
            else:
                c = filter_coefficients[SPC-i-1:SPC]
                s = samples[:i+1]
                ref_out = np.sum(c*s)/(SPC/2)

            error = np.abs(ref_out-out)
            assert (error < 0.0005)
