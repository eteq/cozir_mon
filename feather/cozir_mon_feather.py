import sys
import time
import busio
import board
import digitalio
import rtc_time
import battery_check_feather

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
    from adafruit_bus_device.i2c_device import I2CDevice

    dev = I2CDevice(i2c, 0x58)
    with dev:
        dev.write(bytearray([0x20, 0x03]))
    return dev


def setup_bme280(i2c):
    from adafruit_bus_device.i2c_device import I2CDevice

    dev = I2CDevice(i2c, 0x77)
    with dev:
        # soft reset
        dev.write(bytearray([0xE0, 0xB6]))
        time.sleep(.002) #2ms startup time
        # configure registers for weather-sensing-ish mode
        dev.write(bytearray([0xF2, 0b1]))
        dev.write(bytearray([0xF4, 0b100100]))
        dev.write(bytearray([0xF5, 0]))

    return dev


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


def main_loop(loop_time_sec=60, npx_brightness=.5, cozir_filter=8,
              log_battery=True):
    npx = setup_neopixels()
    i2c, found = setup_i2c_attached()
    sdcard, vfs = setup_sd('/sd')
    sgp30 = setup_sgp30(i2c) if 'sgp30' in found else None
    bme280 = setup_bme280(i2c) if 'bme280' in found else None
    cozir_uart, cozir_warmup_time = setup_cozir(cozir_filter)

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

    if bme280 is not None:
        import bme280_calib

        dt = get_timestamp()
        with bme280:
            tcalibs, pcalibs, hcalibs = bme280_calib.get_calibs(bme280)
        print('Saving bme280 calib info')
        for i, tc in enumerate(tcalibs):
            log_row([dt, bytearray('bme280_calib_t_' + str(i)), bytearray(repr(int(tc)))])
        for i, pc in enumerate(pcalibs):
            log_row([dt, bytearray('bme280_calib_p_' + str(i)), bytearray(repr(int(pc)))])
        for i, hc in enumerate(hcalibs):
            log_row([dt, bytearray('bme280_calib_h_' + str(i)), bytearray(repr(int(hc)))])
        del tcalibs, pcalibs, hcalibs

        del bme280_calib
        del sys.modules['bme280_calib']

    try:
        while True:
            st = time.monotonic()

            npx.fill((0, 0, 0))
            co2_ppm = None

            print('Starting CO2 read cycle')
            cozir_uart.write(b'K 2\r\n')
            time.sleep(cozir_warmup_time)
            cozir_uart.reset_input_buffer()
            cozir_uart.write(b'Q\r\n')
            dt = get_timestamp()
            bs = cozir_uart.read(34)
            cozir_uart.write(b'K 0\r\n')  # switch to sleep/no-sampling mode
            if bs is None:
                print('No response from Cozir! not sampling CO2 data this run')
            else:
                log_row([dt, bytearray('cozirA_humidity'), bs[4:7] + b'.' + bs[7:8]])
                log_row([dt, bytearray('cozirA_temperature'), bs[13:15] + b'.' + bs[15:16]])
                log_row([dt, bytearray('cozirA_filtered'), bs[19:24]])
                log_row([dt, bytearray('cozirA_raw'), bs[27:32]])
                co2_ppm = int(bs[19:24])  # filtered
                print('CO2:', co2_ppm, 'ppm')

            if bme280 is not None:
                with bme280:
                    setup_bytes = bytearray(1)
                    bme280.write_then_readinto(bytearray([0xf4]), setup_bytes)
                    bme280.write(bytearray([0xf4, (setup_bytes[0] & 0b11111100) | 0b1]))

                    # make sure measurement/setup completes
                    setup_bytes[0] = 1
                    while (setup_bytes[0] & 0b1001) != 0:
                        bme280.write_then_readinto(bytearray([0xf3]), setup_bytes)

                    tph_bytes = bytearray(8)
                    bme280.write_then_readinto(bytearray([0xf7]), tph_bytes)
                praw = (tph_bytes[2] >> 4) | (tph_bytes[1] << 4) | (tph_bytes[0]<< 12)
                traw = (tph_bytes[5] >> 4) | (tph_bytes[4] << 4) | (tph_bytes[3]<< 12)
                hraw = (tph_bytes[7]) | (tph_bytes[6] << 8)
                log_row([dt, bytearray('bme280_temp_raw'), bytearray(repr(traw))])
                log_row([dt, bytearray('bme280_pressure_raw'), bytearray(repr(praw))])
                log_row([dt, bytearray('bme280_humidity_raw'), bytearray(repr(hraw))])

                del praw, traw, hraw, tph_bytes, setup_bytes


            if sgp30 is not None:
                b = bytearray(5)
                with sgp30:
                    sgp30.write(bytes([0x20, 0x08]), stop=False)
                    time.sleep(.05)
                    sgp30.readinto(b)
                    #sgp30.write_then_readinto(bytearray([0x20, 0x08]), b)

                dt = get_timestamp()
                eco2 = (b[0] << 8) + b[1]
                # no CRC check
                tvoc = (b[3] << 8) + b[4]
                print('SGP30 eCO2:', eco2, 'TVOC:', tvoc)
                log_row([dt, bytearray('sgp30_eco2'), bytearray(repr(eco2))])
                log_row([dt, bytearray('sgp30_tvoc'), bytearray(repr(tvoc))])

            if log_battery:
                bvolt = battery_check_feather.get_battery_voltage()
                dt = get_timestamp()
                log_row([dt, bytearray('battery_voltage'), bytearray(repr(bvolt))])
                print('battery_voltage:', bvolt, 'V')

            if co2_ppm is not None:
                from ppm_to_rgb import ppm_to_rgb
                npx.fill(ppm_to_rgb(co2_ppm, npx_brightness))

            dt = time.monotonic() - st
            if dt < loop_time_sec:
                time.sleep(loop_time_sec - dt)

    finally:
        if fw is not None:
            fw.close()
