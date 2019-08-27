"""
A monitor script for Cozir-A on an adafruit adalogger
"""
import os
import board
import busio
import digitalio
import adafruit_sdcard
import storage
import time


sd_iters = 9  # times to record measurements if there's an SD card
sd_wait_secs = 90  # time between measurement cycles if there's an SD card
sd_filter = 32  # digital filter (~time scale) setting if there's an SD card
no_sd_wait_secs = 15  # time between measurement cycles if there's no SD card
no_sd_filter = 4  # digital filter (~time scale) setting if there's no SD card
leave_led_on = None  # None means decide depending on sd (False) or not (True)
# user settings - usually these would override the above
if 'user_settings.py' in os.listdir('.'):
    with open('./user_settings.py') as fr:
        exec(fr.read())

# constants according to http://www.co2meters.com/Documentation/Manuals/Manual-GSS-Sensors.pdf
MEASUREMENT_PERIOD_SECS = .02
FILTER_TO_WARM_UP_SECS = {1:1.2, 2:3, 4:5, 8:9, 16:16, 32:32}


gled = digitalio.DigitalInOut(board.GREEN_LED)
gled.direction = digitalio.Direction.OUTPUT
gled.value = False
rled = digitalio.DigitalInOut(board.RED_LED)
rled.direction = digitalio.Direction.OUTPUT
rled.value = False


def blink_led(led, timesec, n=1, endstate=False):
    for i in range(n):
        if i > 0:
            time.sleep(timesec)
        led.value = True
        time.sleep(timesec)
        led.value = False
    led.value = endstate


# Try to connect to the card and mount the filesystem.
# Apply user settings depending on whether this fails or not.
try:
    spi = busio.SPI(board.SCK, board.MOSI, board.MISO)
    cs = digitalio.DigitalInOut(board.SD_CS)
    sdcard = adafruit_sdcard.SDCard(spi, cs)
    vfs = storage.VfsFat(sdcard)
    storage.mount(vfs, "/sd")
    print('Found SD card.')
    blink_led(gled, .075, 8)
    iters = sd_iters
    wait_secs = sd_wait_secs
    digital_filter_value = sd_filter
except Exception as e:
    for _ in range(6):
        blink_led(rled, .075, 1)
        blink_led(gled, .075, 1)
    print('Failed to set up and mount SD card! Exception info:', str(e), '\nPrinting to console instead.')
    sdcard = None
    iters = 1
    wait_secs = no_sd_wait_secs
    digital_filter_value = no_sd_filter
warm_up_secs = FILTER_TO_WARM_UP_SECS[digital_filter_value]
if leave_led_on is None:
    leave_led_on = sdcard is None

print('Using wait time =', wait_secs, '; digital filter =',
      digital_filter_value, '; warm up time =', warm_up_secs,
      '; iterations =', iters, '; leave_led_on=', leave_led_on)

uart = busio.UART(board.TX, board.RX, baudrate=9600)
uart.write(b'K 0\r\n')
uart.write(bytearray('A {}\r\n'.format(int(digital_filter_value))))
time.sleep(.1)
uart.reset_input_buffer()

# check that issuing a command acknowledges correctly to make sure
# communication makes sense
uart.write(b'K 0\r\n')
if b'K 00000' not in uart.read(10):
    for _ in range(100):
        blink_led(rled, .025, 1)
        blink_led(gled, .025, 1)
    raise IOError('CozIR not responding normally')


def main_loop(f, iters, wait_secs, warm_up_secs, leave_led_on):
    while True:
        start_loop_time = time.monotonic()

        uart.write(b'K 2\r\n')
        time.sleep(warm_up_secs)

        print('Starting CO2 read cycle')
        f.write(b'deltat: ' + bytes(bytearray(str(time.monotonic()))) + b'\n')
        for _ in range(iters):
            time.sleep(MEASUREMENT_PERIOD_SECS)
            uart.reset_input_buffer()
            uart.write(b'Q\r\n')
            bs = uart.read(50)
            if bs is None:
                print('No response! aborting this data run')
                break
            f.write(bs.replace(b'\r\n', b'\n'))
        f.write(b'deltat: ' + bytes(bytearray(str(time.monotonic()))) + b'\n')
        f.flush()

        if bs is not None:
            co2_ppm = int(bs.split(b'Z ')[1].split(b' z')[0])
            print('co2 after cycle is:', co2_ppm, 'ppm')
            rled.value = gled.value = False
            if co2_ppm < 500:
                blink_led(gled, .4, 2, leave_led_on)
            elif co2_ppm < 1000:
                blink_led(gled, .2, 4, leave_led_on)
            elif co2_ppm < 1500:
                blink_led(rled, .4, 2, leave_led_on)
            elif co2_ppm < 2000:
                blink_led(rled, .2, 4, leave_led_on)
            if co2_ppm >= 2000:
                blink_led(rled, .1, 8, leave_led_on)

        uart.write(b'K 0\r\n')  # lower power mode

        end_loop_time = time.monotonic()
        sleep_time = wait_secs - (end_loop_time - start_loop_time)
        if sleep_time > 0:
            time.sleep(sleep_time)


# now actually do the main loop with a writer determined by the sd card's presence or absence
if sdcard is None:
    class FakeByteWriter:
        def write(self, x):
            s = ''.join([chr(c) for c in x])
            print(s, end='')
            return
        def flush(self):
            pass
    fake_file = FakeByteWriter()
    main_loop(fake_file, iters, wait_secs, warm_up_secs, leave_led_on)
else:
    co2nums = [int(fn[4:-4]) for fn in os.listdir('/sd') if fn.startswith('co2_') and fn.endswith('.log')]
    if not co2nums:
        co2nums = [-1]
    fn = "/sd/co2_{}.log".format(max(co2nums)+1)
    print('Writing to', fn)
    with open(fn, "wb") as f:
        main_loop(f, iters, wait_secs, warm_up_secs, leave_led_on)
