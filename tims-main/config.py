import numpy as np
import os
from bitstring import Bits
from scipy import signal


# Defines system configuration variables. Most variables can be
# overriden by setting an environment variable with the same name
# and re-running the configuration script
class Config:
    def __init__(self):
        np.random.seed(1234)

        # Main clock frequency of the FPGA logic, Hz
        self.FPGA_FCLK = 160000000

        # Total number of bits in fixed-point representation for
        # general signals
        self.FP_NBITS = 16
        self.FP_MAX = 2**(self.FP_NBITS-1) - 1
        self.FP_MIN = -2**(self.FP_NBITS-1)
        self.FP_NVALS = 2**self.FP_NBITS

        # SPI clock frequency for FPGA-PI communication
        self.INTERFACE_SPI_FREQ = self.FPGA_FCLK//32
        self.INTERFACE_SAMPLING_RATE = 5000
        self.INTERFACE_DATA_NUM_CHANNELS = 16
        self.INTERFACE_WORD_NBITS = \
            self.FP_NBITS * self.INTERFACE_DATA_NUM_CHANNELS
        self.INTERFACE_CONFIG_NUM_WORDS = 4
        self.INTERFACE_DATA_NUM_SAMPLES = 256
        self.INTERFACE_PACKET_NUM_WORDS = self.INTERFACE_CONFIG_NUM_WORDS + \
            self.INTERFACE_DATA_NUM_SAMPLES
        self.INTERFACE_PACKET_NBITS = self.INTERFACE_PACKET_NUM_WORDS * \
            self.INTERFACE_WORD_NBITS
        self.INTERFACE_PACKET_NBYTES = self.INTERFACE_PACKET_NBITS // 8
        self.INTERFACE_PACKET_VALID_KEY = np.random.bytes(
            self.INTERFACE_WORD_NBITS/8)
        self.INTERFACE_CONFIG_BIT_ALIGNMENT = 32

        
        self.MONITOR_TRACE_NAMES = [
            "Ma", "MSa", "Ia₁", "ISa₁", "Ia₂", "ISa₂", "Mb", "MSb", "Ib₁", "ISb₁", "Ib₂", "ISb₂", "F1",
            "F2", "F3", "F4",
        ]

        self.MONITOR_TRACE_DESCRIPTIONS = [
            "Actual modulation in channel A",
            "Setpoint signal for channel A modulation",
            "Actual amplitude of coil A1 current",
            "Setpoint signal for amplitude of coil A1 current",
            "Actual amplitude of coil A2 current",
            "Setpoint signal for amplitude of coil A2 current",
            "Actual modulation in channel B",
            "Setpoint signal for channel B modulation",
            "Actual amplitude of coil B1 current",
            "Setpoint signal for amplitude of coil B1 current",
            "Actual amplitude of coil B2 current",
            "Setpoint signal for amplitude of coil B2 current",
            "F1",
            "F2",
            "F3",
            "F4",
        ]

        # Number of bits added in fixed-point calculations that need extra
        # accuracy
        self.FP_EXTRA_BITS = 8

        # Number of fraction bits in PI controller parameters
        self.PI_CONTROLLER_PARAM_FRACTION_BITS = 10

        # Number of bits in ADCs
        self.ADC_NBITS = 12

        # ADC SPI clock frequency, Hz
        self.ADC_SPI_FREQ = 32000000

        # Number of iterations for CORDIC calculations
        self.CORDIC_NUM_ITERATIONS = self.FP_NBITS - 2

        # CORDIC gain correction factor
        Kn = np.prod([1.0 / np.sqrt(1 + 2**(-2*i))
                      for i in range(self.CORDIC_NUM_ITERATIONS)])
        Kn_fixed = int(Kn * 2**(self.FP_NBITS))
        self.CORDIC_K = Kn_fixed

        # If true, sparse cross-correlation will be used in current magnitude
        # and phase calculation meaning that output is only provided once
        # every carrier period
        self.MAG_PHASE_SPARSE = 1

        # Low-pass filter applied to current feedback cartesian coordinates
        # 0 to disable filtering, or 1 for moving average, or 2 for FIR
        self.FB_LOWPASS_FILTER_TYPE = 0
        self.FB_LOWPASS_FILTER_NTAPS = 2
        # In case of FIR filter, cut-off frequency represented as a ratio
        # of the carrier frequency
        self.FB_LOWPASS_FILTER_CUTOFF = 0.4

        # Low-pass filter applied to coil current amplitude setpoint
        # type: 1 for moving average, or 2 for FIR
        self.AMP_SETPOINT_FILTER_TYPE = 1
        self.AMP_SETPOINT_FILTER_NTAPS = 32
        # In case of FIR filter, cut-off frequency represented as a ratio
        # of the carrier frequency
        self.AMP_SETPOINT_FILTER_CUTOFF = 400  # Hz, in case of FIR filter

        # Number of current sensor ADC clock ticks per carrier period
        # Controls the sampling frequency of the ADC
        self.SAMPLES_PER_CARRIER_PERIOD = 32

        # Minimum clock ticks per sample, corresponding to max allowable
        # sampling rate / carrier frequency
        self.MIN_CLK_TICKS_PER_SAMPLE = 100

        # Deadtime duration (high->low and low->high transitions)
        # for half-bridge control, seconds
        # self.PWM_DEADTIME = 250E-9
        self.PWM_DEADTIME = 400E-9
        self.PWM_DEADTIME_NTICKS = int(
            np.ceil(self.FPGA_FCLK * self.PWM_DEADTIME))

        # Resolution of the modulation control input
        self.MODULATION_RESOLUTION_NBITS = 12

        # Enable bits
        self.SYSTEM_ENABLE_BIT = 0
        self.CHA_CONTROLLER_ENABLE_BIT = 1
        self.CHB_CONTROLLER_ENABLE_BIT = 2

        # Stimulation mode bit definitions
        self.MODE_AM_VS_TI_BIT = 0  # true means TI stimulation
        self.MODE_AMPLITUDE_SETPOINT_INT_VS_EXT_BIT = 1  # true means external
        self.MODE_MODULATION_SETPOINT_INT_VS_EXT_BIT = 2  # true means external
        self.MODE_EXT_AMPLITUDE_EQUAL_CURRENTS_BIT = 3
        self.MODE_NBITS = 4

        # Hardware pins and addresses
        self.GPIO_TRIG_PIN = 27

        # Available capacitance values, nF
        self.AVAILABLE_CAPACITANCES = [100, 150, 220, 330]

        # Capacitor bank constants
        self.CAPACITOR_BANK_ADDRESSES = [0x26, 0x25, 0x24, 0x23]
        self.CAPACITOR_BANK_IODIRA = 0x00
        self.CAPACITOR_BANK_OLATA = 0x14
        self.CAPACITOR_BANK_RELAY_PULSE_DURATION = 400 # ms

        # Flow sensor measurement clock freqeuncy = FPGA_FCLK / CLK_DIVIDER
        self.FLOW_SENSOR_CLK_DIVIDER = 16384
        # Maximum measurable half-period of flow sensor output
        # If output half-period exceeds this it is assumed that flow rate is zero
        self.FLOW_SENSOR_MAX_HALF_PERIOD = int(1*self.FPGA_FCLK/self.FLOW_SENSOR_CLK_DIVIDER)
        # flow_rate_lpm = slope * rpm + intercept
        self.FLOW_SENSOR_SLOPE = 5.5021
        self.FLOW_SENSOR_INTERCEPT = 57.425
        self.FLOW_SENSOR_MEAS_FREQ = self.FPGA_FCLK / self.FLOW_SENSOR_CLK_DIVIDER
        
        # Temperature sensor constants
        self.TEMPERATURE_SENSOR_SMA_WINDOW_SIZE = 16
        self.TEMPERATURE_SENSOR_ADC_SPI_FREQ = 1000000
        self.TEMPERATURE_SENSOR_VREF = 3.3
        self.TEMPERATURE_SENSOR_RDIV = 10.0
        self.TEMPERATURE_SENSOR_R0 = 10.0
        self.TEMPERATURE_SENSOR_T0 = 25.0
        self.TEMPERATURE_SENSOR_B = 3435.0

        # SMBUS PSU
        self.SMBUS_PSU_ADDRESS = 0x5f
        self.SMBUS_PSU_CURRENT_READ_CMD = 0x8C
        self.SMBUS_PSU_POWER_READ_CMD = 0x96

        # Connected hardware. Override in environment variables to realize
        # different (testing) configurations. Used only for the rust GUI.
        self.DATA_DIR = "/home/tims/data"
        self.NUM_COILS = 2
        self.NUM_CAPACITOR_BANKS = 2
        self.DRIVER_CONNECTED = 1
        self.PROGRAM_DRIVER_ON_STARTUP = 1
        self.SMBUS_PSU_CONNECTED = 1
        self.TEMPERATURE_SENSORS_CONNECTED = 1
        self.SAFETY_CHECKS_ENABLED = 1
        self.SOUND_DEVICE_AVAILABLE = 1
        self.MAX_CURRENT_SETPOINT = 0.3
        self.MAX_CARRIER_FREQUENCY = 20E3
        self.MAX_CURRENT = 0.5
        self.MAX_TEMPERATURE = 32.0
        self.MIN_FLOW_RATE = 70.0
        self.MAX_POWER = 520.0
        self.MAX_SUPPLY_CURRENT = self.MAX_POWER / 80.0
        
        # Override configuration variables using environment variables
        for key, value in vars(self).items():
            if key in os.environ:
                setattr(self, key, type(value)(os.environ[key]))

        self.PROTOCOLS_DIR = f"{self.DATA_DIR}/protocols"
        self.SETTINGS_DIR = f"{self.DATA_DIR}/settings"
        self.BITSTREAM_FILEPATH = f"{self.DATA_DIR}/bit/tims_fpga.bit"
        self.SETTINGS_FILEPATH = f"{self.SETTINGS_DIR}/current.json"
        self.SETTINGS_DEFAULT_FILEPATH = f"{self.SETTINGS_DIR}/default.json"


    def generate_verilog_config(self, filepath):
        with open(filepath, 'w', encoding='utf-8') as f:
            for key, value in vars(self).items():
                if key == 'INTERFACE_PACKET_VALID_KEY':
                    f.write(f"`define {key} {self.INTERFACE_WORD_NBITS}'h{self.INTERFACE_PACKET_VALID_KEY.hex().upper()}\n")
                elif type(value) is list:
                    pass
                else:
                    f.write(f'`define {key} {value}\n')

    def generate_vivado_config(self, filepath):
        with open(filepath, 'w') as f:
            f.write('set project_name tims_fpga\n')
            f.write('set fpga_part xc7a35tcpg236-1\n')
            f.write('set board_xdc cmod_a7_35t.xdc\n')
            f.write('set board_clk_freq 12\n')
            f.write(f'set fpga_fclk {int(self.FPGA_FCLK/1000000)}\n')
            f.write(f'set fp_nbits {self.FP_NBITS}\n')
            f.write(f'set fp_extra_bits {self.FP_EXTRA_BITS}\n')

    def generate_rust_config(self, filepath):
        with open(filepath, 'w', encoding='utf-8') as f:
            for key, value in vars(self).items():
                f.write("#[allow(unused)]\n")

                if key == "INTERFACE_PACKET_VALID_KEY":
                    valid_key = [b for b in self.INTERFACE_PACKET_VALID_KEY]
                    f.write(f"pub const {key}: [u8;{self.INTERFACE_WORD_NBITS//8}] = {valid_key};\n")

                elif key == 'AVAILABLE_CAPACITANCES':
                    c_vals = [float(v) for v in self.AVAILABLE_CAPACITANCES]
                    f.write(f"pub const {key}: [f64;{len(self.AVAILABLE_CAPACITANCES)}] = {c_vals};\n")

                elif key == 'CAPACITOR_BANK_ADDRESSES':
                    vals = [v for v in self.CAPACITOR_BANK_ADDRESSES]
                    f.write(f"pub const {key}: [u16;{len(self.CAPACITOR_BANK_ADDRESSES)}] = {vals};\n")

                elif key in ["MONITOR_TRACE_NAMES", "MONITOR_TRACE_DESCRIPTIONS"]:
                    rust_str_array = str(value).replace("'", '"')
                    f.write(f"pub const {key}: [&str;{self.INTERFACE_DATA_NUM_CHANNELS}] = {rust_str_array};\n")




                elif key in ["FP_MAX", "FP_MIN"]:
                    f.write(f"pub const {key}: isize = {value};\n")

                elif type(value) is str:
                    f.write(f"pub const {key}: &str = \"{value}\";\n")

                else:
                    f.write(f"pub const {key}: {'usize' if type(value) is int else 'f64'} = {value};\n")

    def generate_sine_table(self, filepath):
        SPC = self.SAMPLES_PER_CARRIER_PERIOD
        sine_table = [int(np.sin(2*np.pi*i/SPC) * self.FP_MAX)
                      for i in range(SPC)]

        self.write_memfile(filepath, sine_table, self.FP_NBITS)

    def generate_cosine_table(self, filepath):
        SPC = self.SAMPLES_PER_CARRIER_PERIOD
        cosine_table = [int(np.cos(2*np.pi*i/SPC) * self.FP_MAX)
                        for i in range(SPC)]

        self.write_memfile(filepath, cosine_table, self.FP_NBITS)

    def generate_cordic_atan_table(self, filepath):
        atan_table = [int((np.arctan(2**(-i))/(2*np.pi))*self.FP_NVALS)
                      for i in range(self.CORDIC_NUM_ITERATIONS)]

        self.write_memfile(filepath, atan_table, self.FP_NBITS)

    def generate_feedback_lowpass_filter(self, filepath):
        if self.FB_LOWPASS_FILTER_TYPE == 2:
            coeffs = signal.firwin(
                numtaps=self.FB_LOWPASS_FILTER_NTAPS,
                cutoff=self.FB_LOWPASS_FILTER_CUTOFF,
                fs=1.0 if self.MAG_PHASE_SPARSE else self.SAMPLES_PER_CARRIER_PERIOD)
            coeffs = (self.FP_MAX*coeffs[::-1]).astype(np.int32)
        elif self.FB_LOWPASS_FILTER_TYPE == 1:
            coeffs = 2**(self.FP_NBITS-1) * \
                np.ones(self.FB_LOWPASS_FILTER_NTAPS) / \
                self.FB_LOWPASS_FILTER_NTAPS
        elif self.FB_LOWPASS_FILTER_TYPE == 0:
            return
        else:
            raise Exception(
                f'Invalid type {self.FB_LOWPASS_FILTER_TYPE} for feedback lowpass filter')

        self.write_memfile(filepath, coeffs, self.FP_NBITS)

    def generate_amp_setpoint_filter(self, filepath):
        if self.AMP_SETPOINT_FILTER_TYPE == 2:
            coeffs = signal.firwin(
                numtaps=self.AMP_SETPOINT_FILTER_NTAPS,
                cutoff=self.AMP_SETPOINT_FILTER_CUTOFF,
                fs=self.INTERFACE_SAMPLING_RATE)
            coeffs = (self.FP_MAX*coeffs[::-1]).astype(np.int32)
        elif self.AMP_SETPOINT_FILTER_TYPE == 1:
            coeffs = 2**(self.FP_NBITS-1) * \
                np.ones(self.AMP_SETPOINT_FILTER_NTAPS) / \
                self.AMP_SETPOINT_FILTER_NTAPS
        else:
            raise Exception(
                f'Invalid filter type {self.AMP_SETPOINT_FILTER_NTAPS}')

        self.write_memfile(filepath, coeffs, self.FP_NBITS)

    def generate_modulation_to_relative_phase_table(self, filepath):
        num_entries = 2**self.MODULATION_RESOLUTION_NBITS
        table = 2 * np.arccos(np.linspace(0, 1, num_entries))/np.pi
        table = np.round(self.FP_MAX * table).astype(np.int32)

        self.write_memfile(filepath, table, self.FP_NBITS)

    def write_memfile(self, filepath, data, nbits, signed=True):
        with open(filepath, 'w') as f:
            for val in data:
                if signed:
                    f.write(Bits(int=val, length=nbits).bin + "\n")
                else:
                    f.write(Bits(uint=val, length=nbits).bin + "\n")


