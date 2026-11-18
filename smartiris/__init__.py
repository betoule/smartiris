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
import math
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

    def __init__(self, *args, board_version=None, **keys):
        """Initialize the SmartIris instance.

        Args:
            *args: Variable length argument list passed to the parent class.
            board_version: Declare the hardware revision (1 or 2) instead
                of letting it be autodetected from the wired options on
                first use. See the board_version property.
            **keys: Keyword arguments passed to the parent class.
        """
        super().__init__(*args, **keys)
        self.frequency = self.get_frequency()
        # Read mcu temperature sensor calibration constants
        self._ts_offset = self.read_signature_row(0x0002)
        self._ts_gain = self.read_signature_row(0x0003)
        self._board_version = board_version
        self.board_version_source = ('declared' if board_version
                                     is not None else None)
        self._v2_features = None
        self._firmware_info = None

    def _probe_v2_features(self):
        """Discover which of the v2-only ADC channels are actually wired.

        v2 boards drive ADC0 with the external TMP36 temperature probe
        and ADC1 with a voltage divider monitoring the capacitor bank.
        Detection is bounded by what those sources can physically
        output, and by the observed behaviour of unwired v1 inputs:
        their whole ADC header is pulled towards VCC (every channel
        saturates at 1023) or, unpulled, hovers near 0 — it never
        shows stable intermediate readings.

        - TMP36 outputs 0.5 to 1.1 V between -20 and +60 degC (465 to
          1023 counts on the internal 1.1 V reference). A reading
          pinned at the rail is not a (plausibly cold) TMP36. When the
          firmware has test_pullup, the source must also stay inside
          the plausible window while the ~30 kOhm internal pull-up is
          enabled: a low impedance TMP36 output shifts by only ~150
          counts while a high impedance leak is dragged to the rail.
        - The bank divider reads above ~4.2 V as soon as the built-in
          bank is charged, and cannot be at the rail like the v1
          header: all channels saturating together means unwired.
        """
        if not hasattr(self, 'read_adc'):
            # The ADC commands appeared along with the v2 boards: a
            # firmware without them predates them.
            return {'TMP36': False, 'U_BANK': False}

        def median(name, n=3):
            vals = sorted(self.read_adc(adc_pin_maps[name])
                          for _ in range(n))
            return vals[n // 2]

        readings = {'TMP36': median('TMP36'),
                    'U_BANK': median('U_BANK'),
                    'A2': median('A2', 1),
                    'A5': median('A5', 1)}
        unwired = (all(v >= 1010 for v in readings.values())
                   or all(v <= 15 for v in readings.values()))
        if unwired:
            return {'TMP36': False, 'U_BANK': False}

        tmp36_present = 465 <= readings['TMP36'] <= 1005
        if tmp36_present and hasattr(self, 'test_pullup'):
            tmp36_present = 465 <= self.test_pullup(
                adc_pin_maps['TMP36']) <= 1015
        bank_present = readings['U_BANK'] >= 700
        # A floating net still settling after a disturbance (observed
        # right after plugging a board) can pass a one-shot test at an
        # intermediate value, while a wired low impedance source is
        # stable. Re-check the channels that looked present at the end
        # of the sequence, a few milliseconds later.
        if bank_present:
            bank_present = abs(self.read_adc(adc_pin_maps['U_BANK'])
                               - readings['U_BANK']) <= 80
        if tmp36_present:
            tmp36_present = abs(self.read_adc(adc_pin_maps['TMP36'])
                                - readings['TMP36']) <= 80
        return {'TMP36': tmp36_present, 'U_BANK': bank_present}

    @property
    def _v2_present(self):
        if self._v2_features is None:
            if self._board_version is not None:
                driven = self._board_version >= 2
                self._v2_features = dict.fromkeys(('TMP36', 'U_BANK'),
                                                  driven)
            else:
                self._v2_features = self._probe_v2_features()
        return self._v2_features

    @property
    def firmware_info(self):
        """(major, minor, patch, board_target) as compiled into the
        device firmware, or None if it predates version reporting."""
        if (self._firmware_info is None
                and hasattr(self, 'get_firmware_version')):
            self._firmware_info = tuple(self.get_firmware_version())
        return self._firmware_info

    @property
    def firmware_version(self):
        """The device firmware release as (major, minor, patch), or
        None if it predates version reporting."""
        info = self.firmware_info
        return info[:3] if info else None

    @property
    def firmware_board_target(self):
        """The hardware revision this firmware was built for (v1
        builds are flashed with 'make flashv1'), or None if the
        firmware predates version reporting."""
        info = self.firmware_info
        return info[3] if info else None

    @property
    def board_version(self):
        """Hardware revision of the connected board: 1 or 2.

        Taken from the revision the device firmware was compiled for
        ('make flashv1' builds for v1 boards), board_version_source
        then reading 'firmware'. Firmware too old to report it gets
        detected from the presence of the v2-only options instead
        (see _probe_v2_features), source 'detected'. A disagreement
        between the compiled target and the wired options is warned
        about. 'declared' when given explicitly to the
        constructor."""
        if self._board_version is None:
            target = self.firmware_board_target
            if target in (1, 2):
                # The compiled-in target is the authoritative identity;
                # the wiring measurement gates the features and serves
                # as a sanity check only.
                self._board_version = target
                self.board_version_source = 'firmware'
                self._v2_features = self._probe_v2_features()
                detected = 2 if any(self._v2_features.values()) else 1
                if detected != target:
                    import warnings
                    warnings.warn(
                        f'The device firmware is built for a v{target} '
                        f'board while the wired options look like a '
                        f'v{detected} board. Check the wiring, or flash '
                        f'the matching build ("make '
                        f'{"flashv1" if detected == 1 else "flash"}").')
            else:
                # Firmware too old to report its identity.
                self._board_version = (2 if any(
                    self._v2_present.values()) else 1)
                self.board_version_source = 'detected'
        return self._board_version

    @property
    def has_temperature_probe(self):
        """Whether the external TMP36 temperature probe is wired (v2)."""
        return self._v2_present['TMP36']

    @property
    def has_capacitor_bank_monitor(self):
        """Whether the capacitor bank voltage divider is wired (v2)."""
        return self._v2_present['U_BANK']

    def get_frequency(self):
        ''' Return the mcu clock frequency. Nominal or calibrated if avaialable'''
        freq = self.get_clock_calibration()
        if math.isnan(freq):
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
        return int(round(seconds * self.frequency))

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
        """ Read the TMP36 temperature in deg C (v2 boards only)
        """
        if not self.has_temperature_probe:
            raise NotImplementedError(
                'No external temperature probe detected on this v1 '
                'board. The chip temperature remains available with '
                'read_mcu_temperature().')
        V_adc = self.read_adc(adc_pin_maps['TMP36']) * 1.1/1024
        # 10 mV / deg and 750mV @ 25
        temp = 25 + (V_adc - 0.75) * 100
        return temp

    def read_capacitor_bank_voltage(self):
        """ Read the capacitor bank voltage in V (v2 boards only)
        """
        if not self.has_capacitor_bank_monitor:
            raise NotImplementedError(
                'No capacitor bank voltage divider detected on this v1 '
                'board.')
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

