import smartiris
import time
import tqdm

d = smartiris.SmartIris(debug=False)
#d.timed_shutter(delay_sec=1e-6, duration_sec=3, exec=False)
interval = 1

for i in tqdm.tqdm(list(range(100))):
    d.timed_shutter(delay_sec=1e-4, duration_sec=interval, exec=False)
    d.start_program()
    time.sleep(0.2)
    assert d.status()['shutter_A'] == 'open'
    time.sleep(interval)
    assert d.status()['shutter_A'] == 'closed'