CONFIG = Config()


if __name__ == '__main__':
    dir_path = os.path.dirname(os.path.realpath(__file__))

    CONFIG.generate_verilog_config(os.path.join(dir_path, 'fpga', 'config.sv'))
    CONFIG.generate_rust_config(os.path.join( dir_path, 'interface', 'src', 'config.rs'))
    CONFIG.generate_rust_config(os.path.join( dir_path, 'protocols', 'src', 'config.rs'))
    CONFIG.generate_vivado_config(os.path.join(
        dir_path, 'fpga', 'vivado', 'tcl', 'config.tcl'))

    memfiles_dir = os.path.join(dir_path, 'fpga', 'memfiles')
    if not os.path.exists(memfiles_dir):
        os.mkdir(memfiles_dir)

    CONFIG.generate_sine_table(os.path.join(
        memfiles_dir, 'sine_table.mem'))
    CONFIG.generate_cosine_table(os.path.join(
        memfiles_dir, 'cosine_table.mem'))
    CONFIG.generate_cordic_atan_table(os.path.join(
        memfiles_dir, 'cordic_atan_table.mem'))
    CONFIG.generate_feedback_lowpass_filter(os.path.join(
        memfiles_dir, 'fb_lowpass_filter.mem'))
    CONFIG.generate_amp_setpoint_filter(os.path.join(
        memfiles_dir, 'amp_setpoint_filter.mem'))
    CONFIG.generate_modulation_to_relative_phase_table(os.path.join(
        memfiles_dir, 'modulation_to_relative_phase.mem'))
