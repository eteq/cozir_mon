
def setup(port):
    with open(port, 'rwb') as f:
        f.flush()
        f.write(b'K 2\r\n')
        f.flush()

def get_single_measurement(port):
    with open(port, 'rwb') as f:
        f.flush()
        f.write(b'Q\r\n')
        return f.read()

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('output_file')
    parser.add_argument('--port', '-p', default='/dev/serial0')

    args = parser.parse_args()
    setup(args.port)