import smartiris
import time
import tqdm
import numpy as np
import matplotlib.pyplot as plt

d = smartiris.SmartIris(debug=False)
d.close_shutter()
delay=0.5
interval = 0.5
pulse_width=0.035
n = 500

d.timed_shutter(delay_sec=delay, duration_sec=interval, pulsewidth_sec=pulse_width, exec=False)


def test():
    d.start_program()
    d.wait()
    record = d.read_timing_record()
    return record

records = [test() for i in tqdm.tqdm(list(range(n)))]
rec = np.rec.fromrecords([[r[0] for r in record] for record in records if len(record) == 2], names=['open', 'close']) 

prog = d.read_program()
pulses = [r[0]/d.frequency for r in prog]
start_pulse = {'open': pulses[0],
               'close': pulses[2]}
end_pulse = {'open': pulses[1],
             'close': pulses[3]}


np.save(f'shutterBig_timing_{n}_{delay}_{interval}_{pulse_width}.npy', rec)

#rec = np.load('shutterA_timing.npy')
plt.figure()
for x, label in zip((rec['open'], rec['close'], rec['close']-rec['open']),
                    ('opening', 'closing', 'exptime')):
    print(f'Jitter on {label}: {x.std()*1e3:.3f} ms (rms)')
    plt.hist((x-x.mean())*1000, histtype='step', label=label, bins=30)

plt.figure()
ax = plt.gca()
for label in 'open', 'close':
    x = rec[label] - start_pulse[label]
    ax.hist(x*1000, label=label)    
ax.axvline(0, color='k')
ax.text(0 , .95, 'pulse start', 
        rotation=90,            # Rotate 90 degrees for vertical text
        verticalalignment='top',  # Center vertically
        horizontalalignment='right',  # Align left relative to x position
        transform=ax.get_xaxis_transform())
x_end = (end_pulse[label] - start_pulse[label])*1000
ax.axvline(x_end, color='k')
ax.text(x_end, .95, 'pulse end', 
        rotation=90,            # Rotate 90 degrees for vertical text
        verticalalignment='top',  # Center vertically
        horizontalalignment='right',  # Align left relative to x position
        transform=ax.get_xaxis_transform()) 
plt.legend(frameon=False)
plt.xlabel(r'$\Delta t$ [ms]')
