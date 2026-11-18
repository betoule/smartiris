# Copyright 2024-2026 Marc Betoule
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

"""Command line interface to operate the smartiris shutter.

Built with typer, which provides shell completion. To enable it run:

    eval "$(smartiris --show-completion)"

or append its output to your shell init file. `smartiris
--install-completion` does that for you. (On click >= 8.2 the raw
mechanism is `_SMARTIRIS_COMPLETE=source_bash`; older `bash_source`
values no longer work.)
"""

from enum import Enum
from typing import Annotated

import typer

from smartiris import SmartIris

app = typer.Typer(no_args_is_help=True,
                  help='Operate an iris blade shutter.')

# Empty means: autodetect among the connected compatible devices
# (see bincoms.find_devices and the `devices` command below).
DEFAULT_TTY = ''


class PortName(str, Enum):
    A = 'A'
    B = 'B'


def tty_completer(incomplete: str):
    """Complete --tty with the connected serial devices."""
    import glob
    devices = [p.device for p in serial_ports()]
    devices += glob.glob('/dev/serial/by-id/*')
    devices += glob.glob('/dev/serial/by-path/*')
    yield from (d for d in sorted(set(devices)) if d.startswith(incomplete))


def serial_ports():
    try:
        from serial.tools.list_ports import comports
        return comports()
    except Exception:
        return []


def get_device(ctx: typer.Context) -> SmartIris:
    config = ctx.obj
    return SmartIris(dev=config['tty'], baudrate=115200,
                     debug=config['verbose'], reset=config['reset'],
                     board_version=config['board'])


@app.callback()
def main(
    ctx: typer.Context,
    tty: Annotated[
        str, typer.Option(
            '-t', '--tty', autocompletion=tty_completer,
            help='link to a specific tty port. When omitted, the device '
            'is autodetected among the connected compatible devices '
            '(see the devices command)')] = DEFAULT_TTY,
    pulse_width: Annotated[
        float, typer.Option(
            '-w', '--pulse-width', min=5., max=35.,
            help='Duration of the opening and closing pulses (in '
            'milliseconds). Too long pulses might damage the shutter '
            'excitation coil or discharge to deeply the build-in '
            'capacitor bank of controller, causing reset of the device. '
            'Pulses too short will result in incomplete (or unreliable) '
            'opening or closing of the blades.')] = 30.,
    port: Annotated[
        PortName, typer.Option(
            '-p', '--port',
            help='Identifier of the shutter port. "A" is the port on the '
            'left when looking the shutter ports on the box.')] = PortName.A,
    verbose: Annotated[
        bool, typer.Option('-v', '--verbose',
                           help='Print communication debugging info')] = False,
    reset: Annotated[
        bool, typer.Option('-r', '--reset',
                           help='Hard reset the device at startup')] = False,
    board: Annotated[
        int, typer.Option(
            '--board-version', min=0, max=2,
            help='Declare the hardware revision of the device (1 or 2). '
            'By default it is autodetected from the wired options (the '
            'v2 boards have the external temperature probe and the '
            'capacitor bank monitor that the v1 boards lack).')] = 0,
):
    """Operate an iris blade shutter"""
    ctx.obj = {'tty': tty, 'pulse_width': pulse_width * 1e-3,
               'port': port.value, 'verbose': verbose, 'reset': reset,
               'board': board or None}


@app.command()
def open(ctx: typer.Context,
         echo: Annotated[
             bool, typer.Option('-o', '--echo',
                                help='Activate echoing on the trigout '
                                'line')] = False):
    """Open the shutter"""
    config = ctx.obj
    d = get_device(ctx)
    d.open_shutter(port=config['port'], pulsewidth_sec=config['pulse_width'],
                   echo=echo)


@app.command()
def close(ctx: typer.Context,
          echo: Annotated[
              bool, typer.Option('-o', '--echo',
                                 help='Activate echoing on the trigout '
                                 'line')] = False):
    """Close the shutter"""
    config = ctx.obj
    d = get_device(ctx)
    d.close_shutter(port=config['port'], pulsewidth_sec=config['pulse_width'],
                    echo=echo)


@app.command()
def timed(ctx: typer.Context,
          delay: Annotated[
              float, typer.Option('-d', '--delay',
                                  help='Delay before opening the shutter '
                                  '(in seconds)')] = 10e-3,
          echo: Annotated[
              bool, typer.Option('-o', '--echo',
                                 help='Activate echoing on the trigout '
                                 'line')] = False,
          exposure_time: Annotated[
              float, typer.Option('-e', '--exposure-time',
                                  help='Duration to keep the shutter open '
                                  '(in seconds)')] = 1.):
    """Open shutter for a specific duration"""
    config = ctx.obj
    d = get_device(ctx)
    d.timed_shutter(port=config['port'], pulsewidth_sec=config['pulse_width'],
                    duration_sec=exposure_time, delay_sec=delay, echo=echo)


