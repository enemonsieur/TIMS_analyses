import os
import numpy as np
from config import CONFIG

carrier_frequency = 20E3
# carrier_frequency = 35E3
modulation_frequency = 200
series_resistance = 0.15
coil_inductance = 120E-6
# coil_inductance = 45E-6
coupling_factor = 0.05
mode = 2**CONFIG.MODE_AM_VS_TI_BIT  # for TI stimulation
# mode = 0  # for AM stimulation

ramp_time = 0  # 5E-3
num_mod_cycles = 2

amplitude1 = 0.5
amplitude2 = amplitude1

Kp = 5.0
Ki = 1.0

inductance_difference = 0.0E-6
capacitance_mismatch = 02E-9


class SimParams:
    def __init__(self):

        self.R1 = series_resistance
        self.R2 = self.R1

        self.L1 = coil_inductance + inductance_difference/2
        self.L2 = coil_inductance - inductance_difference/2
        self.COUPLING_FACTOR = coupling_factor

        C = (1.0/(2*np.pi*carrier_frequency))**2 / coil_inductance
        self.C1 = C + capacitance_mismatch
        self.C2 = self.C1

        self.FCLK = CONFIG.FPGA_FCLK
        self.CLK_TICKS_PER_SAMPLE = int(np.round(self.FCLK / (carrier_frequency * CONFIG.SAMPLES_PER_CARRIER_PERIOD)))
        # self.CLK_TICKS_PER_SAMPLE = 100
        # self.FCLK = self.CLK_TICKS_PER_SAMPLE * \
        #     CONFIG.SAMPLES_PER_CARRIER_PERIOD * carrier_frequency
        # print(self.FCLK)

        self.FMOD = modulation_frequency
        self.TRAMP = ramp_time
        self.TMAX = num_mod_cycles / modulation_frequency + ramp_time

        self.PHASE_STEP = int(
            2**(CONFIG.FP_NBITS+CONFIG.FP_EXTRA_BITS)
            / (self.CLK_TICKS_PER_SAMPLE * CONFIG.SAMPLES_PER_CARRIER_PERIOD))

        self.AMPLITUDE1 = amplitude1
        self.AMPLITUDE2 = amplitude2

        self.FP_NBITS = CONFIG.FP_NBITS

        self.SIM_DEADTIME_NTICKS = int(
            np.ceil(self.FCLK * CONFIG.PWM_DEADTIME))
        self.SIM_ADC_NBITS = 8

        self.KP = int(Kp*(2**CONFIG.PI_CONTROLLER_PARAM_FRACTION_BITS))
        self.KI = int(Ki*(2**CONFIG.PI_CONTROLLER_PARAM_FRACTION_BITS))

        self.MODE = mode

    def generate_verilog_params(self, filepath):
        with open(filepath, 'w') as f:
            for key, value in vars(self).items():
                f.write(f'`define {key} {value}\n')

    def generate_spice_params(self, filepath):
        with open(filepath, 'w') as f:
            f.write("* Simulation parameters\n")
            for key, value in vars(self).items():
                f.write(f'.param {key} = {value}\n')


PARAMS = SimParams()

if __name__ == "__main__":
    dir_path = os.path.dirname(os.path.realpath(__file__))

    PARAMS.generate_verilog_params(os.path.join(dir_path, 'params.sv'))
    PARAMS.generate_spice_params(os.path.join(dir_path, 'params.cir'))
