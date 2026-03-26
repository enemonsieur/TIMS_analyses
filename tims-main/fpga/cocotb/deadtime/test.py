import numpy as np
import cocotb
from cocotb.triggers import Timer
from fractions import Fraction
from cocotb.clock import Clock
from config import CONFIG

clk_period = Fraction(1, CONFIG.FPGA_FCLK)
tstart = 10 * clk_period

max_pulse_duration = 4*CONFIG.PWM_DEADTIME_NTICKS
pulse_durations = np.arange(0, max_pulse_duration, 1)


@cocotb.test()
async def test(dut):
    clock = Clock(dut.clk, clk_period, units="sec")
    dut.rst.value = 1
    cocotb.start_soon(clock.start())
    await Timer(tstart, units='sec')
    dut.rst.value = 0

    for pulse_duration in pulse_durations:
        H = []
        L = []
        for i in range(max_pulse_duration*2):
            dut.SIG.value = int((i < pulse_duration))
            await Timer(clk_period, units='sec')
            H.append(int(dut.H.value))
            L.append(int(dut.L.value))

        H = np.array(H)
        L = np.array(L)

        assert (np.sum(H*L) == 0)

        if pulse_duration > CONFIG.PWM_DEADTIME_NTICKS+1:
            assert (np.where(H == 1)[0][0] == CONFIG.PWM_DEADTIME_NTICKS)
            assert (np.where(L == 1)[0][0] ==
                    CONFIG.PWM_DEADTIME_NTICKS+pulse_duration)
