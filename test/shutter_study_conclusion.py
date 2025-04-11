import numpy as np
import matplotlib.pyplot as plt

plt.rc('axes.spines', right=False, top=False, left=False)
plt.rc('text', usetex=True)

data = {'SHB05@30ms': np.load('shutterA_timing_1000.npy'),
        'SHB1T@30ms': np.load('shutterBig_timing_1000.npy'),
        'SHB1T@35ms': np.load('shutterBig_timing_500_0.5_0.5_0.035.npy')}

colors = {'SHB05@30ms': '#1b9e77',
          'SHB1T@30ms': '#d95f02',
          'SHB1T@35ms': '#7570b3'}

def reproducibility_plot(x, label='', ax=None):
    if ax is None:
        ax = plt.gca()
    print(f'Jitter on {label}: {x.std()*1e3:.3f} ms (rms)')
    ax.hist((x-x.mean())*1000, histtype='step', label=label + rf' $(\sigma={x.std()*1e3:.1f}$ ms)', bins=30, range=[-10, 10], density=True, color=colors[label])

plt.ion()
plt.figure('Exposure time reproducibility')
for label, rec in data.items():
    reproducibility_plot(rec['close'] - rec['open'], label=label)
plt.xlabel('exposure time error [ms]')
plt.yticks([])
plt.legend(frameon=False)
plt.tight_layout()
plt.savefig('doc/exposure_time.png', dpi=300)

fig = plt.figure('Opening and closing time')
ax1, ax2 = fig.subplots(2,1,sharex=True)
ax1.set_yticks([])
ax2.set_yticks([])
start_pulses = {'SHB05@30ms': {'open': 1e-4,
                               'close': 1.0001},
                'SHB1T@30ms': {'open': 1e-4,
                               'close': 1.0001},
                'SHB1T@35ms': {'open': 0.5,
                               'close': 1.},
                }


for label, rec in data.items():
    start_pulse = start_pulses[label]
    x = rec['open'] - start_pulse['open']
    ax1.hist(x*1000,  histtype='step', label=label, density=True, color=colors[label])
    x = rec['close'] - start_pulse['close']
    ax2.hist(x*1000, histtype='step', label=label, density=True, color=colors[label], ls=':')
    x_end = 35 if '@35' in label else 30
    ax1.axvline(x_end, color=colors[label])
    ax2.axvline(x_end, color=colors[label])
    ax1.text(x_end, .95, 'pulse end', 
            rotation=90,            # Rotate 90 degrees for vertical text
            verticalalignment='top',  # Center vertically
            horizontalalignment='right',  # Align left relative to x position
            transform=ax1.get_xaxis_transform(),
            color=colors[label]) 

ax1.axvline(0, color='k')
ax2.axvline(0, color='k')
ax1.text(0 , .95, 'opening pulse', 
         rotation=90,            # Rotate 90 degrees for vertical text
         verticalalignment='top',  # Center vertically
         horizontalalignment='right',  # Align left relative to x position
         transform=ax1.get_xaxis_transform())
ax2.text(0 , .95, 'closing pulse', 
         rotation=90,            # Rotate 90 degrees for vertical text
         verticalalignment='top',  # Center vertically
         horizontalalignment='right',  # Align left relative to x position
         transform=ax2.get_xaxis_transform())
plt.legend(frameon=False)
plt.xlim([0, 40])
plt.xlabel(r'$\Delta t$ [ms]')
plt.tight_layout()
plt.savefig('doc/opening_and_closing_time.png', dpi=300)

plt.show()
