"""Prepara i dati per la dashboard: focolai FIRMS + meteo orario (Open-Meteo/ERA5).
Uso: python3 scripts/prepare_data.py  -> scrive web/data/*.json"""
import csv, json, os, urllib.request
from datetime import datetime, timezone

BBOX = (12.3, 36.5, 15.7, 38.4)          # Sicilia: lon_min, lat_min, lon_max, lat_max
START, END = "2023-07-22", "2023-07-28"
RAW, OUT = "data/raw", "web/data"
FIRMS = "https://firms.modaps.eosdis.nasa.gov/data/country/{s}/2023/{s}_2023_Italy.csv"
SOURCES = ["modis", "viirs-snpp"]

def fetch(url, path):
    if not os.path.exists(path):
        urllib.request.urlretrieve(url, path)
    return path

def hotspots():
    pts = []
    for s in SOURCES:
        try:
            p = fetch(FIRMS.format(s=s), f"{RAW}/{s}_2023_Italy.csv")
        except Exception as e:
            print("skip", s, e); continue
        for r in csv.DictReader(open(p)):
            lat, lon = float(r["latitude"]), float(r["longitude"])
            if not (BBOX[0] <= lon <= BBOX[2] and BBOX[1] <= lat <= BBOX[3]): continue
            if not (START <= r["acq_date"] <= END): continue
            if r.get("confidence", "") in ("l", "low"): continue
            t = r["acq_time"].zfill(4)
            ts = datetime.strptime(r["acq_date"] + t, "%Y-%m-%d%H%M").replace(tzinfo=timezone.utc)
            pts.append([round(lon, 4), round(lat, 4), int(ts.timestamp()),
                        round(float(r.get("frp") or 0), 1), s[0].upper()])
    pts.sort(key=lambda p: p[2])
    return pts

def weather():
    lats = [36.75 + 0.5 * i for i in range(4)]
    lons = [12.5 + 0.5 * j for j in range(7)]
    grid = [(la, lo) for la in lats for lo in lons]
    url = ("https://archive-api.open-meteo.com/v1/archive?latitude=" + ",".join(str(g[0]) for g in grid)
           + "&longitude=" + ",".join(str(g[1]) for g in grid)
           + f"&start_date={START}&end_date={END}&timezone=GMT&wind_speed_unit=kmh"
           + "&hourly=wind_speed_10m,wind_direction_10m,temperature_2m,relative_humidity_2m")
    data = json.load(urllib.request.urlopen(url))
    t0 = int(datetime.fromisoformat(data[0]["hourly"]["time"][0]).replace(tzinfo=timezone.utc).timestamp())
    pts = [{"lat": g[0], "lon": g[1], "ws": d["hourly"]["wind_speed_10m"], "wd": d["hourly"]["wind_direction_10m"],
            "t": d["hourly"]["temperature_2m"], "rh": d["hourly"]["relative_humidity_2m"]}
           for g, d in zip(grid, data)]
    return {"t0": t0, "step": 3600, "points": pts}

if __name__ == "__main__":
    os.makedirs(RAW, exist_ok=True); os.makedirs(OUT, exist_ok=True)
    h = hotspots(); w = weather()
    json.dump(h, open(f"{OUT}/hotspots.json", "w"), separators=(",", ":"))
    json.dump(w, open(f"{OUT}/weather.json", "w"), separators=(",", ":"))
    tmax = max(max(p["t"]) for p in w["points"])
    print(f"focolai: {len(h)} | punti meteo: {len(w['points'])} | Tmax {tmax}°C")
