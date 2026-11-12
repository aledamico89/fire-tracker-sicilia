"""Modello di probabilità di innesco per comune e giorno (Gradient Boosting).
Addestra 2014-2021, valida su 2022-2025 (anni mai visti), confronta con FWI e storico,
poi riaddestra su tutto e salva models/fire_model.joblib + web/data/model.json."""
import csv, json
from collections import defaultdict
import numpy as np, joblib
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.inspection import permutation_importance
from sklearn.metrics import roc_auc_score, average_precision_score
from features import FEATURES, daily, calendar, statics
from fetch_era5 import grid_points, YEARS

def build():
    st = statics(); _, gp = grid_points(); n = len(st)
    ign = defaultdict(int); per_year = defaultdict(lambda: [0] * n)
    for d, c in csv.reader(open("data/raw/ignitions.csv")):
        ign[(d, int(c))] = 1; per_year[int(d[:4])][int(c)] += 1
    X, y, yr = [], [], []
    for Y in YEARS:
        prev = np.sum([per_year[k] for k in range(2001, Y)], axis=0) / (Y - 2001)
        D = json.load(open(f"data/raw/era5_{Y}.json"))
        feats = [daily(g["time"], g["temperature_2m_max"], g["relative_humidity_2m_min"], g["wind_speed_10m_max"], g["precipitation_sum"]) for g in D]
        dates = D[0]["time"]
        for k, d in enumerate(dates):
            cal = calendar(d)
            for c in range(n):
                X.append(feats[gp[c]][k] + st[c] + [prev[c]] + cal); y.append(ign.get((d, c), 0)); yr.append(Y)
    return np.array(X, np.float32), np.array(y, np.int8), np.array(yr)

def lift(y, s, top=.1):
    k = int(len(s) * top); return y[np.argsort(-s)[:k]].sum() / y.sum()

if __name__ == "__main__":
    X, y, yr = build(); f = FEATURES.index
    print("righe:", len(y), "| inneschi:", int(y.sum()), "| tasso:", round(y.mean(), 5), flush=True)
    tr, te = yr <= 2021, yr >= 2022
    params = dict(learning_rate=.05, max_iter=400, max_leaf_nodes=31, min_samples_leaf=200, l2_regularization=1.0, early_stopping=True, random_state=0)
    m = HistGradientBoostingClassifier(**params).fit(X[tr], y[tr])
    p = m.predict_proba(X[te])[:, 1]; yt = y[te]
    hist = X[te, f("hist_rate")]; fw = X[te, f("fwi")]
    fcls = np.digitize(fw, [5.2, 11.2, 21.3, 38, 50]); hl = np.digitize(hist, np.quantile(X[tr, f("hist_rate")], [.6, .9]))
    scores = {"Modello ML": p, "Solo FWI (meteo)": fw, "Solo storico comune": hist, "Priorità attuale (FWI + storico)": fcls + hl + fw / 1000}
    metrics = {k: {"auroc": round(roc_auc_score(yt, s), 3), "auprc": round(average_precision_score(yt, s), 4), "top10": round(lift(yt, s), 3)} for k, s in scores.items()}
    for k, v in metrics.items(): print(f"{k:34s} AUROC {v['auroc']}  AUPRC {v['auprc']}  top10% {v['top10']:.0%}")
    idx = np.random.default_rng(0).choice(np.where(te)[0], 300000, replace=False)
    pi = permutation_importance(m, X[idx], y[idx], scoring="average_precision", n_repeats=3, random_state=0, n_jobs=-1)
    imp = sorted(zip(FEATURES, pi.importances_mean), key=lambda t: -t[1])
    print("importanza:", [(k, round(v, 4)) for k, v in imp[:8]])
    final = HistGradientBoostingClassifier(**{**params, "early_stopping": False, "max_iter": m.n_iter_}).fit(X, y)
    joblib.dump(final, "models/fire_model.joblib", compress=3)
    json.dump({"features": FEATURES, "base_rate": float(y.mean()), "train": "2014-2021", "test": "2022-2025", "n_test_ign": int(yt.sum()),
               "metrics": metrics, "importance": [[k, round(float(v), 5)] for k, v in imp]}, open("web/data/model.json", "w"), indent=1)
    print("salvato, iterazioni:", m.n_iter_)
