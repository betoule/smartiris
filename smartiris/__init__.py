# Copyright 2024 Marc Betoule
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, version 2 of the License.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import bincoms
import struct
import time
import numpy as np

import numpy as np
import struct
import time


class SmartIris(bincoms.SerialBC):
    """A class to control an iris blade shutter via serial communication.

    Inherits from bincoms.SerialBC to provide low-level serial communication
    functionality. This class manages shutter operations such as opening,
    closing, and timed sequences using a microcontroller's timer.

    Attributes:
        time_resolution (float): The timer resolution in seconds (default: 0.5e-6).
    """

    def __init__(self, *args, **keys):
        """Initialize the SmartIris instance.

        Args:
            *args: Variable length argument list passed to the parent class.
            **keys: Keyword arguments passed to the parent class.
        """
        super().__init__(*args, **keys)
        self.frequency = self.get_frequency()
        # Read mcu temperature sensor calibration constants
        self._ts_offset = self.read_signature_row(0x0002)
        self._ts_gain = self.read_signature_row(0x0003)
        
    def get_frequency(self):
        ''' Return the mcu clock frequency. Nominal or calibrated if avaialable'''
        freq = self.get_clock_calibration()
        if np.isnan(freq):
            import warnings
            warnings.warn('The mcu clock is not calibrated. If you need precise timings consider running "smartiris calibrate".')
            return 2e6
        else:
            return freq

    def calibrate(self, duration_min=10, output_file=''):
        import smartiris.clock_calibration
        mcu_data, ntp_data = smartiris.clock_calibration.acquire_clock_data(self, duration=duration_min*60)
        slope, eslope = smartiris.clock_calibration.clock_calibration_fit(mcu_data['start'], mcu_data['mcu'])
        print(f'Measured a time scale difference of {(slope-1) * 100:.4f}% (±{eslope*100:.4f}%)')
        if output_file:
            smartiris.clock_calibration.save(mcu_data, ntp_data, output_file)
            print(f'Calibration data saved in {output_file}. Clock scale not adjusted')
        else:
            calibrated_frequency = self.frequency * slope
            print(f'Adjusting frequency from {self.frequency * 1e-6:.6f} MHz to {calibrated_frequency * 1e-6:.6f} MHz')
            self.set_clock_calibration(calibrated_frequency)
            self.frequency = calibrated_frequency
        
    def _ct(self, seconds):
        """Convert a duration in seconds to a microcontroller timer count.

        Args:
            seconds (float): Duration in seconds to convert.

        Returns:
            int: The number of timer counts, rounded to the nearest integer.
        """
        return int(np.round(seconds * self.frequency))

