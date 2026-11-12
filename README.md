# Fire Tracker Sicilia

Dashboard open source per visualizzare e studiare gli incendi in Sicilia.
Prima tappa: **replay degli incendi del 22–28 luglio 2023** (Palermo, 24–25 luglio) con focolai satellitari, vento orario e terreno 3D.

**Demo:** https://aledamico89.github.io/fire-tracker-sicilia/

## Cosa mostra
- Focolai rilevati da satellite (NASA FIRMS, MODIS + VIIRS), colorati per età: giallo = appena rilevato, rosso scuro = più di 12 ore.
- Vento a 10 m, temperatura e umidità orarie (rianalisi ERA5 via Open-Meteo).
- Terreno 3D, timeline con play e istogramma dei focolai.

## Analisi dell'evento
- **Pericolo incendi:** Fire Weather Index (FWI) giornaliero calcolato dai dati meteo, classi EFFIS. Il 25 luglio a Palermo: 57,5, classe *estremo*.
- **Qualità dell'aria:** PM10 orario in 9 città (modello CAMS). Picchi vicino a 90 µg/m³ a Palermo e Messina, limite UE 50.
- **Comuni colpiti:** comuni con almeno un focolaio e popolazione residente (160 nell'intera settimana).

## Storico 2001–2025 (`storico.html`)
- 28.793 rilevazioni satellitari MODIS (Etna, impianti industriali e falsi positivi esclusi), circa 15.600 inneschi stimati.
- **Dove brucia sempre:** 725 aree di circa 1 km² bruciate in almeno 5 anni diversi.
- **Quando:** stagionalità; nel weekend gli inneschi sono il 12% in più che nei giorni feriali, un indizio di origine umana.
- **Scheda comune** stampabile in PDF: inneschi, anni con incendi, ultimo anno, posizione in Sicilia. Monreale è prima e ha bruciato in tutti i 25 anni.

## Rischio previsto (`rischio.html`)
- **Pericolo meteo:** FWI per ognuno dei 391 comuni, oggi e i 6 giorni successivi, ricalcolato **ogni mattina** in automatico da GitHub Actions (`scripts/forecast.py`).
- **Priorità:** pericolo meteo + propensione storica del comune. Formula trasparente, spiegata nella pagina.
- **Modello ML:** probabilità di innesco per comune e giorno, espressa come multiplo della media siciliana.
- Scheda comune con temperatura, umidità, vento e collegamento alla scheda storica.

### Modello ML (`scripts/model.py`)
Gradient boosting (scikit-learn) su 1,7 milioni di righe comune × giorno, 2014–2025. Input: meteo giornaliero ERA5 e indici FWI, quota, superficie, densità abitativa, storico degli inneschi **solo degli anni precedenti**, calendario. Etichetta: innesco MODIS stimato (nessun focolaio entro 2 km nei 3 giorni prima). Addestrato su 2014–2021, valutato su anni mai visti 2022–2025:

| Metodo | AUROC | AUPRC | Inneschi nel 10% più a rischio |
|---|---|---|---|
| **Modello ML** | **0,92** | **0,077** | **75%** |
| Priorità (FWI + storico) | 0,87 | 0,040 | 57% |
| Solo storico comune | 0,83 | 0,022 | 49% |
| Solo FWI | 0,84 | 0,021 | 47% |

Variabili più importanti: storico del comune, periodo dell'anno, temperatura massima, superficie, FFMC. Limiti: l'addestramento usa ERA5 su griglia di 50 km, la previsione usa dati previsionali al centroide del comune; MODIS non vede i piccoli incendi. La probabilità assoluta resta bassa (media 0,4% per comune al giorno): conta il confronto relativo.

## Rigenerare i dati
```bash
python3 scripts/prepare_data.py
```
```bash
python3 scripts/analysis.py
python3 scripts/history.py
python3 scripts/fetch_era5.py   # ~1 h, limiti Open-Meteo
python3 scripts/model.py       # richiede scikit-learn
python3 scripts/forecast.py
```
Scrivono `web/data/*.json`. Libreria standard Python, salvo `model.py` e la parte ML di `forecast.py` (scikit-learn). Il calcolo FWI (`scripts/fwi.py`) riproduce il caso di riferimento di Van Wagner.

## Vedere in locale
```bash
python3 -m http.server 8000 -d web
```

## Roadmap
1. Analisi evento e storico (fatto) · dati live (prossimo)
2. Rischio previsto FWI per comune (fatto) · modello machine learning (fatto)
3. Simulatore di propagazione interattivo

## Limiti
Prototipo di ricerca e divulgazione, **non è un sistema di allerta**. Un focolaio è un pixel caldo visto dal satellite, non un perimetro; fumo e nuvole possono nasconderlo. Il meteo è una rianalisi su griglia di circa 50 km.

## Fonti e licenze
- Codice: MIT.
- Focolai: [NASA FIRMS](https://firms.modaps.eosdis.nasa.gov). Meteo e aria: [Open-Meteo](https://open-meteo.com) (CC BY 4.0), Copernicus ERA5 e CAMS. Comuni: [openpolis](https://github.com/openpolis/geojson-italy) (CC BY 4.0), popolazione © OpenStreetMap (ODbL).
- Terreno: Mapzen Terrain Tiles (AWS Open Data). Immagini: [Sentinel-2 cloudless by EOX](https://s2maps.eu) (CC BY-NC-SA 4.0, uso non commerciale).

Costruito con [Claude Code](https://claude.com/claude-code).
