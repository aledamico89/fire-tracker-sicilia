"""Rotte dei mezzi aerei antincendio sopra la Sicilia, dagli archivi giornalieri open data di adsb.lol (ODbL).
Legge il .tar a flusso e tiene solo: Canadair/aerei antincendio (tipo ICAO o immatricolazione I-DPC…, nominativo CAN…)
ed elicotteri a bassa quota, con almeno un punto nel riquadro della Sicilia.
Uso: python3 scripts/aerei.py file.tar | -  [--append]   ("-" = archivio da stdin, es. curl -sL URL | ...) → web/data/aerei.json"""
import gzip, json, os, sys, tarfile

BBOX = (12.3, 36.5, 15.8, 38.4)
FIRE_TYPES = {"CL2P", "CL2T", "CL4T", "CL5T", "AT3T", "AT5T", "AT6T", "AT8T", "C130"}
STEP = 20   # secondi tra due punti conservati
inside = lambda lat, lon: BBOX[1] <= lat <= BBOX[3] and BBOX[0] <= lon <= BBOX[2]

def keep(d, cs, heli):
    t, r = d.get("t") or "", (d.get("r") or "").upper()
    if t in FIRE_TYPES or r.startswith("I-DPC") or cs.startswith("CAN"): return "aereo"
    if heli: return "elicottero"
    return None

OUT = "web/data/aerei.json"
out = json.load(open(OUT)) if "--append" in sys.argv and os.path.exists(OUT) else []
stats = {"letti": 0, "in_sicilia": 0}
for path in [a for a in sys.argv[1:] if a != "--append"]:
    with (tarfile.open(fileobj=sys.stdin.buffer, mode="r|") if path == "-" else tarfile.open(path, "r|")) as tf:
        for m in tf:
            if not m.isfile() or "trace_full_" not in m.name: continue
            raw = tf.extractfile(m).read()
            try: d = json.loads(gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw)
            except Exception: continue
            stats["letti"] += 1
            base, tr = d.get("timestamp", 0), d.get("trace", [])
            pts = [p for p in tr if inside(p[1], p[2])]
            if not pts: continue
            stats["in_sicilia"] += 1
            cs, heli = "", False
            for p in tr:
                a = p[8] if len(p) > 8 and isinstance(p[8], dict) else None
                if a:
                    cs = cs or (a.get("flight") or "").strip()
                    heli = heli or a.get("category") == "A7"
            kind = keep(d, cs, heli)
            if not kind: continue
            if kind == "elicottero" and all(isinstance(p[3], (int, float)) and p[3] > 4000 for p in pts): continue
            last, rows = -1e9, []
            for p in pts:
                t = base + p[0]
                if t - last >= STEP:
                    alt = p[3] if isinstance(p[3], (int, float)) else 0
                    rows.append([int(t), round(p[2], 4), round(p[1], 4), int(alt)]); last = t
            key = (d.get("icao"), rows[0][0] // 86400)
            out = [x for x in out if (x["icao"], x["pts"][0][0] // 86400) != key]
            out.append({"icao": d.get("icao"), "r": d.get("r"), "t": d.get("t"), "desc": d.get("desc"), "cs": cs, "tipo": kind, "pts": rows})
json.dump(out, open(OUT, "w"), separators=(",", ":"))
a = [x for x in out if x["tipo"] == "aereo"]; e = [x for x in out if x["tipo"] == "elicottero"]
print(f"tracce lette {stats['letti']}, sopra la Sicilia {stats['in_sicilia']} | aerei antincendio {len(a)}, elicotteri bassa quota {len(e)}")
for x in sorted(out, key=lambda x: -len(x["pts"]))[:12]:
    print(" ", x["tipo"], x["r"], x["t"], x["cs"], "punti", len(x["pts"]), "dalle", __import__("time").strftime("%H:%M", __import__("time").gmtime(x["pts"][0][0])), "UTC")
