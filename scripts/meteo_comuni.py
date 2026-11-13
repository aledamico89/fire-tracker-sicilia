"""Meteo e pericolo incendi (FWI) per ogni comune durante l'evento 22-28 luglio 2023, al centro del comune.
Temperatura e umidità: ERA5-Land (~9 km, solo terraferma); vento e pioggia: ERA5 (0,25°). FWI con avvio dal 1° aprile.
Uso: python3 scripts/meteo_comuni.py → web/data/meteo_comuni.json"""
import json, sys, time, urllib.parse, urllib.request
sys.path.insert(0, "scripts")
from fwi import series

SPINUP, START, END, CHUNK = "2023-04-01", "2023-07-22", "2023-07-28", 40
pts = [(s[0], s[1]) for s in json.load(open("models/static.json"))]

def get(locs):
    q = urllib.parse.urlencode({"latitude": ",".join(str(a) for a, _ in locs), "longitude": ",".join(str(b) for _, b in locs),
        "start_date": SPINUP, "end_date": END, "timezone": "GMT", "wind_speed_unit": "kmh", "models": "era5_land,era5",
        "hourly": "temperature_2m,relative_humidity_2m,wind_speed_10m,wind_direction_10m,precipitation"})
    for k in range(6):
        try:
            r = urllib.request.urlopen(urllib.request.Request("https://archive-api.open-meteo.com/v1/archive?" + q, headers={"User-Agent": "fire-tracker-sicilia/0.1"}), timeout=180)
            d = json.load(r); return d if isinstance(d, list) else [d]
        except Exception as e:
            print("  riprovo:", str(e)[:60], flush=True); time.sleep(90 * (k + 1))
    raise SystemExit("Open-Meteo non risponde")

fwi, H = [], {"ws": [], "wd": [], "t": [], "rh": []}
for c in range(0, len(pts), CHUNK):
    for d in get(pts[c:c + CHUNK]):
        h = d["hourly"]; days = [s[:10] for s in h["time"][::24]]
        T = [a if a is not None else b for a, b in zip(h["temperature_2m_era5_land"], h["temperature_2m_era5"])]
        RH = [a if a is not None else b for a, b in zip(h["relative_humidity_2m_era5_land"], h["relative_humidity_2m_era5"])]
        W, D, P = h["wind_speed_10m_era5"], h["wind_direction_10m_era5"], h["precipitation_era5"]
        rows = []
        for k in range(len(days)):
            n = k * 24 + 11   # mezzogiorno ora solare
            rows.append((int(days[k][5:7]), T[n], RH[n], W[n], sum(x or 0 for x in P[max(0, n - 23):n + 1])))
        i0 = days.index(START) * 24
        fwi.append([round(v, 1) for v in series(rows)[days.index(START):]])
        for key, src in (("ws", W), ("wd", D), ("t", T), ("rh", RH)):
            H[key].append([round(v) if v is not None else None for v in src[i0:i0 + 168]])
    print(f"comuni {min(c + CHUNK, len(pts))}/{len(pts)}", flush=True)
    if c + CHUNK < len(pts): time.sleep(45)
json.dump({"t0": 1689984000, "step": 3600, "fonte": "ERA5-Land (T, UR) + ERA5 (vento, pioggia) via Open-Meteo, centro del comune",
           "fwi": fwi, **H}, open("web/data/meteo_comuni.json", "w"), separators=(",", ":"))
f = [max(x) for x in fwi]
print("FWI max per comune: min", min(f), "mediana", sorted(f)[len(f) // 2], "max", max(f))