#    def async_packet_read(self):
#        """Read and unpack an asynchronous response packet from the device.
#
#        Returns:
#            tuple: A tuple containing two values unpacked from the response
#                (format: '<IB', little-endian unsigned int and byte).
#        """
#        ans = self.rcv()
#        answer = struct.unpack('<IB', ans)
#        return answer

    def pulse_sec(self, pin, pulsewidth_sec):
        """Generate a pulse on the specified pin for a given duration.

        Args:
            pin (int): The pin number to pulse.
            pulsewidth_sec (float): Duration of the pulse in seconds.
        """
        self.pulse(pin, self._ct(pulsewidth_sec))

    def safe_program_pulse(self, pin, pos, timing_sec, retries=2):
        ''' Encapsulate the program_pulse method, reading back values to ensure integrity of the program

        Args:
            pin (int): The pin number to pulse
            pos (int): The position of the pulse in the program
            timing (float): The timing of the pulse in seconds
        '''
        timing_count = self._ct(timing_sec)
        for i in range(retries):
            try:
                self.program_pulse(pin, pos, timing_count)
                rtiming, rpin = self.get_program(pos, 0)
                if (rtiming == timing_count) and (rpin == pin):
                    return
            except ValueError:
                print('Catched communication error')
                self.flush()
        raise IOError(f'Corrupted program on device. Asked for ({timing_count}, {1<<pin}) got ({rtiming}, {rpin}) in position {pos}')
                
    def timed_shutter(self, delay_sec=1e-4, duration_sec=1, port='A', pulsewidth_sec=30e-3, exec=True, echo=False):
        """Program a sequence to open and close the shutter with specified timing.

        This method sets up a sequence of pulses to open the shutter after a delay,
        keep it open for a duration, and then close it. 

        Args:
            delay_sec (float): Initial delay before starting (default: 100 μs).
            duration_sec (float): Time to keep the shutter open (default: 1 s).
            port (str): Shutter port identifier (default: 'A').
            pulsewidth_sec (float): Duration of the opening/closing pulses (default: 0.03 s).
            exec (bool): If false program only. The execution can be triggered later using method start_program.
            echo (bool): If True, the pulses are echoed on the trigger out line.
        """
        pins = port_pins_with_echo[port] if echo else port_pins[port]
        self.safe_program_pulse(pins['open'], 0, delay_sec)
        self.safe_program_pulse(pins['open'], 1, delay_sec + pulsewidth_sec)
        self.safe_program_pulse(pins['close'], 2, delay_sec + duration_sec)
        self.safe_program_pulse(pins['close'], 3, delay_sec + duration_sec + pulsewidth_sec)
        if exec:
            self.start_program()

    def open_shutter(self, port='A', pulsewidth_sec=30e-3, delay_sec=10e-3, exec=True, echo=False):
        """Open the shutter on the specified port.

        Programs and starts a sequence to activate the open pin for the given pulse width.

        Args:
            port (str): Shutter port identifier (default: 'A').
            pulsewidth_sec (float): Duration of the opening pulse (default: 0.03 s).
            delay_sec (float): Delay before starting (default: 0.01 s).
            exec (bool): If false program only. The execution can be triggered later using method start_program.
            echo (bool): If True, the pulses are echoed on the trigger out line.
        """
        pins = port_pins_with_echo[port] if echo else port_pins[port]
        self.program_pulse(pins['open'], 0, self._ct(delay_sec))
        self.program_pulse(pins['open'], 1, self._ct(delay_sec + pulsewidth_sec))
        if exec:
            self.start_program()

    def close_shutter(self, port='A', pulsewidth_sec=30e-3, delay_sec=10e-3, exec=True, echo=False):
        """Close the shutter on the specified port.

        Programs and starts a sequence to activate the close pin for the given pulse width.

        Args:
            port (str): Shutter port identifier (default: 'A').
            pulsewidth_sec (float): Duration of the closing pulse (default: 0.03 s).
            delay_sec (float): Delay before starting (default: 0.01 s).
            exec (bool): If false program only. The execution can be triggered later using method start_program.
            echo (bool): If True, the pulses are echoed on the trigger out line.
        """
        pins = port_pins_with_echo[port] if echo else port_pins[port]
        self.program_pulse(pins['close'], 0, self._ct(delay_sec))
        self.program_pulse(pins['close'], 1, self._ct(delay_sec + pulsewidth_sec))
        if exec:
            self.start_program()

    def read_program(self):
        """Print the programmed pulse sequence for debugging.

        Reads and displays the program steps (up to 4) from the device.
        """
        program_length = self.status()['program_length']
        return [self.get_program(i, 0) for i in range(program_length)]

    def read_timing_record(self):
        """Read the record of sensor detection timing.
        """
        nrecords = self.status()['events_recorded']
        def convert(i):
            timing, pin = self.get_program(i, 1)
            return timing/self.frequency, ['', 'sensorA', 'sensorB'][pin]
        return [convert(i) for i in range(nrecords)]

    def read_mcu_temperature(self):
        V_adc = self.read_adc(adc_pin_maps['MCU_TEMP'])
        return (V_adc - 273 + 100 - self._ts_offset)*128/self._ts_gain + 25
    
    def read_temperature(self):
        """ Read the TMP36 temperature in deg C
        """
        V_adc = self.read_adc(adc_pin_maps['TMP36']) * 1.1/1024
        # 10 mV / deg and 750mV @ 25
        temp = 25 + (V_adc - 0.75) * 100
        return temp

    def read_capacitor_bank_voltage(self):
        """ Read the capacitor bank voltage in V
        """
        V_adc = self.read_adc(adc_pin_maps['U_BANK']) * 1.1/1024
        return 46 / 10 * V_adc # Divider 10k/36k

    def status(self):
        """Retrieve the current status of the shutter driver.

        Returns:
            dict: A dictionary containing:
                - 'shutter_A': State of shutter A ('open' or 'closed').
                - 'shutter_B': State of shutter B ('open' or 'closed').
                - 'busy': Boolean indicating if a program is running.
                - 'program_length': number of pin changes in the program.
                - 'events_recorded': The number of recorded sensor events.
        """
        com_port, read_port, program_cursor, program_length, nrecords = self.raw_status()
        if self.debug:
            print(f'{com_port=}, {read_port=}, {program_cursor=},{program_length=}, {nrecords=}')
        status = {
            'shutter_A': 'closed' if read_port & 0b100 else 'open',
            'shutter_B': 'closed' if read_port & 0b1000 else 'open',
            'busy': program_cursor != 0,
            'program_length': program_length,
            'events_recorded': nrecords,
        }
        return status

    def wait(self):
        """Block execution until the shutter program completes.

        Polls the status until the 'busy' flag is cleared, checking every 0.1 seconds.
        """
        while self.status()['busy']:
            time.sleep(0.1)

    def enable_buttons(self):
        self._set_interrupt_mask((1<<5 | 1<<6))

    def disable_buttons(self):
        self._set_interrupt_mask(0)

# This is the portB mask corresponding to each pins
pin_map = {8: 1 << 0,
           9: 1 << 1,
           10: 1 << 2,
           11: 1 << 3,
           12: 1 << 4,
           13: 1 << 5, # Trig_out
           }

port_pins = {'A': {'close': pin_map[8],
                   'open': pin_map[9]},
             'B': {'close': pin_map[10],
                   'open': pin_map[11],
                   },
             }

# If we want to echo the changes on the trig_out line 
port_pins_with_echo = {k: {s: (p | pin_map[13]) for s, p in d.items()} for k, d in port_pins.items()}

adc_pin_maps = {'TMP36': 0,
                'U_BANK': 1,
                'A2': 2,
                'A3': 3,
                'A4': 4,
                'A5': 5,
                'A6': 6,
                'A7': 7,
                'MCU_TEMP': 8, # internal MCU temp sensor
                'VBG': 0b1110, # Internal voltage ref
                'GND': 0b1111, # Ground
                }

