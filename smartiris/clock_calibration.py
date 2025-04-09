import ntplib
import time
import numpy as np
import smartiris
import matplotlib.pyplot as plt

server="pool.ntp.org"
client = ntplib.NTPClient()
        
#device = smartiris.SmartIris()

def mcu_tic():
    start = time.time()
    devtime = device.get_time()
    stop = time.time()
    return start, devtime/2e6, stop

def ntp_tic():
    start = time.time()
    devtime = device.get_time()
    response = client.request(server, version=4)
    stop = time.time()
    return start, response.tx_time, stop

def acquire_clock_data(device, duration=600, ntp=0, interval=0.1):
    ''' Acquire clock synchronisation data from the host and mcu.
    
    Note:
    -----
    Keep in mind that the mcu ~2MHz clock roll over after ~35.79 minutes (2**32/2e6)

    Parameters:
    -----------
    device: SmartIris object
    duration: float
      Acquisition duration in seconds
    ntp: float
      If non zero, attempt to perform ntp queries at the provided interval to check the host clock calibration as well
    interval: float
      Approximate interval between 2 mcu queries in seconds

    return:
    -------
    mcu_data: numpy record array
    ntp_data: numpy record array
    '''
    mcu_data = []
    ntp_data = []
    last_ntp = 0
    start = time.time()
    device._start_timer()    
    while(time.time() - start < duration):
        
        mcu_data.append(mcu_tic())
        elif not ntp:
            # No need to continue longer
            break
        if ntp and ((time - last_ntp) > ntp):
            try:
                ntp_data.append(ntp_tic())
            except:
                pass
        time.sleep(interval)
    return (np.rec.fromrecord(mcu_data, names=['start', 'mcu', 'stop']),
            np.rec_fromrecord(mcu_data, names=['start', 'nntp', 'stop']))


def save(mcu_data, ntp_data, filename='timing.npz'):
    np.savez(filename, ntp_data=ntp_data, mcu_data=mcu_data)

def load(filename='timing.npz'):
    data = np.load(filename)
    return data['mcu_data'], data['ntp_data']

def clock_calibration_fit(t1, t2, show=False, axes=None):
    x = t1 - t1.min()
    y = t2 - t2.min()
    p, cov = np.polyfit(x, y, 1, cov=True)
    res = y - np.polyval(p, x)
    eslope = np.sqrt(cov[0,0])
    if show: 
        if axes is None:
            axes = plt.gcf().subplots(2,1,sharex=True)
        ax1, ax2 = axes

        ax1.plot(x, y-x, 'o')
        v = [x.min(), x.max()]
        ax1.plot(v, np.polyval(p, v)-np.array(v), 'k-', label=f'{p[0]:.5f}±{eslope:.5f}')
        ax1.legend()
        ax2.plot(x, res, 'o', label=f'{res.std()*1000:.2f}ms')
        ax2.legend()
        ax2.set_xlabel('host clock [s]')
        ax1.set_ylabel('mcu - host [s]')
        ax2.set_ylabel(f'mcu - {p[0]:.3f} host [s]')
        return p[0], eslope, axes 
    else:
        return p[0], eslope

if __name__ == '__main__':
    
    mcu_data, ntp_data = load('timing3.npz')
    
    d1 = mcu_data[:mcu_data['mcu'].argmax()+1]
    d2 = mcu_data[mcu_data['mcu'].argmax()+1:]
    slope1, eslope1, axes = clock_calibration_fit(d1['start'], d1['mcu'], show=True)
    slope2, eslope2, axes = clock_calibration_fit(d2['start'], d2['mcu'], show=True, axes=axes)

    calibrated_frequency = 2e6 * slope1
    
#axes = calib(mcu_data['start'] - mcu_data['start'].min(), mcu_data['mcu'] - mcu_data['mcu'].min())
#calib(ntp_data['start'] - ntp_data['start'].min(), ntp_data['ntp'] - ntp_data['ntp'].min(), axes)
