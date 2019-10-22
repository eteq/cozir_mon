import re
import sys
from collections import defaultdict

import numpy as np
from matplotlib import pyplot as plt

from astropy import table, time

import atmosphere_conversions


def parse_cozir_file(file, start_time=None, end_time=None):
    if hasattr(file, 'read'):
        t = table.Table.read(file.read(), format='ascii')
    else:  # assume name
        t = table.Table.read(file, format='ascii')

    t.rename_columns(['col1', 'col2', 'col3'],
                     ['timestamp', 'measurement_type', 'value'])

    t['timestamp'] = time.Time(t['timestamp'])

    if start_time is not None:
        if not isinstance(start_time, time.Time):
            start_time = time.Time(start_time)
        t = t[t['timestamp']>=start_time]
    if end_time is not None:
        if not isinstance(end_time, time.Time):
            end_time = time.Time(end_time)
        t = t[t['timestamp']<=end_time]

    return t


def plot_cozir_data(tab, outfilename=None, width=10, heightperplot=5,
                    include_types=None, exclude_types=None,
                    humidity_unit='rel', temp_unit='c'):
    if include_types is not None and exclude_types is not None:
        raise ValueError('at least one of include_types and exclude_types must '
                         'be None')

    try:
        bmecalib = BME280_calibrator.coeffs_from_table(tab)
    except ValueError:
        bmecalib = None
    if bmecalib is not None:
        # assume both raw measurements *and* calibs are present if cals are ok.
        calib_tabs = {}
        for nm in ['temp', 'pressure', 'humidity']:
            calib_tabs[nm] = nmtab = tab[tab['measurement_type'] == f'bme280_{nm}_raw']
            nmcalib = getattr(bmecalib, 'calibrate_' + nm)(nmtab['value'])
            nmtab['value'][:] = nmcalib
            nmtab['measurement_type'][:] = 'bme280_' + nm

        # now identify the raw/calib rows and remove them
        skipmsk = np.ones(len(tab), dtype=bool)
        for mtype in np.unique(tab['measurement_type']):
            if mtype.startswith('bme280_calib'):
                skipmsk &= tab['measurement_type']!=mtype
            elif mtype.startswith('bme280_') and mtype.endswith('_raw'):
                skipmsk &= tab['measurement_type']!=mtype

        # now drop the raws and add back in the calibrated measurements
        tab = table.vstack([tab[skipmsk], calib_tabs['temp'],
                                          calib_tabs['pressure'],
                                          calib_tabs['humidity']])

    # group the table into individual measurements, and then put the individual
    # time series into sets based on the physical type of the measurement
    grped_tab = tab.group_by('measurement_type')

    # map of "known" measurement names to their type for grouping
    plot_types = {'cozirA_filtered': 'co2',
                  'cozirA_raw': 'co2',
                  'sgp30_eco2': 'co2',
                  'bme280_temp': 'temperature',
                  'cozirA_temperature': 'temperature',
                  'bme280_pressure': 'pressure',
                  'bme280_humidity': 'humidity',
                  'cozirA_humidity': 'humidity'}

    plot_groups = defaultdict(list)  # keys are plot types, values are lists of (x, y, name) tuples
    for grp in grped_tab.groups:
        type_name = grp['measurement_type'][0]
        if include_types is not None and type_name not in include_types:
            continue
        if exclude_types is not None and type_name in exclude_types:
            continue

        plot_type = plot_types.get(type_name, type_name)
        plot_groups[plot_type].append((grp['timestamp'].plot_date, grp['value'], type_name))

    ccycle = iter(plt.rcParams['axes.prop_cycle'].by_key()['color'])
    height = len(plot_groups) * heightperplot
    fig, axs = plt.subplots(len(plot_groups), 1, figsize=(width, height))

    # define some transformations for particular plot types:
    y_transforms = defaultdict(lambda: lambda x: x)
    y_transforms['pressure'] = lambda x: x/101325.  # Pa->atm

    if temp_unit == 'c':
        pass
    elif temp_unit == 'f':
        y_transforms['temperature'] = atmosphere_conversions.c_to_f
    else:
        raise ValueError(f'invalid temperature unit {temp_unit}')

    if humidity_unit == 'dewpoint':
        t = plot_groups['temperature'][0][1]
        def dptrans(rh):
            return atmosphere_conversions.hum_rel_to_dewpoint(rh/100, t)
        y_transforms['humidity'] = lambda x: y_transforms['temperature'](dptrans(x))
    elif humidity_unit == 'abs':
        t = plot_groups['temperature'][0][1]
        def abshumtrans(rh):
            return atmosphere_conversions.hum_rel_to_abs(rh/100, t)
        y_transforms['humidity'] = abshumtrans
    elif humidity_unit == 'rel':
        pass
    else:
        raise ValueError(f'invalid humidity unit {humidity_unit}')

    for grpname, grpvals, ax in zip(plot_groups.keys(), plot_groups.values(), axs.ravel()):
        for val in grpvals:
            ax.plot_date(val[0], y_transforms[grpname](val[1]), color=next(ccycle), label=val[2], fmt='-')
        ax.set_xlabel('date')
        ax.set_ylabel(grpname)
        ax.legend()
        for l in ax.xaxis.get_majorticklabels():
            l.set_rotation(45)

        if grpname == 'pressure':
            yl, yu = ax.get_ylim()
            ax2 = ax.twinx()
            ax2.set_ylim(yl*101.325, yu*101.325)
            ax2.set_ylabel('[kPa]')
            ax.set_ylabel('pressure [atm]')
        elif grpname == 'co2':
            ax.set_ylabel('CO2 concentration [ppm]')
        elif grpname == 'temperature':
            if temp_unit == 'f':
                ax.set_ylabel('temperature [deg F]')
            else:
                ax.set_ylabel('temperature [deg C]')
        elif grpname == 'humidity':
            if humidity_unit == 'rel':
                ax.set_ylabel('Relative Humidity [%]')
            elif humidity_unit == 'abs':
                ax.set_ylabel(r'Absolute Humidity [$g\;m^{-3}$]')
            elif humidity_unit == 'dewpoint':
                ax.set_ylabel(f'Dew Point [deg {temp_unit}]')

    fig.tight_layout()

    if outfilename is not None:
        plt.savefig(outfilename)


