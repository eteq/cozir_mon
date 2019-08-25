"""
A monitor script for Cozir-A on an adafruit adalogger
"""

ITERS = 5
WAIT_SECS = 5


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

def blink_led(led, timesec, n=1):
    for i in range(n):
        if i > 0:
            time.sleep(timesec)
        led.value = True
        time.sleep(timesec)
        led.value = False


# Connect to the card and mount the filesystem.
spi = busio.SPI(board.SCK, board.MOSI, board.MISO)
cs = digitalio.DigitalInOut(board.SD_CS)
try:
    sdcard = adafruit_sdcard.SDCard(spi, cs)
    vfs = storage.VfsFat(sdcard)
    storage.mount(vfs, "/sd")
except Exception as e:
    for _ in range(6):
        blink_led(rled, .075, 1)
        blink_led(gled, .075, 1)
    print('Failed to set up and mount SD card! Exception info:', str(e),'\nPrinting to console instead.')
    sdcard = None

uart = busio.UART(board.TX, board.RX, baudrate=9600)
uart.write(b'K 0\r\n')
time.sleep(.1)
uart.reset_input_buffer()
uart.write(b'K 2\r\n')
if b'K 00002' not in uart.read(10):
    for _ in range(25):
        blink_led(rled, .05, 1)
        blink_led(gled, .05, 1)
    raise IOError('CozIR not responding normally')


def main_loop(f):
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
            blink_led(gled, .4, 2)
        elif co2_ppm < 1000:
            blink_led(gled, .2, 4)
        elif co2_ppm < 1500:
            blink_led(rled, .4, 2)
        elif co2_ppm < 2000:
            blink_led(rled, .2, 4)
        if co2_ppm >= 2000:
            blink_led(rled, .1, 5)
            rled.value = True

        time.sleep(WAIT_SECS)

if sdcard is None:
    class FakeByteWriter:
        def write(self, x):
            s = ''.join([chr(c) for c in x])
            print(s)
            return
    fake_file = FakeByteWriter()
    main_loop(fake_file)

with open("/sd/co2.log", "wb") as f:
    main_loop(f)
