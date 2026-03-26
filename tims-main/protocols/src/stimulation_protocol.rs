use crate::{N, Signal, TIMSError, W};
use byteorder::{BigEndian, ByteOrder};
use serde::{Deserialize, Serialize};

#[derive(Default, Clone, PartialEq, Deserialize, Serialize, Debug)]
pub struct StimulationProtocol {
    // these are to be specified by the client using new()
    duration: f64,
    signals: Vec<Signal>,
    amplitude_a1_signal_idx: usize,
    amplitude_a2_signal_idx: usize,
    amplitude_b1_signal_idx: usize,
    amplitude_b2_signal_idx: usize,
    modulation_a_signal_idx: usize,
    modulation_b_signal_idx: usize,

    // these are computed on the serve by calling compute()
    index: usize,
    num_samples: usize,
    amplitude_a1: Vec<i16>,
    amplitude_a2: Vec<i16>,
    amplitude_b1: Vec<i16>,
    amplitude_b2: Vec<i16>,
    modulation_a: Vec<i16>,
    modulation_b: Vec<i16>,
}

impl StimulationProtocol {
    pub fn new(
        duration: f64,
        signals: Vec<Signal>,
        amplitude_a1_signal_idx: usize,
        amplitude_a2_signal_idx: usize,
        amplitude_b1_signal_idx: usize,
        amplitude_b2_signal_idx: usize,
        modulation_a_signal_idx: usize,
        modulation_b_signal_idx: usize,
    ) -> Result<Self, TIMSError> {
        if signals.is_empty() {
            log::error!("Stimulation protocol contains no signals");
            return Err(TIMSError::ProtocolError);
        }
        for idx in [
            amplitude_a1_signal_idx,
            amplitude_a2_signal_idx,
            amplitude_b1_signal_idx,
            amplitude_b2_signal_idx,
            modulation_a_signal_idx,
            modulation_b_signal_idx,
        ] {
            if idx >= signals.len() {
                log::error!("Stimulation protocol contains reference to non-existing signal");
                return Err(TIMSError::ProtocolError);
            }
        }

        Ok(Self {
            duration,
            signals,
            amplitude_a1_signal_idx,
            amplitude_a2_signal_idx,
            amplitude_b1_signal_idx,
            amplitude_b2_signal_idx,
            modulation_a_signal_idx,
            modulation_b_signal_idx,
            ..Default::default()
        })
    }

    pub fn compute(&mut self) {
        self.index = 0;
        self.num_samples = Signal::duration_to_num_samples(self.duration);
        self.amplitude_a1 =
            self.signals[self.amplitude_a1_signal_idx].compute(self.duration, &self.signals);
        self.amplitude_a2 =
            self.signals[self.amplitude_a2_signal_idx].compute(self.duration, &self.signals);
        self.amplitude_b1 =
            self.signals[self.amplitude_b1_signal_idx].compute(self.duration, &self.signals);
        self.amplitude_b2 =
            self.signals[self.amplitude_b2_signal_idx].compute(self.duration, &self.signals);
        self.modulation_a =
            self.signals[self.modulation_a_signal_idx].compute(self.duration, &self.signals);
        self.modulation_b =
            self.signals[self.modulation_b_signal_idx].compute(self.duration, &self.signals);
    }

    pub fn to_buffer(&mut self, tx_buffer: &mut [u8]) -> f64 {
        if self.num_samples == 0 {
            log::error!("Attempted to use an empty stimulation protocol");
            return 1.0;
        }

        let mut done = false;
        for i in 0..N {
            let word = &mut tx_buffer[i * W..(i + 1) * W];
            let j = self.index + i;

            if j >= self.num_samples {
                word.fill(0);
                done = true;
            } else {
                StimulationProtocol::to_word(&self.amplitude_a1, j, word, 0);
                StimulationProtocol::to_word(&self.amplitude_a2, j, word, 1);
                StimulationProtocol::to_word(&self.amplitude_b1, j, word, 2);
                StimulationProtocol::to_word(&self.amplitude_b2, j, word, 3);
                StimulationProtocol::to_word(&self.modulation_a, j, word, 4);
                StimulationProtocol::to_word(&self.modulation_b, j, word, 5);
            }
        }

        if !done {
            self.index += N;
        } else {
            self.index = self.num_samples;
        }

        return self.index as f64 / self.num_samples as f64;
    }

    fn to_word(arr: &Vec<i16>, arr_idx: usize, word: &mut [u8], word_idx: usize) {
        if !arr.is_empty() {
            BigEndian::write_i16(&mut word[word_idx * 2..(word_idx + 1) * 2], arr[arr_idx]);
        }
    }
}