class BME280_calibrator:
    """
    Note that temp *must* be calculated before pressure/humidity to set the t_fine
    correctly
    """
    def __init__(self, t_calib, p_calib, h_calib):
        self.t_calib = t_calib
        self.p_calib = p_calib
        self.h_calib = h_calib
        self.t_fine = None

    @classmethod
    def coeffs_from_table(cls, tab, which=-1):
        calib_meas_names = [(t, t[-3], int(t[-1])) for t in
                            np.unique(tab['measurement_type']) if
                            t.startswith('bme280_calib')]

        calib_coeffs = []
        for calib_type in ['t', 'p', 'h']:
            calib_num_to_name = {i: nm for nm,t,i in calib_meas_names if
                                           t == calib_type}
            calib_meas_name = [calib_num_to_name[k] for k in sorted(calib_num_to_name.keys())]
            calib_coeffs.append([tab[tab['measurement_type']==n][which]['value'] for n in calib_meas_name])

        if len(calib_coeffs[0]) < 3:
            raise ValueError('could not find all temp calib coeffs')
        if len(calib_coeffs[1]) < 9:
            raise ValueError('could not find all pressure calib coeffs')
        if len(calib_coeffs[2]) < 6:
            raise ValueError('could not find all humidity calib coeffs')

        return cls(*calib_coeffs)


    def _set_t_fine(self, traw):
        var1 = (traw/16384.0 - (self.t_calib[0])/1024.0) * (self.t_calib[1])
        var2 = ((traw/131072.0 - (self.t_calib[0])/8192.0) * (traw/131072.0 - (self.t_calib[0])/8192.0)) * (self.t_calib[2])
        self.t_fine = var1 + var2

    def calibrate_temp(self, traw):
        """
        Returns temperature in deg C
        """
        self._set_t_fine(traw)
        return np.clip(self.t_fine / 5120.0, -273.15, None)

    def calibrate_pressure(self, praw):
        """
        Returns pressure in Pa
        """
        var1 = self.t_fine/2.0 - 64000.0
        var2 = var1 * var1 * self.p_calib[5] / 32768.0
        var2 = var2 + var1 * self.p_calib[4] * 2.0
        var2 = (var2/4.0)+(self.p_calib[3] * 65536.0)
        var1 = (self.p_calib[2] * var1 * var1 / 524288.0 + self.p_calib[1] * var1) / 524288.0
        var1 = (1.0 + var1 / 32768.0)*self.p_calib[0]

        p = 1048576.0 - praw
        p = (p - (var2 / 4096.0)) * 6250.0 / var1
        var1 = (self.p_calib[8]) * p * p / 2147483648.0
        var2 = p * (self.p_calib[7]) / 32768.0
        p = p + (var1 + var2 + (self.p_calib[6])) / 16.0
        return np.clip(p, 0, None)

    def calibrate_humidity(self, hraw):
        """
        Returns humidity in RH (%)
        """
        var_H = self.t_fine - 76800.0
        var_H = (hraw - (self.h_calib[3] * 64.0 + self.h_calib[4] / 16384.0 * var_H)) * (self.h_calib[1] / 65536.0 * (1.0 + self.h_calib[5] / 67108864.0 * var_H * (1.0 + self.h_calib[2] / 67108864.0 * var_H)))
        var_H = var_H * (1.0 - self.h_calib[0] * var_H / 524288.0)

        return np.clip(var_H, 0, 100)

    def calibrate_table(self, tab, measurement_types={'temp(C)': 'bme280_temp_raw',
                                                      'pressure(Pa)': 'bme280_pressure_raw',
                                                      'humidity(%)': 'bme280_humidity_raw'}):
        calibed = {}
        # temp must go first...
        measurement_keys = list(measurement_types.keys())
        measurement_keys.remove('temp(C)')
        measurement_keys.insert(0, 'temp(C)')

        for nm in measurement_keys:
            mtype = measurement_types[nm]

            rawvals = tab[tab['measurement_type'] == mtype]['value']
            if nm == 'temp(C)':
                calibvals = self.calibrate_temp(rawvals)
            elif nm == 'pressure(Pa)':
                calibvals = self.calibrate_pressure(rawvals)
            elif nm == 'humidity(%)':
                calibvals = self.calibrate_humidity(rawvals)
            else:
                raise ValueError(f'unrecognized measurement result {nm}')

            calibed[nm] = calibvals

        return calibed


