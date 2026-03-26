import numpy as np
import tempfile
import os

protocol_name = "DR-pulse-5min"
stimulator_ip = "tims@10.42.0.131"
stimulator_protocols_dir = "/home/tims/data/protocols"


sample_rate = 5000 #
duration = 60.0*5     # in seconds                
freq_Repetition = 1.0                   # frequency of repetition (Hz) — 1 s period
freq_TIMS_stim = 50.0                      # frequency of TIMS stimulation (ex: 50Hz)

n = int(sample_rate * duration)

# build protocol array: columns = a1,a2,b1,b2,mod_a,mod_b
# A1 is the amplitude for channel A, B1 is the amplitude for channel B, 
# mod_a and mod_b are the changes in amplitude over time (ex: 10hz )
# find the parameters in protocol.rs 
protocol_array = np.zeros((n, 6), dtype=np.float64) # columns: 
protocol_array[:, 0] = 1                # example: A1 = 0.5 mA
protocol_array[:, 1] = 1                # other amps = 0

# CREATE single 50 Hz cycle every 4 s
duration_run = np.arange(n) / sample_rate #
mask = (duration_run % freq_Repetition) >= (freq_Repetition - 1.0 / freq_TIMS_stim) # last 1/50 s of each 1 s period
protocol_array[:, 4] = np.where(mask, 0.5*(np.sin(2*np.pi*freq_TIMS_stim*(duration_run%freq_Repetition)-np.pi/2)+1), 0.0)
protocol_array[:, 5] = protocol_array[:, 4]     # same modulation for channel B

#print(protocol_array.shape)  # should be (n, 6)
#print(protocol_array[:10])   # print first 10 rows to verify
import matplotlib.pyplot as plt
plt.plot(duration_run[:10000], protocol_array[:10000, 4])  # plot first 2 seconds
plt.xlabel('Time (s)')
plt.ylabel('Modulation (a)')
plt.title('Example Modulation Pattern')
plt.show()

#np.save("dose_response.npy", protocol_array)
with tempfile.NamedTemporaryFile() as tmp:
    print(tmp.name)
    np.save(tmp, protocol_array)
    os.system(f"scp {tmp.name} {stimulator_ip}:{stimulator_protocols_dir}/{protocol_name}.npy")
