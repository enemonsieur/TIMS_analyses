import numpy as np
import cocotb
from cocotb.triggers import Timer
from fractions import Fraction
from cocotb.clock import Clock
from config import CONFIG
import matplotlib.pyplot as plt

clk_period = Fraction(1, CONFIG.FPGA_FCLK)
tstart = 10 * clk_period

latency = 100

SPC = CONFIG.SAMPLES_PER_CARRIER_PERIOD
mod_period = 100*SPC
num_mod_periods = 1
amplitude = 0.5

feedback_amplitude = 0.5
feedback_phase_offset = 0.5

Kp = 0.5
Ki = 0.001

@cocotb.test()
async def test(dut):
    num_samples = mod_period * num_mod_periods
    ii = np.arange(num_samples)
    ref_phase = ((ii%SPC)/SPC)
    mod = (np.sin(2*np.pi*(np.arange(num_samples)%mod_period)/mod_period)+1)/2
    relative_phase = (2 * np.arccos(mod))/(2*np.pi)
    
    setpoint_mag = amplitude * np.ones(num_samples)
    setpoint_phase = ref_phase
    feedback = feedback_amplitude * np.sin(2*np.pi*ref_phase + feedback_phase_offset)
    
    clock = Clock(dut.clk, clk_period, units="sec")
    dut.rst.value = 1
    dut.input_ready.value = 0
    dut.p_factor.value = int(Kp * 2**CONFIG.PI_CONTROLLER_PARAM_FRACTION_BITS)
    dut.i_factor.value = int(Ki * 2**CONFIG.PI_CONTROLLER_PARAM_FRACTION_BITS)
    cocotb.start_soon(clock.start())

    await Timer(tstart, units='sec')
    dut.rst.value = 0

    for i in ii:
        dut.setpoint_mag.value = int(setpoint_mag[i] * CONFIG.FP_MAX)
        dut.setpoint_phase.value = int(setpoint_phase[i] * 2**CONFIG.FP_NBITS)
        dut.sample.value = int(feedback[i] * CONFIG.FP_MAX)
        dut.input_ready.value = 1
        await Timer(clk_period, 'sec')
        dut.input_ready.value = 0
        await Timer(latency * clk_period, 'sec')
