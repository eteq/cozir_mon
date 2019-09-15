"""
A monitor script for Cozir-A on an adafruit adalogger
"""
import os
import board
import digitalio

# constants according to http://www.co2meters.com/Documentation/Manuals/Manual-GSS-Sensors.pdf
MEASUREMENT_PERIOD_SECS = .02
FILTER_TO_WARM_UP_SECS = {1:1.2, 2:3, 4:5, 8:9, 16:16, 32:32}
SGP_ITERS = 3


def setup_i2c():
    return busio.I2C(board.SCL, board.SDA, frequency=100000)





# user settings - usually these would override the above
if 'user_settings.py' in os.listdir('.'):
    with open('./user_settings.py') as fr:
        exec(fr.read())


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


# import busio
# import adafruit_sdcard
# import storage
# import time
# from battery_check_feather import get_battery_voltage


sd_iters = 9  # times to record measurements if there's an SD card
sd_wait_secs = 90  # time between measurement cycles if there's an SD card
sd_filter = 32  # digital filter (~time scale) setting if there's an SD card
no_sd_wait_secs = 15  # time between measurement cycles if there's no SD card
no_sd_filter = 4  # digital filter (~time scale) setting if there's no SD card
leave_led_on = None  # None means decide depending on sd (False) or not (True)






def from_bcd(b):  # from BCD to binary
    return b - 6 * (b >> 4)

# default from-start-up-time
def get_time_byte():
    return b'deltat: ' + bytes(bytearray(str(time.monotonic())))

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

#I2C thingies
i2cok = False
try:
    i2c = busio.I2C(board.SCL, board.SDA, frequency=100000)
    i2cok = True
except Exception as e:
    print('I2C did not initialize!: ' + str(e))

sgp30 = None
if i2cok:
    try:
        import adafruit_sgp30
        # set up the SGP30
        sgp30 = adafruit_sgp30.Adafruit_SGP30(i2c)
        print("SGP30 found - serial #", [hex(i) for i in sgp30.serial])
        test_measurements = sgp30.eCO2, sgp30.TVOC
    except ImportError:
        print('adafruit_sgp30 not present.  Skipping sgp30 setup')

# set up RTC
if i2cok:
    RTC_ADDR = 0x68
    def rtc_read(addr, nbytes=1):
        while not i2c.try_lock():
            pass
        b = bytearray(nbytes)
        i2c.writeto(RTC_ADDR, bytearray([addr]), stop=False)
        i2c.readfrom_into(RTC_ADDR, b)
        i2c.unlock()
        return b
    try:
        status_register = rtc_read(0x0f)[0]
        if status_register & 0b10000000:
            print('RTC may be inaccurate...')
        # this will make it actually happen
        def get_time_byte():
            # assumes 24 hour time is set
            sec, min, hr, day, date, mon, yr = rtc_read(0, 7)
            return bytearray('dt:20{:02}-{:02}-{:02} {}:{}:{}.0'.format(from_bcd(yr),
                   from_bcd(mon&0b11111), from_bcd(date), from_bcd(hr&0b111111),
                   from_bcd(min), from_bcd(sec)))
    except Exception as e:
        print('RTC did not initialize: ' + str(e))
        raise


def main_loop(f, iters, wait_secs, warm_up_secs, leave_led_on):
    if sgp30 is not None:
        f.write(bytearray('eCO2 baseline:{}, '
                'TVOC baseline:{}\n'.format(sgp30.baseline_eCO2,
                                            sgp30.baseline_TVOC)))

    while True:
        start_loop_time = time.monotonic()

        uart.write(b'K 2\r\n')
        time.sleep(warm_up_secs)

        print('Starting CO2 read cycle')
        f.write(get_time_byte() + b'\n')
        for _ in range(iters):
            time.sleep(MEASUREMENT_PERIOD_SECS)
            uart.reset_input_buffer()
            uart.write(b'Q\r\n')
            bs = uart.read(50)
            if bs is None:
                print('No response! aborting this data run')
                break
            f.write(bs.replace(b'\r\n', b'\n'))
        if sgp30 is not None:
            for _ in range(SGP_ITERS):
                sgp30.iaq_measure()
                time.sleep(1)  # 1Hz aq makes the baseline correction good according to datasheet
            eco2, tvoc = sgp30.iaq_measure()
            f.write(bytearray(' eCO2:{} TVOC:{}\n'.format(eco2, tvoc)))
        f.write(b'battery V:' + bytearray('{:.5f}'.format(get_battery_voltage())) + b'\n')
        print('battery voltage:', '{:.5f}'.format(get_battery_voltage()))

        f.write(get_time_byte() + b'\n')
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
