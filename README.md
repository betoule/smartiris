SmartIris USB-Powered Shutter Controller
========================================

A compact and efficient USB-powered controller designed to handle two
independent Iris shutters by
[Thorlabs](https://www.thorlabs.com/newgrouppage9.cfm?objectgroup_id=6619&pn=SHB1T#7096). This
project offers an alternative solution that avoids heat dissipation,
sending only the necessary current pulses to open or close the
shutter. This alternative is suitable for low actuation rates (<1Hz).

Features
--------

* Easy-to-use USB interface for power and control
* Open-source design for customization
* Independently controlled channels for two Iris shutters
* Python library
* Improved energy efficiency by avoiding continuous heat dissipation
* Precise timing of the iris movements

Getting Started
---------------

### Requirements

* One or Two Thorlabs Iris shutters
* USB A to Mini-B cable
* 3D printed or custom PCB case (optional)

### Software Installation

1. Download and install the control software for your operating system from the project's GitHub repository:
```bash
git clone https://github.com/betoule/smartiris.git
cd smartiris
pip install .
```
2. Connect the controller to your computer via a USB port using a USB A to Mini-B cable.
3. Ensure that an Iris shutters is properly connected to the controller with matching channel assignments. Port "A" and "B" refers to the left and right port respectively.
4. Test the status:
```bash
smartiris status
```
Example output for two closed and connected shutters:
```
{'shutter_A': 'closed', 'shutter_B': 'closed', 'busy': False}
```

Unconnected shutters appear as `closed`. Partly open shutters may appear as closed or open depending on the sensor location on the device.

### Troubleshooting

#### Permission errors 

Errors of the kind:
```
PermissionError: [Errno 13] Permission denied: '/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_AQ01L27T-if00-port
```
occur when you don't have access rights to the serial devices. On linux systems you need to add yourself to the dialout group:
```bash
sudo usermod -a -G dialout username
```
Group changes typically take effect after the user logs out and logs back in. To apply the change immediately without logging out, you can use
```bash
newgrp dialout
```

#### FileNotFound errors

Errors of the kind:
```
FileNotFoundError: [Errno 2] No such file or directory: '/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_AQ01L27T-if00-port0'
```
occur when the serial device is not at the spectified location. You need to identify the path to the device file by looking at appearing files in:
```bash
ls /dev/serial/by-id/
#plug the device
ls /dev/serial/by-id/
#Look for the new line
```
after the device has been plugged. Once the device has been identified you can specify its path as:
```bash
smartiris -t /dev/serial/by-id/{actual_device_id} status
```

Mac-OS users should look for the device appearing in:
```bash
ls /dev/tty*.*
```

### Hardware build

* Schematics is available in directory `schematics`
* Files to build a 3D case are available in `3D`
* Once assembled connect your computer to the arduino and flash the firmware using the arduino IDE. The code is compatible with version 1.8 of the IDE. Open the sketch `smartiris.ino` and upload the sketch.

Usage
-----
### Command line

The `smartiris` command-line tool controls supports several commands and options to operate the shutter.

#### Basic Syntax
```
smartiris [OPTIONS] COMMAND
```

#### Options
- `-t, --tty PORT`  
  Specify the TTY port (default: `/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_AQ01L27T-if00-port0`).
- `-w, --pulse-width SECONDS`  
  Set the duration of opening/closing pulses in seconds (default: `0.03`).
- `-p, --port ID`  
  Select the shutter port (default: `A`).
- `-v, --verbose`  
  Enable debug output for communication.
- `-r, --reset`  
  Perform a hard reset of the device on startup. The execution of the command is slower at first call.

#### Commands
- `open`  
  Open the shutter.  
  Example: `smartiris open`

- `close`  
  Close the shutter.  
  Example: `smartiris close`

- `timed`  
  Open the shutter for a specified duration.  
  Additional options:  
  - `-d, --delay SECONDS`  
    Delay before action (default: `0.01` seconds).  
  - `-e, --exposure-time SECONDS`  
    Duration to keep the shutter open (default: `1.0` seconds).  
  Example: `smartiris timed -e 2.5`

- `stop`  
  Interrupt execution, leaving the shutter in its current state.  
  Example: `smartiris stop`

- `status`  
  Display the current status of the shutter driver.  
  Example: `smartiris status`

#### Examples
- Open the shutter with a custom pulse width on port B:  
  `smartiris -p B -w 25 open`
- Keep the shutter open for 3 seconds:  
  `smartiris timed -e 3.0`
- Check the shutter status with verbose output of the communication with the device:  
  `smartiris -v status`
- Interrupt a long duration exposure. The shutter will remain in its current state.
  ```
  smartiris timed -e 10
  sleep 0.1
  smartiris status
  smartiris stop
  smartiris status
  ```

### Python library

The python library provides direct access to the controler. The control logic works as follows: a short program is written to the controler specifying which pins to operate at specific timings to energize the activation coils of the shutters. The timing are specified with a resolution of 0.5μs and can extend over a duration of up to 17 minutes. The high level functions are `open_shutter` and `close_shutter` which execute a two step program (energize the coil for a given duration then release) and `timed_shutter` which executes a 4 step program chaining the two operations separated by a given interval. All writen program executions can be prevented by specifying `exec=False` then triggered latter at will by calls to `start_program`. The use of delayed execution avoid cummulating random delays in the USB communication and offer the best synchronisation timing between the host and the device. Here is a complete example illustrating the various functions of the library:

```python
import smartiris

print('Connect to the device')
d = smartiris.SmartIris(dev='/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_AQ01L27T-if00-port0')

print(' Query the shutter status')
print(d.status())

print('Open the port A shutter')
d.open_shutter()
print('Wait for completion')
d.wait()

print('Close port A shutter')
d.close_shutter()
print('Wait for completion')
d.wait()

print('Open for 3 seconds after a 2 seconds delay (setup only)')
d.timed_shutter(delay_sec=2, duration_sec=3)
print('Wait for completion')
d.wait()

print('re-trigger')
d.start_program()
print('Wait for completion')
d.wait()
```

Roadmap
-------

- [ ] Record the timings of the hall sensor trigger
- [ ] Handle manual operation
- [ ] Robustify the serial communication

Release History
---------------
### v0.2
- Handle button event
- Pull-up sensor lines to make unconnected shutter consistently appear as close
- Auto-detect the device port

### v0.1
First release in use during the april 2025 OHP campaign

Contributing
------------

Main contributors are:
- Marc Betoule, for the firmware and the host python library
- Fabien Frerot, for the electronics and schematics

Pull requests are welcome! For major changes, please open an issue first to discuss proposed modifications.

License
-------

This project is licensed under GPL V2 License - see the [LICENSE.md](LICENSE.md) file for details.

Acknowledgments
--------------

* Thorlabs for manufacturing quality Iris shutters
* Open-source community for valuable contributions and support
