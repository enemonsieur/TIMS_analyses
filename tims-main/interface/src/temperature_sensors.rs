use rppal::spi::{Bus, Mode, SlaveSelect, Spi};
use simple_moving_average::{SMA, SumTreeSMA};

pub const NUM_SENSORS: usize = 16;
const N: usize = NUM_SENSORS;
const SMA_WINDOW_SIZE: usize = 16;
const SPI_FREQ: u32 = 1000000;
const VREF: f64 = 3.3;
const RDIV: f64 = 10.0;
const R0: f64 = 10.0;
const T0: f64 = 25.0;
const B: f64 = 3435.0;

pub struct TemperatureSensors {
    pub temperature: [f64; N],
    adc0_bus: Spi,
    adc1_bus: Spi,
    rx_buffer: [u8; 3],
    tx_buffer: [u8; 3],
    sma: [SumTreeSMA<f64, f64, SMA_WINDOW_SIZE>; N],
}

impl TemperatureSensors {
    pub fn new() -> Self {
        TemperatureSensors {
            temperature: [-1.0; N],
            adc0_bus: Spi::new(Bus::Spi1, SlaveSelect::Ss0, SPI_FREQ, Mode::Mode1).unwrap(),
            adc1_bus: Spi::new(Bus::Spi1, SlaveSelect::Ss1, SPI_FREQ, Mode::Mode1).unwrap(),
            rx_buffer: [0; 3],
            tx_buffer: [0; 3],
            sma: core::array::from_fn(|_| SumTreeSMA::<f64, f64, SMA_WINDOW_SIZE>::new()),
        }
    }

    pub fn read(&mut self) {
        for i in 0..16 {
            self.read_channel(i);
        }
    }

    fn read_channel(&mut self, channel: usize) {
        let adc_ch = (if channel < 8 { channel } else { channel - 8 }) as u8;

        self.tx_buffer[0] = 6 | (adc_ch & 4) >> 2;
        self.tx_buffer[1] = (adc_ch & 3) << 6;

        if channel < 8 {
            self.adc0_bus
                .transfer(&mut self.rx_buffer, &self.tx_buffer)
                .unwrap();
        } else {
            self.adc1_bus
                .transfer(&mut self.rx_buffer, &self.tx_buffer)
                .unwrap();
        }

        let data: u16 = (((self.rx_buffer[1] as u16) & 15) << 8) + self.rx_buffer[2] as u16;

        let v: f64 = (data as f64 / 4096.0) * VREF;

        let r = v * RDIV / (VREF - v);

        let temp = 1.0 / (1.0 / (T0 + 273.15) + (1.0 / B) * f64::ln(r / R0)) - 273.15;

        self.sma[channel].add_sample(temp);

        self.temperature[channel] = self.sma[channel].get_average();
    }
}
