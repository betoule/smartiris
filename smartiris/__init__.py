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

class SmartIris(bincoms.SerialBC):
    def __init__(self, *args, **keys):
        super().__init__(*args, **keys)
        self.time_resolution = 0.5e-6

    def _ct(self, seconds):
        ''' Convert the floating point duration in seconds to a count number for the microcontroller timer
        '''
        return int(np.round(seconds/self.time_resolution))
    
    def async_packet_read(self):
        ans = self.rcv()
        answer = struct.unpack('<IB', ans)
        return answer

    def pulse_sec(self, pin, pulsewidth_sec):
        ''' Pulse the provided pin for a number of seconds
        '''
        self.pulse(pin, self._ct(pulsewidth_sec))

    def program_open(self, delay_sec=10e-3, duration_sec=1, port='A', pulsewidth_sec=30e-3):
        pins = port_pins[port]
        self.program_pulse(pins['open'], 0, self._ct(delay_sec))
        self.program_pulse(pins['open'], 1, self._ct(delay_sec + pulsewidth_sec))
        self.program_pulse(pins['close'], 2, self._ct(delay_sec + duration_sec))
        self.program_pulse(pins['close'], 3, self._ct(delay_sec + duration_sec + pulsewidth_sec))
        #self.start_program()

    def open_shutter(self, port='A', pulsewidth_sec=30e-3, delay_sec=10e-3):
        pins = port_pins[port]
        self.program_pulse(pins['open'], 0, self._ct(delay_sec))
        self.program_pulse(pins['open'], 1, self._ct(delay_sec + pulsewidth_sec))
        self.start_program()
        
    def close_shutter(self, port='A', pulsewidth_sec=30e-3, delay_sec=10e-3):
        pins = port_pins[port]
        self.program_pulse(pins['close'], 0, self._ct(delay_sec))
        self.program_pulse(pins['close'], 1, self._ct(delay_sec + pulsewidth_sec))
        self.start_program()

    def read_program(self):
        for i in range(4):
            print(self.get_program(i))
    
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

def test():
    ''' Operate the shutter from the command line'''
    import argparse
    parser = argparse.ArgumentParser(
        description='Operate an iris blade shutter')
    parser.add_argument(
        '-t', '--tty', default='/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_AQ01L27T-if00-port0',
        help='link to a specific tty port')
    parser.add_argument(
        '-w', '--pulse-width', default=30e-3, type=float,
        help='Duration of the opening and closing pulses (in seconds).')
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
        '-d', '--duration', type=float, default=1.,
        help='Duration to keep the shutter open (in seconds)')

    parser_status = subparsers.add_parser('status', help='Print the shutter driver status')

    args = parser.parse_args()

    d = SmartIris(dev=args.tty, baudrate=1000000, debug=args.verbose, reset=args.reset)
    if args.command == 'open':
        d.open_shutter(port=args.port, pulsewidth_sec=args.pulse_width)
    elif args.command == 'close':
        d.close_shutter(port=args.port, pulsewidth_sec=args.pulse_width)
    elif args.command == 'timed':
        d.program_open(port=args.port, pulsewidth_sec=args.pulse_width, duration_sec=args.duration)
        d.start_program()
    elif args.command == 'status':
        print(d.status())
    #d.open_for(duration_sec=args.interval, pulsewidth_sec=args.duration)
    #for i in range(args.n_pulses):
    #    d.pulse_sec(pin_map[args.pin], args.duration)
    #    time.sleep(args.interval)
    
    #for l in args.enabled_lines:
    #    if len(l) != 2:
    #        raise ValueError(f"Line identifier {l} does not comply with expected format [0-6][fr]")
    #    lid, front = int(l[0]), l[1].encode() 
    #    d.enable_line(lid, front)
    #import numpy as np
    #print(f'Recording lines {args.enabled_lines} for {args.duration}s')
    #result = np.rec.fromrecords(d.get_data(), names=['time', 'pinstate'])
    #print(f'Record saved to file {args.output_file}')
    #np.save(args.output_file, result)
