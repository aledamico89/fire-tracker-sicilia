"""Località OSM (frazioni, contrade, monti) vicine a ogni area bruciata, per abbinare le notizie.
Uso: python3 scripts/localita.py monreale 2023 → aggiunge "localita" a web/data/impatto_<comune>_<anno>.json"""
import json, os, re, sys, urllib.parse, urllib.request
from shapely.geometry import shape, Point
from shapely.ops import transform as stransform
from pyproj import Transformer

SLUG, YEAR = sys.argv[1], sys.argv[2]
FW = Transformer.from_crs(4326, 32633, always_xy=True).transform
d = json.load(open(f"web/data/catasto_{SLUG}_{YEAR}.json"))
x0, y0, x1, y1 = shape(d["confine"]).buffer(0.02).bounds
p = f"data/raw/osm_{SLUG}_places.json"
if not os.path.exists(p):
    q = f'[out:json][timeout:120];(node["place"~"^(village|hamlet|locality|suburb|isolated_dwelling|neighbourhood)$"]({y0},{x0},{y1},{x1});node["natural"="peak"]["name"]({y0},{x0},{y1},{x1}););out qt;'
    r = urllib.request.urlopen(urllib.request.Request(os.environ.get("OVERPASS", "https://overpass-api.de") + "/api/interpreter", urllib.parse.urlencode({"data": q}).encode(), {"User-Agent": "fire-tracker-sicilia/0.1"}), timeout=200).read()
    open(p, "wb").write(r)
pl = [(Point(FW(e["lon"], e["lat"])), re.sub(r"[<>\"`&]", "", e["tags"]["name"]), e["tags"].get("place") or "monte")
      for e in json.load(open(p))["elements"] if e.get("tags", {}).get("name")]
ip = f"web/data/impatto_{SLUG}_{YEAR}.json"
im = json.load(open(ip))
for f in d["features"]:
    g = stransform(FW, shape(f["geometry"]))
    near = sorted((g.distance(pt), n, t) for pt, n, t in pl if g.distance(pt) < 2500)
    im["aree"].setdefault(str(f["properties"]["id"]), {})["localita"] = list(dict.fromkeys(n for _, n, _ in near))[:5]
json.dump(im, open(ip, "w"), separators=(",", ":"))
print("luoghi OSM", len(pl))
