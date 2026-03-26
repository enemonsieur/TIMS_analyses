use std::error;

use rppal::spi::{Bus, Mode, SlaveSelect, Spi};
use simple_moving_average::{SMA, SumTreeSMA};

use config::TEMPERATURE_SENSOR_ADC_SPI_FREQ as SPI_FREQ;
use config::TEMPERATURE_SENSOR_B as B;
use config::TEMPERATURE_SENSOR_R0 as R0;
use config::TEMPERATURE_SENSOR_RDIV as RDIV;
use config::TEMPERATURE_SENSOR_SMA_WINDOW_SIZE as SMA_WINDOW_SIZE;
use config::TEMPERATURE_SENSOR_T0 as T0;
use config::TEMPERATURE_SENSOR_VREF as VREF;
use protocols::config;

type Result<T> = std::result::Result<T, Box<dyn error::Error>>;

pub struct TemperatureSensors {
    temperature: Vec<f64>,
    num_sensors: usize,
    adc0_bus: Spi,
    adc1_bus: Spi,
    rx_buffer: [u8; 3],
    tx_buffer: [u8; 3],
    sma: Vec<SumTreeSMA<f64, f64, SMA_WINDOW_SIZE>>,
}

impl TemperatureSensors {
    pub fn new(num_sensors: usize) -> Result<Self> {
        Ok(TemperatureSensors {
            temperature: vec![-1.0; num_sensors],
            num_sensors,
            adc0_bus: Spi::new(Bus::Spi1, SlaveSelect::Ss0, SPI_FREQ as u32, Mode::Mode1)?,
            adc1_bus: Spi::new(Bus::Spi1, SlaveSelect::Ss1, SPI_FREQ as u32, Mode::Mode1)?,
            rx_buffer: [0; 3],
            tx_buffer: [0; 3],
            sma: (0..num_sensors)
                .map(|_| SumTreeSMA::<f64, f64, SMA_WINDOW_SIZE>::new())
                .collect(),
        })
    }

    pub fn read(&mut self) -> Result<&Vec<f64>> {
        for i in 0..self.num_sensors {
            self.read_channel(i)?;
        }

        Ok(&self.temperature)
    }

    fn read_channel(&mut self, channel: usize) -> Result<()> {
        let adc_ch = (if channel < 8 { channel } else { channel - 8 }) as u8;

        self.tx_buffer[0] = 6 | (adc_ch & 4) >> 2;
        self.tx_buffer[1] = (adc_ch & 3) << 6;

        if channel < 8 {
            self.adc0_bus
                .transfer(&mut self.rx_buffer, &self.tx_buffer)?;
        } else {
            self.adc1_bus
                .transfer(&mut self.rx_buffer, &self.tx_buffer)?;
        }

        let data: u16 = (((self.rx_buffer[1] as u16) & 15) << 8) + self.rx_buffer[2] as u16;

        let v: f64 = (data as f64 / 4096.0) * VREF;

        let r = v * RDIV / (VREF - v);

        let temp = 1.0 / (1.0 / (T0 + 273.15) + (1.0 / B) * f64::ln(r / R0)) - 273.15;

        self.sma[channel].add_sample(temp);

        self.temperature[channel] = self.sma[channel].get_average();
        Ok(())
    }
}
