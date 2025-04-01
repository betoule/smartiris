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

### Troubleshooting

#### Permission errors 

Errors of the kind:
```
PermissionError: [Errno 13] Permission denied: '/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_AQ01L27T-if00-port
```
means that you don't have rights to access the serial devices. On linux systems you need to add yourself to the dialout group:
```bash
sudo usermod -a -G dialout username
```
Group changes typically take effect after the user logs out and logs back in. To apply the change immediately without logging out, you can use
```bash
newgrp dialout
```

### Hardware build

* Schematics is available in directory `schematics`
* Files to build a 3D case are available in `3D`
* Once assembled connect your computer to the arduino and flash the firmware using the arduino IDE. The code is compatible with version 1.8 of the IDE. Open the sketch `smartiris.ino` and upload the sketch.

Contributing
------------

Pull requests are welcome! For major changes, please open an issue first to discuss proposed modifications.

License
-------

This project is licensed under GPL V2 License - see the [LICENSE.md](LICENSE.md) file for details.

Acknowledgments
--------------

* Thorlabs for manufacturing quality Iris shutters
* Open-source community for valuable contributions and support
