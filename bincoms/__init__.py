# Copyright 2022 Marc Betoule
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

import struct
import time
import serial
import types
import os
import select
from serial.serialutil import Timeout
import termios

status_codes = ['STATUS_OK',
                'STATUS_BUSY',
                'STATUS_ERROR',
                'UNDEFINED_FUNCTION_ERROR',
                'BYTE_COUNT_ERROR',
                'COMMUNICATION_ERROR',
                'CHECKSUM_ERROR',
                'VALUE_ERROR']

status_message = ['Action performed successfully',
                  'Device is busy with another action',
                  'Action failed for undefined cause',
                  'Unknown function code (check command_count)',
                  'Incorrect size for the provided data buffer (check get_command_names({f},1) for the requested number of arguments',
                  'Ill-formed message on the communication port',
                  'Not used for now',
                  'The provided arguments are outside the allowed range']

def find_devices(keep_open=False):
    """Discover all bincom compatible devices.

    Returns the paths of the compatible devices. With keep_open=True,
    returns connected SerialBC instances instead (closed again unless
    exactly one device was found, so they are ready to be adopted for
    a single-device autodetect connection)."""
    import serial.tools.list_ports
    ports = serial.tools.list_ports.comports()
    devices = []
    for port in ports:
        if port.vid is not None:
            try:
                device = SerialBC(dev=port.device)
            except Exception:
                continue
            if keep_open:
                devices.append(device)
            else:
                device.com.close()
                devices.append(port.device)
    if keep_open and len(devices) != 1:
        for device in devices:
            device.com.close()
    return devices
            
def _command_factory(self, f, s, a):
    def func(self, *args):
        try:
            data = struct.pack(b'<B' + s, f, *args)
        except struct.error:
            raise ValueError(f'Provided arguments {args} do not match the requested types {s}')
        if self.debug:
            print(f'Encoding request with arguments {args} according to format {b"B"+s} as: {data}')
        r = self.snd(data)
        if a == b's':
            if self.debug:
                print(f'data: {r}')
            return r.decode()
        else:
            try:
                answer = struct.unpack(a, r)
                if self.debug:
                    print(f'data: {answer}')
                if len(answer) == 1:
                    return answer[0]
                else:
                    return answer
            except:
                buffer = self.flush()
                raise ValueError(f'Received answer "{r}" does not match the expected argument format: "{a}", trailing bytes:{buffer}')
    return types.MethodType(func, self)

class SerialBC(object):
    def __init__(self, dev='/dev/ttyUSB0', baudrate=115200, debug=False, reset=False):
        if not dev:
            # Autodetect: a single probed device is adopted as-is,
            # saving a second full connection handshake.
            candidates = find_devices(keep_open=True)
            if len(candidates) == 1:
                probed = candidates[0]
                probed.debug = debug
                if reset or baudrate != probed._baudrate:
                    probed._baudrate = baudrate
                    probed._open(reset=reset)
                self.__dict__.update(probed.__dict__)
                return
            elif len(candidates) > 1:
                raise IOError(f'Several compatible devices found: {[d._dev for d in candidates]}. Please specify which one to use with smartiris -t [device_path]')
            else:
                raise IOError(f'No compatible device found')

        self.debug=debug
        self._dev = dev
        self._baudrate = baudrate
        self._open(reset=reset)
        #self.com.set_low_latency_mode(True)
        #time.sleep(5)
        #self.com.flush()
        for i in range(2):
            try:
                self._register_commands()
                break
            except ValueError:
                self.com.flush()

    def _open(self, timeout=3, reset=False):
        try:
            self.com.close()
        except:
            pass
        # Disable reset after hangup
        if self.debug:
            print('Port closed')
        f=os.open(self._dev, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
        attrs = termios.tcgetattr(f)
        attrs[2] = attrs[2] & ~termios.HUPCL
        termios.tcsetattr(f, termios.TCSAFLUSH, attrs)
        os.close(f)
        if self.debug:
            print('Port set')
        try:
            self.com = serial.Serial(self._dev, baudrate=self._baudrate, timeout=timeout, dsrdtr=None)
            try:
                # FTDI based adapters wait up to 16 ms (default
                # latency timer) before sending a partially filled
                # USB packet, adding the same delay to every round
                # trip. Setting the timer to 1 ms makes communication
                # feel instant. Silently ignored for other chips.
                self.com.set_low_latency_mode(True)
            except Exception:
                pass
        except:
            print('Connexion failed')
        if self.debug:
            print('Port open')
        if reset:
            if self.debug:
                print('Hard reset')
            self.com.setDTR(False) # Drop DTR
            time.sleep(0.022)    # Read somewhere that 22ms is what the UI does.
            self.com.setDTR(True)

        
    def _read(self, size):
        read = bytearray()
        #timeout = Timeout(self.com._timeout)
        for i in range(10000):
            buf = os.read(self.com.fd, size - len(read))
            read.extend(buf)
            if len(read) == size:
                break
            time.sleep(0.0001)
        return bytes(read)
    
    def _register_commands(self):
        self._get_nfunc = _command_factory(self, 0x00, b'', b'B')
        self._get_func_name = _command_factory(self, 0x01, b'BB', b's')
        for i in range(2, self._get_nfunc()):
            name, arg_format, answer_format = [self._get_func_name(i, a) for a in range(3)]
            if self.debug:
                print(f'Registering user function "{name}"')
            setattr(self, name, _command_factory(self, i, arg_format.encode(), answer_format.encode()))
                    
    def rcv(self):
        b = self.com.read(3)
        if self.debug:
            print(f'Received: {b}')
        try:
            m, a, l = struct.unpack(b'ccB', b)
        except:
            raise ValueError(f'Answer header: "{b}" does not match expected format "bcB"')
        a = int.from_bytes(a, byteorder='little', signed=False)
        if self.debug:
            print(f'header: {m.decode()},{status_codes[a]},{l}')  
        if (m == b'b' ) and (a == 0):
            data = self.com.read(l)
        elif (m == b'b') and (a < len(status_codes)):
            raise ValueError(f'{status_codes[a]}, {status_message[a]}')
        else:
            self.com.flush()
            raise ValueError (f'Answered string not understood: {b}')
        return data

    def snd(self, data):
        b = struct.pack(b'ccB', b'b', b'\x00', len(data))
        #print(b+data)
        if self.debug:
            print(f'Send: {b+data}')
        self.com.write(b+data)
        return self.rcv()

    def flush(self):
        return self.com.read_all()

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(
        description='Communicate with device implementing the generic bincoms protocol')
    parser.add_argument(
        '-t', '--tty', action='append', default=[],
        help='link to a specific tty port')
    args = parser.parse_args()
    
    for dev in args.tty:
        d = SerialBC(dev)
