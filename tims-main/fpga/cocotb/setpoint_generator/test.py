import numpy as np
import cocotb
from cocotb.triggers import Timer
from fractions import Fraction
from cocotb.clock import Clock
from config import CONFIG
import matplotlib.pyplot as plt

clk_period = Fraction(1, CONFIG.FPGA_FCLK)
tstart = 10 * clk_period

latency = 5

SPC = CONFIG.SAMPLES_PER_CARRIER_PERIOD
mod_period = 100*SPC
num_mod_periods = 1


async def run(dut, amplitude1, amplitude2, modulation, mode):
    num_samples = len(modulation)
    ii = np.arange(num_samples)
    ref_phase = ((ii % SPC)/SPC)
    setpoint1 = np.zeros_like(ii, dtype=np.float32)
    setpoint2 = np.zeros_like(ii, dtype=np.float32)
    for i in ii:
        dut.amplitude1.value = int(amplitude1 * CONFIG.FP_MAX)
        dut.amplitude2.value = int(amplitude2 * CONFIG.FP_MAX)
        dut.modulation.value = int(modulation[i] * CONFIG.FP_MAX)
        dut.mode.value = int(mode)
        dut.input_ready.value = 1
        await Timer(clk_period, 'sec')
        dut.input_ready.value = 0
        await Timer(latency * clk_period, 'sec')

        setpoint_mag1 = dut.setpoint_mag1.value.signed_integer / CONFIG.FP_MAX
        setpoint_mag2 = dut.setpoint_mag2.value.signed_integer / CONFIG.FP_MAX
        setpoint_phase1 = dut.setpoint_phase1.value.signed_integer / CONFIG.FP_MAX
        setpoint_phase2 = dut.setpoint_phase2.value.signed_integer / CONFIG.FP_MAX

        setpoint1[i] = setpoint_mag1 * \
            np.sin(ref_phase[i]*2*np.pi + setpoint_phase1*np.pi)
        setpoint2[i] = setpoint_mag2 * \
            np.sin(ref_phase[i]*2*np.pi + setpoint_phase2*np.pi)

    return setpoint1, setpoint2, ref_phase


@cocotb.test()
async def amplitude_modulation_test(dut):
    clock = Clock(dut.clk, clk_period, units="sec")
    dut.rst.value = 1
    dut.input_ready.value = 0
    cocotb.start_soon(clock.start())

    await Timer(tstart, units='sec')
    dut.rst.value = 0

    mod = (np.sin(2*np.pi*(np.arange(mod_period*num_mod_periods) %
           mod_period)/mod_period)+1)/2
    mode = 0
    np.random.seed(12334)
    for a1 in np.linspace(0, 1, 10):
        a2 = np.random.uniform(0, 1)

        setpoint1, setpoint2, ref_phase = await run(dut, a1, a2, mod, mode)

        setpoint1_ref = a1 * mod * np.sin(ref_phase*2*np.pi)
        setpoint2_ref = a2 * mod * np.sin(ref_phase*2*np.pi)

        assert (np.mean(np.abs(setpoint1_ref - setpoint1)) < 0.0001)
        assert (np.mean(np.abs(setpoint2_ref - setpoint2)) < 0.0001)


@cocotb.test()
async def temporal_interference_test(dut):
    clock = Clock(dut.clk, clk_period, units="sec")
    dut.rst.value = 1
    dut.input_ready.value = 0
    cocotb.start_soon(clock.start())

    await Timer(tstart, units='sec')
    dut.rst.value = 0

    mod = (np.sin(2*np.pi*(np.arange(mod_period*num_mod_periods) %
           mod_period)/mod_period)+1)/2
    mode = 2**CONFIG.MODE_AM_VS_TI_BIT
    for a in np.linspace(0, 1, 10):
        setpoint1, setpoint2, ref_phase = await run(dut, a, a, mod, mode)

        relative_phase_ref = 2 * np.arccos(mod)
        setpoint1_ref = a * np.sin(ref_phase*2*np.pi + relative_phase_ref/2)
        setpoint2_ref = a * np.sin(ref_phase*2*np.pi - relative_phase_ref/2)

        assert (np.mean(np.abs(setpoint1_ref - setpoint1)) < 0.0005)
        assert (np.mean(np.abs(setpoint2_ref - setpoint2)) < 0.0005)
