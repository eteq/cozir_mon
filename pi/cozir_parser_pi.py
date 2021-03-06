#!/usr/bin/env python

import re
from datetime import datetime

import numpy as np

__all__ = ['parse_cozir_file', 'plot_cozir_data']


def _parse_lines(datalines, startdt, enddt):
    dt = (enddt - startdt)/len(datalines)

    dts = []
    hs = []
    ts = []
    Zs = []
    zs = []

    sgpdts = []
    eco2s = []
    tvocs = []
    batvs = []

    currdt = startdt + dt/2
    for line in datalines:
        if line.startswith(' eCO2:'):
            eco2, tvoc = line.split(' ')[1:]
            eco2s.append(int(eco2[5:]))
            tvocs.append(int(tvoc[5:]))
            sgpdts.append(enddt)
        elif line.startswith('battery V:'):
            batvs.append(float(line.split(':')[-1].strip()))
        else:
            match = re.match(r' H (\d*) T (\d*) Z (\d*) z (\d*)\n', line)
            grps = match.groups()
            dts.append(currdt)
            hs.append(int(grps[0])/10)
            ts.append((int(grps[1])-1000)/10)
            Zs.append(float(grps[2]))
            zs.append(float(grps[3]))

        currdt = currdt + dt
    return dts, hs, ts, Zs, zs, sgpdts, eco2s, tvocs, batvs


def parse_cozir_file(forfn):
    if hasattr(forfn, 'read'):
        # file-like
        return _do_parsing(forfn)
    else:
        with open(forfn, 'r') as f:
            return _do_parsing(f)


def parse_time_line(line):
    if line.startswith('dt:'):
        return datetime.strptime(line[3:-1], '%Y-%m-%d %H:%M:%S.%f')
    elif line.startswith('deltat:'):
        return float(line[7:-1])
    else:
        raise ValueError(f'Not a time line: {line}')


def _do_parsing(f):
    dts, hs, ts, Zs, zs, sgpdts, eco2s, tvocs, batvs = (list() for _ in range(9))

    header = True
    startdt = enddt = None
    datalines = []

    for line in f:
        if line.startswith('d'):
            header = False
            if startdt is None:
                startdt = parse_time_line(line)
            else:
                enddt = parse_time_line(line)
                if datalines:  # ocassionally the measuring fails.
                    dti, hi, ti, Zi, zi, sgpdt, eco2, tvoc, batv = _parse_lines(datalines, startdt, enddt)
                    dts.append(dti)
                    hs.append(hi)
                    ts.append(ti)
                    Zs.append(Zi)
                    zs.append(zi)
                    sgpdts.append(sgpdt)
                    eco2s.append(eco2)
                    tvocs.append(tvoc)
                    batvs.append(batv)
                startdt = enddt = None
                datalines = []
        elif not header:
            datalines.append(line)

    if hasattr(dts[0][0], 'date') and hasattr(dts[0][0], 'time'):
        dts = np.array(np.concatenate(dts), dtype='datetime64')
        sgpdts = np.array(np.concatenate(sgpdts), dtype='datetime64')
    else:
        dts = np.array(np.concatenate(dts), dtype=float)
        sgpdts = np.array(np.concatenate(sgpdts), dtype=float)
    hs = np.concatenate(hs)
    ts = np.concatenate(ts)
    Zs = np.concatenate(Zs)
    zs = np.concatenate(zs)
    eco2s = np.concatenate(eco2s)
    tvocs = np.concatenate(tvocs)
    dps = hum_rel_to_dewpoint(hs/100, ts)

    return {'datetime': dts,
            'temperature_c': ts, 'temperature_f': ts * 9/5 + 32,
            'dewpoint_c': dps, 'dewpoint_f': dps * 9/5 + 32,
            'humidity_rel': hs, 'humidity_abs': hum_rel_to_abs(hs, ts),
            'co2_ppm_filtered': Zs, 'co2_ppm_raw': zs, 'battery_voltage':batvs,
            'datetime_single': sgpdts, 'eCO2': eco2s, 'TVOC': tvocs}


def hum_rel_to_dewpoint(rh, ts):
    """
    temps in celsius, humidity in float (i.e., *not* percent).
    """
    # https://www.vaisala.com/sites/default/files/documents/Humidity_Conversion_Formulas_B210973EN-F.pdf
    C = 2.16679  # gK/J

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


