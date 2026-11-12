"""Aree percorse dal fuoco per un comune e un anno (bozza di catasto incendi, L. 353/2000).
Metodo: per ogni incendio visto da MODIS/VIIRS, dNBR Sentinel-2 L2A (prima/dopo, 20 m),
zone bruciate tenute solo se vicine a un focolaio. Copertura del suolo: ESA WorldCover 2021.
Uso: python3 scripts/burned.py Monreale 2023"""
import csv, json, os, sys, urllib.request
from datetime import date, timedelta
import numpy as np, rasterio, shapely
from concurrent.futures import ThreadPoolExecutor
from shapely.ops import unary_union
from rasterio.windows import from_bounds
from rasterio.features import rasterize, shapes
from rasterio.warp import reproject, Resampling
from rasterio.transform import from_origin
from scipy import ndimage
from pyproj import Transformer
from shapely.geometry import shape, mapping
from shapely.ops import transform as stransform

os.environ.update(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif", GDAL_HTTP_MAX_RETRY="4")
NAME, YEAR = (sys.argv[1], int(sys.argv[2])) if len(sys.argv) > 2 else ("Monreale", 2023)
RAW, OUT, RES = "data/raw", "web/data", 20
CACHE = f"{RAW}/s2"; os.makedirs(CACHE, exist_ok=True)
TH, POST_MAX, MIN_PX, NEAR_M = 0.20, 0.15, 13, 1000          # soglia dNBR, area minima 0,5 ha, distanza dal focolaio
FW = Transformer.from_crs(4326, 32633, always_xy=True).transform
BW = Transformer.from_crs(32633, 4326, always_xy=True).transform
WC = "https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/ESA_WorldCover_10m_2021_v200_N36E012_Map.tif"

def comune():
    for f in json.load(open(f"{RAW}/comuni_sicilia.geojson"))["features"]:
        if f["properties"]["name"] == NAME:
            return f["properties"]["com_istat_code"], shape(f["geometry"])

def hotspots(poly):
    x0, y0, x1, y1 = poly.buffer(0.02).bounds
    pts = []
    for src in ("modis", "viirs-snpp"):
        p = f"{RAW}/{src}_{YEAR}_Italy.csv"
        if not os.path.exists(p):
            urllib.request.urlretrieve(f"https://firms.modaps.eosdis.nasa.gov/data/country/{src}/{YEAR}/{src}_{YEAR}_Italy.csv", p)
        for r in csv.DictReader(open(p)):
            lon, lat = float(r["longitude"]), float(r["latitude"])
            if r["type"] == "0" and x0 < lon < x1 and y0 < lat < y1 and r["confidence"] not in ("l",) and not (src == "modis" and int(r["confidence"]) < 30):
                pts.append((*FW(lon, lat), date.fromisoformat(r["acq_date"]), src))
    return pts

def events(pts):
    """Raggruppa i focolai: entro 2 km ed entro 3 giorni = stesso incendio."""
    par = list(range(len(pts)))
    def find(i):
        while par[i] != i: par[i] = par[par[i]]; i = par[i]
        return i
    for i, a in enumerate(pts):
        for j in range(i + 1, len(pts)):
            b = pts[j]
            if abs((a[2] - b[2]).days) <= 3 and (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 < 4e6:
                par[find(i)] = find(j)
    g = {}
    for i, p in enumerate(pts): g.setdefault(find(i), []).append(p)
    return sorted(g.values(), key=lambda e: min(p[2] for p in e))

def stac():
    p = f"{CACHE}/stac_{NAME}_{YEAR}.json"
    if os.path.exists(p): return json.load(open(p))
    body = {"collections": ["sentinel-2-l2a"], "bbox": BBOX4326, "limit": 200,
            "datetime": f"{YEAR}-03-01T00:00:00Z/{YEAR}-12-15T00:00:00Z", "query": {"eo:cloud_cover": {"lt": 40}}}
    url, items = "https://earth-search.aws.element84.com/v1/search", []
    while url:
        req = urllib.request.Request(url, json.dumps(body).encode(), {"Content-Type": "application/json"})
        d = json.load(urllib.request.urlopen(req, timeout=60))
        items += [{"id": x["id"], "date": x["properties"]["datetime"][:10], "cloud": x["properties"]["eo:cloud_cover"],
                   "b8a": x["assets"]["nir08"]["href"], "b12": x["assets"]["swir22"]["href"], "scl": x["assets"]["scl"]["href"],
                   "red": x["assets"]["red"]["href"], "green": x["assets"]["green"]["href"], "blue": x["assets"]["blue"]["href"]} for x in d["features"]]
        nxt = [l for l in d.get("links", []) if l["rel"] == "next"]
        url, body = (nxt[0]["href"], nxt[0].get("body", body)) if nxt else (None, None)
    json.dump(items, open(p, "w"))
    return items

def read(href, b, shape_):
    with rasterio.open(href) as s:
        w = from_bounds(*b, s.transform)
        return s.read(1, window=w, boundless=True, fill_value=0, out_shape=shape_)

def nbr(item, b, shp):
    """NBR su finestra b (UTM); NaN dove nuvole/acqua/fuori tile."""
    k = f"{CACHE}/{item['id']}_{int(b[0])}_{int(b[1])}_{shp[0]}x{shp[1]}.npz"
    if os.path.exists(k): raw = np.load(k)["a"]
    else:
        raw = np.stack([read(item[x], b, shp) for x in ("b8a", "b12", "scl")]); np.savez_compressed(k, a=raw)
    n, s = raw[0] * 1e-4 - .1, raw[1] * 1e-4 - .1
    v = np.isin(raw[2], (2, 3, 4, 5, 7)) & (raw[0] > 0) & (raw[1] > 0) & (n > .01) & (s > .01)
    return np.where(v, (n - s) / (n + s), np.nan).astype("f4")

def composite(cands, b, shp, k=3):
    with ThreadPoolExecutor(6) as ex:
        arr = list(ex.map(lambda it: nbr(it, b, shp), cands[:k + 3]))
    stack = [a for a in arr if np.isfinite(a).mean() > .3][:k]
    if not stack: return None, []
    with np.errstate(all="ignore"):
        return np.nanmedian(stack, 0), stack

istat, poly = comune()
BBOX4326 = list(poly.bounds)
pu = stransform(FW, poly)
x0, y0, x1, y1 = (int(v // RES * RES) for v in pu.bounds); x1 += RES; y1 += RES
W, H = (x1 - x0) // RES, (y1 - y0) // RES
T = from_origin(x0, y1, RES, RES)
inside = rasterize([pu], (H, W), transform=T).astype(bool)

pts = hotspots(poly)
evs = [e for e in events(pts) if any(pu.buffer(NEAR_M).contains(__import__("shapely").Point(p[0], p[1])) for p in e)]
items = sorted(stac(), key=lambda i: i["date"])
print(f"{NAME} {YEAR}: focolai {len(pts)}, incendi {len(evs)}, scene {len(items)}")

dmax = np.zeros((H, W), "f4"); pnbr = np.ones((H, W), "f4"); evid = np.full((H, W), -1, "i2"); near = np.zeros((H, W), bool); near5 = np.zeros((H, W), bool)
meta = []
for ei, e in enumerate(evs):
    d0, d1 = min(p[2] for p in e), max(p[2] for p in e)
    ex, ey = [p[0] for p in e], [p[1] for p in e]
    b = (max(x0, (min(ex) - 3000) // RES * RES), max(y0, (min(ey) - 3000) // RES * RES),
         min(x1, (max(ex) + 3000) // RES * RES + RES), min(y1, (max(ey) + 3000) // RES * RES + RES))
    shp = (int((b[3] - b[1]) // RES), int((b[2] - b[0]) // RES))
    pre = [i for i in reversed(items) if d0 - timedelta(20) <= date.fromisoformat(i["date"]) < d0]
    post = [i for i in items if d1 < date.fromisoformat(i["date"]) <= d1 + timedelta(8)]
    a, sa = composite(pre, b, shp); p_, sp = composite(post, b, shp, 2)
    if a is None or p_ is None:
        print(f"  {d0} saltato: mancano scene"); continue
    dn = np.nan_to_num(a - p_, nan=0)
    r0, c0 = int((y1 - b[3]) // RES), int((b[0] - x0) // RES)
    sl = (slice(r0, r0 + shp[0]), slice(c0, c0 + shp[1]))
    pm = np.zeros(shp, bool)
    for x, y, *_ in e:
        r, c = int((b[3] - y) // RES), int((x - b[0]) // RES)
        if 0 <= r < shp[0] and 0 <= c < shp[1]: pm[r, c] = True
    dist = ndimage.distance_transform_edt(~pm) * RES; pm = dist < NEAR_M
    upd = dn > dmax[sl]
    dmax[sl] = np.where(upd, dn, dmax[sl]); pnbr[sl] = np.where(upd, np.nan_to_num(p_, nan=1), pnbr[sl]); evid[sl] = np.where(upd, ei, evid[sl]); near[sl] |= pm; near5[sl] |= dist < 500
    meta.append((ei, d0, d1, len(e)))

# copertura del suolo (WorldCover 10 m → griglia 20 m, valore più frequente ≈ nearest)
lc = np.zeros((H, W), "u1")
with rasterio.open(WC) as s:
    lb = stransform(BW, __import__("shapely").box(x0, y0, x1, y1)).bounds
    w = from_bounds(*lb, s.transform).round_offsets().round_lengths()
    src = s.read(1, window=w)
    reproject(src, lc, src_transform=s.window_transform(w), src_crs=s.crs, dst_transform=T, dst_crs="EPSG:32633", resampling=Resampling.mode)
VINC = np.isin(lc, (10, 20, 30, 90))          # bosco, arbusteti, prati/pascoli, zone umide

emon = np.array([m[1].month for m in sorted(meta)] if meta else [0])
full = np.zeros(max(m[0] for m in meta) + 1, "i1"); full[[m[0] for m in meta]] = [m[1].month for m in meta]
mon = np.where(evid >= 0, full[np.maximum(evid, 0)], 0)
agri = np.isin(lc, (30, 40))                  # coltivi e prati: in autunno arature simili a bruciature
autumn = agri & (mon >= 9)
burn = inside & near & np.where(lc == 40, (dmax >= .3) & (pnbr <= -.05), (dmax >= TH) & (pnbr <= POST_MAX))
burn &= ~autumn | (near5 & (dmax >= .45) & (pnbr <= -.1))
lab, n = ndimage.label(burn, np.ones((3, 3)))
keep = np.zeros(n + 1, bool)
idx = np.arange(1, n + 1)
keep[1:] = ndimage.sum(burn, lab, idx) >= MIN_PX
burn = keep[lab]
lab, n = ndimage.label(burn, np.ones((3, 3)))

ED = {m[0]: m for m in meta}
feats, cls = [], lambda v: "alta" if v >= .66 else "medio-alta" if v >= .44 else "medio-bassa" if v >= .27 else "bassa"
parts = {}
for g, v in shapes(lab.astype("i4"), mask=burn, transform=T, connectivity=8):
    parts.setdefault(int(v), []).append(shape(g))
objs = ndimage.find_objects(lab)
for k, gs in parts.items():
    sl = objs[k - 1]; m = lab[sl] == k; E, DM, V, L = evid[sl], dmax[sl], VINC[sl], lc[sl]
    ev = ED[int(np.bincount(E[m][E[m] >= 0]).argmax())]
    ha = m.sum() * RES * RES / 1e4; dv = float(DM[m].mean()); vf = float(V[m].mean())
    geo = shapely.set_precision(stransform(BW, unary_union(gs)).simplify(0.00008), 1e-5)
    feats.append({"type": "Feature", "geometry": mapping(geo), "properties": {
        "id": k, "ha": round(ha, 2), "dal": str(ev[1]), "al": str(ev[2]), "focolai": ev[3],
        "dnbr": round(dv, 2), "gravita": cls(dv), "bosco_pascolo": round(vf, 2),
        "lc": {str(c): round(float((L[m] == c).mean()), 2) for c in np.unique(L[m]) if (L[m] == c).mean() >= .05},
        "vincolo": vf >= .5, "affidabilita": "alta" if vf >= .5 or ev[1].month < 9 else "da verificare",
        "edifici_fino": YEAR + 10 if vf >= .5 else None, "destinazione_fino": YEAR + 15 if vf >= .5 else None}})
feats.sort(key=lambda f: -f["properties"]["ha"])
for i, f in enumerate(feats, 1): f["properties"]["id"] = i

slug = NAME.lower().replace(" ", "_")
json.dump({"type": "FeatureCollection", "comune": NAME, "istat": istat, "anno": YEAR,
           "metodo": {"soglia_dnbr": TH, "area_min_ha": MIN_PX * RES * RES / 1e4, "dist_focolaio_m": NEAR_M, "risoluzione_m": RES},
           "confine": mapping(poly.simplify(0.0003)), "features": feats}, open(f"{OUT}/catasto_{slug}_{YEAR}.json", "w"), separators=(",", ":"))
tot = sum(f["properties"]["ha"] for f in feats); vin = sum(f["properties"]["ha"] for f in feats if f["properties"]["vincolo"])
print(f"aree: {len(feats)} | ettari: {tot:.0f} | soggetti a vincolo: {vin:.0f} | top3: {[(f['properties']['ha'], f['properties']['dal']) for f in feats[:3]]}")
