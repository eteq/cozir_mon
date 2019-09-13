import board
import busio

def from_bcd(b):  # from BCD to binary
    return b - 6 * (b >> 4)


def to_bcd(n):  # from binary to BCD
    return n + 6 * (n // 10)


RTC_ADDR = 0x68  # for DS4323

def rtc_read(i2c, addr, nbytes=1):
    b = bytearray(nbytes)
    while not i2c.try_lock():
        pass
    try:
        i2c.writeto(RTC_ADDR, bytearray([addr]), stop=False)
        i2c.readfrom_into(RTC_ADDR, b)
        return b
    finally:
        i2c.unlock()

def rtc_write(i2c, addr, bytestowrite):
    b = bytearray(len(bytestowrite) + 1)
    b[1:] = bytearray(bytestowrite)
    b[0] = addr
    while not i2c.try_lock():
        pass
    try:
        return i2c.writeto(RTC_ADDR, b)
    finally:
        i2c.unlock()


def setup_i2c():
    return busio.I2C(board.SCL, board.SDA, frequency=100000)


def setup_rtc(i2c):
    status_register = rtc_read(i2c, 0x0f)[0]
    if status_register & 0b10000000:
        print('Status bit set, so RTC may not have kept time well. Resetting.')
    rtc_write(i2c, 0x0f, [0])


def check_time(i2c):
    # assumes 24 hour time is set
    sec, min, hr, day, date, mon, yr = rtc_read(i2c, 0, 7)
    return 'dt:20{:02}-{:02}-{:02} {}:{}:{}.0 day:{}'.format(from_bcd(yr),
           from_bcd(mon&0b11111), from_bcd(date), from_bcd(hr&0b111111),
           from_bcd(min), from_bcd(sec), from_bcd(day))


def set_time(i2c, yr, mon, date, day, hr, min, sec, reset_osf=True):
    """
    day is 1-7 w/ Mon as 1
    """
    yr_bcd = to_bcd(yr % 100) & 0b11111111
    mon_bcd = to_bcd(mon) & 0b11111
    date_bcd = to_bcd(date) & 0b111111
    day_bcd = (day-1) % 7 + 1
    hr_bcd = to_bcd(hr) & 0b111111  # unsetting seventh bit forces to 24-hr time
    min_bcd = to_bcd(min) & 0b1111111
    sec_bcd = to_bcd(sec) & 0b1111111

    to_write = [sec_bcd, min_bcd, hr_bcd, day_bcd, date_bcd, mon_bcd, yr_bcd]
    rtc_write(i2c, 0, to_write)

    if reset_osf:
        status_reg = rtc_read(i2c, 0x0f)[0]
        toset = status_reg & 0b01111111  # reset osf bit to 0
        rtc_write(i2c, 0x0f, bytearray([toset]))
