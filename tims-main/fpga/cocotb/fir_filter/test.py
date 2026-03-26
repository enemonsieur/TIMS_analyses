import numpy as np
import cocotb
from cocotb.triggers import Timer
from fractions import Fraction
from cocotb.clock import Clock
from config import CONFIG
from scipy import signal
import matplotlib.pyplot as plt

clk_period = Fraction(1, CONFIG.FPGA_FCLK)
tstart = 10 * clk_period

SPC = CONFIG.SAMPLES_PER_CARRIER_PERIOD
FP_MAX = 2**(CONFIG.FP_NBITS-1)-1

num_taps = 16
fs = SPC
cutoff = 1
f = 1/100
tmax = 2/f

coeffs = signal.firwin(num_taps, cutoff=cutoff, fs=fs)
CONFIG.write_memfile('filter.mem', (FP_MAX*coeffs[::-1]).astype(np.int32), 16)

num_samples = int(tmax*fs)
t = np.arange(0, tmax, 1/fs)
samples = 0.5 * np.sin(2*np.pi*f*t)
np.random.seed(1234)
samples += np.random.normal(scale=0.1, size=samples.shape)

filtered = signal.lfilter(b=coeffs, a=1, x=samples)

@cocotb.test()
async def test(dut):
    clock = Clock(dut.clk, clk_period, units="sec")
    cocotb.start_soon(clock.start())

    dut.rst.value = 1
    dut.sample_ready.value = 0
    await Timer(tstart, 'sec')
    dut.rst.value = 0

    out = np.zeros_like(samples)
    for i in np.arange(num_samples):
        dut.sample.value = int(FP_MAX * samples[i])
        dut.sample_ready.value = 1
        await Timer(clk_period, 'sec')
        dut.sample_ready.value = 0

        await Timer((num_taps+5)*clk_period, 'sec')
        out[i] = dut.out.value.signed_integer/FP_MAX

    plt.plot(t, filtered)
    plt.plot(t, out)
    # plt.show()

    for i in np.arange(num_samples):
        error = np.abs(out[i]-filtered[i])
        assert(error<0.0005)
