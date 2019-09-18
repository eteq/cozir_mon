
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
