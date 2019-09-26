import struct

def get_calibs(i2cdev):
    tp_bytes = bytearray(24)
    with i2cdev:
        i2cdev.write_then_readinto(bytearray([0x88]), tp_bytes)
    tp_coeffs = struct.unpack('<HhhHhhhhhhhh', tp_bytes)
    # t_calib = [float(c) for c in tp_coeffs[:3]]
    # p_calib = [float(c) for c in tp_coeffs[3:]]

    # # reuse the allocated array
    # with i2cdev:
    #     i2cdev.write_then_readinto(bytearray([0xa1]), tp_bytes, in_start=0, in_end=1)
    #     i2cdev.write_then_readinto(bytearray([0xe1]), tp_bytes, in_start=1, in_end=8)

    # h_coeffs = struct.unpack('<BhBbBbb', tp_bytes[:8])
    # h_calib = [None]*6
    # h_calib[0] = float(h_coeffs[0])
    # h_calib[1] = float(h_coeffs[0])
    # h_calib[2] = float(h_coeffs[1])
    # h_calib[3] = float((h_coeffs[2] << 4) |  (h_coeffs[3] & 0xF))
    # h_calib[4] = float((h_coeffs[4] << 4) | (h_coeffs[3] >> 4))
    # h_calib[5] = float(h_coeffs[5])

    # return tuple(t_calib), tuple(p_calib), tuple(h_calib)

def data_registers_to_raw(data_regs):
    pres_val = data_regs[2] >> 4
    pres_val +=  data_regs[1] << 4
    pres_val +=  data_regs[0] << 12

    temp_val = data_regs[5] >> 4
    temp_val +=  data_regs[4] << 4
    temp_val +=  data_regs[3] << 12

    hum_val = data_regs[7] + (data_regs[6] << 8)

    return temp_val, pres_val, hum_val

def raw_to_t_fine(rawtemp, calib_vals):
    """
    Used in all the other calibration formulae
    """
    if rawtemp < 0:
        return rawtemp

    temp_calib = calib_vals[0]

    var1 = (rawtemp / 16384.0 - temp_calib[0] / 1024.0) * temp_calib[1]
    var2 = ((rawtemp / 131072.0 - temp_calib[0] / 8192.0) * (
        rawtemp / 131072.0 - temp_calib[0] / 8192.0)) * temp_calib[2]

    return int(var1 + var2)

def raw_to_calibrated_temp(rawtemp, calib_vals):
    """
    If rawtemp is negative, it's interpreted as -t_fine
    """
    t_fine = raw_to_t_fine(rawtemp, calib_vals)
    deg_C = ((t_fine * 5 + 128) >> 8)/100.
    return deg_C

def raw_to_calibrated_pressure(rawpress, rawtemp, calib_vals):
    """
    If rawtemp is negative, it's interpreted as -t_fine
    """
    t_fine = raw_to_t_fine(rawtemp, calib_vals)
    pressure_calib = calib_vals[1]

    var1 = float(t_fine) / 2.0 - 64000.0
    var2 = var1 * var1 * pressure_calib[5] / 32768.0
    var2 = var2 + var1 * pressure_calib[4] * 2.0
    var2 = var2 / 4.0 + pressure_calib[3] * 65536.0
    var3 = pressure_calib[2] * var1 * var1 / 524288.0
    var1 = (var3 + pressure_calib[1] * var1) / 524288.0
    var1 = (1.0 + var1 / 32768.0) * pressure_calib[0]

    pressure = 1048576.0 - rawpress
    pressure = ((pressure - var2 / 4096.0) * 6250.0) / var1
    var1 = pressure_calib[8] * pressure * pressure / 2147483648.0
    var2 = pressure * pressure_calib[7] / 32768.0
    pressure = pressure + (var1 + var2 + pressure_calib[6]) / 16.0

    return pressure / 100

def raw_to_calibrated_humidity(rawhum, rawtemp, calib_vals):
    """
    If rawtemp is negative, it's interpreted as -t_fine
    """
    t_fine = raw_to_t_fine(rawtemp, calib_vals)
    humidity_calib = calib_vals[2]

    var1 = float(self._t_fine) - 76800.0
    var2 = (humidity_calib[3] * 64.0 + (humidity_calib[4] / 16384.0) * var1)
    var3 = rawhum - var2
    var4 = humidity_calib[1] / 65536.0
    var5 = (1.0 + (humidity_calib[2] / 67108864.0) * var1)
    var6 = 1.0 + (humidity_calib[5] / 67108864.0) * var1 * var5
    var6 = var3 * var4 * (var5 * var6)
    return var6 * (1.0 - humidity_calib[0] * var6 / 524288.0)
