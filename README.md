# EVRA Dashboard 🌿

Dashboard Streamlit completa con:
- Produzione
- Reparti
- Famiglie prodotto
- Semilavorati
- Formulazioni/maltodestrina
- Acquisti
- Vendite
- Business Intelligence

## File inclusi
- data/commesse.xlsx
- data/reparti.xlsx
- data/acquisti.xlsx
- data/vendite.xlsx
- assets/evra_logo.svg

## Avvio locale
```bash
pip install -r requirements.txt
streamlit run app.py
```


Aggiornamento: tema dark sobrio, colori attenuati, titolo con fogliolina.


Aggiornamento v9: KPI homepage filtrati per anno, unità di misura, trend globali acquisti/vendite e trend cliente/fornitore.


v10: correzione filtro anni vendite/acquisti, cumulativi mensili, rimozione Business Intelligence, dettaglio cliente in Vendite e dettaglio fornitore in Acquisti.


v12: anno corrente giallo, filtri codice/descrizione visibili, sezioni riviste, semilavorati rimossi come sezione autonoma, formulazioni su medie aritmetiche e dettagli codice, acquisti/vendite con ricerca articolo.


v13: cumulativi acquisti/verifica anni, 2026 giallo coerente, filtri ricercabili codice+descrizione, grafici famiglia corretti, istogramma malto composto.


v14: 2026 giallo anche vendite, filtri selectbox ricercabili codice|descrizione, dettaglio codice a linea, top vendite separati fluidi/secchi.


v15: mass yield per droga MDR lavorata, filtro acquisti ristretto a MDR/ME/estratti, trend annuali aggiunti oltre ai cumulativi.
\n\nv16: correzione definitiva Mass Yield su droga MDR, tabella semilavorati con mass yield/taglio medio, filtro acquisti difensivo su codici validi.\n\n\nv17: percentuali Mass Yield/taglio espresse come 20% e non 0,2; trend vendite con metrica fatturato/quantità.\n\n\nv18: trend annuo Mass Yield/taglio per droga, tabella per codice droga, filtro droga, trend acquisti/vendite con scelta separata valore-quantità.\n\n\nv19: grafici e tabelle Mass Yield/taglio costruiti direttamente per codice droga MDR lavorata.\n

v20: sezione Estrazione semplificata con KPI Mass Yield/taglio e ricerche operative per droga e semilavorato.


v21: top codici coerenti con filtro anni e Mass Yield totale ponderata sui kg droga.


v22: resa calcolata solo come Extract Yield = (kg semilavorato - kg malto) / kg droga, solo quando il lotto ha una sola MDR distinta e dati coerenti.


v23: sezione Vendite separata tra Fluidi ed Estratti secchi finiti.


v24: trend annuali con annualizzazione opzionale dell'anno corrente.
\n\nv25: aggiunta ricerca formulazione per lotto con percentuali di tutti i materiali utilizzati.\n