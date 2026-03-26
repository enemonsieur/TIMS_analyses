use std::f64::consts::PI;
use std::path::PathBuf;
use std::fs::File;
use std::io::BufReader;

use byteorder::{BigEndian, ByteOrder};
use npyz::NpyFile;
use ndarray::Array2;

use crate::config;

pub struct Protocol {
    pub duration: f64,
    amplitude_a1: Vec<i16>,
    amplitude_a2: Vec<i16>,
    amplitude_b1: Vec<i16>,
    amplitude_b2: Vec<i16>,
    modulation_a: Vec<i16>,
    modulation_b: Vec<i16>,
    index: usize,
}

impl Default for Protocol {
    fn default() -> Self {
        Protocol {
            duration: Protocol::num_samples_to_duration(config::INTERFACE_DATA_NUM_SAMPLES as usize),
            amplitude_a1: vec![0; config::INTERFACE_DATA_NUM_SAMPLES as usize],
            amplitude_a2: vec![0; config::INTERFACE_DATA_NUM_SAMPLES as usize],
            amplitude_b1: vec![0; config::INTERFACE_DATA_NUM_SAMPLES as usize],
            amplitude_b2: vec![0; config::INTERFACE_DATA_NUM_SAMPLES as usize],
            modulation_a: vec![0; config::INTERFACE_DATA_NUM_SAMPLES as usize],
            modulation_b: vec![0; config::INTERFACE_DATA_NUM_SAMPLES as usize],
            index: 0,
        }
    }
}

impl Protocol {
    pub fn external_amp_and_phase_control(duration: f64) -> Self {
        let n = Protocol::duration_to_num_samples(duration);

        Protocol {
            duration: Protocol::num_samples_to_duration(n),
            amplitude_a1: vec![Protocol::to_fp(0.0); n],
            amplitude_a2: vec![Protocol::to_fp(0.0); n],
            amplitude_b1: vec![Protocol::to_fp(0.0); n],
            amplitude_b2: vec![Protocol::to_fp(0.0); n],
            modulation_a: vec![Protocol::to_fp(0.0); n],
            modulation_b: vec![Protocol::to_fp(0.0); n],
            index: 0,
        }
    }

    pub fn constant_amp_external_phase_control(duration: f64) -> Self {
        let n = Protocol::duration_to_num_samples(duration);

        Protocol {
            duration: Protocol::num_samples_to_duration(n),
            amplitude_a1: vec![Protocol::to_fp(1.0); n],
            amplitude_a2: vec![Protocol::to_fp(1.0); n],
            amplitude_b1: vec![Protocol::to_fp(1.0); n],
            amplitude_b2: vec![Protocol::to_fp(1.0); n],
            modulation_a: vec![Protocol::to_fp(0.0); n],
            modulation_b: vec![Protocol::to_fp(0.0); n],
            index: 0,
        }
    }

    pub fn constant_amp_constant_phase(duration: f64, m: f64) -> Self {
        let n = Protocol::duration_to_num_samples(duration);

        Protocol {
            duration: Protocol::num_samples_to_duration(n),
            amplitude_a1: vec![Protocol::to_fp(1.0); n],
            amplitude_a2: vec![Protocol::to_fp(1.0); n],
            amplitude_b1: vec![Protocol::to_fp(1.0); n],
            amplitude_b2: vec![Protocol::to_fp(1.0); n],
            modulation_a: vec![Protocol::to_fp(m); n],
            modulation_b: vec![Protocol::to_fp(m); n],
            index: 0,
        }
    }

    pub fn sine_modulation(duration: f64, f: f64, d: f64) -> Self {
        let n = Protocol::duration_to_num_samples(duration);

        let mut modulation = vec![0; n];
        for i in 0..n {
            let t = i as f64 / config::INTERFACE_SAMPLING_RATE as f64;

            let m = 0.5 * d * (f64::sin(2.0 * PI * f * t - PI / 2.0) + 1.0) + (1.0 - d);
            modulation[i] = Protocol::to_fp(m);
        }

        Protocol {
            duration: Protocol::num_samples_to_duration(n),
            amplitude_a1: vec![Protocol::to_fp(1.0); n],
            amplitude_a2: vec![Protocol::to_fp(1.0); n],
            amplitude_b1: vec![Protocol::to_fp(1.0); n],
            amplitude_b2: vec![Protocol::to_fp(1.0); n],
            modulation_a: modulation.clone(),
            modulation_b: modulation.clone(),
            index: 0,
        }
    }

