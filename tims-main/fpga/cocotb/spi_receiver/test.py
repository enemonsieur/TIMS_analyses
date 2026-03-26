import cocotb
from cocotb.triggers import Timer
from fractions import Fraction
from cocotb.clock import Clock
from config import CONFIG
from cocotbext.spi import SpiBus, SpiConfig, SpiMaster
from bitstring import BitArray

clk_period = Fraction(1, CONFIG.FPGA_FCLK)
tstart = 10 * clk_period

@cocotb.test()
async def test(dut):
    clock = Clock(dut.clk, clk_period, units="sec")

    spi_bus = SpiBus.from_entity(dut, sclk_name='sck', mosi_name='rx', miso_name='tx', cs_name='cs')
    spi_config = SpiConfig(
        word_width = 8,
        sclk_freq  = CONFIG.INTERFACE_SPI_FREQ,
        cpol       = False,
        cpha       = True,
        msb_first  = True,
        cs_active_low = True
    )

    spi_transmitter = SpiMaster(spi_bus, spi_config)    
    cocotb.start_soon(clock.start())
    dut.data_in_ready = 0
    await Timer(tstart, units='sec')

    dut.data_in_ready = 1
    dut.data_in.value = cocotb.binary.BinaryValue(
        BitArray(CONFIG.INTERFACE_PACKET_VALID_KEY).bin, n_bits=CONFIG.INTERFACE_WORD_NBITS) 
    await Timer(clk_period, 'sec')
    dut.data_in_ready.value = 1

    spi_transmitter.write_nowait(CONFIG.INTERFACE_PACKET_VALID_KEY, burst=True)
    await spi_transmitter.wait()
    read_bytes = await spi_transmitter.read()

    assert(read_bytes == CONFIG.INTERFACE_PACKET_VALID_KEY)
    assert(BitArray(bin = str(dut.data_out.value)).tobytes() == CONFIG.INTERFACE_PACKET_VALID_KEY)
