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

## Rigenerare i dati
```bash
python3 scripts/prepare_data.py
```
```bash
python3 scripts/analysis.py
```
Scrivono `web/data/*.json`. Solo libreria standard Python. Il calcolo FWI (`scripts/fwi.py`) riproduce il caso di riferimento di Van Wagner.

## Vedere in locale
```bash
python3 -m http.server 8000 -d web
```

## Roadmap
1. Dashboard storica e live (in corso)
2. Modello di rischio giornaliero (baseline: dataset Mesogeos)
3. Simulatore di propagazione interattivo

## Limiti
Prototipo di ricerca e divulgazione, **non è un sistema di allerta**. Un focolaio è un pixel caldo visto dal satellite, non un perimetro; fumo e nuvole possono nasconderlo. Il meteo è una rianalisi su griglia di circa 50 km.

## Fonti e licenze
- Codice: MIT.
- Focolai: [NASA FIRMS](https://firms.modaps.eosdis.nasa.gov). Meteo e aria: [Open-Meteo](https://open-meteo.com) (CC BY 4.0), Copernicus ERA5 e CAMS. Comuni: [openpolis](https://github.com/openpolis/geojson-italy) (CC BY 4.0), popolazione © OpenStreetMap (ODbL).
- Terreno: Mapzen Terrain Tiles (AWS Open Data). Immagini: [Sentinel-2 cloudless by EOX](https://s2maps.eu) (CC BY-NC-SA 4.0, uso non commerciale).

Costruito con [Claude Code](https://claude.com/claude-code).
