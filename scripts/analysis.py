"""Analisi evento: FWI giornaliero, qualità dell'aria, comuni colpiti. Scrive web/data/analysis.json.
Richiede prima scripts/prepare_data.py."""
import json, os, urllib.request, urllib.parse

from fwi import series
from prepare_data import START, END, RAW, OUT

SPINUP = "2023-04-01"  # i codici di umidità del combustibile partono da inizio stagione
CITIES = {"Palermo": (38.116, 13.361), "Trapani": (38.018, 12.514), "Agrigento": (37.311, 13.577),
          "Caltanissetta": (37.490, 14.062), "Enna": (37.567, 14.279), "Messina": (38.193, 15.554),
          "Catania": (37.502, 15.087), "Siracusa": (37.075, 15.286), "Ragusa": (36.925, 14.731)}

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "fire-tracker-sicilia/0.1"})
    return json.load(urllib.request.urlopen(req, timeout=120))

def fwi_grid(points):
    q = urllib.parse.urlencode({"latitude": ",".join(str(p["lat"]) for p in points),
        "longitude": ",".join(str(p["lon"]) for p in points), "start_date": SPINUP, "end_date": END,
        "timezone": "GMT", "wind_speed_unit": "kmh",
        "hourly": "temperature_2m,relative_humidity_2m,wind_speed_10m,precipitation"})
    data = get("https://archive-api.open-meteo.com/v1/archive?" + q)
    days = [s[:10] for s in data[0]["hourly"]["time"][::24]]
    i0 = days.index(START)
    out = []
    for d in data:
        h = d["hourly"]; rows = []
        for k in range(len(days)):
            n = k * 24 + 11  # mezzogiorno ora solare (UTC+1)
            rain = sum(x or 0 for x in h["precipitation"][max(0, n - 23):n + 1])
            rows.append((int(days[k][5:7]), h["temperature_2m"][n], h["relative_humidity_2m"][n], h["wind_speed_10m"][n], rain))
        out.append(series(rows)[i0:])
    return days[i0:], out

def air():
    names = list(CITIES)
    q = urllib.parse.urlencode({"latitude": ",".join(str(CITIES[c][0]) for c in names),
        "longitude": ",".join(str(CITIES[c][1]) for c in names), "start_date": START, "end_date": END,
        "timezone": "GMT", "hourly": "pm10,pm2_5"})
    data = get("https://air-quality-api.open-meteo.com/v1/air-quality?" + q)
    return [{"name": c, "lat": CITIES[c][0], "lon": CITIES[c][1], "pm10": d["hourly"]["pm10"], "pm25": d["hourly"]["pm2_5"]}
            for c, d in zip(names, data)]

def inside(x, y, ring):
    c = False
    for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1]):
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            c = not c
    return c

def comuni(hot):
    p = f"{RAW}/comuni_sicilia.geojson"
    if not os.path.exists(p):
        urllib.request.urlretrieve("https://raw.githubusercontent.com/openpolis/geojson-italy/master/geojson/limits_R_19_municipalities.geojson", p)
    feats = json.load(open(p))["features"]
    ov = "[out:json][timeout:90];area[\"ISO3166-2\"=\"IT-82\"]->.a;relation(area.a)[admin_level=8][boundary=administrative];out tags;"
    tags = [e["tags"] for e in get("https://overpass-api.de/api/interpreter?data=" + urllib.parse.quote(ov))["elements"]]
    pop = {t.get("ref:ISTAT", "").zfill(6): int(t["population"].replace(".", "")) for t in tags if t.get("population", "").replace(".", "").isdigit()}
    polys = []
    for f in feats:
        g = f["geometry"]; rings = [g["coordinates"][0]] if g["type"] == "Polygon" else [c[0] for c in g["coordinates"]]
        rings = [[tuple(pt) for pt in r] for r in rings]
        xs = [pt[0] for r in rings for pt in r]; ys = [pt[1] for r in rings for pt in r]
        polys.append((rings, (min(xs), min(ys), max(xs), max(ys))))
    idx = []
    for lon, lat, *_ in hot:
        k = next((i for i, (rings, b) in enumerate(polys) if b[0] <= lon <= b[2] and b[1] <= lat <= b[3]
                  and any(inside(lon, lat, r) for r in rings)), -1)
        idx.append(k)
    used = sorted(set(i for i in idx if i >= 0))
    remap = {i: n for n, i in enumerate(used)}
    props = [feats[i]["properties"] for i in used]
    lst = [[pr["name"], pr.get("prov_acr", ""), pop.get(str(pr["com_istat_code"]).zfill(6))] for pr in props]
    return lst, [remap.get(i, -1) for i in idx]

if __name__ == "__main__":
    hot = json.load(open(f"{OUT}/hotspots.json"))
    wx = json.load(open(f"{OUT}/weather.json"))
    days, fw = fwi_grid(wx["points"])
    aq = air()
    cl, hc = comuni(hot)
    json.dump({"days": days, "fwi": fw, "air": aq, "comuni": cl, "hc": hc},
              open(f"{OUT}/analysis.json", "w"), separators=(",", ":"))
    pal = min(range(len(wx["points"])), key=lambda i: abs(wx["points"][i]["lat"] - 38.12) + abs(wx["points"][i]["lon"] - 13.36))
    print("FWI Palermo:", dict(zip(days, fw[pal])))
    print("FWI max griglia:", max(max(f) for f in fw))
    print("PM10 max:", {a["name"]: max(v or 0 for v in a["pm10"]) for a in aq})
    print("comuni:", len(cl), "| senza pop:", sum(1 for c in cl if c[2] is None), "| fuori comune:", hc.count(-1))
    from collections import Counter
    print("top:", [(cl[i][0], n) for i, n in Counter(x for x in hc if x >= 0).most_common(5)])
