import numpy as np
import cocotb
from cocotb.triggers import Timer
from fractions import Fraction
from cocotb.clock import Clock
from config import CONFIG


clk_period = Fraction(1, CONFIG.FPGA_FCLK)
tstart = 10 * clk_period

latency = CONFIG.FP_NBITS + 1

@cocotb.test()
async def test(dut):
    clock = Clock(dut.clk, clk_period, units="sec")
    dut.rst.value = 1
    dut.input_ready.value = 0
    cocotb.start_soon(clock.start())

    await Timer(tstart, units='sec')

    dut.rst.value = 0

    x_errors = []
    y_errors = []

    for r in np.linspace(0, 1, 100):
        for theta in np.linspace(-1, 1, 100):
            dut.mag.value = int(r*CONFIG.FP_MAX)
            dut.phase.value = int(theta*CONFIG.FP_MAX)
            dut.input_ready.value = 1
            await Timer(clk_period, units='sec')
            dut.input_ready.value = 0
            await Timer(latency*clk_period, units='sec')
            x = dut.x.value.signed_integer/CONFIG.FP_MAX
            y = dut.y.value.signed_integer/CONFIG.FP_MAX

            x_ref = r * np.cos(theta*np.pi)
            y_ref = r * np.sin(theta*np.pi)

            x_errors.append(np.abs(x-x_ref))
            y_errors.append(np.abs(y-y_ref))

            assert(x_errors[-1] < 0.001)
            assert(y_errors[-1] < 0.001)

    x_error = np.mean(x_errors)
    y_error = np.mean(y_errors)

    print(f'x error = {x_error}')
    print(f'y error = {y_error}')
