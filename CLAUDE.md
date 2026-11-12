# Fire Tracker Sicilia — regole (leggere a ogni prompt)

## Token: centellinare ogni token
- Risposte brevi, in italiano. Niente riepiloghi di cose già dette, niente elenchi di opzioni scartate.
- Leggere solo il necessario: `head`/`sed -n`/`grep`, `offset/limit`, `max_chars`. Mai file interi se basta un pezzo.
- Mai stampare dati grezzi: riassumere con script (conteggi, min/max, prime 3 righe).
- Dati pesanti in `data/raw/` (lettura vietata): si elaborano solo via script.
- Un comando Bash concatenato invece di tante chiamate; chiamate indipendenti in parallelo.
- Edit puntuali, mai riscrivere file interi. Non rileggere file appena scritti.
- Ricerche ampie / letture web → agente `scout` (Haiku), che restituisce solo la conclusione.
- Niente agenti per compiti da 1-3 chiamate. Niente screenshot se basta `read_page`/`get_page_text`.
- Nessuna dipendenza/build se evitabile: frontend statico (HTML + CDN), Python standard library dove possibile.

## Progetto
- Ruoli: Claude scrive il codice, il maintainer cura design/UX.
- Fase 1: dashboard replay incendi Palermo 24-25 luglio 2023 (FIRMS, vento Open-Meteo/ERA5, terreno 3D).
- `firetrack` (guillaumebdx) non ha licenza: solo ispirazione, non copiare codice.
- Struttura: `scripts/` (Python, prepara dati) → `web/data/*.json` (piccoli) → `web/index.html`.
