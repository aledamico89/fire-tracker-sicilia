"""Variabili del modello: stesse funzioni per addestramento (storico) e previsione (quotidiana)."""
import json, math, os, urllib.request
from datetime import date
from fwi import components

DAILY = ["tmax", "rhmin", "wmax", "prec", "ffmc", "dmc", "dc", "isi", "bui", "fwi", "dry_days"]
STATIC = ["lat", "lon", "elev", "area_km2", "log_dens", "hist_rate"]
CAL = ["doy", "weekday", "festivo"]
FEATURES = DAILY + STATIC + CAL
HOLIDAYS = {(1, 1), (1, 6), (4, 25), (5, 1), (6, 2), (8, 15), (11, 1), (12, 8), (12, 25), (12, 26)}

def daily(dates, tmax, rhmin, wmax, prec):
    """Serie giornaliere (giorni consecutivi) -> righe DAILY. FWI su massimi/minimi giornalieri (stima prudente)."""
    rows = [(int(d[5:7]), t or 0, h if h is not None else 50, w or 0, r or 0) for d, t, h, w, r in zip(dates, tmax, rhmin, wmax, prec)]
    out, dry = [], 0
    for (m, t, h, w, r), comp in zip(rows, components(rows)):
        dry = dry + 1 if r < 1 else 0
        out.append([t, h, w, r, *comp, dry])
    return out

def calendar(d):
    dt = date.fromisoformat(d)
    return [dt.timetuple().tm_yday, dt.weekday(), int(dt.weekday() >= 5 or (dt.month, dt.day) in HOLIDAYS)]

def area_km2(geom):
    tot = 0
    for poly in geom["coordinates"]:
        r = poly[0]; k = math.cos(math.radians(r[0][1])) * 111.32 * 110.57
        tot += abs(sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(r, r[1:] + r[:1]))) / 2 * k
    return tot

def statics(path="models/static.json"):
    """lat, lon, quota, area, densità per comune (cache)."""
    if os.path.exists(path): return json.load(open(path))
    from forecast import centroid
    feats = json.load(open("web/data/comuni.geojson"))["features"]; H = json.load(open("web/data/history.json"))
    cents = [centroid(f["geometry"]) for f in feats]; elev = []
    for i in range(0, len(cents), 100):
        part = cents[i:i + 100]
        url = f"https://api.open-meteo.com/v1/elevation?latitude={','.join(str(c[0]) for c in part)}&longitude={','.join(str(c[1]) for c in part)}"
        elev += json.load(urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "fire-tracker-sicilia/0.1"})))["elevation"]
    out = []
    for f, c, e, h in zip(feats, cents, elev, H["comuni"]):
        a = area_km2(f["geometry"]); out.append([c[0], c[1], e, round(a, 1), round(math.log1p((h[2] or 0) / a), 3)])
    json.dump(out, open(path, "w")); return out
