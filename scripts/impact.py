"""Impatto fisico di ogni area bruciata: pendenze (Copernicus DEM 30 m), edifici e strade (OpenStreetMap),
aree protette (Natura 2000, EEA). Uso: python3 scripts/impact.py monreale 2023 → web/data/impatto_<comune>_<anno>.json"""
import json, os, sys, urllib.parse, urllib.request
import numpy as np, rasterio
from rasterio.merge import merge
from rasterio.features import rasterize
from pyproj import Transformer
from shapely.geometry import shape, Point, LineString
from shapely.ops import transform as stransform
from shapely.strtree import STRtree

os.environ.update(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR")
SLUG, YEAR = (sys.argv[1], sys.argv[2]) if len(sys.argv) > 2 else ("monreale", "2023")
RAW = "data/raw"
FW = Transformer.from_crs(4326, 32633, always_xy=True).transform
UA = {"User-Agent": "fire-tracker-sicilia/0.1"}
d = json.load(open(f"web/data/catasto_{SLUG}_{YEAR}.json"))
G = {f["properties"]["id"]: shape(f["geometry"]) for f in d["features"]}
x0, y0, x1, y1 = shape(d["confine"]).buffer(0.01).bounds

def overpass(q, name):
    p = f"{RAW}/osm_{SLUG}_{name}.json"
    if not os.path.exists(p):
        body = urllib.parse.urlencode({"data": f"[out:json][timeout:300];{q}"}).encode()
        for i, srv in enumerate(["https://overpass-api.de", "https://overpass.kumi.systems", "https://overpass.private.coffee", "https://overpass-api.de"]):
            try:
                r = urllib.request.urlopen(urllib.request.Request(srv + "/api/interpreter", body, UA), timeout=400).read(); open(p, "wb").write(r); break
            except Exception as e:
                print("overpass", srv, e); __import__("time").sleep(20)
    return json.load(open(p))["elements"]

bb = f"({y0},{x0},{y1},{x1})"
bld = [Point(FW(e["center"]["lon"], e["center"]["lat"])) for e in overpass(f'way["building"]{bb};out center qt;', "buildings") if "center" in e]
rd = [(LineString([FW(p["lon"], p["lat"]) for p in e["geometry"]]), e["tags"]) for e in
      overpass(f'way["highway"~"^(motorway|trunk|primary|secondary|tertiary|unclassified|residential)$"]{bb};out geom qt;', "roads") if len(e.get("geometry", [])) > 1]
bt, rt = STRtree(bld), STRtree([r[0] for r in rd])
print("edifici", len(bld), "strade", len(rd))

# Natura 2000 (ZSC/SIC e ZPS)
p = f"{RAW}/natura2000_{SLUG}.json"
if not os.path.exists(p):
    nat = []
    for lay in (0, 1, 2):
        q = urllib.parse.urlencode({"geometry": f"{x0},{y0},{x1},{y1}", "geometryType": "esriGeometryEnvelope", "inSR": 4326, "outSR": 4326,
                                    "spatialRel": "esriSpatialRelIntersects", "outFields": "SITECODE,SITENAME,SITETYPE", "f": "geojson"})
        nat += json.load(urllib.request.urlopen(f"https://bio.discomap.eea.europa.eu/arcgis/rest/services/ProtectedSites/Natura2000Sites/MapServer/{lay}/query?{q}", timeout=120))["features"]
    json.dump(nat, open(p, "w"))
nat = [(stransform(FW, shape(f["geometry"])).buffer(0), f["properties"]) for f in json.load(open(p))]
print("siti Natura 2000", len({n[1]["SITECODE"] for n in nat}))

# pendenze dal DEM Copernicus 30 m
tiles = [f"https://copernicus-dem-30m.s3.amazonaws.com/Copernicus_DSM_COG_10_N{la:02d}_00_E{lo:03d}_00_DEM/Copernicus_DSM_COG_10_N{la:02d}_00_E{lo:03d}_00_DEM.tif"
         for la in range(int(y0), int(y1) + 1) for lo in range(int(x0), int(x1) + 1)]
srcs = [rasterio.open(t) for t in tiles]
dem, tr = merge(srcs, bounds=(x0, y0, x1, y1)); dem = dem[0].astype("f4")
lat = tr.f + tr.e * (np.arange(dem.shape[0]) + .5)
dy = abs(tr.e) * 111320; dx = tr.a * 111320 * np.cos(np.radians(lat))[:, None]
gy, gx = np.gradient(dem); slope = np.hypot(gx / dx, gy / dy) * 100          # pendenza in %
lab = rasterize([(g, k) for k, g in G.items()], dem.shape, transform=tr, dtype="i4")

out = {}
for k, g in G.items():
    m = lab == k
    s, z = (slope[m], dem[m]) if m.any() else (np.array([0.]), np.array([0.]))
    gu = stransform(FW, g)
    inside = [i for i in bt.query(gu) if gu.contains(bld[i])]
    near = [i for i in bt.query(gu.buffer(200)) if gu.buffer(200).contains(bld[i])]
    roads = {}
    for i in rt.query(gu.buffer(100)):
        ln, t = rd[i]; L = ln.intersection(gu.buffer(100)).length
        if L > 0:
            n = t.get("ref") or t.get("name") or {"residential": "strade urbane", "unclassified": "strade locali"}.get(t["highway"], t["highway"])
            roads[n] = roads.get(n, 0) + L
    prot = {}
    for ng, pr in nat:
        if ng.intersects(gu):
            prot[pr["SITECODE"]] = [pr["SITENAME"], round(ng.intersection(gu).area / 1e4, 1)]
    out[k] = {"pend_media": round(float(s.mean()), 1), "pend_ripida_pct": round(float((s > 30).mean()), 2),
              "quota": [int(z.min()), int(z.max())], "edifici_dentro": len(inside), "edifici_200m": len(near) - len(inside),
              "strade_km": round(sum(roads.values()) / 1000, 2),
              "strade": [n for n, _ in sorted(roads.items(), key=lambda x: -x[1]) if n][:5], "natura2000": prot}
json.dump({"comune": d["comune"], "anno": d["anno"], "aree": out}, open(f"web/data/impatto_{SLUG}_{YEAR}.json", "w"), separators=(",", ":"))
v = list(out.values())
print("edifici dentro", sum(a["edifici_dentro"] for a in v), "| entro 200 m", sum(a["edifici_200m"] for a in v),
      "| strade km", round(sum(a["strade_km"] for a in v), 1), "| aree in Natura 2000", sum(1 for a in v if a["natura2000"]),
      "| aree con >30% versanti ripidi", sum(1 for a in v if a["pend_ripida_pct"] > .3))
