import spidev
import RPi.GPIO as GPIO
import numpy as np
from bitstring import BitArray
from config import CONFIG

TRIG_GPIO = 27

spi = spidev.SpiDev()
spi.open(0, 0)
spi.max_speed_hz = 10000000
spi.mode = 0b01

class FPGA:
    N = CONFIG.INTERFACE_DATA_NUM_SAMPLES
    C = CONFIG.INTERFACE_CONFIG_NUM_WORDS
    M = CONFIG.INTERFACE_DATA_NUM_CHANNELS
    W = CONFIG.INTERFACE_WORD_NBITS
    Q = CONFIG.FP_NBITS
    SPC = CONFIG.SAMPLES_PER_CARRIER_PERIOD
    V = CONFIG.INTERFACE_CONFIG_BIT_ALIGNMENT

    rst = 1
    stimulation_mode = CONFIG.MODE_TEMPORAL_INTERFERENCE
    clk_ticks_per_sample1 = 0
    clk_ticks_per_sample2 = 0
    phase_step1 = 0
    phase_step2 = 0
    p_factor = 0
    i_factor = 0

    amplitude1 = np.zeros(N, dtype=np.float32)+1
    amplitude2 = np.zeros(N, dtype=np.float32)+1
    amplitude3 = np.zeros(N, dtype=np.float32)
    amplitude4 = np.zeros(N, dtype=np.float32)
    modulation_a = np.zeros(N, dtype=np.float32)
    modulation_b = np.zeros(N, dtype=np.float32)

    def set_carrier_frequency(self, channel, frequency):
        clk_ticks_per_sample = int(np.round(CONFIG.FPGA_FCLK/(self.SPC*frequency)))
        phase_step = int(2**(self.Q+CONFIG.FP_EXTRA_BITS) / (clk_ticks_per_sample * self.SPC)) 

        actual_frequency = CONFIG.FPGA_FCLK / (self.SPC*clk_ticks_per_sample)
        print(f'Setting carrier frequency of channel {channel} to {actual_frequency}')
        
        if channel == 1:
            self.clk_ticks_per_sample1 = clk_ticks_per_sample
            self.phase_step1 = phase_step
        elif channel == 2:
            self.clk_ticks_per_sample2 = clk_ticks_per_sample
            self.phase_step2 = phase_step
        else:
            print(f'Invalid channel: {channel}')

    def generate_setpoint_and_config_packet(self):
        packet = BitArray()
        for i in range(CONFIG.INTERFACE_DATA_NUM_SAMPLES):
            setpoint_vals = [
                self.amplitude1[i],
                self.amplitude2[i],
                self.amplitude3[i],
                self.amplitude4[i],
                self.modulation_a[i],
                self.modulation_b[i],
                0, 0, 0, 0, 0, 0, 0, 0, 0, 0
            ]

            for v in setpoint_vals:
                packet.append(f'int{CONFIG.FP_NBITS}={int(v*CONFIG.FP_MAX)}')

        packet.append(CONFIG.INTERFACE_PACKET_VALID_KEY)
        config_vals = [
            self.rst,
            self.stimulation_mode,
            self.clk_ticks_per_sample1,
            self.clk_ticks_per_sample2,
            self.phase_step1,
            self.phase_step2,
            self.p_factor,
            self.i_factor
        ]

        for v in config_vals:
            packet.append(f'uint{self.V}={v}')
        for _ in range(CONFIG.INTERFACE_CONFIG_NUM_WORDS-2):
            packet.append(f'uint{CONFIG.INTERFACE_WORD_NBITS}=0')

        return packet

if __name__ == '__main__':
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(TRIG_GPIO, GPIO.IN)

    fpga = FPGA()
    fpga.rst = 0
    fpga.set_carrier_frequency(1, 20000)
    packet = fpga.generate_setpoint_and_config_packet().bytes
    
    while True:
        GPIO.wait_for_edge(TRIG_GPIO, GPIO.RISING)
        reply_packet = bytes(spi.xfer3(packet)[32*FPGA.N:32*FPGA.N+32]).hex()
        print(reply_packet)
