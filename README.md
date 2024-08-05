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

### Hardware build


### Software Installation

1. Connect the controller to your computer via a USB port using a USB A to Mini-B cable.
2. Download, install, and run the control software for your operating system from the project's GitHub repository.
3. Ensure that both Iris shutters are properly connected to the controller with matching channel assignments.
4. Use the intuitive graphical user interface (GUI) to independently control each shutter's opening and closing.

Usage
-----

1. To open or close a specific iris, select the desired channel using the dropdown menu in the GUI.
2. Press the "Open" button to fully open the selected iris, or press the "Close" button to fully close it.
3. Adjust the speed settings for fine-tuned control over the movement (optional).
4. Disconnect the controller when not in use to conserve power and prolong its life span.

Troubleshooting
--------------

For any issues, consult the project's documentation or visit the GitHub repository for more information and support.

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
