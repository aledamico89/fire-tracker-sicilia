"""Previsione pericolo incendi (FWI) per ogni comune siciliano, oggi + 6 giorni.
Usa solo file in web/data (gira anche su GitHub Actions). Scrive web/data/forecast.json."""
import json, urllib.request, urllib.parse
from datetime import datetime, timezone
from fwi import series

OUT, PAST, DAYS, CHUNK = "web/data", 60, 7, 100

def centroid(geom):
    pts = [p for poly in geom["coordinates"] for ring in poly[:1] for p in ring]
    return round(sum(p[1] for p in pts) / len(pts), 3), round(sum(p[0] for p in pts) / len(pts), 3)

def fetch(locs):
    q = urllib.parse.urlencode({"latitude": ",".join(str(l[0]) for l in locs), "longitude": ",".join(str(l[1]) for l in locs),
        "past_days": PAST, "forecast_days": DAYS, "timezone": "GMT", "wind_speed_unit": "kmh",
        "hourly": "temperature_2m,relative_humidity_2m,wind_speed_10m,precipitation"})
    req = urllib.request.Request("https://api.open-meteo.com/v1/forecast?" + q, headers={"User-Agent": "fire-tracker-sicilia/0.1"})
    d = json.load(urllib.request.urlopen(req, timeout=120))
    return d if isinstance(d, list) else [d]

if __name__ == "__main__":
    locs = [centroid(f["geometry"]) for f in json.load(open(f"{OUT}/comuni.geojson"))["features"]]
    data = [x for i in range(0, len(locs), CHUNK) for x in fetch(locs[i:i + CHUNK])]
    times = data[0]["hourly"]["time"]; nd = len(times) // 24
    days = [times[k * 24][:10] for k in range(nd)][-DAYS:]
    fwi, tmax, rhmin, wmax = [], [], [], []
    for d in data:
        h = d["hourly"]; rows = []
        for k in range(nd):
            n = k * 24 + 11
            rain = sum(x or 0 for x in h["precipitation"][max(0, n - 23):n + 1])
            rows.append((int(times[n][5:7]), h["temperature_2m"][n], h["relative_humidity_2m"][n], h["wind_speed_10m"][n], rain))
        fwi.append(series(rows)[-DAYS:])
        day = lambda key, f: [round(f(v for v in h[key][k * 24:(k + 1) * 24] if v is not None)) for k in range(nd - DAYS, nd)]
        tmax.append(day("temperature_2m", max)); rhmin.append(day("relative_humidity_2m", min)); wmax.append(day("wind_speed_10m", max))
    json.dump({"run": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"), "days": days, "fwi": fwi, "tmax": tmax, "rhmin": rhmin, "wmax": wmax},
              open(f"{OUT}/forecast.json", "w"), separators=(",", ":"))
    flat = [v for f in fwi for v in f]
    print("comuni:", len(fwi), "| giorni:", days[0], "→", days[-1], "| FWI min/med/max:", min(flat), round(sum(flat) / len(flat), 1), max(flat))
