import cocotb
from cocotb.triggers import Timer
from fractions import Fraction
from cocotb.clock import Clock
from config import CONFIG
import numpy as np


clk_period = Fraction(1, CONFIG.FPGA_FCLK)
tstart = 10 * clk_period
latency = 4


@cocotb.test()
async def test(dut):
    clock = Clock(dut.clk, clk_period, units="sec")

    dut.rst.value = 1
    cocotb.start_soon(clock.start())
    dut.rst.value = 0

    for _ in range(1000):
        x = np.random.randint(CONFIG.FP_MIN, CONFIG.FP_MAX)
        y = np.random.randint(CONFIG.FP_MIN, CONFIG.FP_MAX)

        dut.x.value = int(x)
        dut.y.value = int(y)

        await Timer(latency * clk_period, units='sec')
        out = dut.out.value.signed_integer

        ref = x*y/(2**(CONFIG.FP_NBITS-1))

        error = np.abs(ref-out)

        assert (error < 1.0)
