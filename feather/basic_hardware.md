# Basic hardware assembly instructions

This document describes the basic hardware required to implement the feather CO2 monitor.

## Microcontroller/Feather Board

There are several different options that will work fine for this project.  The only real requirements are a board that has a UART, I2C,  some kind of loggable storage space, and the capability to run CircuitPython.  At the time of this writing, most Circuitpython-capable boards already satisfy the other needs.  For specific recommended boards consider:

* [Adafruit Feather M0 Express](https://www.adafruit.com/product/3403) - easiest to start with
* [Adafruit Feather M0 Adalogger](https://www.adafruit.com/product/2796) - requires added parts, but has the best logging potential
* [Adafruit Feather M4 Express](https://www.adafruit.com/product/3857) - has a more capable microcontroller, allowing potential future expansion of your build's capabilities

If you go the Adalogger direction you'll also need:
* An SD Card (buy just about anywhere you can get cameras, smartphones, etc)
* A Neopixel to show the CO2 level. Easiest option is probably https://www.adafruit.com/product/1312, but you'll want
* A [FeatherWing Proto](https://www.adafruit.com/product/2884) to solder your components to the adalogger, and headers to connect the feather to the FeatherWing (see the Adafruit pages on those product for specific options).

## CO2 Sensor

Two possible CO2 sensors are supported:

* The best option is the [CozirA](https://www.gassensing.co.uk/product/cozir-co2-sensor/) sensor.  This sensor uses infrared light to detect absorption due to CO2, so it is pretty well tuned specifically to CO2. It also comes in a few different sensitivity ranges (0-2000, 0-5000, and 0-10000 ppm) It is a bit more expensive than other options, though - ~$100 at the time of writing (and seems to show an upward tred...).  A known-good (at least as of mid-2019) place to purchase one is [here](https://www.co2meter.com/collections/0-1-co2/products/cozir-2000-ppm-co2-sensor).
* A much cheaper option is the [SGP30](https://www.adafruit.com/product/3709) - the downside is that it is significantly less accurate, mainly due to the fact that its measurement technique as cross-reactive with a wide variety of other things that might be in the air (e.g. volatile organics, etc), and claims to need calibration against a known reference to be absolutely reliable.

## Additional parts

* If you want to log real time instead of time since last startup, you'll need a real-time clock (RTC).  A good option is the DS3231, which only requires a few wires to interface with a feather. Adafruit provides a [DS3231 Featherwing](https://www.adafruit.com/product/3028) but you can get one from many other places by just googling around for DS3231.  Be sure to also get a coin-cell battery to keep the clock running when the power is disconnected (usually easiest to find at your local drug store in the "weird random battery" section).
* If you want a more general environment sensor you may wish to add a BME280, which you can find from various online sources with appropriate breakout boards (include [Adafruit](https://www.adafruit.com/product/2652), of course).
