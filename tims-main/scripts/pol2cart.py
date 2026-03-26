import numpy as np

FP_NBITS = 16
FP_MAX = 2**(FP_NBITS-1)

def pol2cart(mag, phase, num_iterations):
    atan_table = [int((np.arctan(2**(-i))/np.pi)*FP_MAX)
                  for i in range(num_iterations)]

    
    Kn = np.prod([1.0 / np.sqrt(1 + 2**(-2*i))
                  for i in range(num_iterations)])
    Kn_fixed = int(Kn * 2**(FP_NBITS-1))

    phase_in = int(phase*FP_MAX)

    if phase_in > FP_MAX/2 or phase_in < -FP_MAX/2:
        phase = FP_MAX - phase_in
        reflected = True
    else:
        phase = phase_in
        reflected = False
    if phase > FP_MAX:
        phase -= 2*FP_MAX
        
    
    x = int(mag*FP_MAX)
    y = 0
    phi = 0
        
    for i in range(num_iterations):
        if phi >= phase :   # rotate clockwise
            x_new = x + (y >> i)
            y_new = y - (x >> i)

            phi = phi - atan_table[i]
        else:  # rotate counter-clockwise
            x_new = x - (y >> i)
            y_new = y + (x >> i)

            phi = phi + atan_table[i]
    
        x, y = x_new, y_new
        print(x, y)
        
    x = (x * Kn_fixed) >> (FP_NBITS-1)
    y = (y * Kn_fixed) >> (FP_NBITS-1)

    if reflected:
        x = -x
    
    return x/FP_MAX, y/FP_MAX

mag = 0.65
phase = 0.2

x_ref = mag * np.cos(phase*np.pi)
y_ref = mag * np.sin(phase*np.pi)

x, y = pol2cart(mag, phase, 16)

print(x, y)
print(x_ref, y_ref)

    
