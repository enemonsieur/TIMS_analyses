import numpy as np
import cocotb
from cocotb.triggers import Timer
from fractions import Fraction
from cocotb.clock import Clock
from config import CONFIG

clk_period = Fraction(1, CONFIG.FPGA_FCLK)
tstart = 10 * clk_period


@cocotb.test()
async def test(dut):
    clock = Clock(dut.clk, clk_period, units="sec")
    cocotb.start_soon(clock.start())
    await Timer(tstart, units='sec')

    for i in range(5):
        dut.signal.value = 1
        await Timer(10*16384*clk_period, 'sec')
        dut.signal.value = 0
        await Timer(10*16384*clk_period, 'sec')
