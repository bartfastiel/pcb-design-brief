"""Engineering formulas for sizing parts (brief CI-1, CI-2, EN-3). Plain Python, SI units unless the name says
otherwise. Each function returns numbers; row() turns a result into a line of the review PDF's calculation table.

  python -m pcbtools calc led 5 2.0 0.003       -> resistor for an LED: E24 value, current, power
  python -m pcbtools calc divider 5 10000 10000 -> divider output, current, source impedance
  python -m pcbtools calc crystal 18            -> load capacitors for a crystal with 18 pF load
  python -m pcbtools calc track 2 --rise 10     -> track width (IPC-2221, outer layer, 35 um)
  python -m pcbtools calc heat 0.5 93 47 14     -> enclosure surface temperature rise"""
import math

E12 = [1.0, 1.2, 1.5, 1.8, 2.2, 2.7, 3.3, 3.9, 4.7, 5.6, 6.8, 8.2]
E24 = [1.0, 1.1, 1.2, 1.3, 1.5, 1.6, 1.8, 2.0, 2.2, 2.4, 2.7, 3.0, 3.3, 3.6, 3.9, 4.3, 4.7, 5.1, 5.6, 6.2, 6.8,
       7.5, 8.2, 9.1]
E96 = [round(10 ** (k / 96), 2) for k in range(96)]


def e_series(value, series=E24, mode="nearest"):
    """Standard value: nearest, or the next one up/down."""
    decade = 10 ** math.floor(math.log10(value))
    candidates = [v * decade * f for f in (0.1, 1, 10) for v in series]
    if mode == "up":
        return min(c for c in candidates if c >= value * 0.9999)
    if mode == "down":
        return max(c for c in candidates if c <= value * 1.0001)
    return min(candidates, key=lambda c: abs(math.log(c / value)))


def resistor_power(r, v=None, i=None):
    return v * v / r if v is not None else i * i * r


def led(v_supply, v_forward, current, series=E24):
    r = e_series((v_supply - v_forward) / current, series, "up")
    actual = (v_supply - v_forward) / r
    return {"r": r, "current": actual, "power": actual * actual * r}


def divider(v_in, r_top, r_bottom, load=None):
    r_low = r_bottom if load is None else r_bottom * load / (r_bottom + load)
    v_out = v_in * r_low / (r_top + r_low)
    return {"v_out": v_out, "current": v_in / (r_top + r_low), "source_impedance": r_top * r_low / (r_top + r_low),
            "power_top": (v_in - v_out) ** 2 / r_top, "power_bottom": v_out ** 2 / r_low}


def crystal(load_pf, stray_pf=5.0):
    """Two equal load capacitors: C = 2 x (CL - Cstray)."""
    c = 2 * (load_pf - stray_pf)
    return {"exact_pf": c, "e12_pf": e_series(c, E12)}


def track_width(current, rise=10.0, copper_um=35.0, outer=True):
    """IPC-2221: A[mil2] = (I / (k x dT^0.44))^(1/0.725); width from the copper thickness. Returns mm."""
    k = 0.048 if outer else 0.024
    area_mil2 = (current / (k * rise ** 0.44)) ** (1 / 0.725)
    thickness_mil = copper_um / 25.4
    return area_mil2 / thickness_mil * 0.0254


def rc(r, c):
    return r * c


def enclosure_rise(power, w_mm, d_mm, h_mm, h_coef=9.0):
    """Surface temperature rise of a closed box by natural convection and radiation (h about 9 W/m2K);
    inside air typically 1.5 times that."""
    area = 2 * (w_mm * d_mm + w_mm * h_mm + d_mm * h_mm) / 1e6
    surface = power / (h_coef * area)
    return {"area_m2": area, "surface_rise": surface, "inside_rise": 1.5 * surface}


def row(ref, function, case, load, limit, share, allowed=0.5, note=""):
    return {"ref": ref, "function": function, "case": case, "load": load, "limit": limit, "share": share,
            "allowed": allowed, "note": note}


def main(argv):
    kind, *args = argv
    numbers = [float(a) for a in args if not a.startswith("--")]
    if kind == "led":
        print(led(*numbers[:3]))
    elif kind == "divider":
        print(divider(*numbers[:3]) if len(numbers) < 4 else divider(*numbers[:4]))
    elif kind == "crystal":
        print(crystal(*numbers[:2]))
    elif kind == "track":
        rise = float(args[args.index("--rise") + 1]) if "--rise" in args else 10.0
        print(f"{track_width(numbers[0], rise):.2f} mm")
    elif kind == "heat":
        print(enclosure_rise(*numbers[:4]))
    else:
        raise SystemExit(__doc__)
