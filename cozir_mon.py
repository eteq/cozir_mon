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
        ser.flush()
        lines.append(ser.read(200))

    return b''.join(lines)


def do_measurement_loop(ser, fn, delay, n_samples, verbose=False, append=False):
    with open(fn, 'a' if append else 'w') as f:
        while True:
            if verbose:
                print('Measuring...')
            f.write('dt:' + str(datetime.now()) + '\n')
            meas = get_single_measurement(ser, n_samples)
            f.write(meas.decode())
            f.write('dt:')
            f.write('dt:' + str(datetime.now()) + '\n')

            f.flush()

            sleep(delay)

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--output-file', '-o', default=None)
    parser.add_argument('--port', '-p', default='/dev/serial0')
    parser.add_argument('--delay', '-d', default=60)
    parser.add_argument('--number-samples', '-n', default=5)
    parser.add_argument('--verbose', '-v', action='store_true')
    parser.add_argument('--append-file', '-a', action='store_true')

    args = parser.parse_args()


    ser = setup_connection(args.port)
    try:
        if args.verbose:
            print("First measurement")
        print(get_single_measurement(ser))
        if args.output_file is not None:
            if args.verbose:
                print("Looping")
            do_measurement_loop(ser, args.output_file, args.delay, args.number_samples, append=args.append_file, verbose=args.verbose)
    finally:
        ser.close()