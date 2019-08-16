import serial

def setup_connection(port):
    ser = serial.Serial(port, timeout=1)
    ser.write(b'K 2\r\n')
    ser.flush()
    ser.close()

    return serial.Serial(port, timeout=1)

def get_single_measurement(ser):
    ser.write(b'Q\r\n')
    return ser.read(200)

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('output_file')
    parser.add_argument('--port', '-p', default='/dev/serial0')

    args = parser.parse_args()

    ser = setup_connection(args.port)
    print(get_single_measurement(ser))
    ser.close()