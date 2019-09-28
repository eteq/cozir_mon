
import numpy as np
from matplotlib import pyplot as plt

from astropy import table, time


def parse_cozir_file(file):
    if hasattr(file, 'read'):
        t = table.Table.read(file.read(), format='ascii')
    else:  # assume name
        t = table.Table.read(file, format='ascii')

    t.rename_columns(['col1', 'col2', 'col3'],
                     ['timestamp', 'measurement_type', 'value'])

    t['timestamp'] = time.Time(t['timestamp'])

    return t


def plot_cozir_data(tab, outfilename=None, width=10, heightperplot=5):
    grp_tab = tab.group_by('measurement_type')
    ccycle = iter(plt.rcParams['axes.prop_cycle'].by_key()['color'])

    height = len(grp_tab.groups) * heightperplot
    fig, axs = plt.subplots(len(grp_tab.groups), 1, figsize=(width, height))

    for grp, ax in zip(grp_tab.groups, axs.ravel()):
        ax.plot_date(grp['timestamp'].plot_date, grp['value'],
                      fmt='-', color=next(ccycle))
        ax.set_xlabel('date')
        ax.set_ylabel(grp['measurement_type'][0])
        for l in ax.xaxis.get_majorticklabels():
            l.set_rotation(45)

    fig.tight_layout()

    if outfilename is not None:
        plt.savefig(outfilename)

if __name__ == '__main__':
    import sys
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('input_file', help='file to parse and plot or "-" for stdin')
    parser.add_argument('output_name', nargs='?', help='filename to save the plot to', default=None)

    args = parser.parse_args()

    if args.input_file == '-':
        data_table = parse_cozir_file(sys.stdin)
    else:
        data_table = parse_cozir_file(args.input_file)

    plot_cozir_data(data_table, outfilename=args.output_name)


class BME280_calibrator:
    """
    Note that temp *must* be calculated before pressure/humidity to set the t_fine
    correctly
    """
    def __init__(self, calibcoeffs):
        self.t_calib = calibcoeffs[0]
        self.p_calib = calibcoeffs[1]
        self.h_calib = calibcoeffs[2]


        self.t_fine = None


    def _set_t_fine(self, traw):
        var1 = (traw/16384.0 - (self.t_calib[0])/1024.0) * (self.t_calib[1])
        var2 = ((traw/131072.0 - (self.t_calib[0])/8192.0) * (traw/131072.0 - (self.t_calib[0])/8192.0)) * (self.t_calib[2])
        self.t_fine = var1 + var2

    def calib_temp(self, traw):
        """
        Returns temperature in deg C
        """
        self._set_t_fine(traw)
        return np.clip(self.t_fine / 5120.0, -273.15, None)

    def calib_pressure(self, praw):
        """
        Returns pressure in Pa
        """
        var1 = self.t_fine/2.0 - 64000.0
        var2 = var1 * var1 * self.p_calib[5] / 32768.0
        var2 = var2 + var1 * self.p_calib[4] * 2.0
        var2 = (var2/4.0)+(self.p_calib[3] * 65536.0)
        var1 = (self.p_calib[2] * var1 * var1 / 524288.0 + self.p_calib[1] * var1) / 524288.0
        var1 = (1.0 + var1 / 32768.0)*self.p_calib[0]

        p = 1048576.0 - float(praw)
        p = (p - (var2 / 4096.0)) * 6250.0 / var1
        var1 = (self.p_calib[8]) * p * p / 2147483648.0
        var2 = p * (self.p_calib[7]) / 32768.0
        p = p + (var1 + var2 + (self.p_calib[6])) / 16.0
        return np.clip(p, 0, None)

    def calib_humidity(self, hraw):
        """
        Returns humidity in RH (%)
        """
        var_H = self.t_fine - 76800.0
        var_H = (hraw - (self.h_calib[3] * 64.0 + self.h_calib[4] / 16384.0 * var_H)) * (self.h_calib[1] / 65536.0 * (1.0 + self.h_calib[5] / 67108864.0 * var_H * (1.0 + self.h_calib[2] / 67108864.0 * var_H)))
        var_H = var_H * (1.0 - self.h_calib[0] * var_H / 524288.0)

        return np.clip(var_H, 0, 100)