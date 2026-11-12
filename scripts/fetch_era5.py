"""Scarica meteo giornaliero ERA5 (Open-Meteo) 2014-2025 per i punti griglia 0,5° più vicini ai comuni.
Un anno per richiesta con pausa, per rispettare i limiti gratuiti. Cache in data/raw/era5_<anno>.json."""
import json, os, sys, time, urllib.request, urllib.parse, urllib.error
from forecast import centroid

YEARS = range(2014, 2026)
VARS = "temperature_2m_max,relative_humidity_2m_min,wind_speed_10m_max,precipitation_sum"

def grid_points():
    pts = json.load(open("web/data/weather.json"))["points"]
    cents = [centroid(f["geometry"]) for f in json.load(open("web/data/comuni.geojson"))["features"]]
    near = [min(range(len(pts)), key=lambda k: (pts[k]["lat"] - la) ** 2 + (pts[k]["lon"] - lo) ** 2) for la, lo in cents]
    used = sorted(set(near))
    return [(pts[k]["lat"], pts[k]["lon"]) for k in used], [used.index(k) for k in near]

if __name__ == "__main__":
    pts, _ = grid_points(); print("punti griglia:", len(pts), flush=True)
    for y in YEARS:
        p = f"data/raw/era5_{y}.json"
        if os.path.exists(p): continue
        q = urllib.parse.urlencode({"latitude": ",".join(str(a) for a, _ in pts), "longitude": ",".join(str(b) for _, b in pts),
            "start_date": f"{y}-01-01", "end_date": f"{y}-12-31", "timezone": "GMT", "wind_speed_unit": "kmh", "daily": VARS})
        for attempt in range(6):
            try:
                req = urllib.request.Request("https://archive-api.open-meteo.com/v1/archive?" + q, headers={"User-Agent": "fire-tracker-sicilia/0.1"})
                d = json.load(urllib.request.urlopen(req, timeout=180)); break
            except urllib.error.HTTPError as e:
                print(y, "HTTP", e.code, "attendo", flush=True); time.sleep(600 if e.code == 429 else 30)
            except (TimeoutError, urllib.error.URLError, ConnectionError) as e:
                print(y, "rete:", e, "riprovo", flush=True); time.sleep(60)
        else:
            sys.exit(f"fallito {y}")
        json.dump([x["daily"] for x in d], open(p, "w")); print(y, "ok", flush=True)
        time.sleep(420)
