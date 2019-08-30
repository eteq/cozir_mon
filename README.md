# cozir_mon

![badge-img](https://img.shields.io/badge/Made%20at-%23AstroHackWeek-8063d5.svg?style=flat)

Python scripts for CO2 monitoring with a [Cozir NDIR CO2 sensor module](https://www.gassensing.co.uk/product/cozir-co2-sensor/).

The monitoring scripts are for various portable microcontroller/SoC-based boards. At the time of this writing, those include `cozir_mon_pi.py` for raspberry pi, and `cozir_mon_feather.py` for an [Adafruit feather M0 adalogger](https://learn.adafruit.com/adafruit-feather-m0-adalogger). 

The script for generating plots from the log files is `cozir_parser.py`.  To try it out on the example data, from the base of the repo do ``python cozir_parser.py example_feather_data.log test_plot.png``.
