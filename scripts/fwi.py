"""Canadian Fire Weather Index (Van Wagner 1987). T °C, H %, W km/h, r mm (24 h), mese 1-12."""
from math import exp, log

def ffmc(T, H, W, r, Fo):
    mo = 147.2 * (101 - Fo) / (59.5 + Fo)
    if r > 0.5:
        rf = r - 0.5
        mo += 42.5 * rf * exp(-100 / (251 - mo)) * (1 - exp(-6.93 / rf)) + (0.0015 * (mo - 150) ** 2 * rf ** 0.5 if mo > 150 else 0)
        mo = min(mo, 250)
    ed = 0.942 * H ** 0.679 + 11 * exp((H - 100) / 10) + 0.18 * (21.1 - T) * (1 - exp(-0.115 * H))
    if mo > ed:
        ko = 0.424 * (1 - (H / 100) ** 1.7) + 0.0694 * W ** 0.5 * (1 - (H / 100) ** 8)
        m = ed + (mo - ed) * 10 ** (-ko * 0.581 * exp(0.0365 * T))
    else:
        ew = 0.618 * H ** 0.753 + 10 * exp((H - 100) / 10) + 0.18 * (21.1 - T) * (1 - exp(-0.115 * H))
        if mo < ew:
            k1 = 0.424 * (1 - ((100 - H) / 100) ** 1.7) + 0.0694 * W ** 0.5 * (1 - ((100 - H) / 100) ** 8)
            m = ew - (ew - mo) * 10 ** (-k1 * 0.581 * exp(0.0365 * T))
        else:
            m = mo
    return max(0, min(101, 59.5 * (250 - m) / (147.2 + m)))

LE = [6.5, 7.5, 9.0, 12.8, 13.9, 13.9, 12.4, 10.9, 9.4, 8.0, 7.0, 6.0]
LF = [-1.6, -1.6, -1.6, 0.9, 3.8, 5.8, 6.4, 5.0, 2.4, 0.4, -1.6, -1.6]

def dmc(T, H, r, Po, mon):
    K = 1.894 * (max(T, -1.1) + 1.1) * (100 - H) * LE[mon - 1] * 1e-6
    if r > 1.5:
        re = 0.92 * r - 1.27
        Mo = 20 + exp(5.6348 - Po / 43.43)
        b = 100 / (0.5 + 0.3 * Po) if Po <= 33 else (14 - 1.3 * log(Po) if Po <= 65 else 6.2 * log(Po) - 17.2)
        Po = max(0, 244.72 - 43.43 * log(Mo + 1000 * re / (48.77 + b * re) - 20))
    return Po + 100 * K

def dc(T, r, Do, mon):
    V = max(0, 0.36 * (max(T, -2.8) + 2.8) + LF[mon - 1])
    if r > 2.8:
        Qr = 800 * exp(-Do / 400) + 3.937 * (0.83 * r - 1.27)
        Do = max(0, 400 * log(800 / Qr))
    return Do + 0.5 * V

def fwi(F, P, D, W):
    fm = 147.2 * (101 - F) / (59.5 + F)
    isi = 0.208 * exp(0.05039 * W) * 91.9 * exp(-0.1386 * fm) * (1 + fm ** 5.31 / 4.93e7)
    if P + D == 0:
        U = 0
    elif P <= 0.4 * D:
        U = 0.8 * P * D / (P + 0.4 * D)
    else:
        U = max(0, P - (1 - 0.8 * D / (P + 0.4 * D)) * (0.92 + (0.0114 * P) ** 1.7))
    fD = 0.626 * U ** 0.809 + 2 if U <= 80 else 1000 / (25 + 108.64 * exp(-0.023 * U))
    B = 0.1 * isi * fD
    return exp(2.72 * (0.434 * log(B)) ** 0.647) if B > 1 else B

def series(days):
    """days: lista di (mese, T, H, W, r) a mezzogiorno. Ritorna FWI giornaliero."""
    F, P, D, out = 85.0, 6.0, 15.0, []
    for mon, T, H, W, r in days:
        H = min(H, 100)
        F, P, D = ffmc(T, H, W, r, F), dmc(T, H, r, P, mon), dc(T, r, D, mon)
        out.append(round(fwi(F, P, D, W), 1))
    return out