    pub fn burst_train_modulation(
        duration: f64,
        burst_frequency: f64,
        burst_num_cycles: isize,
        burst_repetition_frequency: f64,
        bursts_per_train: isize,
        intertrain_interval: f64,
    ) -> Self {
        let n = Protocol::duration_to_num_samples(duration);

        let burst_duration = burst_num_cycles as f64 / burst_frequency;
        let burst_repetition_period = 1.0 / burst_repetition_frequency;

        let train_duration = bursts_per_train as f64 * burst_repetition_period;
        let train_repetition_period = train_duration + intertrain_interval;

        let mut modulation = vec![0; n];
        for i in 0..n {
            let t = i as f64 / config::INTERFACE_SAMPLING_RATE as f64;

            let trt = t % train_repetition_period;
            let trb = trt % burst_repetition_period;

            if trt < train_duration {
                if trb < burst_duration {
                    let m = 0.5 * (f64::sin(2.0 * PI * burst_frequency * trb - PI / 2.0) + 1.0);
                    modulation[i] = Protocol::to_fp(m);
                } else {
                    modulation[i] = Protocol::to_fp(0.0);
                }
            }
        }

        Protocol {
            duration: Protocol::num_samples_to_duration(n),
            amplitude_a1: vec![Protocol::to_fp(1.0); n],
            amplitude_a2: vec![Protocol::to_fp(1.0); n],
            amplitude_b1: vec![Protocol::to_fp(1.0); n],
            amplitude_b2: vec![Protocol::to_fp(1.0); n],
            modulation_a: modulation.clone(),
            modulation_b: modulation.clone(),
            index: 0,
        }
    }

    pub fn from_file(path: PathBuf) -> Self {
        let file = File::open(path).unwrap();
        let reader = BufReader::new(file);
        let npy = NpyFile::new(reader).unwrap();

        let shape = npy.shape().to_owned();
        let (rows, cols) = (shape[0] as usize, shape[1] as usize);

        let flat: Vec<f64> = npy.into_vec().unwrap();

        let array: Array2<f64> =
            Array2::from_shape_vec((rows, cols), flat)
            .expect("shape mismatch");

        let mut amplitude_a1 = vec![0; rows];
        let mut amplitude_a2 = vec![0; rows]; 
        let mut amplitude_b1 = vec![0; rows]; 
        let mut amplitude_b2 = vec![0; rows]; 
        let mut modulation_a = vec![0; rows]; 
        let mut modulation_b = vec![0; rows]; 

        for i in 0..rows {
            amplitude_a1[i] = Protocol::to_fp(array[[i, 0]]);
            amplitude_a2[i] = Protocol::to_fp(array[[i, 1]]);
            amplitude_b1[i] = Protocol::to_fp(array[[i, 2]]);
            amplitude_b2[i] = Protocol::to_fp(array[[i, 3]]);
            modulation_a[i] = Protocol::to_fp(array[[i, 4]]);
            modulation_b[i] = Protocol::to_fp(array[[i, 5]]);
        }

        Protocol {
            duration: Protocol::num_samples_to_duration(rows),
            amplitude_a1,
            amplitude_a2,
            amplitude_b1,
            amplitude_b2,
            modulation_a,
            modulation_b,
            index: 0,
        }
    }

    pub fn fill_data_buffer(&mut self, tx_buffer: &mut [u8]) -> f64 {
        const W: usize = (config::INTERFACE_WORD_NBITS / 8) as usize;
        const N: usize = config::INTERFACE_DATA_NUM_SAMPLES as usize;

        let mut done = false;

        for i in 0..N {
            let word = &mut tx_buffer[i * W..(i + 1) * W];
            let j = self.index + i;

            if j >= self.amplitude_a1.len() {
                word.fill(0);
                done = true;
            } else {
                BigEndian::write_i16(&mut word[0 * 2..1 * 2], self.amplitude_a1[j]);
                BigEndian::write_i16(&mut word[1 * 2..2 * 2], self.amplitude_a2[j]);
                BigEndian::write_i16(&mut word[2 * 2..3 * 2], self.amplitude_b1[j]);
                BigEndian::write_i16(&mut word[3 * 2..4 * 2], self.amplitude_b2[j]);
                BigEndian::write_i16(&mut word[4 * 2..5 * 2], self.modulation_a[j]);
                BigEndian::write_i16(&mut word[5 * 2..6 * 2], self.modulation_b[j]);
            }
        }

        if !done {
            self.index += N;
        } else {
            self.index = self.amplitude_a1.len();
        }

        return self.index as f64 / self.amplitude_a1.len() as f64;
    }

    fn duration_to_num_samples(duration: f64) -> usize {
        f64::ceil(duration * config::INTERFACE_SAMPLING_RATE as f64) as usize
    }

    fn num_samples_to_duration(n: usize) -> f64 {
        n as f64 / config::INTERFACE_SAMPLING_RATE as f64
    }

    fn to_fp(val: f64) -> i16 {
        f64::round(val * config::FP_MAX as f64) as i16
    }
}
