# EVRA Dashboard Streamlit

Dashboard web per analisi produzioni, semilavorati, reparti, taglio malto, mass yield e formulazioni.

## Avvio locale

```bash
pip install -r requirements.txt
streamlit run app.py
```

## File dati

I file sono nella cartella `data/`:
- `commesse.xlsx`
- `reparti.xlsx`

## Note calcolo

Mass Yield:
- dal 2026, se disponibili molle e residuo: `Molle * %RS / Droga`
- altrimenti: `(Semilavorato prodotto - Maltodestrina) / Droga`
- se non calcolabile: ND

Taglio malto:
- `Maltodestrina / Semilavorato prodotto`, massimo 98%

DER:
- estratto dalla descrizione, gestendo anche range tipo `3-4:1` come valore medio.
