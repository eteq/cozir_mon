"""
This script is to be run on the *host* to send the time the host thinks it is
to the RTC on the feather. Note that rtc_time.py must be present on the feather
for this to work.

Requires pyserial
"""
import time
import serial
from datetime import datetime, timedelta

CTRLC = chr(3).encode()
CTRLD = chr(4).encode()

def get_repl(ser, wait_for_reset_sec=.5):
    ot = ser.timeout
    try:
        ser.timeout = wait_for_reset_sec
        ser.write(CTRLD)  # first get out of repl if already in it
        time.sleep(wait_for_reset_sec)
        ser.write(CTRLC)  # now reset to repl mode
        time.sleep(wait_for_reset_sec)
        ser.reset_input_buffer()
        ser.write(CTRLC)
        time.sleep(wait_for_reset_sec)
        prompt = ser.read(1024)
    finally:
        ser.timeout = ot

    if not prompt.endswith(b'>>> '):
        raise IOError(f'REPL did not reset properly!  Got "{prompt}" instead')

    return prompt

def run_code(ser, codestr):
    outs = []
    for i, line in enumerate(codestr.split('\n')):
        towrite = line.encode() + b'\r\n'

        ser.reset_input_buffer()
        nwritten = ser.write(towrite)
        echo = ser.read(nwritten)
        assert echo == towrite, f'"{echo}"!="{towrite}"'

        out = b''
        while not out.endswith(b'>>> '):
            out += ser.read(1024)
            if b'Traceback (most recent call last):\r\n' in out:
                raise ValueError(f'Got traceback!:\n{out}')
            if out.rstrip().endswith(b'...'):
                raise ValueError(f'Got stuck in a "...":\n{out}')
        outs.append(out[:-4])
    return outs

def set_time_from_datetime(ser, dt):
    set_time_dct = {'yr':dt.year, 'mon':dt.month, 'date':dt.day,
                    'day': dt.weekday()+1,
                    'hr':dt.hour, 'min':dt.minute, 'sec':dt.second}

    run_code(ser, 'import rtc_time, board, busio\n'
                  'i2c=busio.I2C(board.SCL, board.SDA)\n'
                  #'i2c.try_lock()\n'
                  'rtc_time.setup_rtc(i2c)\n')
    set_time_args = ','.join([nm+'='+str(v) for nm, v in set_time_dct.items()])
    run_code(ser, f'rtc_time.set_time(i2c, {set_time_args})\n')
    time.sleep(1)
    results = run_code(ser, 'bytes(rtc_time.get_time_bytearray(i2c))\ni2c.deinit()\n')
    return results[0].decode()



if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--baudrate', '-b', default=115200)
    parser.add_argument('--waittime', '-w', default=0.5)
    parser.add_argument('--tzoffset', '-z', default=0.0)
    parser.add_argument('--offset-secs', '-o', default=0.0)
    parser.add_argument('serialport')

    args = parser.parse_args()

    with serial.Serial(args.serialport, args.baudrate,
                       timeout=args.waittime) as ser:

        get_repl(ser, args.waittime)
        dt = timedelta(seconds=args.offset_secs, hours=args.tzoffset)
        res = set_time_from_datetime(ser, datetime.now() + dt)
        print("Result from setting time:", res)