if __name__ == '__main__':
    import sys
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('input_file', help='file to parse and plot or "-" for stdin')
    parser.add_argument('output_name', nargs='?', help='filename to save the plot to', default=None)
    parser.add_argument('--start-time', default=None, help='A timestamp for the earliest data point to use.')
    parser.add_argument('--end-time', default=None, help='A timestamp for the latest data point to use.')
    parser.add_argument('--include', default=None, help='A comma-separated list of measurement types to include')
    parser.add_argument('--exclude', default=None, help='A comma-separated list of measurement types to exclude')
    parser.add_argument('-d', '--dewpoint', action='store_true', help='Show the dewpoint instead of relative humidity')
    parser.add_argument('-a', '--absolute-humidity', action='store_true', help='Show the absolute instead of relative humidity')
    parser.add_argument('-f', '--farenheit', action='store_true', help='Set temperature unit to farenheit')

    args = parser.parse_args()

    parsekwargs = dict(start_time=args.start_time, end_time=args.end_time)
    if args.input_file == '-':
        data_table = parse_cozir_file(sys.stdin, **parsekwargs)
    else:
        data_table = parse_cozir_file(args.input_file, **parsekwargs)

    if args.include is not None and args.exclude is not None:
        print('Cannot both include and exclude!')
        sys.exit(1)

    humidity_unit = 'rel'
    if args.dewpoint and args.absolute_humidity:
        print('Cannot do both dewpoint and absolute humidity')
        sys.exit(1)
    elif args.dewpoint:
        humidity_unit = 'dewpoint'
    elif args.absolute_humidity:
        humidity_unit = 'abs'


    plot_cozir_data(data_table, outfilename=args.output_name,
                    temp_unit='f' if args.farenheit else 'c',
                    humidity_unit=humidity_unit,
                    include_types=None if args.include is None else args.include.split(','),
                    exclude_types=None if args.exclude is None else args.exclude.split(','))
