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
import argparse

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

    def get_frequency(self):
        ''' Return the mcu clock frequency. Nominal or calibrated if avaialable'''
        freq = self.get_clock_calibration()
        if np.isnan(freq):
            import warnings
            warnings.warn('The mcu clock is not calibrated. If you need precise timings consider running "smartiris calibrate".')
            return 2e6
        else:
            return freq

    def calibrate(self, duration_min=10):
        import smartiris.clock_calibration
        mcu_data, ntp_data = smartiris.clock_calibration.acquire_clock_data(self, duration=duration_min*60)
        slope, eslope = smartiris.clock_calibration.clock_calibration_fit(mcu_data['start'], mcu_data['mcu'])
        print(f'Measured a time scale difference of {(slope-1) * 100:.4f}% (±{eslope*100:.4f}%)')
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
                rtiming, rpin = self.get_program(pos)
                if (rtiming == timing_count) and (rpin == 1<<pin):
                    return
            except ValueError:
                print('Catched communication error')
                self.flush()
        raise IOError(f'Corrupted program on device. Asked for ({timing_count}, {1<<pin}) got ({rtiming}, {rpin}) in position {pos}')
                
    def timed_shutter(self, delay_sec=1e-4, duration_sec=1, port='A', pulsewidth_sec=30e-3, exec=True):
        """Program a sequence to open and close the shutter with specified timing.

        This method sets up a sequence of pulses to open the shutter after a delay,
        keep it open for a duration, and then close it. 

        Args:
            delay_sec (float): Initial delay before starting (default: 100 μs).
            duration_sec (float): Time to keep the shutter open (default: 1 s).
            port (str): Shutter port identifier (default: 'A').
            pulsewidth_sec (float): Duration of the opening/closing pulses (default: 0.03 s).
            exec (bool): If false program only. The execution can be triggered later using method start_program.
        """
        pins = port_pins[port]
        self.safe_program_pulse(pins['open'], 0, delay_sec)
        self.safe_program_pulse(pins['open'], 1, delay_sec + pulsewidth_sec)
        self.safe_program_pulse(pins['close'], 2, delay_sec + duration_sec)
        self.safe_program_pulse(pins['close'], 3, delay_sec + duration_sec + pulsewidth_sec)
        if exec:
            self.start_program()

    def open_shutter(self, port='A', pulsewidth_sec=30e-3, delay_sec=10e-3, exec=True):
        """Open the shutter on the specified port.

        Programs and starts a sequence to activate the open pin for the given pulse width.

        Args:
            port (str): Shutter port identifier (default: 'A').
            pulsewidth_sec (float): Duration of the opening pulse (default: 0.03 s).
            delay_sec (float): Delay before starting (default: 0.01 s).
            exec (bool): If false program only. The execution can be triggered later using method start_program.
        """
        pins = port_pins[port]
        self.program_pulse(pins['open'], 0, self._ct(delay_sec))
        self.program_pulse(pins['open'], 1, self._ct(delay_sec + pulsewidth_sec))
        if exec:
            self.start_program()

    def close_shutter(self, port='A', pulsewidth_sec=30e-3, delay_sec=10e-3):
        """Close the shutter on the specified port.

        Programs and starts a sequence to activate the close pin for the given pulse width.

        Args:
            port (str): Shutter port identifier (default: 'A').
            pulsewidth_sec (float): Duration of the closing pulse (default: 0.03 s).
            delay_sec (float): Delay before starting (default: 0.01 s).
            exec (bool): If false program only. The execution can be triggered later using method start_program.
        """
        pins = port_pins[port]
        self.program_pulse(pins['close'], 0, self._ct(delay_sec))
        self.program_pulse(pins['close'], 1, self._ct(delay_sec + pulsewidth_sec))
        if exec:
            self.start_program()

    def read_program(self):
        """Print the programmed pulse sequence for debugging.

        Reads and displays the program steps (up to 4) from the device.
        """
        for i in range(4):
            print(self.get_program(i))

    def status(self):
        """Retrieve the current status of the shutter driver.

        Returns:
            dict: A dictionary containing:
                - 'shutter_A': State of shutter A ('open' or 'closed').
                - 'shutter_B': State of shutter B ('open' or 'closed').
                - 'busy': Boolean indicating if a program is running.
        """
        com_port, read_port, program_cursor, program_length = self.raw_status()
        if self.debug:
            print(f'{com_port=}, {read_port=}, {program_cursor=},{program_length=}')
        status = {
            'shutter_A': 'closed' if read_port & 0b100 else 'open',
            'shutter_B': 'closed' if read_port & 0b1000 else 'open',
            'busy': program_cursor != 0,
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
            
pin_map = {8: 0,
           9: 1,
           10: 2,
           11: 3,
           12: 4,
           13: 5,
           }

port_pins = {'A': {'close': pin_map[8],
                   'open': pin_map[9]},
             'B': {'close': pin_map[10],
                   'open': pin_map[11],
                   },
             }


def restricted_float(x, min_val=5., max_val=35.):
    try:
        x = float(x)  # Convert string input to float
    except ValueError:
        raise argparse.ArgumentTypeError(f"{x} is not a valid float")
    if not (min_val <= x <= max_val):
        raise argparse.ArgumentTypeError(f"{x} is not in range [{min_val}, {max_val}]")
    return x

def test():
    ''' Operate the shutter from the command line'''
    parser = argparse.ArgumentParser(
        description='Operate an iris blade shutter')
    parser.add_argument(
        '-t', '--tty', default='',
        help='link to a specific tty port')
    parser.add_argument(
        '-w', '--pulse-width', default=30e-3,
        type=lambda x: restricted_float(x, min_val=5., max_val=35.) * 1e-3,
        help='Duration of the opening and closing pulses (in milliseconds). Too long pulses might damage the shutter excitation coil or discharge to deeply the build-in capacitor bank of controller, causing reset of the device. Pulses too short will result in incomplete (or unreliable) opening or closing of the blades.')
    parser.add_argument(
        '-p', '--port', default='A', choices=port_pins,
        help='Identifier of the shutter port. "A" is the port on the left when looking the shutter ports on the box.')
    parser.add_argument(
        '-v', '--verbose', action='store_true',
        help='Print communication debugging info')
    parser.add_argument(
        '-r', '--reset', action='store_true',
        help='Hard reset the device at startup')
    
    # Create subparsers for the commands
    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # Parser for the 'open' command
    parser_open = subparsers.add_parser('open', help='Open the shutter')

    # Parser for the 'close' command
    parser_close = subparsers.add_parser('close', help='Close the shutter')

    # Parser for the 'timed' command
    parser_timed = subparsers.add_parser('timed', help='Open shutter for a specific duration')
    parser_timed.add_argument(
        '-d', '--delay', type=float, default=10e-3,
        help='Duration to keep the shutter open (in seconds)')

    parser_timed.add_argument(
        '-e', '--exposure-time', type=float, default=1.,
        help='Duration to keep the shutter open (in seconds)')
    # Parser for the 'stop' command
    parser_close = subparsers.add_parser('stop', help='Interrupt the execution of the program. The shutter will remain in its current state')

    parser_status = subparsers.add_parser('status', help='Print the shutter status')
    parser_status.add_argument('--raw', action='store_true', help='Display raw (unprocess) device status')

    parser_disable = subparsers.add_parser('disable_buttons', help='Disable device buttons for the session to avoid interference with remote controle.')
    parser_enable = subparsers.add_parser('enable_buttons', help='Re-enable device buttons for the session, They will have precedence over remote operations.')
    parser_calibrate = subparsers.add_parser('calibrate', help='Run time calibration procedure')
    parser_calibrate.add_argument(
        '-d', '--duration', type=float, default=10,
        help='Duration of the calibration procedure (in minutes)')
    
    
    args = parser.parse_args()
        
    d = SmartIris(dev=args.tty, baudrate=115200, debug=args.verbose, reset=args.reset)
    if args.command == 'open':
        d.open_shutter(port=args.port, pulsewidth_sec=args.pulse_width)
    elif args.command == 'close':
        d.close_shutter(port=args.port, pulsewidth_sec=args.pulse_width)
    elif args.command == 'timed':
        d.timed_shutter(port=args.port, pulsewidth_sec=args.pulse_width, duration_sec=args.exposure_time, delay_sec=args.delay)
    elif args.command == 'status':
        if args.raw:
            print(d.raw_status())
        else:
            print(d.status())
    elif args.command == 'stop':
        print(d.stop_program())
    elif args.command == 'disable_buttons':
        d.disable_buttons()
    elif args.command == 'enable_buttons':
        d.enable_buttons()
    elif args.command == 'calibrate':
        d.calibrate(args.duration)
