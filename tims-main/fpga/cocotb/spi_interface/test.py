import cocotb
from cocotb.triggers import Timer, RisingEdge
from fractions import Fraction
from cocotb.clock import Clock
from config import CONFIG
from cocotbext.spi import SpiBus, SpiConfig, SpiMaster
from bitstring import BitArray
import random

random.seed(1234)

N = CONFIG.INTERFACE_DATA_NUM_SAMPLES
W = CONFIG.INTERFACE_WORD_NBITS

clk_period = Fraction(1, CONFIG.FPGA_FCLK)

num_buffer_cycles = 8

monitor_data = [[random.randint(0, 2**W) for _ in range(N)]
                for _ in range(num_buffer_cycles)]
setpoint_data = [[random.randint(0, 2**W) for _ in range(N)]
                 for _ in range(num_buffer_cycles)]

config0 = [random.randint(0, 2**W) for _ in range(num_buffer_cycles)]
config1 = [random.randint(0, 2**W) for _ in range(num_buffer_cycles)]
config2 = [random.randint(0, 2**W) for _ in range(num_buffer_cycles)]
config3 = [random.randint(0, 2**W) for _ in range(num_buffer_cycles)]

status0 = [random.randint(0, 2**W) for _ in range(num_buffer_cycles)]
status1 = [random.randint(0, 2**W) for _ in range(num_buffer_cycles)]
status2 = [random.randint(0, 2**W) for _ in range(num_buffer_cycles)]
status3 = [random.randint(0, 2**W) for _ in range(num_buffer_cycles)]


def generate_setpoint_and_config_packet(cycle):
    packet = BitArray()
    for v in setpoint_data[cycle]:
        packet.append(f'uint{W}={v}')

    packet.append(f'uint{W}={config0[cycle]}')
    packet.append(f'uint{W}={config1[cycle]}')
    packet.append(f'uint{W}={config2[cycle]}')
    packet.append(f'uint{W}={config3[cycle]}')

    return packet


@cocotb.test()
async def test(dut):

    clock = Clock(dut.clk, clk_period, units="sec")

    spi_bus = SpiBus.from_entity(
        dut, sclk_name='sck', mosi_name='rx', miso_name='tx', cs_name='cs')
    spi_config = SpiConfig(
        word_width=8,
        sclk_freq=CONFIG.INTERFACE_SPI_FREQ,
        cpol=False,
        cpha=True,
        msb_first=True,
        cs_active_low=True
    )

    spi_transmitter = SpiMaster(spi_bus, spi_config)
    cocotb.start_soon(clock.start())

    for cycle in range(num_buffer_cycles):
        dut.status0.value = status0[cycle]
        dut.status1.value = status1[cycle]
        dut.status2.value = status2[cycle]
        dut.status3.value = status3[cycle]

        for i in range(N):
            print(f"Cycle {cycle}, sample {i}")

            dut.monitor_data.value = monitor_data[cycle][i]
            await RisingEdge(dut.sampling_clk)
            await Timer(10*clk_period, 'sec')

            if i == 0:
                packet = generate_setpoint_and_config_packet(cycle)
                assert (len(packet) == CONFIG.INTERFACE_PACKET_NBITS)
                spi_transmitter.write_nowait(packet.bytes, burst=True)

            if cycle > 0:
                assert (dut.setpoint_data.value.integer ==
                        setpoint_data[cycle-1][i])

            if i == CONFIG.INTERFACE_DATA_NUM_SAMPLES-1:
                assert (dut.config0.value.integer == config0[cycle])
                assert (dut.config1.value.integer == config1[cycle])
                assert (dut.config2.value.integer == config2[cycle])
                assert (dut.config3.value.integer == config3[cycle])

                reply_packet = BitArray(await spi_transmitter.read())
                data_packet = reply_packet[:N*W]
                status_packet = reply_packet[N*W:]

                assert (status_packet[0*W:1*W].uint == status0[cycle])
                assert (status_packet[1*W:2*W].uint == status1[cycle])
                assert (status_packet[2*W:3*W].uint == status2[cycle])
                assert (status_packet[3*W:4*W].uint == status3[cycle])

                if cycle > 0:
                    for j in range(N):
                        sample = data_packet[j*W:(j+1)*W].uint
                        assert (sample == monitor_data[cycle-1][j])

