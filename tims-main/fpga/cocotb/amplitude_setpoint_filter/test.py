import numpy as np
import cocotb
from cocotb.triggers import Timer
from fractions import Fraction
from cocotb.clock import Clock
from config import CONFIG
import matplotlib.pyplot as plt

clk_period = Fraction(1, CONFIG.FPGA_FCLK)
tstart = 10 * clk_period

FP_MAX = 2**(CONFIG.FP_NBITS-1)-1

tmax = 10E-3  # sec
fs = CONFIG.INTERFACE_SAMPLING_RATE
t = np.arange(0, tmax, 1.0/fs)
y = (t > tmax/2).astype(np.float64)


@cocotb.test()
async def run(dut):
    dut.rst.value = 1
    await Timer(tstart, units='sec')
    dut.rst.value = 0

    clock = Clock(dut.clk, clk_period, units="sec")
    cocotb.start_soon(clock.start())

    z = np.zeros_like(y)
    for i, yi in enumerate(y):
        dut.setpoint.value = int(FP_MAX * yi)
        await Timer(1.0/fs, "sec")
        z[i] = float(dut.setpoint_filtered.value) / FP_MAX

    plt.plot(t, y)
    plt.plot(t, z)
    plt.show()
