"""Particelle catastali dentro ogni area bruciata (WMS INSPIRE Agenzia delle Entrate, GetFeatureInfo).
Campiona un punto ogni 70 m (aree con vincolo) o 150 m (altre) dentro ogni poligono. Uso: python3 scripts/parcels.py web/data/catasto_monreale_2023.json"""
import json, os, re, sys, time, urllib.request
from concurrent.futures import ThreadPoolExecutor
from shapely.geometry import shape, Point
from shapely.prepared import prep

P = sys.argv[1]
CACHE = "data/raw/parcels_cache.json"
URL = ("https://wms.cartografia.agenziaentrate.gov.it/inspire/wms/ows01.php?service=WMS&version=1.3.0&request=GetFeatureInfo"
       "&layers=CP.CadastralParcel&query_layers=CP.CadastralParcel&styles=&crs=EPSG:4258&width=101&height=101&i=50&j=50"
       "&info_format=text/html&feature_count=1&bbox={a},{b},{c},{d}")
cache = {k: v for k, v in (json.load(open(CACHE)) if os.path.exists(CACHE) else {}).items() if v is not None}

def ask(pt):
    """Riferimento catastale nel punto; '' se nessuna particella. Se il servizio limita le richieste, attende."""
    k = f"{pt[1]:.5f},{pt[0]:.5f}"
    if cache.get(k) is not None: return k, cache[k]
    lat, lon, h = pt[1], pt[0], .0002
    for i in range(12):
        try:
            t = urllib.request.urlopen(URL.format(a=lat - h, b=lon - h, c=lat + h, d=lon + h), timeout=30).read().decode("latin1")
            if "ServiceException" in t: raise IOError(t[-60:])
            m = re.search(r"([A-Z]\d{3}_\w{6}\.\w+)", t)
            time.sleep(.3)
            return k, m.group(1) if m else ""
        except Exception as e:
            print("  attesa:", str(e)[:50], flush=True); time.sleep(min(60 * 2 ** i, 900))
    return k, None

d = json.load(open(P))
for f in sorted(d["features"], key=lambda f: not f["properties"]["vincolo"]):
    STEP = 70 if f["properties"]["vincolo"] else 150; dlat = STEP / 111320
    g = shape(f["geometry"]); pg = prep(g)
    x0, y0, x1, y1 = g.bounds
    dlon = STEP / (111320 * .79)
    pts = [(x0 + i * dlon, y0 + j * dlat) for i in range(int((x1 - x0) / dlon) + 1) for j in range(int((y1 - y0) / dlat) + 1)]
    pts = [p for p in pts if pg.contains(Point(p))] or [g.representative_point().coords[0]]
    with ThreadPoolExecutor(2) as ex:
        res = list(ex.map(ask, pts))
    for k, v in res:
        if v is not None: cache[k] = v
    refs = sorted({v for _, v in res if v})
    # F377_010900.136 → comune F377, foglio 109, particella 136
    f["properties"]["particelle"] = [[r.split("_")[0], int(r.split("_")[1][:4]), r.split(".", 1)[1]] for r in refs if re.match(r"\w{4}_\d{4}\w{2}\.", r)]
    print(f["properties"]["id"], f["properties"]["ha"], "ha →", len(pts), "punti,", len(refs), "particelle", flush=True)
    json.dump(cache, open(CACHE, "w"))
json.dump(d, open(P, "w"), separators=(",", ":"))
n = sum(len(f["properties"]["particelle"]) for f in d["features"])
print("particelle totali:", n, "| fogli:", len({(p[0], p[1]) for f in d["features"] for p in f["properties"]["particelle"]}))
