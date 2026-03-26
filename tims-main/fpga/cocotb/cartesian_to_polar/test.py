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

    mag_scale_factor = 2**(CONFIG.FP_NBITS-1) - 1

    mag_errors = []
    phase_errors = []

    for r in np.linspace(0.01, 1, 100):
        for theta in np.linspace(0, 2*np.pi, 100):
            dut.x.value = int(r * np.cos(theta) * mag_scale_factor)
            dut.y.value = int(r * np.sin(theta) * mag_scale_factor)

            dut.input_ready.value = 1
            await Timer(clk_period, units='sec')
            dut.input_ready.value = 0
            await Timer(latency*clk_period, units='sec')
            mag = int(dut.mag.value)
            phase = int(dut.phase.value)

            r_out = mag/mag_scale_factor
            theta_out = 2*np.pi*phase/(2**CONFIG.FP_NBITS)

            mag_errors.append(np.abs(r-r_out))
            phase_errors.append(
                np.abs(np.angle(np.exp((theta - theta_out)*1j))))

    mag_error = np.mean(mag_errors)
    phase_error = np.mean(phase_errors)

    print(f'Magnitude error = {mag_error}')
    print(f'Phase error = {phase_error}')

    assert (mag_error < 0.00005)
    assert (phase_error < 0.0005)
