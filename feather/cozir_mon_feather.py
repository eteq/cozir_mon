import time
import busio
import board
import digitalio
import rtc_time

# constants according to http://www.co2meters.com/Documentation/Manuals/Manual-GSS-Sensors.pdf
MEASUREMENT_PERIOD_SECS = .02
FILTER_TO_WARM_UP_SECS = {1:1.2, 2:3, 4:5, 8:9, 16:16, 32:32}

# hardware setup
NEOPIXEL_PIN = board.D11


def setup_leds():
    leds = []
    for ledpin in (board.RED_LED, board.GREEN_LED):
        led = digitalio.DigitalInOut(ledpin)
        led.direction = digitalio.Direction.OUTPUT
        led.value = False
        leds.append(led)
    return tuple(leds)
rled, gled = setup_leds()


def blink_led(led, timesec, n=1):
    for i in range(n):
        if i > 0:
            time.sleep(timesec)
        led.value = True
        time.sleep(timesec)
        led.value = False


def setup_neopixels():
    import neopixel
    return neopixel.NeoPixel(NEOPIXEL_PIN, 1)


def setup_sd(mountpoint='/sd'):
    import adafruit_sdcard
    import storage
    try:
        spi = busio.SPI(board.SCK, board.MOSI, board.MISO)
        cs = digitalio.DigitalInOut(board.SD_CS)
        sdcard = adafruit_sdcard.SDCard(spi, cs)
        vfs = storage.VfsFat(sdcard)
        storage.mount(vfs, mountpoint)
        print('Found SD card.')
        blink_led(gled, .075, 5)
        return sdcard, vfs
    except Exception as e:
        print('Failed to set up and mount SD card! Exception info:', str(e), '\nPrinting to console instead.')
        blink_led(rled, .075, 5)
        return None, None


def setup_sgp30(i2c):
    try:
        import adafruit_sgp30
        # set up the SGP30
        sgp30 = adafruit_sgp30.Adafruit_SGP30(i2c)
        print("SGP30 found - serial #", [hex(i) for i in sgp30.serial])
        test_measurements = sgp30.eCO2, sgp30.TVOC
        return sgp30
    except Exception as e:
        print('adafruit_sgp30 not present or failed to init:' + str(e))
        return None


def setup_bme280(i2c):
    try:
        import adafruit_bme280
        bme280 = adafruit_bme280.Adafruit_BME280_I2C(i2c)
        test_measurements = bme280.temperature, bme280.humidity, bme280.pressure
        return bme280
    except Exception as e:
        print('adafruit_bme280 not present or failed to init:' + str(e))
        return None

def setup_cozir(digital_filter_value=32):
    uart = busio.UART(board.TX, board.RX, baudrate=9600, receiver_buffer_size=64)
    uart.write(b'K 0\r\n')
    uart.write(bytearray('A {}\r\n'.format(int(digital_filter_value))))
    time.sleep(.1)
    uart.reset_input_buffer()

    # check that issuing a command acknowledges correctly to make sure
    # communication makes sense
    uart.write(b'K 0\r\n')
    if b'K 00000' not in uart.read(10):
        for _ in range(25):
            blink_led(rled, .025, 1)
            blink_led(gled, .025, 1)
        raise IOError('CozIR not responding normally')

    return uart, FILTER_TO_WARM_UP_SECS[digital_filter_value]


def setup_i2c_attached():
    i2c = busio.I2C(board.SCL, board.SDA, frequency=100000)
    while not i2c.try_lock():
        pass
    try:
        scanres = i2c.scan()
    finally:
        i2c.unlock()

    found = []
    if 0x58 in scanres:
        found.append('sgp30')
    if 0x77 in scanres:
        found.append('bme280')
    if 0x68 in scanres:
        found.append('rtc_ds3231')
    if 0x57 in scanres:
        found.append('nvm_at24c32')

    return i2c, tuple(found)


def ppm_to_rgb(co2_ppm, value=1):
    rf = max(0, (co2_ppm - 1500)/500)
    gf = max(0, (1500-co2_ppm)/1500)
    if co2_ppm < 1200:
        bf = co2_ppm/1200
    else:
        bf = max(0, (1600-co2_ppm)/400)
    return int(255*value*rf), int(255*value*gf), int(255*value*bf)


def main_loop(loop_time_sec=60, npx_brightness=.25):
    npx = setup_neopixels()
    i2c, found = setup_i2c_attached()
    sdcard, vfs = setup_sd('/sd')
    #sgp30 = setup_sgp30(i2c) if 'sgp30' in found else None
    #bme280 = setup_bme280(i2c) if 'bme280' in found else None
    cozir_uart, cozir_warmup_time = setup_cozir(8)

    if 'rtc_ds3231' in found:
        get_timestamp = lambda:rtc_time.get_time_bytearray(i2c)
    else:
        get_timestamp = lambda:bytearray(repr(time.monotonic()))
    del found

    if sdcard is None:
        fw = None
        log_row = lambda x:None
    else:
        fw = open('/sd/co2.log', 'ab')
        def log_row(bytearrs):
            first = True
            for b in bytearrs:
                if first:
                    first = False
                else:
                    fw.write(b' ')
                fw.write(b)
            fw.write(b'\n')
            fw.flush()
    try:
        while True:
            st = time.monotonic()

            print('Starting CO2 read cycle')
            cozir_uart.write(b'K 2\r\n')
            time.sleep(cozir_warmup_time)
            cozir_uart.reset_input_buffer()
            cozir_uart.write(b'Q\r\n')
            dt = get_timestamp()
            bs = cozir_uart.read(34)
            if bs is None:
                print('No response from Cozir! not sampling CO2 data this run')
            else:
                log_row([dt, bytearray('cozirA_humidity'), bs[4:7] + b'.' + bs[7:8]])
                log_row([dt, bytearray('cozirA_temperature'), bs[13:15] + b'.' + bs[15:16]])
                log_row([dt, bytearray('cozirA_filtered'), bs[19:24]])
                log_row([dt, bytearray('cozirA_raw'), bs[27:32]])
                co2_ppm = int(bs[19:24])  # filtered
                print('CO2:', co2_ppm, 'ppm')
                npx.fill(ppm_to_rgb(co2_ppm, npx_brightness))

            dt = time.monotonic() - st
            if dt < loop_time_sec:
                time.sleep(loop_time_sec - dt)

    finally:
        if fw is not None:
            fw.close()
