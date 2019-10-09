# Feather software for Cozir CO2 monitor

This directory contains the software to run on a Feather M0 on CircuitPython, connected to a CozirA CO2 monitor.

## Hardware Assumptions

This software was desined and tested on a Feather M0 Adalogger.  It should work on *any* M0, however, and should log out-of-the-box on any Adafruit Express boards (which come with 2MB built-in flash) or anything with an SPI-connected SD card (e.g. a featherwing logger).

The only required sensor is a CozirA connected to the standard Tx/Rx pins.  However, a DS3231 RTC, BME280 temp/pressure/humidity sensor, or SGP30 gas sensor will also be logged if present.
A NeoPixel attached to D11 is also necessary to see the colored indicator light.

## Installation

The software pushes up against the M0's memory limits in CircuitPython, so it requires some additional steps beyond simply dropping .py files into the board.  Specifically, on an M0 it requires the `mpy-cross` tool. Some good instructions on this for CircuitPython are here:
    ://learn.adafruit.com/creating-and-sharing-a-circuitpython-library?view=all#mpy-2-11in.value(1)

Once you have the `mpy-cross` tool installed, use it to build .mpy files for:

* `bme280_calib.py`
* `rtc_time.py`
* `ppm_to_rgb.py`
* `cozir_mon_feather.py`

Copy all of the resulting `.mpy` files to your board, along with:

* `battery_check_feather.py`
* code.py
* (optional) `setup_sd.py`

The last one is not mandatory, but may make working with your feather at the prompt a bit easier.

Once that software is installed, 

