"""Storico incendi Sicilia 2001-2025 da NASA FIRMS MODIS (serie omogenea).
Scrive web/data/history.json e web/data/comuni.geojson. Richiede analysis.py (confini comuni in data/raw)."""
import csv, json, os, urllib.request, urllib.parse
from collections import defaultdict
from datetime import date, timedelta
from analysis import get, inside
from prepare_data import BBOX, RAW, OUT

YEARS = list(range(2001, 2026))
URL = "https://firms.modaps.eosdis.nasa.gov/data/country/modis/{y}/modis_{y}_Italy.csv"
GAP_DAYS, CELL = 3, 0.02  # innesco = nessun focolaio entro ~2 km nei 3 giorni precedenti

def population():
    p = f"{RAW}/pop.json"
    if not os.path.exists(p):
        ov = "[out:json][timeout:90];area[\"ISO3166-2\"=\"IT-82\"]->.a;relation(area.a)[admin_level=8][boundary=administrative];out tags;"
        tags = [e["tags"] for e in get("https://overpass-api.de/api/interpreter?data=" + urllib.parse.quote(ov))["elements"]]
        json.dump({t.get("ref:ISTAT", "").zfill(6): int(t["population"].replace(".", "")) for t in tags
                   if t.get("population", "").replace(".", "").isdigit()}, open(p, "w"))
    return json.load(open(p))

def load_comuni():
    feats = json.load(open(f"{RAW}/comuni_sicilia.geojson"))["features"]
    polys = []
    for f in feats:
        g = f["geometry"]; rings = [g["coordinates"][0]] if g["type"] == "Polygon" else [c[0] for c in g["coordinates"]]
        xs = [p[0] for r in rings for p in r]; ys = [p[1] for r in rings for p in r]
        polys.append((rings, (min(xs), min(ys), max(xs), max(ys))))
    return feats, polys

def simplify(ring):
    out = []
    for x, y in ring:
        pt = [round(x, 3), round(y, 3)]
        if not out or pt != out[-1]: out.append(pt)
    return out if len(out) >= 4 else [[round(x, 3), round(y, 3)] for x, y in ring]

if __name__ == "__main__":
    feats, polys = load_comuni(); pop = population()
    cache = {}
    def comune(lon, lat):
        k = (round(lon, 3), round(lat, 3))
        if k not in cache:
            cache[k] = next((i for i, (rings, b) in enumerate(polys) if b[0] <= lon <= b[2] and b[1] <= lat <= b[3]
                             and any(inside(lon, lat, r) for r in rings)), -1)
        return cache[k]
    det = []; skipped = defaultdict(int)
    for y in YEARS:
        p = f"{RAW}/modis_{y}_Italy.csv"
        if not os.path.exists(p): urllib.request.urlretrieve(URL.format(y=y), p)
        for r in csv.DictReader(open(p)):
            lon, lat = float(r["longitude"]), float(r["latitude"])
            if not (BBOX[0] <= lon <= BBOX[2] and BBOX[1] <= lat <= BBOX[3]): continue
            if r.get("type", "0") != "0": skipped["type " + r["type"]] += 1; continue
            if int(r["confidence"]) < 30: skipped["conf<30"] += 1; continue
            c = comune(lon, lat)
            if c < 0: skipped["fuori comuni"] += 1; continue
            det.append((r["acq_date"], lon, lat, c))
    det.sort()
    n = len(feats); Y = len(YEARS)
    per_year = [0] * Y; ign_year = [0] * Y; month = [0] * 12; wday = [0] * 7
    c_det = [[0] * Y for _ in range(n)]; c_ign = [0] * n
    cells = defaultdict(lambda: [set(), 0]); last = {}
    for d, lon, lat, c in det:
        dt = date.fromisoformat(d); yi = dt.year - YEARS[0]
        per_year[yi] += 1; c_det[c][yi] += 1
        k = (round(lon / .01) * .01, round(lat / .01) * .01); cells[k][0].add(dt.year); cells[k][1] += 1
        gx, gy = int(lon // CELL), int(lat // CELL)
        near = [last.get((gx + i, gy + j)) for i in (-1, 0, 1) for j in (-1, 0, 1)]
        if not any(x and dt - x <= timedelta(days=GAP_DAYS) for x in near):
            ign_year[yi] += 1; month[dt.month - 1] += 1; wday[dt.weekday()] += 1; c_ign[c] += 1
        last[(gx, gy)] = dt
    com = [[f["properties"]["name"], f["properties"].get("prov_acr", ""), pop.get(str(f["properties"]["com_istat_code"]).zfill(6)),
            c_det[i], c_ign[i]] for i, f in enumerate(feats)]
    json.dump({"years": YEARS, "det": per_year, "ign": ign_year, "month": month, "wday": wday, "comuni": com,
               "cells": [[round(k[0], 2), round(k[1], 2), len(v[0]), v[1]] for k, v in cells.items()]},
              open(f"{OUT}/history.json", "w"), separators=(",", ":"))
    gj = {"type": "FeatureCollection", "features": [{"type": "Feature", "id": i, "properties": {},
          "geometry": {"type": "MultiPolygon", "coordinates": [[simplify(r)] for r in rings]}} for i, (rings, _) in enumerate(polys)]}
    json.dump(gj, open(f"{OUT}/comuni.geojson", "w"), separators=(",", ":"))
    print("rilevazioni:", len(det), "| scartate:", dict(skipped))
    print("per anno:", dict(zip(YEARS, per_year)))
    print("inneschi per anno:", dict(zip(YEARS, ign_year)))
    print("mesi:", month, "| lun-dom:", wday)
    print("celle:", len(cells), "| ricorrenti >=5 anni:", sum(1 for v in cells.values() if len(v[0]) >= 5))
    top = sorted(range(n), key=lambda i: -sum(c_det[i]))[:8]
    print("top comuni:", [(com[i][0], sum(c_det[i]), sum(1 for x in c_det[i] if x)) for i in top])
