import cocotb
from cocotb.triggers import Timer
from fractions import Fraction
from cocotb.clock import Clock
from config import CONFIG
from cocotbext.spi import SpiBus, SpiConfig, SpiSlaveBase
import numpy as np


class SimpleSpiSlave(SpiSlaveBase):
    def __init__(self, bus):
        self._config = SpiConfig(
            word_width=CONFIG.ADC_NBITS,
            sclk_freq=CONFIG.ADC_SPI_FREQ,
            cpol=False,
            cpha=True,
            msb_first=True,
            cs_active_low=True
        )

        self.content = 0
        self.payload = 0
        super().__init__(bus)

    async def get_content(self):
        await self.idle.wait()
        return self.content

    async def _transaction(self, frame_start, frame_end):
        await frame_start
        self.idle.clear()

        await Timer(2/CONFIG.ADC_SPI_FREQ, units='sec')

        # self.payload = 4094
        self.content = int(
            await self._shift(CONFIG.ADC_NBITS, tx_word=(int(self.payload))))

        await frame_end


def offset_and_scale(v):
    scale = 2**(CONFIG.FP_NBITS-CONFIG.ADC_NBITS)
    offset = (2**CONFIG.ADC_NBITS)/2

    return int(scale * (v-offset))


clk_period = Fraction(1, CONFIG.FPGA_FCLK)
tstart = 10 * clk_period


@cocotb.test()
async def test(dut):
    clock = Clock(dut.clk, clk_period, units="sec")

    device1 = SimpleSpiSlave(SpiBus.from_entity(
        dut, sclk_name='sck', mosi_name='cs_a', miso_name='sdl1', cs_name='cs_a'))

    device2 = SimpleSpiSlave(SpiBus.from_entity(
        dut, sclk_name='sck', mosi_name='cs_a', miso_name='sdl2', cs_name='cs_a'))

    device3 = SimpleSpiSlave(SpiBus.from_entity(
        dut, sclk_name='sck', mosi_name='cs_b', miso_name='sdl3', cs_name='cs_b'))

    device4 = SimpleSpiSlave(SpiBus.from_entity(
        dut, sclk_name='sck', mosi_name='cs_b', miso_name='sdl4', cs_name='cs_b'))

    cocotb.start_soon(clock.start())
    dut.rst.value = 1
    await Timer(tstart, units='sec')
    dut.rst.value = 0
    await Timer(3*clk_period, units='sec')

    for _ in range(1000):
        v1 = np.random.randint(0, 2**CONFIG.ADC_NBITS)
        v2 = np.random.randint(0, 2**CONFIG.ADC_NBITS)
        v3 = np.random.randint(0, 2**CONFIG.ADC_NBITS)
        v4 = np.random.randint(0, 2**CONFIG.ADC_NBITS)

        device1.payload = v1
        device2.payload = v2
        device3.payload = v3
        device4.payload = v4

        await Timer(np.random.randint(1, 50) * clk_period, units='sec')
        dut.trig_a.value = 1
        await Timer(np.random.randint(1, 50) * clk_period, units='sec')
        dut.trig_b.value = 1
        await Timer(50 * clk_period, units='sec')
        dut.trig_a.value = 0
        dut.trig_b.value = 0
        await Timer(50 * clk_period, units='sec')

        o1 = dut.sample1.value.signed_integer
        o2 = dut.sample2.value.signed_integer
        o3 = dut.sample3.value.signed_integer
        o4 = dut.sample4.value.signed_integer

        assert (offset_and_scale(v1) == o1)
        assert (offset_and_scale(v2) == o2)
        assert (offset_and_scale(v3) == o3)
        assert (offset_and_scale(v4) == o4)
