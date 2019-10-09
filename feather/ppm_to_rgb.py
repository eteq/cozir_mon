def ppm_to_rgb(co2_ppm, intensity=1):
    if co2_ppm < 400:
        r = g = 0
        b = 1
    elif co2_ppm > 2000:
        r = 1
        g = b = 0
    elif co2_ppm < 1000:
        r = 0
        g = (co2_ppm - 400)/600
        b = (1000 - co2_ppm)/600
    else:
        b = 0
        g = (2000 - co2_ppm)/1000
        r = (co2_ppm - 1000)/1000

    tot = r + g + b
    scale = intensity * 255 / tot
    r = r * scale
    g = g * scale
    b = b * scale
    return int(r), int(g), int(b)