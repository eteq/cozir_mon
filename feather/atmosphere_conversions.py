"""
Functions for doing humidity/dewpoint/etc conversions.
"""

import numpy as np


def hum_rel_to_dewpoint(rh, ts):
    """
    temps in celsius, humidity in float (i.e., *not* percent).
    """
    # https://www.vaisala.com/sites/default/files/documents/Humidity_Conversion_Formulas_B210973EN-F.pdf
    # these constants are good to ~.1% from -20 to +50 C
    A = 6.116441
    m = 7.591386
    Tn = 240.7263  # appropriate for outputs in C

    Pw = saturation_vapor_pressure(ts + 273.15) * rh

    return Tn/(m/np.log10(Pw/A) - 1)


def hum_rel_to_abs(rh, ts):
    """
    temp in celsius, humidity in float (i.e., *not* percent). Returns
    absolute humidity in g/m^3
    """
    # https://www.vaisala.com/sites/default/files/documents/Humidity_Conversion_Formulas_B210973EN-F.pdf
    C = 2.16679  # gK/J
    ts_K = ts + 273.15  # temp formulae are in Kelvin
    return C * saturation_vapor_pressure(ts_K) * rh / ts_K


def saturation_vapor_pressure(ts_K):
    Tc = 647.096  # K
    Pc = 220640  # hPa

    Coeffs = [-7.85951783, 1.84408259, -11.7866497, 22.6807411, -15.9618719, 1.80122502]
    powers = [1, 1.5, 3, 3.5, 4, 7.5]

    v = 1 - ts_K/Tc
    lnrp = Tc / ts_K * np.sum([C*v**p for C,p in zip(Coeffs, powers)], axis=0)
    return Pc * np.exp(lnrp)


def c_to_f(degc):
    return degc * 1.8 + 32
