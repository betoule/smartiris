import smartiris
import time
import tqdm

d = smartiris.SmartIris(debug=False)
#d.timed_shutter(delay_sec=1e-6, duration_sec=3, exec=False)
interval = 1
d.timed_shutter(delay_sec=1e-4, duration_sec=interval, exec=False, pulsewidth_sec=30e-3)

voltage = []

for i in tqdm.tqdm(list(range(100))):
    time.sleep(0.5)
    d.start_program()
    time.sleep(0.2)
    assert d.status()['shutter_A'] == 'open'
    d.wait()
    assert d.status()['shutter_A'] == 'closed'
    voltage.append(d.read_capacitor_bank_voltage())

