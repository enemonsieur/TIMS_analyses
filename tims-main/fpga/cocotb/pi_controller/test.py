import numpy as np
import cocotb
from cocotb.triggers import Timer
from fractions import Fraction
from cocotb.clock import Clock
from config import CONFIG

latency = 6

clk_period = Fraction(1, CONFIG.FPGA_FCLK)
tstart = 10 * clk_period

def float_to_signed_fixed_point(value,
                                total_bits=CONFIG.FP_NBITS,
                                fraction_bits=CONFIG.PI_CONTROLLER_PARAM_FRACTION_BITS):
    # Calculate the scaling factor
    scaling_factor = 1 << fraction_bits  # Equivalent to 2^fraction_bits
    
    # Scale the float to fixed point
    fixed_value = int(round(value * scaling_factor))
    
    # Calculate min and max values based on total_bits
    max_val = (1 << (total_bits - 1)) - 1  # Maximum positive value
    min_val = -(1 << (total_bits - 1))     # Minimum negative value
    
    # Saturate if out of bounds
    if fixed_value > max_val:
        print(f"Warning: Value {fixed_value} exceeds max, saturating to {max_val}.")
        fixed_value = max_val
    elif fixed_value < min_val:
        print(f"Warning: Value {fixed_value} below min, saturating to {min_val}.")
        fixed_value = min_val
    
    return fixed_value

@cocotb.test()
async def test(dut):
    clock = Clock(dut.clk, clk_period, units="sec")
    dut.rst.value = 1
    dut.input_ready.value = 0
    cocotb.start_soon(clock.start())
    await Timer(tstart, units='sec')

    num_samples = 20
    num_tests = 5000

    np.random.seed(1234)
    for j in range(num_tests):
        Kp = np.random.uniform(-1, 1)
        Ki = np.random.uniform(0, 1) * Kp
        error = np.random.uniform(-1, 1)
        
        dut.rst.value = 1
        await Timer(clk_period, 'sec')
        dut.rst.value = 0
        await Timer(clk_period, 'sec')
        
        dut.p_factor.value = float_to_signed_fixed_point(Kp)
        dut.i_factor.value = float_to_signed_fixed_point(Ki)
        dut.error.value = int(error * CONFIG.FP_MAX)

        i_term = 0
        for i in range(num_samples):
            dut.input_ready.value = 1
            await Timer(clk_period, 'sec')
            dut.input_ready.value = 0

            await Timer(latency*clk_period, 'sec')
            out = dut.out.value.signed_integer/CONFIG.FP_MAX

            p_term = Kp * error
            i_term += Ki * error
            out_ref = p_term + i_term
            out_ref = min(max(out_ref, -1), 1)
            assert(np.abs(out_ref - out) < 0.0005*(i+1))
