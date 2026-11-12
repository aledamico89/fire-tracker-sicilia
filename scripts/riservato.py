"""Sposta le particelle catastali dal file pubblico a un file cifrato (AES-256-GCM, chiave da PBKDF2-SHA256).
La chiave di ogni comune sta in .secrets/chiavi.json (escluso da git). Uso: python3 scripts/riservato.py monreale 2023"""
import base64, json, os, secrets, sys
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

SLUG, YEAR = sys.argv[1], sys.argv[2]
PUB, PRIV, KEYS, ITER = f"web/data/catasto_{SLUG}_{YEAR}.json", f"web/data/riservato_{SLUG}_{YEAR}.json", ".secrets/chiavi.json", 600_000
os.makedirs(".secrets", exist_ok=True)
keys = json.load(open(KEYS)) if os.path.exists(KEYS) else {}
if SLUG not in keys:   # 25 caratteri senza simboli ambigui, ~125 bit
    a = "abcdefghjkmnpqrstuvwxyz23456789"
    keys[SLUG] = "-".join("".join(secrets.choice(a) for _ in range(5)) for _ in range(5))
    json.dump(keys, open(KEYS, "w"), indent=1)

d = json.load(open(PUB))
old = {}
if os.path.exists(PRIV):   # conserva particelle già cifrate se il file pubblico non le ha più
    e = json.load(open(PRIV)); b = lambda k: base64.b64decode(e[k])
    key = PBKDF2HMAC(hashes.SHA256(), 32, b("salt"), e["iter"]).derive(keys[SLUG].encode())
    old = json.loads(AESGCM(key).decrypt(b("iv"), b("ct"), None))
par = {}
for f in d["features"]:
    p = f["properties"]; k = str(p["id"])
    par[k] = p.pop("particelle", None) or old.get(k, [])
    p["n_particelle"] = len(par[k])
salt, iv = secrets.token_bytes(16), secrets.token_bytes(12)
key = PBKDF2HMAC(hashes.SHA256(), 32, salt, ITER).derive(keys[SLUG].encode())
ct = AESGCM(key).encrypt(iv, json.dumps(par, separators=(",", ":")).encode(), None)
enc = lambda x: base64.b64encode(x).decode()
json.dump({"alg": "AES-256-GCM", "kdf": "PBKDF2-SHA256", "iter": ITER, "salt": enc(salt), "iv": enc(iv), "ct": enc(ct)}, open(PRIV, "w"))
json.dump(d, open(PUB, "w"), separators=(",", ":"))
print(f"particelle cifrate: {sum(map(len, par.values()))} in {PRIV} | chiave in {KEYS}")