def plot_cozir_data(datadct, outfile=None, figsize=(12, 8), degf=False,
                    dewpoint=False, abshum=False, minutes=False, battery=False):
    # import here so that the rest of the module works even if there's no mpl
    from matplotlib import pyplot as plt

    if dewpoint and abshum:
        raise ValueError('cannot ask for both dewpoint and absolute humidity in plot')

    if minutes:
        datadct = datadct.copy()
        datadct['datetime'] = datadct['datetime']/60

    temperature_name = 'temperature_' + ('f' if degf else 'c')

    ccycle = iter(plt.rcParams['axes.prop_cycle'].by_key()['color'])

    fig, axs = plt.subplots(2, 1, figsize=figsize, sharex=True)
    ax1, ax2 = axs
    ax22 = ax2.twinx()

    line2 = ax2.plot(datadct['datetime'], datadct[temperature_name], c=next(ccycle))[0]
    ax2.set_ylabel('temperature [deg {}]'.format('F' if degf else 'C'), color=line2.get_color())
    if dewpoint:
        dp = datadct['dewpoint_' + ('f' if degf else 'c')]
        line22 = ax22.plot(datadct['datetime'], dp, c=next(ccycle))[0]
        ax22.set_ylabel('dewpoint [deg {}]'.format('F' if degf else 'C'), color=line22.get_color())
    else:
        line22 = ax22.plot(datadct['datetime'], datadct['humidity_'+('abs' if abshum else 'rel')], c=next(ccycle))[0]
        ax22.set_ylabel('humidity [{}]'.format('$g/m^3$' if abshum else '%'), color=line22.get_color())

    # set the side axes color to match the lines
    for line, ax in ((line2, ax2), (line22, ax22)):
        c = line.get_color()
        for li in ax.yaxis.get_majorticklabels():
            li.set_color(c)
        for li in ax.yaxis.get_majorticklines():
            li.set_c(c)
    # match the y-axes if using dewpoints
    if dewpoint:
        l2, u2 = ax2.get_ylim()
        l22, u22 = ax22.get_ylim()
        l, u = min(l2, l22), max(u2, u22)
        for ax in ax2, ax22:
            ax.set_ylim(l, u)

    ax1.plot(datadct['datetime'], datadct['co2_ppm_raw'], c=next(ccycle))
    ax1.plot(datadct['datetime'], datadct['co2_ppm_filtered'], c='k')
    if len(datadct['datetime_single']) > 0:
        line1 = ax1.plot(datadct['datetime_single'], datadct['eCO2'], c='k', ls='--')[0]
        ax12 = ax1.twinx()
        line12 = ax12.plot(datadct['datetime_single'], datadct['TVOC'], c=next(ccycle))[0]
        ax12.set_ylabel('TVOCs [ppm]', color=line12.get_color())
        # set the right axes color to match the lines
        for line, ax in ((line12, ax12),):
            c = line.get_color()
            for li in ax.yaxis.get_majorticklabels():
                li.set_color(c)
            for li in ax.yaxis.get_majorticklines():
                li.set_c(c)
    ax1.set_ylabel('co2 concentration [ppm]')

    # these threshold values come from https://dash.harvard.edu/bitstream/handle/1/27662232/4892924.pdf
    ax1.axhline(300, c='g', ls=':', lw=1)
    ax1.axhline(1000, c='y', ls=':', lw=1)
    ax1.axhline(1500, c='orange', ls='-.', lw=1)
    ax1.axhline(2000, c='r', ls='--', lw=1)

    if battery:
        ax2.cla()
        ax22.cla()
        ax2.plot(datadct['datetime_single'], datadct['battery_voltage'], color=line2.get_color())
        ax2.set_ylabel('Battery voltage')

    # have the date axes be legible
    for ax in (ax1, ax2):
        for l in ax.xaxis.get_majorticklabels():
            l.set_rotation(45)


    fig.tight_layout()

    if outfile is not None:
        plt.savefig(outfile)

    return fig


if __name__ == '__main__':
    import sys
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('input_file', help='file to parse and plot or "-" for stdin')
    parser.add_argument('output_name', nargs='?', help='filename to save the plot to', default=None)
    parser.add_argument('--deg-f', '-f', help='degrees in farenheit instead of celsius', action='store_true')
    parser.add_argument('--dewpoint', '-d', help='humidity in dewpoint instead of percent', action='store_true')
    parser.add_argument('--absolute-humidity', '-a', help='absolute humidity instead of relative', action='store_true')
    parser.add_argument('--minutes', '-m', help='delta-t in minutes instead of seconds', action='store_true')
    parser.add_argument('--battery', '-b', help='plot battery voltage instead of env conditions', action='store_true')

    args = parser.parse_args()

    if args.input_file == '-':
        datadct = parse_cozir_file(sys.stdin)
    else:
        datadct = parse_cozir_file(args.input_file)

    plot_cozir_data(datadct, outfile=args.output_name, degf=args.deg_f,
                    dewpoint=args.dewpoint, abshum=args.absolute_humidity,
                    minutes=args.minutes, battery=args.battery)
