"""Rassegna stampa per comune e anno: verifica i link e abbina ogni articolo alle aree bruciate
(data compatibile + località citata). Input: data/raw/stampa_<comune>_<anno>_raw.json (raccolta curata).
Uso: python3 scripts/stampa.py monreale 2023 → web/data/stampa_<comune>_<anno>.json"""
import json, sys, urllib.request
from datetime import date, timedelta

SLUG, YEAR = sys.argv[1], sys.argv[2]
raw = json.load(open(f"data/raw/stampa_{SLUG}_{YEAR}_raw.json"))
d = json.load(open(f"web/data/catasto_{SLUG}_{YEAR}.json"))
im = json.load(open(f"web/data/impatto_{SLUG}_{YEAR}.json"))["aree"]
norm = lambda s: s.lower().replace("'", "").replace("’", "").replace(" ", "")

def ok(u):
    try:
        r = urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0 fire-tracker-sicilia"}), timeout=20)
        return r.status < 400
    except Exception as e:
        return getattr(e, "code", 0) in (401, 403)   # alcuni siti bloccano i bot ma la pagina esiste

out = []
for a in raw:
    if not a.get("url", "").startswith("https://") or not ok(a["url"]):
        print("scartato (link non raggiungibile):", a.get("url")); continue
    da = date.fromisoformat(a["data"]); luoghi = [norm(l) for l in a.get("luoghi", []) if len(l) > 3]
    aree = []
    for f in d["features"]:
        p = f["properties"]
        if p["affidabilita"] != "alta" or not (date.fromisoformat(p["dal"]) - timedelta(1) <= da <= date.fromisoformat(p["al"]) + timedelta(4)): continue
        loc = [norm(l) for l in im.get(str(p["id"]), {}).get("localita", [])]
        if any(l in x or x in l for l in luoghi for x in loc): aree.append(p["id"])
    a["aree"] = aree
    out.append({k: a[k] for k in ("data", "testata", "titolo", "url", "sintesi", "fatti", "luoghi", "match", "aree") if k in a})
json.dump(out, open(f"web/data/stampa_{SLUG}_{YEAR}.json", "w"), ensure_ascii=False, separators=(",", ":"))
print(f"articoli: {len(out)}/{len(raw)} | abbinati ad aree: {sum(1 for a in out if a['aree'])}")
