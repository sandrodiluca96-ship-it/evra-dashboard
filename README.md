# EVRA Dashboard Streamlit - versione aggiornata

Questa versione aggiorna la logica reparti:

- trend mensile per reparto
- esclusione Pastorizzazione e Concentrazione
- aggregazione delle lavorazioni di Granulazione
- Estrazione calcolata dagli scarichi MDR presenti nell'esplosione commesse
- utilizzo del termine "Lavorato" al posto di "Carico"
- istogrammi separati per reparto, con scale indipendenti
- semilavorati trattati come stock che poi vengono lavorati in Miscelazione al momento dell'ordine

## Avvio locale

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Aggiornamento su Streamlit Cloud

Sostituire nel repository GitHub:
- `app.py`
- `data/commesse.xlsx`
- `data/reparti.xlsx`
