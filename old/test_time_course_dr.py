from preprocessing import load_and_extract_signals
import matplotlib.pyplot as plt

# Easy-to-change settings
STIM_VHDR = r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\TIMS_data_sync\pilot\doseresp\exp02-phantom-stim-pulse-10hz-GT-run02.vhdr"
BASELINE_VHDR = r"C:\Users\njeuk\OneDrive\Documents\Charite Berlin\TIMS\TIMS_data_sync\pilot\doseresp\exp02-phantom-baseline-run01.vhdr"
RECORDING = "stim"  # "stim" or "baseline"
CHANNELS = ["Cz", "C3", "F4"]  # choose your EEG channels here
START_S, DURATION_S = 30.0, 40.0
LOW_HZ, HIGH_HZ, NOTCH_HZ = 0.5, 45.0, 50.0


bundle = load_and_extract_signals(STIM_VHDR, BASELINE_VHDR, reference_channel="Cz", preload=True)
raw = bundle["stim_raw"] if RECORDING == "stim" else bundle["baseline_raw"]
missing = [ch for ch in CHANNELS if ch not in raw.ch_names]
if missing:
    raise ValueError(f"Missing channels in {RECORDING}: {missing}")

plot_raw = raw.copy().pick(CHANNELS).load_data()
plot_raw.notch_filter(NOTCH_HZ, verbose=False)
plot_raw.filter(LOW_HZ, HIGH_HZ, verbose=False)
plot_raw.plot(
    start=START_S,
    duration=DURATION_S,
    n_channels=len(CHANNELS),
    scalings="auto",
    title=f"{RECORDING} time course: {', '.join(CHANNELS)}", show=True
)
plt.show()