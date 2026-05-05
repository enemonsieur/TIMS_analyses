import unittest

import numpy as np

import preprocessing


class TestExp04SplitSegmentSpectral(unittest.TestCase):
    def test_split_segment_helper_returns_expected_shapes(self):
        rng = np.random.default_rng(0)
        sfreq = 100.0
        pre_times_s = np.arange(-3.0, -1.0 + 1.0 / sfreq, 1.0 / sfreq)
        post_times_s = np.arange(0.08, 3.0 + 1.0 / sfreq, 1.0 / sfreq)
        pre_epochs = rng.standard_normal((4, 3, pre_times_s.size))
        post_epochs = rng.standard_normal((4, 3, post_times_s.size))

        summary = preprocessing.compute_split_segment_post_tfr(
            pre_epochs=pre_epochs,
            pre_times_s=pre_times_s,
            post_epochs=post_epochs,
            post_times_s=post_times_s,
            sampling_rate_hz=sfreq,
        )

        self.assertEqual(summary["pre_power"].shape, (4, 3, 37, pre_times_s.size))
        self.assertEqual(summary["post_power"].shape, (4, 3, 37, post_times_s.size))
        self.assertEqual(summary["post_power_logratio"].shape, (4, 3, 37, post_times_s.size))
        self.assertEqual(summary["valid_post_time_mask"].dtype, np.bool_)
        self.assertTrue(summary["valid_post_time_mask"].any())
        self.assertEqual(len(summary["band_window_metrics"]), 4 * 4 * 2)

    def test_split_segment_helper_rejects_too_short_pre_segment(self):
        rng = np.random.default_rng(1)
        sfreq = 100.0
        pre_times_s = np.arange(-2.0, -1.0 + 1.0 / sfreq, 1.0 / sfreq)
        post_times_s = np.arange(0.08, 3.0 + 1.0 / sfreq, 1.0 / sfreq)
        pre_epochs = rng.standard_normal((2, 2, pre_times_s.size))
        post_epochs = rng.standard_normal((2, 2, post_times_s.size))

        with self.assertRaises(ValueError):
            preprocessing.compute_split_segment_post_tfr(
                pre_epochs=pre_epochs,
                pre_times_s=pre_times_s,
                post_epochs=post_epochs,
                post_times_s=post_times_s,
                sampling_rate_hz=sfreq,
            )


if __name__ == "__main__":
    unittest.main()
