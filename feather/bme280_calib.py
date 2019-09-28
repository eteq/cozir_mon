import struct

def get_calibs(i2cdev):
    # requires that the lock already be present!
    tp_bytes = bytearray(24)
    i2cdev.write_then_readinto(bytearray([0x88]), tp_bytes)
    tp_coeffs = struct.unpack('<HhhHhhhhhhhh', tp_bytes)
    t_calib = [float(c) for c in tp_coeffs[:3]]
    p_calib = [float(c) for c in tp_coeffs[3:]]

    # reuse the allocated array
    i2cdev.write_then_readinto(bytearray([0xa1]), tp_bytes, in_start=0, in_end=1)
    i2cdev.write_then_readinto(bytearray([0xe1]), tp_bytes, in_start=1, in_end=8)

    h_coeffs = struct.unpack('<BhBbBbb', tp_bytes[:8])
    h_calib = [None]*6
    h_calib[0] = float(h_coeffs[0])
    h_calib[1] = float(h_coeffs[0])
    h_calib[2] = float(h_coeffs[1])
    h_calib[3] = float((h_coeffs[2] << 4) |  (h_coeffs[3] & 0xF))
    h_calib[4] = float((h_coeffs[4] << 4) | (h_coeffs[3] >> 4))
    h_calib[5] = float(h_coeffs[5])

    return tuple(t_calib), tuple(p_calib), tuple(h_calib)