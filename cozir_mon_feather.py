"""
A monitor script for Cozir-A on an adafruit adalogger
"""

ITERS = 5
WAIT_SECS = 30


import board
import busio
import digitalio
import adafruit_sdcard
import storage
import time

gled = digitalio.DigitalInOut(board.GREEN_LED)
gled.direction = digitalio.Direction.OUTPUT
gled.value = False
rled = digitalio.DigitalInOut(board.RED_LED)
rled.direction = digitalio.Direction.OUTPUT
rled.value = False

def blink_led(led, time, n=1):
    for i in range(n):
        if i > 0:
            time.sleep(time)
        led.value = True
        time.sleep(time)
        led.value = False



# Connect to the card and mount the filesystem.
spi = busio.SPI(board.SCK, board.MOSI, board.MISO)
cs = digitalio.DigitalInOut(board.SD_CS)
try:
    sdcard = adafruit_sdcard.SDCard(spi, cs)
except:
    rled.value = True
    raise
vfs = storage.VfsFat(sdcard)
storage.mount(vfs, "/sd")

uart = busio.UART(board.TX, board.RX, baudrate=9600)
uart.write(b'K 0\r\n')
uart.reset_input_buffer()
uart.write(b'K 2\r\n')
assert uart.read(10) == b' K 00002\r\n', 'CozIR not responding normally'

with open("/sd/co2.log", "wb") as f:
    while True:
        f.write(b'deltat: ' + bytes(bytearray(str(time.monotonic()))))
        for _ in range(ITERS):
            uart.write(b'Q\r\n')
            bs = uart.read(50)
            f.write(bs)
        f.write(b'deltat: ' + bytes(bytearray(str(time.monotonic()))))

        co2_ppm = int(bs.split(b'Z ')[1].split(b' z')[0])
        print('co2 after cycle is:', co2_ppm, 'ppm')
        rled.value = False
        if co2_ppm < 500:
            blink_led(gled, .2, 1)
        elif co2_ppm < 1000:
            blink_led(gled, .2, 3)
        elif co2_ppm < 1500:
            blink_led(rled, .2, 1)
        elif co2_ppm <= 2000:
            blink_led(rled, .2, 3)
        if co2_ppm == 2000:
            rled.value = True

        time.sleep(WAIT_SECS)