@app.command()
def devices():
    """List the connected bincom compatible devices. Use --tty to select
    one when several are found."""
    import serial.tools.list_ports
    from bincoms import find_devices
    found = find_devices()
    if not found:
        print('No compatible device found')
        raise typer.Exit(1)
    port_info = {p.device: p for p in serial.tools.list_ports.comports()}
    for dev in found:
        info = port_info.get(dev)
        extra = f' - {info.description}' if info else ''
        print(f'{dev}{extra}')


@app.command()
def stop(ctx: typer.Context):
    """Interrupt the execution of the program. The shutter will remain in
    its current state"""
    d = get_device(ctx)
    print(d.stop_program())


@app.command()
def status(ctx: typer.Context,
           raw: Annotated[
               bool, typer.Option('--raw',
                                  help='Display raw (unprocess) device '
                                  'status')] = False):
    """Print the shutter status"""
    d = get_device(ctx)
    if raw:
        print(d.raw_status())
        return
    from rich.console import Console
    from rich.table import Table
    st = d.status()
    green = lambda v: f'[green]{v}[/green]'
    yellow = lambda v: f'[yellow]{v}[/yellow]'
    shutter = lambda v: green(v) if v == 'open' else yellow(v)
    program = green('idle') if not st['busy'] else yellow('running')
    table = Table(box=None, show_header=False, pad_edge=False)
    table.add_column('property', style='bold')
    table.add_column('value')
    table.add_row('Board', f'v{d.board_version} ({d.board_version_source})')
    table.add_row('Shutter A', shutter(st['shutter_A']))
    table.add_row('Shutter B', shutter(st['shutter_B']))
    table.add_row('Program', program)
    table.add_row('Program length', str(st['program_length']))
    table.add_row('Events recorded', str(st['events_recorded']))
    Console().print(table)


@app.command('disable_buttons')
def disable_buttons(ctx: typer.Context):
    """Disable device buttons for the session to avoid interference with
    remote controle."""
    d = get_device(ctx)
    d.disable_buttons()


@app.command('enable_buttons')
def enable_buttons(ctx: typer.Context):
    """Re-enable device buttons for the session, They will have precedence
    over remote operations."""
    d = get_device(ctx)
    d.enable_buttons()


@app.command('set_board_version')
def set_board_version(ctx: typer.Context,
                      version: Annotated[
                          int, typer.Argument(
                              min=1, max=2,
                              help='Hardware revision of the device')] = 2):
    """Store the hardware revision in the device EEPROM. The value then
    takes precedence over autodetection (it survives firmware updates).
    Requires current firmware on the device."""
    d = get_device(ctx)
    d.provision_board_version(version)
    print(f'Board version v{version} stored in the device EEPROM.')


@app.command()
def calibrate(ctx: typer.Context,
              duration: Annotated[
                  float, typer.Option('-d', '--duration',
                                      help='Duration of the calibration '
                                      'procedure (in minutes)')] = 1.,
              output_file: Annotated[
                  str, typer.Option(
                      '-o', '--output-file',
                      help='Instead of calibrating the MCU clock register '
                      'the calibration data into the provided file')] = ''):
    """Run time calibration procedure"""
    d = get_device(ctx)
    d.calibrate(duration, output_file)


@app.command()
def read(ctx: typer.Context):
    """Report measured timings of sensor events"""
    d = get_device(ctx)
    record = d.read_timing_record()
    print(f'Recorded sensor events: {record}')
    if len(record) == 2:
        exptime = record[1][0] - record[0][0]
        print(f'Measured exposure time: {exptime} s')


@app.command('start_server')
def start_server(ctx: typer.Context,
                 hostname: Annotated[
                     str, typer.Option('-H', '--hostname',
                                       help='Specify the address the server '
                                       'listens to')] = '0.0.0.0',
                 server_port: Annotated[
                     int, typer.Option('-P', '--server-port',
                                       help='Specify the port the server '
                                       'listens to')] = 7913):
    """Start an xmlrpc server exposing the device functionalities. The
    server daemonizes unless verbose mode is on."""
    from . import daemon_servers
    d = get_device(ctx)
    daemon_servers.setup_logging('smartiris')
    server = daemon_servers.BasicServer((hostname, server_port), 'smartiris', d)
    print(f'Listening on http://{hostname}:{server_port}')
    if not ctx.obj['verbose']:
        daemon_servers.daemonize(server)
    else:
        server.main()


if __name__ == '__main__':
    app()
