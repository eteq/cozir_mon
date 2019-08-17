import re
from datetime import datetime

import numpy as np

__all__ = ['parse_vozir_file', 'plot_cozir_data']

def _parse_lines(datalines, startdt, enddt):
    dt = (enddt - startdt)/len(datalines)

    dts = []
    hs = []
    ts = []
    Zs = []
    zs = []
    currdt = startdt + dt/2
    for line in datalines:
        match = re.match(r' H (\d*) T (\d*) Z (\d*) z (\d*)\n', line)
        grps = match.groups()
        dts.append(currdt)
        hs.append(int(grps[0])/10)
        ts.append((int(grps[1])-1000)/10)
        Zs.append(float(grps[2]))
        zs.append(float(grps[3]))

        currdt = currdt + dt
    return dts, hs, ts, Zs, zs


def parse_cozir_file(fn):
    with open(fn, 'r') as f:
        dts, hs, ts, Zs, zs = (list() for _ in range(5))

        startdt = enddt = None
        datalines = []

        for line in f:
            if line.startswith('dt:'):
                if startdt is None:
                    startdt = datetime.strptime(line[3:-1], '%Y-%m-%d %H:%M:%S.%f')
                else:
                    enddt = datetime.strptime(line[3:-1], '%Y-%m-%d %H:%M:%S.%f')
                    dti, hi, ti, Zi, zi = _parse_lines(datalines, startdt, enddt)
                    dts.append(dti)
                    hs.append(hi)
                    ts.append(ti)
                    Zs.append(Zi)
                    zs.append(zi)
                    startdt = enddt = None
                    datalines = []
            else:
                datalines.append(line)

    dts = np.array(np.concatenate(dts), dtype='datetime64')
    hs = np.concatenate(hs)
    ts = np.concatenate(ts)
    Zs = np.concatenate(Zs)
    zs = np.concatenate(zs)

    return {'datetime':dts, 'temperature_c': ts, 'temperature_f': ts *9/5 + 32,
            'humidity': hs, 'co2_ppm_filtered':Zs, 'co2_ppm_raw':zs}

def plot_cozir_data(datadct, outfile=None, figsize=(12, 8), degf=False):
    # import here so that the rest of the module works even if there's no mpl
    from matplotlib import pyplot as plt

    temperature_name = 'temperature_' + ('f' if degf else 'c')

    ccycle = iter(plt.rcParams['axes.prop_cycle'].by_key()['color'])

    fig, axs = plt.subplots(2, 1, figsize=figsize, sharex=True)
    ax1, ax2 = axs
    ax22 = ax2.twinx()

    line1 = ax2.plot(datadct['datetime'], datadct[temperature_name], c=next(ccycle))[0]
    ax2.set_ylabel('temperature [deg {}]'.format ('F' if degf else 'C'), color=line1.get_color())
    line22 = ax22.plot(datadct['datetime'], datadct['humidity'], c=next(ccycle))[0]
    ax22.set_ylabel('humidity [%]', color=line22.get_color())
    # set the side axes color to match the lines
    for line, ax in ((line1, ax2), (line22, ax22)):
        c = line.get_color()
        for li in ax.yaxis.get_majorticklabels():
            li.set_color(c)
        for li in ax.yaxis.get_majorticklines():
            li.set_c(c)

    ax1.plot(datadct['datetime'], datadct['co2_ppm_raw'], c=next(ccycle))
    ax1.plot(datadct['datetime'], datadct['co2_ppm_filtered'], c='k')
    ax1.set_ylabel('co2 concentration [ppm]')

    # these threshold values come from https://dash.harvard.edu/bitstream/handle/1/27662232/4892924.pdf
    ax1.axhline(300, c='g', ls=':', lw=1)
    ax1.axhline(1000, c='y', ls=':', lw=1)
    ax1.axhline(1500, c='orange', ls='-.', lw=1)
    ax1.axhline(2000, c='r', ls='--', lw=1)

    # have the date axes be legible
    for ax in (ax1, ax2):
        for l in ax.xaxis.get_majorticklabels():
            l.set_rotation(45)

    fig.tight_layout()

    if outfile is not None:
        plt.savefig(outfile)

    return fig