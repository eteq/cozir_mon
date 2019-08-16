from time import sleep
import serial
from datetime import datetime

def setup_connection(port):
    ser = serial.Serial(port, timeout=1)
    ser.write(b'K 2\r\n')
    ser.flush()
    ser.close()

    return serial.Serial(port, timeout=1)

def get_single_measurement(ser, n_samples=1):
    lines = []
    for _ in range(n_samples):
        ser.write(b'Q\r\n')
        lines.append(ser.read(200))

    return b''.join(lines)


def do_measurement_loop(ser, fn, delay, n_samples):
    with open(fn, 'w') as f:
        while True:
            f.write(str(datetime.now()))
            meas = get_single_measurement(ser, n_samples)
            f.write(meas)
            f.write(str(datetime.now()))

            f.flush()

            sleep(delay)

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--output-file', '-o', default=None)
    parser.add_argument('--port', '-p', default='/dev/serial0')
    parser.add_argument('--delay', '-d', default=60)
    parser.add_argument('--number-samples', '-n', default=5)

    args = parser.parse_args()


    ser = setup_connection(args.port)
    try:
        if args.output_file is None:
            print(get_single_measurement(ser))
        else:
            do_measurement_loop(ser, args.output_file, args.delay, args.number_samples)
    finally:
        ser.close()