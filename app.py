import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from pathlib import Path
from datetime import datetime, time
from io import BytesIO

st.set_page_config(page_title="OEE Spray Dryer", layout="wide")

# ============================================================
# STILE
# ============================================================

st.markdown("""
<style>
.stButton > button[kind="primary"],
.stFormSubmitButton > button[kind="primary"] {
    background-color: #2E7D32 !important;
    color: white !important;
    border: 1px solid #2E7D32 !important;
    font-weight: 700 !important;
}
.stButton > button[kind="secondary"],
.stFormSubmitButton > button[kind="secondary"] {
    border: 1px solid #757575 !important;
    font-weight: 600 !important;
}
.alert-standby {
    background-color: #FFF3CD;
    border-left: 6px solid #FF9800;
    padding: 12px 16px;
    border-radius: 6px;
    color: #4E342E;
    font-weight: 600;
}
.alert-ok {
    background-color: #E8F5E9;
    border-left: 6px solid #2E7D32;
    padding: 12px 16px;
    border-radius: 6px;
    color: #1B5E20;
    font-weight: 600;
}
.small-muted {
    color: #777;
    font-size: 0.9rem;
}
.required-box {
    background-color: #FFF8CC;
    border-left: 6px solid #FFC107;
    padding: 10px 14px;
    border-radius: 6px;
    color: #4E342E;
    font-weight: 600;
    margin-bottom: 8px;
}
.required-ok {
    background-color: #E8F5E9;
    border-left: 6px solid #2E7D32;
    padding: 10px 14px;
    border-radius: 6px;
    color: #1B5E20;
    font-weight: 600;
    margin-bottom: 8px;
}
.field-status-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 8px;
    margin-bottom: 12px;
}
.status-yellow {
    background-color: #FFF8CC;
    border: 2px solid #FFC107;
    border-left: 8px solid #FFC107;
    border-radius: 8px;
    padding: 10px 12px;
    font-weight: 700;
    color: #4E342E;
}
.status-green {
    background-color: #E8F5E9;
    border: 2px solid #2E7D32;
    border-left: 8px solid #2E7D32;
    border-radius: 8px;
    padding: 10px 12px;
    font-weight: 700;
    color: #1B5E20;
}
.status-title {
    font-size: 0.85rem;
    opacity: 0.85;
}
.status-value {
    font-size: 1rem;
    margin-top: 2px;
}
</style>
""", unsafe_allow_html=True)

# ============================================================
# CONFIGURAZIONE
# ============================================================

ADMIN_PASSWORD = "EVRA26%"
STANDARD_ESTRATTO_PURO = 0.40
TURNO_H = 8

TURNI = {
    "1": {"inizio": time(6, 0), "fine": time(14, 0)},
    "2": {"inizio": time(14, 0), "fine": time(22, 0)},
    "3": {"inizio": time(22, 0), "fine": time(6, 0)},
}

TIPI_EVENTO = [
    "Produzione",
    "Attesa prodotto",
    "Attesa analisi",
    "Cambio lotto",
    "Lavaggio",
    "Guasto",
    "Manutenzione programmata",
    "Manutenzione straordinaria",
    "Pulizia",
    "Altro",
]

TIPI_PRODUZIONE = [
    "Apertura lotto",
    "Prosecuzione lotto",
    "Chiusura lotto",
]

CAUSALI_TECNICHE = ["Guasto", "Manutenzione straordinaria"]

CAUSE_NC = [
    "Titolo insufficiente",
    "Umidità alta",
    "Umidità bassa",
    "Granulometria fuori specifica",
    "Densità apparente",
    "Colore",
    "Odore",
    "Microbiologia",
    "Residui solventi",
    "Corpo estraneo",
    "Errore documentale",
    "Altro",
]

DATA_DIR = Path("data")
ASSETS_DIR = Path("assets")

PRODOTTI_FILE = DATA_DIR / "prodotti.csv"
EVENTI_FILE = DATA_DIR / "eventi_turno.csv"
LOTTI_FILE = DATA_DIR / "lotti.csv"

COL_PRODOTTI = [
    "codice_prodotto",
    "descrizione_prodotto",
    "capacita_kg_h",
]

COL_EVENTI = [
    "id_evento",
    "id_turno",
    "data",
    "turno",
    "tipo_evento",
    "tipo_produzione",
    "lotto_molle",
    "codice_prodotto",
    "descrizione_prodotto",
    "ora_inizio",
    "ora_fine",
    "durata_h",
    "kg_molle",
    "residuo_secco",
    "kg_secco_puro",
    "kg_maltodestrina",
    "kg_polvere_teorica",
    "taglio_maltodestrina_pct",
    "estratto_puro_pct",
    "kg_polvere_finale",
    "kg_equivalenti_standard",
    "note",
]

COL_LOTTI = [
    "lotto_molle",
    "codice_prodotto",
    "descrizione_prodotto",
    "data_apertura",
    "data_chiusura",
    "stato_lotto",
    "kg_molle",
    "residuo_secco",
    "kg_secco_puro",
    "kg_maltodestrina",
    "kg_polvere_teorica",
    "taglio_maltodestrina_pct",
    "estratto_puro_pct",
    "kg_polvere_finale",
    "kg_equivalenti_standard",
    "ore_produzione_totali",
    "resa_fisica",
    "resa_equivalente",
    "stato_analisi",
    "kg_conformi",
    "kg_nc",
    "causa_nc",
    "note_nc",
    "data_rilascio_analisi",
]

# ============================================================
# FUNZIONI DATI
# ============================================================

def inizializza_file():
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    if not PRODOTTI_FILE.exists():
        pd.DataFrame(columns=COL_PRODOTTI).to_csv(PRODOTTI_FILE, index=False)

    if not EVENTI_FILE.exists():
        pd.DataFrame(columns=COL_EVENTI).to_csv(EVENTI_FILE, index=False)

    if not LOTTI_FILE.exists():
        pd.DataFrame(columns=COL_LOTTI).to_csv(LOTTI_FILE, index=False)


def leggi_csv(path, colonne):
    inizializza_file()
    df = pd.read_csv(path, dtype=str)

    for col in colonne:
        if col not in df.columns:
            df[col] = ""

    return df[colonne]


def salva_csv(df, path, colonne):
    for col in colonne:
        if col not in df.columns:
            df[col] = ""
    df[colonne].to_csv(path, index=False)


def leggi_prodotti():
    df = leggi_csv(PRODOTTI_FILE, COL_PRODOTTI)

    if df.empty:
        df = pd.DataFrame([{
            "codice_prodotto": "INSERIRE",
            "descrizione_prodotto": "Inserire anagrafica prodotto",
            "capacita_kg_h": "20",
        }])

    df["capacita_kg_h"] = pd.to_numeric(df["capacita_kg_h"], errors="coerce").fillna(20)
    return df


def leggi_eventi():
    return leggi_csv(EVENTI_FILE, COL_EVENTI)


def leggi_lotti():
    return leggi_csv(LOTTI_FILE, COL_LOTTI)


def safe_float(value, default=0.0):
    val = pd.to_numeric(value, errors="coerce")
    if pd.isna(val):
        return default
    return float(val)


def safe_div(num, den):
    try:
        if den is None or den == 0 or pd.isna(den):
            return 0
        return num / den
    except Exception:
        return 0


def nuovo_id():
    return datetime.now().strftime("%Y%m%d%H%M%S%f")


def ore_da_orari(ora_inizio, ora_fine):
    if ora_inizio is None or ora_fine is None:
        return 0

    try:
        dt_i = datetime.combine(datetime.today(), ora_inizio)
        dt_f = datetime.combine(datetime.today(), ora_fine)
        durata = (dt_f - dt_i).total_seconds() / 3600

        if durata < 0:
            durata += 24

        return durata
    except Exception:
        return 0


def parse_time_str(value, fallback):
    try:
        if value in [None, "", "nan"]:
            return fallback
        return datetime.strptime(str(value)[:8], "%H:%M:%S").time()
    except Exception:
        try:
            return datetime.strptime(str(value)[:5], "%H:%M").time()
        except Exception:
            return fallback


def calcola_miscele(kg_molle, residuo_secco, kg_maltodestrina, kg_polvere_finale=None):
    kg_secco_puro = kg_molle * residuo_secco / 100
    kg_polvere_teorica = kg_secco_puro + kg_maltodestrina
    taglio_malto_pct = safe_div(kg_maltodestrina, kg_polvere_teorica) * 100
    estratto_puro_pct = safe_div(kg_secco_puro, kg_polvere_teorica) * 100

    if kg_polvere_finale is None or kg_polvere_finale == "":
        kg_equivalenti = 0
    else:
        kg_equivalenti = safe_float(kg_polvere_finale) * safe_div((estratto_puro_pct / 100), STANDARD_ESTRATTO_PURO)

    return {
        "kg_secco_puro": kg_secco_puro,
        "kg_polvere_teorica": kg_polvere_teorica,
        "taglio_maltodestrina_pct": taglio_malto_pct,
        "estratto_puro_pct": estratto_puro_pct,
        "kg_equivalenti_standard": kg_equivalenti,
    }


def prepara_eventi(df):
    if df.empty:
        return df

    for col in [
        "durata_h",
        "kg_molle",
        "residuo_secco",
        "kg_secco_puro",
        "kg_maltodestrina",
        "kg_polvere_teorica",
        "taglio_maltodestrina_pct",
        "estratto_puro_pct",
        "kg_polvere_finale",
        "kg_equivalenti_standard",
    ]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    df["data"] = pd.to_datetime(df["data"], errors="coerce")
    return df


def prepara_lotti(df):
    if df.empty:
        return df

    for col in [
        "kg_molle",
        "residuo_secco",
        "kg_secco_puro",
        "kg_maltodestrina",
        "kg_polvere_teorica",
        "taglio_maltodestrina_pct",
        "estratto_puro_pct",
        "kg_polvere_finale",
        "kg_equivalenti_standard",
        "ore_produzione_totali",
        "resa_fisica",
        "resa_equivalente",
        "kg_conformi",
        "kg_nc",
    ]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    df["data_apertura"] = pd.to_datetime(df["data_apertura"], errors="coerce")
    df["data_chiusura"] = pd.to_datetime(df["data_chiusura"], errors="coerce")
    return df


def aggiorna_lotti_da_eventi():
    eventi = prepara_eventi(leggi_eventi())
    lotti = leggi_lotti()

    if eventi.empty:
        return

    prod_events = eventi[eventi["tipo_evento"] == "Produzione"].copy()

    if prod_events.empty:
        return

    rows = []

    for lotto, grp in prod_events.groupby("lotto_molle"):
        if str(lotto).strip() == "":
            continue

        aperture = grp[grp["tipo_produzione"] == "Apertura lotto"]
        chiusure = grp[grp["tipo_produzione"] == "Chiusura lotto"]

        if not aperture.empty:
            ap = aperture.iloc[0]
            codice = ap["codice_prodotto"]
            descr = ap["descrizione_prodotto"]
            kg_molle = ap["kg_molle"]
            rs = ap["residuo_secco"]
            kg_puro = ap["kg_secco_puro"]
            kg_malto = ap["kg_maltodestrina"]
            kg_teorica = ap["kg_polvere_teorica"]
            taglio = ap["taglio_maltodestrina_pct"]
            estratto = ap["estratto_puro_pct"]
            data_apertura = ap["data"]
        else:
            codice = grp.iloc[0]["codice_prodotto"]
            descr = grp.iloc[0]["descrizione_prodotto"]
            kg_molle = 0
            rs = 0
            kg_puro = 0
            kg_malto = 0
            kg_teorica = 0
            taglio = 0
            estratto = 0
            data_apertura = grp["data"].min()

        if not chiusure.empty:
            ch = chiusure.iloc[-1]
            kg_finale = ch["kg_polvere_finale"]
            data_chiusura = ch["data"]
            kg_equiv = ch["kg_equivalenti_standard"]

            if kg_equiv == 0 and estratto > 0:
                kg_equiv = kg_finale * safe_div((estratto / 100), STANDARD_ESTRATTO_PURO)

            stato_lotto = "CHIUSO"
            stato_analisi = "ATTESA_ANALISI"
        else:
            kg_finale = 0
            data_chiusura = ""
            kg_equiv = 0
            stato_lotto = "APERTO"
            stato_analisi = "NON_APPLICABILE"

        ore_totali = grp["durata_h"].sum()
        resa_fisica = safe_div(kg_finale, kg_teorica)
        resa_equiv = safe_div(kg_equiv, kg_teorica)

        # Mantiene eventuale esito qualità già registrato
        existing = lotti[lotti["lotto_molle"].astype(str) == str(lotto)] if not lotti.empty else pd.DataFrame()
        if not existing.empty and str(existing.iloc[0].get("stato_analisi", "")) in ["CONFORME", "NON_CONFORME"]:
            stato_analisi = existing.iloc[0]["stato_analisi"]
            kg_conformi = existing.iloc[0].get("kg_conformi", 0)
            kg_nc = existing.iloc[0].get("kg_nc", 0)
            causa_nc = existing.iloc[0].get("causa_nc", "")
            note_nc = existing.iloc[0].get("note_nc", "")
            data_rilascio = existing.iloc[0].get("data_rilascio_analisi", "")
        else:
            kg_conformi = 0
            kg_nc = 0
            causa_nc = ""
            note_nc = ""
            data_rilascio = ""

        rows.append({
            "lotto_molle": lotto,
            "codice_prodotto": codice,
            "descrizione_prodotto": descr,
            "data_apertura": data_apertura,
            "data_chiusura": data_chiusura,
            "stato_lotto": stato_lotto,
            "kg_molle": kg_molle,
            "residuo_secco": rs,
            "kg_secco_puro": kg_puro,
            "kg_maltodestrina": kg_malto,
            "kg_polvere_teorica": kg_teorica,
            "taglio_maltodestrina_pct": taglio,
            "estratto_puro_pct": estratto,
            "kg_polvere_finale": kg_finale,
            "kg_equivalenti_standard": kg_equiv,
            "ore_produzione_totali": ore_totali,
            "resa_fisica": resa_fisica,
            "resa_equivalente": resa_equiv,
            "stato_analisi": stato_analisi,
            "kg_conformi": kg_conformi,
            "kg_nc": kg_nc,
            "causa_nc": causa_nc,
            "note_nc": note_nc,
            "data_rilascio_analisi": data_rilascio,
        })

    out = pd.DataFrame(rows)
    salva_csv(out, LOTTI_FILE, COL_LOTTI)


def crea_excel_completo():
    eventi = leggi_eventi()
    lotti = leggi_lotti()
    prodotti = leggi_prodotti()

    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        eventi.to_excel(writer, sheet_name="Eventi turno", index=False)
        lotti.to_excel(writer, sheet_name="Lotti", index=False)
        prodotti.to_excel(writer, sheet_name="Prodotti", index=False)

        # Foglio sintetico
        eventi_p = prepara_eventi(eventi.copy())
        lotti_p = prepara_lotti(lotti.copy())

        sintesi = pd.DataFrame([{
            "kg_fisici": lotti_p["kg_polvere_finale"].sum() if not lotti_p.empty else 0,
            "kg_equivalenti_standard_40": lotti_p["kg_equivalenti_standard"].sum() if not lotti_p.empty else 0,
            "lotti_totali": len(lotti_p),
            "lotti_aperti": len(lotti_p[lotti_p["stato_lotto"] == "APERTO"]) if not lotti_p.empty else 0,
            "lotti_attesa_analisi": len(lotti_p[lotti_p["stato_analisi"] == "ATTESA_ANALISI"]) if not lotti_p.empty else 0,
        }])
        sintesi.to_excel(writer, sheet_name="Sintesi", index=False)

    output.seek(0)
    return output


def box_campo(nome, compilato):
    if compilato:
        st.markdown(
            f"<div class='required-ok'>✓ {nome} compilato</div>",
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            f"<div class='required-box'>⚠ {nome} da compilare</div>",
            unsafe_allow_html=True
        )


def status_card(label, value, compilato):
    classe = "status-green" if compilato else "status-yellow"
    icona = "🟢" if compilato else "🟡"
    valore = value if value not in [None, ""] else "Da compilare"
    st.markdown(
        f"""
        <div class="{classe}">
            <div class="status-title">{icona} {label}</div>
            <div class="status-value">{valore}</div>
        </div>
        """,
        unsafe_allow_html=True
    )


def avanzamento_compilazione(stati):
    if not stati:
        return
    completati = sum(1 for stato in stati if stato)
    totale = len(stati)
    avanzamento = completati / totale
    st.progress(avanzamento)
    st.caption(f"Avanzamento compilazione: {completati}/{totale} campi obbligatori completati")


def controlla_campi_obbligatori(tipo_evento, evento):
    mancanti = []

    if evento.get("durata_h", 0) <= 0:
        mancanti.append("orario inizio/fine evento valido")

    if tipo_evento == "Produzione":
        if str(evento.get("lotto_molle", "")).strip() == "":
            mancanti.append("lotto molle")

        if evento.get("tipo_produzione") == "Apertura lotto":
            if str(evento.get("codice_prodotto", "")).strip() == "":
                mancanti.append("prodotto")
            if safe_float(evento.get("kg_molle")) <= 0:
                mancanti.append("kg molle")
            if safe_float(evento.get("residuo_secco")) <= 0:
                mancanti.append("residuo secco %")
            if safe_float(evento.get("kg_maltodestrina")) < 0:
                mancanti.append("kg maltodestrina")

        if evento.get("tipo_produzione") == "Chiusura lotto":
            if safe_float(evento.get("kg_polvere_finale")) <= 0:
                mancanti.append("kg polvere finale")

    return mancanti


def importa_excel(uploaded_file):
    xls = pd.ExcelFile(uploaded_file)

    imported = {}

    if "Eventi turno" in xls.sheet_names:
        ev = pd.read_excel(xls, sheet_name="Eventi turno", dtype=str).fillna("")
        imported["eventi"] = ev

    if "Lotti" in xls.sheet_names:
        lo = pd.read_excel(xls, sheet_name="Lotti", dtype=str).fillna("")
        imported["lotti"] = lo

    if "Prodotti" in xls.sheet_names:
        pr = pd.read_excel(xls, sheet_name="Prodotti", dtype=str).fillna("")
        imported["prodotti"] = pr

    return imported


def gauge_oee(valore):
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=valore * 100,
        number={"suffix": "%", "font": {"size": 42}},
        title={"text": "OEE Spray Dryer", "font": {"size": 24}},
        gauge={
            "axis": {"range": [0, 100]},
            "bar": {"thickness": 0.28},
            "steps": [
                {"range": [0, 50], "color": "#ff4b4b"},
                {"range": [50, 65], "color": "#ffa500"},
                {"range": [65, 75], "color": "#ffd966"},
                {"range": [75, 85], "color": "#9be564"},
                {"range": [85, 100], "color": "#2ecc71"},
            ],
            "threshold": {"line": {"color": "black", "width": 4}, "thickness": 0.75, "value": 75},
        },
    ))
    fig.update_layout(height=330, margin=dict(l=30, r=30, t=70, b=20))
    return fig


def calcola_kpi(eventi, lotti):
    eventi = prepara_eventi(eventi.copy())
    lotti = prepara_lotti(lotti.copy())

    if eventi.empty:
        return {
            "availability": 0, "availability_technical": 0, "performance_eq": 0,
            "quality": 0, "oee": 0, "kg_fisici": 0, "kg_equiv": 0,
            "kg_puro": 0, "taglio_medio": 0,
        }

    turni = eventi[["data", "turno"]].drop_duplicates().shape[0]
    tempo_pianificato = turni * TURNO_H

    fermi = eventi[eventi["tipo_evento"] != "Produzione"].copy()
    ore_fermo = fermi["durata_h"].sum() if not fermi.empty else 0
    ore_fermo_tecnico = fermi[fermi["tipo_evento"].isin(CAUSALI_TECNICHE)]["durata_h"].sum() if not fermi.empty else 0

    availability = max(0, safe_div(tempo_pianificato - ore_fermo, tempo_pianificato))
    availability_technical = max(0, safe_div(tempo_pianificato - ore_fermo_tecnico, tempo_pianificato))

    lotti_chiusi = lotti[lotti["stato_lotto"] == "CHIUSO"].copy()
    kg_equiv = lotti_chiusi["kg_equivalenti_standard"].sum() if not lotti_chiusi.empty else 0
    kg_fisici = lotti_chiusi["kg_polvere_finale"].sum() if not lotti_chiusi.empty else 0
    kg_puro = lotti_chiusi["kg_secco_puro"].sum() if not lotti_chiusi.empty else 0
    ore_prod = lotti_chiusi["ore_produzione_totali"].sum() if not lotti_chiusi.empty else 0

    # Capacità media: per semplicità usa capacità prodotto sui lotti chiusi
    prodotti = leggi_prodotti()[["codice_prodotto", "capacita_kg_h"]]
    lotti_cap = lotti_chiusi.merge(prodotti, on="codice_prodotto", how="left") if not lotti_chiusi.empty else lotti_chiusi
    if not lotti_cap.empty:
        lotti_cap["capacita_kg_h"] = pd.to_numeric(lotti_cap["capacita_kg_h"], errors="coerce").fillna(20)
        denominatore = (lotti_cap["capacita_kg_h"] * lotti_cap["ore_produzione_totali"]).sum()
    else:
        denominatore = 0

    performance_eq = safe_div(kg_equiv, denominatore)

    analizzati = lotti[lotti["stato_analisi"].isin(["CONFORME", "NON_CONFORME"])].copy()
    quality = safe_div(analizzati["kg_conformi"].sum(), analizzati["kg_polvere_finale"].sum()) if not analizzati.empty else 0

    oee = availability * performance_eq * quality

    taglio_medio = safe_div(
        (lotti_chiusi["taglio_maltodestrina_pct"] * lotti_chiusi["kg_polvere_finale"]).sum(),
        lotti_chiusi["kg_polvere_finale"].sum()
    ) if not lotti_chiusi.empty else 0

    return {
        "availability": availability,
        "availability_technical": availability_technical,
        "performance_eq": performance_eq,
        "quality": quality,
        "oee": oee,
        "kg_fisici": kg_fisici,
        "kg_equiv": kg_equiv,
        "kg_puro": kg_puro,
        "taglio_medio": taglio_medio,
    }

# ============================================================
# SESSIONE
# ============================================================

inizializza_file()
aggiorna_lotti_da_eventi()

if "eventi_turno_buffer" not in st.session_state:
    st.session_state["eventi_turno_buffer"] = []

if "evento_da_modificare" not in st.session_state:
    st.session_state["evento_da_modificare"] = None

if "salvato" not in st.session_state:
    st.session_state["salvato"] = False


def reset_buffer():
    st.session_state["eventi_turno_buffer"] = []
    st.session_state["evento_da_modificare"] = None

# ============================================================
# APP
# ============================================================

st.title("⚙️ Dashboard OEE Spray Dryer")

if st.session_state["salvato"]:
    st.session_state["salvato"] = False
    st.success("Operazione salvata correttamente.")

tab_turno, tab_lotti, tab_qualita, tab_cruscotto, tab_formule, tab_prodotti, tab_gestione = st.tabs([
    "Turno",
    "Lotti in corso",
    "Qualità",
    "Cruscotto OEE",
    "Assunzioni e formule",
    "Anagrafica prodotti",
    "Gestione dati",
])

# ============================================================
# TURNO
# ============================================================

with tab_turno:
    st.subheader("Compilazione turno tramite eventi")

    c0, c1 = st.columns(2)
    with c0:
        data_turno = st.date_input("Data turno")
    with c1:
        turno = st.selectbox("Turno", ["1", "2", "3"])

    st.markdown("### Stato compilazione dati turno")
    sc1, sc2 = st.columns(2)
    with sc1:
        status_card("Data turno", str(data_turno), data_turno is not None)
    with sc2:
        status_card("Turno", turno, str(turno).strip() != "")

    avanzamento_compilazione([
        data_turno is not None,
        str(turno).strip() != "",
    ])

    st.caption(
        f"Turno {turno}: {TURNI[turno]['inizio'].strftime('%H:%M')} - "
        f"{TURNI[turno]['fine'].strftime('%H:%M')} | Durata pianificata: 8 h"
    )

    st.divider()
    st.markdown("### Aggiungi evento")

    prodotti = leggi_prodotti()
    prodotti["label"] = prodotti["codice_prodotto"].astype(str) + " - " + prodotti["descrizione_prodotto"].astype(str)

    idx_mod = st.session_state["evento_da_modificare"]
    evento_mod = None

    if idx_mod is not None and 0 <= idx_mod < len(st.session_state["eventi_turno_buffer"]):
        evento_mod = st.session_state["eventi_turno_buffer"][idx_mod]
        st.info(f"Modifica attiva: evento {idx_mod + 1} - {evento_mod['tipo_evento']}")

    default_tipo = evento_mod["tipo_evento"] if evento_mod else "Produzione"
    default_tipo_index = TIPI_EVENTO.index(default_tipo) if default_tipo in TIPI_EVENTO else 0

    tipo_evento = st.selectbox("Tipo evento", TIPI_EVENTO, index=default_tipo_index, key="tipo_evento_select")

    status_card("Tipo evento", tipo_evento, str(tipo_evento).strip() != "")

    if tipo_evento != "Produzione":
        st.caption("Evento di fermo: non sono richiesti prodotto, lotto o quantità.")

    with st.form("form_evento", clear_on_submit=False):
        default_start = parse_time_str(evento_mod["ora_inizio"] if evento_mod else "", TURNI[turno]["inizio"])
        default_end = parse_time_str(evento_mod["ora_fine"] if evento_mod else "", TURNI[turno]["fine"])

        c2, c3 = st.columns(2)
        with c2:
            ora_inizio = st.time_input("Ora inizio evento", value=default_start)
        with c3:
            ora_fine = st.time_input("Ora fine evento", value=default_end)

        durata_h = ore_da_orari(ora_inizio, ora_fine)

        if durata_h <= 0:
            st.warning("Inserire ora inizio e ora fine evento valide.")
        else:
            st.metric("Durata evento", f"{durata_h:.2f} h")

        so1, so2, so3 = st.columns(3)
        with so1:
            status_card("Ora inizio", str(ora_inizio), ora_inizio is not None)
        with so2:
            status_card("Ora fine", str(ora_fine), ora_fine is not None)
        with so3:
            status_card("Durata evento", f"{durata_h:.2f} h", durata_h > 0)

        evento = {
            "tipo_evento": tipo_evento,
            "tipo_produzione": "",
            "lotto_molle": "",
            "codice_prodotto": "",
            "descrizione_prodotto": "",
            "ora_inizio": str(ora_inizio),
            "ora_fine": str(ora_fine),
            "durata_h": durata_h,
            "kg_molle": 0.0,
            "residuo_secco": 0.0,
            "kg_secco_puro": 0.0,
            "kg_maltodestrina": 0.0,
            "kg_polvere_teorica": 0.0,
            "taglio_maltodestrina_pct": 0.0,
            "estratto_puro_pct": 0.0,
            "kg_polvere_finale": 0.0,
            "kg_equivalenti_standard": 0.0,
            "note": "",
        }

        if tipo_evento == "Produzione":
            default_tipo_prod = evento_mod["tipo_produzione"] if evento_mod else "Apertura lotto"
            default_tipo_prod_idx = TIPI_PRODUZIONE.index(default_tipo_prod) if default_tipo_prod in TIPI_PRODUZIONE else 0

            tipo_produzione = st.selectbox(
                "Tipo produzione",
                TIPI_PRODUZIONE,
                index=default_tipo_prod_idx,
                help="Apertura: inserisci dati di composizione. Prosecuzione: solo lotto e orari. Chiusura: lotto, orari e kg polvere finale."
            )

            evento["tipo_produzione"] = tipo_produzione

            lotti = leggi_lotti()
            lotti_aperti = lotti[lotti["stato_lotto"].astype(str) == "APERTO"]["lotto_molle"].dropna().astype(str).tolist() if not lotti.empty else []

            if tipo_produzione == "Apertura lotto":
                lotto_molle = st.text_input("Lotto molle", value=evento_mod["lotto_molle"] if evento_mod else "")

                labels = prodotti["label"].tolist()
                default_prod_idx = 0
                if evento_mod and evento_mod["codice_prodotto"]:
                    matches = prodotti.index[prodotti["codice_prodotto"].astype(str) == str(evento_mod["codice_prodotto"])].tolist()
                    if matches:
                        default_prod_idx = prodotti.index.get_loc(matches[0])

                if evento_mod:
                    prodotto_label = st.selectbox("Prodotto", labels, index=default_prod_idx)
                else:
                    prodotto_label = st.selectbox("Prodotto", ["-- Seleziona prodotto --"] + labels, index=0)

                prodotto = None if prodotto_label == "-- Seleziona prodotto --" else prodotti[prodotti["label"] == prodotto_label].iloc[0]

                p1, p2, p3 = st.columns(3)
                with p1:
                    kg_molle = st.number_input("Kg molle", min_value=0.0, step=1.0, value=float(evento_mod["kg_molle"]) if evento_mod else 0.0)
                with p2:
                    residuo_secco = st.number_input("Residuo secco %", min_value=0.0, max_value=100.0, step=0.1, value=float(evento_mod["residuo_secco"]) if evento_mod else 0.0)
                with p3:
                    kg_maltodestrina = st.number_input("Kg maltodestrina aggiunta", min_value=0.0, step=1.0, value=float(evento_mod["kg_maltodestrina"]) if evento_mod else 0.0)

                mix = calcola_miscele(kg_molle, residuo_secco, kg_maltodestrina)

                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Kg secco puro", f"{mix['kg_secco_puro']:.2f}")
                m2.metric("Kg polvere teorica", f"{mix['kg_polvere_teorica']:.2f}")
                m3.metric("Taglio maltodestrina", f"{mix['taglio_maltodestrina_pct']:.1f}%")
                m4.metric("Estratto puro", f"{mix['estratto_puro_pct']:.1f}%")

                st.markdown("#### Stato campi apertura lotto")
                ss1, ss2, ss3 = st.columns(3)
                with ss1:
                    status_card("Lotto molle", lotto_molle, str(lotto_molle).strip() != "")
                with ss2:
                    status_card("Prodotto", prodotto_label, prodotto is not None)
                with ss3:
                    status_card("Kg molle", f"{kg_molle:.1f}", kg_molle > 0)

                ss4, ss5, ss6 = st.columns(3)
                with ss4:
                    status_card("Residuo secco %", f"{residuo_secco:.1f}%", residuo_secco > 0)
                with ss5:
                    status_card("Maltodestrina", f"{kg_maltodestrina:.1f} kg", kg_maltodestrina >= 0)
                with ss6:
                    status_card("Polvere teorica", f"{mix['kg_polvere_teorica']:.1f} kg", mix["kg_polvere_teorica"] > 0)

                avanzamento_compilazione([
                    str(lotto_molle).strip() != "",
                    prodotto is not None,
                    kg_molle > 0,
                    residuo_secco > 0,
                    kg_maltodestrina >= 0,
                    mix["kg_polvere_teorica"] > 0,
                ])

                evento.update({
                    "lotto_molle": lotto_molle,
                    "codice_prodotto": "" if prodotto is None else prodotto["codice_prodotto"],
                    "descrizione_prodotto": "" if prodotto is None else prodotto["descrizione_prodotto"],
                    "kg_molle": kg_molle,
                    "residuo_secco": residuo_secco,
                    "kg_secco_puro": mix["kg_secco_puro"],
                    "kg_maltodestrina": kg_maltodestrina,
                    "kg_polvere_teorica": mix["kg_polvere_teorica"],
                    "taglio_maltodestrina_pct": mix["taglio_maltodestrina_pct"],
                    "estratto_puro_pct": mix["estratto_puro_pct"],
                })

            elif tipo_produzione == "Prosecuzione lotto":
                options = ["-- Inserisci manualmente --"] + lotti_aperti
                scelta = st.selectbox("Lotto molle aperto", options)

                if scelta == "-- Inserisci manualmente --":
                    lotto_molle = st.text_input("Lotto molle")
                else:
                    lotto_molle = scelta

                st.caption("Prosecuzione lotto: inserire solo lotto e orari. La composizione viene presa dall'apertura.")

                status_card("Lotto molle", lotto_molle, str(lotto_molle).strip() != "")
                avanzamento_compilazione([
                    str(lotto_molle).strip() != "",
                    durata_h > 0,
                ])

                evento.update({"lotto_molle": lotto_molle})

            elif tipo_produzione == "Chiusura lotto":
                options = ["-- Inserisci manualmente --"] + lotti_aperti
                scelta = st.selectbox("Lotto molle da chiudere", options)

                if scelta == "-- Inserisci manualmente --":
                    lotto_molle = st.text_input("Lotto molle")
                else:
                    lotto_molle = scelta

                kg_polvere_finale = st.number_input("Kg polvere finale ottenuta", min_value=0.0, step=1.0, value=float(evento_mod["kg_polvere_finale"]) if evento_mod else 0.0)

                st.markdown("#### Stato campi chiusura lotto")
                sca1, sca2 = st.columns(2)
                with sca1:
                    status_card("Lotto molle", lotto_molle, str(lotto_molle).strip() != "")
                with sca2:
                    status_card("Kg polvere finale", f"{kg_polvere_finale:.1f} kg", kg_polvere_finale > 0)

                avanzamento_compilazione([
                    str(lotto_molle).strip() != "",
                    kg_polvere_finale > 0,
                    durata_h > 0,
                ])

                # Recupera composizione da lotto aperto, se presente
                lotti_all = prepara_lotti(leggi_lotti())
                rec = lotti_all[lotti_all["lotto_molle"].astype(str) == str(lotto_molle)] if not lotti_all.empty else pd.DataFrame()

                if not rec.empty:
                    base = rec.iloc[0]
                    estratto_puro_pct = base["estratto_puro_pct"]
                    kg_equiv = kg_polvere_finale * safe_div((estratto_puro_pct / 100), STANDARD_ESTRATTO_PURO)

                    st.info(
                        f"Composizione recuperata da apertura: estratto puro {estratto_puro_pct:.1f}% | "
                        f"kg equivalenti standard 40% = {kg_equiv:.2f}"
                    )

                    evento.update({
                        "lotto_molle": lotto_molle,
                        "codice_prodotto": base["codice_prodotto"],
                        "descrizione_prodotto": base["descrizione_prodotto"],
                        "kg_molle": base["kg_molle"],
                        "residuo_secco": base["residuo_secco"],
                        "kg_secco_puro": base["kg_secco_puro"],
                        "kg_maltodestrina": base["kg_maltodestrina"],
                        "kg_polvere_teorica": base["kg_polvere_teorica"],
                        "taglio_maltodestrina_pct": base["taglio_maltodestrina_pct"],
                        "estratto_puro_pct": estratto_puro_pct,
                        "kg_polvere_finale": kg_polvere_finale,
                        "kg_equivalenti_standard": kg_equiv,
                    })
                else:
                    st.warning("Lotto non trovato tra i lotti aperti. Sarà comunque salvato, ma l'equivalente resterà 0 finché non sarà presente un'apertura lotto.")
                    evento.update({
                        "lotto_molle": lotto_molle,
                        "kg_polvere_finale": kg_polvere_finale,
                    })

        else:
            note = st.text_area("Note evento", value=evento_mod["note"] if evento_mod else "")
            evento["note"] = note

        st.markdown("#### Controllo campi obbligatori")
        mancanti_preview = controlla_campi_obbligatori(tipo_evento, evento)

        if not mancanti_preview:
            st.markdown(
                "<div class='required-ok'>✓ Tutti i campi obbligatori dell'evento sono compilati.</div>",
                unsafe_allow_html=True
            )
        else:
            for campo in mancanti_preview:
                st.markdown(
                    f"<div class='required-box'>⚠ Campo obbligatorio da completare: {campo}</div>",
                    unsafe_allow_html=True
                )

        if evento_mod is None:
            submit_evento = st.form_submit_button("Aggiungi evento al turno", type="primary")
            submit_modifica = False
            submit_annulla = False
        else:
            b1, b2 = st.columns(2)
            with b1:
                submit_modifica = st.form_submit_button("Salva modifiche evento", type="primary")
            with b2:
                submit_annulla = st.form_submit_button("Annulla modifica", type="secondary")
            submit_evento = False

    if submit_evento or submit_modifica:
        mancanti = controlla_campi_obbligatori(tipo_evento, evento)

        if mancanti:
            st.error("Completa i campi obbligatori: " + ", ".join(mancanti))
        elif tipo_evento == "Produzione" and durata_h < (1 / 60):
            st.error("La produzione deve durare almeno 1 minuto.")
        else:
            if submit_modifica and idx_mod is not None:
                st.session_state["eventi_turno_buffer"][idx_mod] = evento
                st.session_state["evento_da_modificare"] = None
            else:
                st.session_state["eventi_turno_buffer"].append(evento)

            st.rerun()

    if submit_annulla:
        st.session_state["evento_da_modificare"] = None
        st.rerun()

    st.divider()
    st.markdown("### Eventi inseriti nel turno")

    eventi_buffer = pd.DataFrame(st.session_state["eventi_turno_buffer"])

    if eventi_buffer.empty:
        st.info("Nessun evento inserito.")
    else:
        st.dataframe(eventi_buffer, use_container_width=True)

        st.markdown("### Gestione evento selezionato")

        indice_evento = st.selectbox(
            "Seleziona evento",
            range(len(eventi_buffer)),
            format_func=lambda x: (
                f"{x + 1} - {eventi_buffer.iloc[x]['tipo_evento']} "
                f"{eventi_buffer.iloc[x].get('tipo_produzione', '')} "
                f"({eventi_buffer.iloc[x]['ora_inizio']} - {eventi_buffer.iloc[x]['ora_fine']})"
            )
        )

        g1, g2, g3 = st.columns(3)
        with g1:
            if st.button("Modifica evento", type="primary"):
                st.session_state["evento_da_modificare"] = indice_evento
                st.rerun()
        with g2:
            if st.button("Elimina evento", type="secondary"):
                st.session_state["eventi_turno_buffer"].pop(indice_evento)
                st.session_state["evento_da_modificare"] = None
                st.rerun()
        with g3:
            if st.button("Duplica evento", type="secondary"):
                nuovo = st.session_state["eventi_turno_buffer"][indice_evento].copy()
                st.session_state["eventi_turno_buffer"].insert(indice_evento + 1, nuovo)
                st.rerun()

        ore_produzione = eventi_buffer[eventi_buffer["tipo_evento"] == "Produzione"]["durata_h"].sum()
        ore_fermo = eventi_buffer[eventi_buffer["tipo_evento"] != "Produzione"]["durata_h"].sum()
        copertura = ore_produzione + ore_fermo

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Ore produzione", f"{ore_produzione:.2f}")
        c2.metric("Ore fermo", f"{ore_fermo:.2f}")
        c3.metric("Copertura turno", f"{safe_div(copertura, TURNO_H):.1%}")
        c4.metric("Kg teorici apertura", f"{eventi_buffer['kg_polvere_teorica'].sum():.1f}")

        scostamento = copertura - TURNO_H

        if abs(scostamento) <= 0.01:
            st.markdown("<div class='alert-ok'>Copertura turno corretta: gli eventi coprono le 8 ore pianificate.</div>", unsafe_allow_html=True)
        elif scostamento > 0:
            st.markdown(f"<div class='alert-standby'>Attenzione: gli eventi superano il turno di {scostamento:.2f} h. Il turno resta in stand-by.</div>", unsafe_allow_html=True)
        else:
            st.markdown(f"<div class='alert-standby'>Attenzione: mancano {abs(scostamento):.2f} h per coprire le 8 ore. Il turno resta in stand-by.</div>", unsafe_allow_html=True)

        r1, r2 = st.columns(2)
        with r1:
            if st.button("Svuota eventi turno", type="secondary"):
                reset_buffer()
                st.rerun()

        with r2:
            if st.button("Salva turno", type="primary"):
                if abs(copertura - TURNO_H) > 0.01:
                    st.error("Turno non salvato: la somma degli eventi non coincide con le 8 ore pianificate.")
                    st.stop()

                id_turno = nuovo_id()
                eventi_storico = leggi_eventi()

                rows = []
                for i, ev in enumerate(st.session_state["eventi_turno_buffer"], start=1):
                    row = {
                        "id_evento": f"{id_turno}-E{i}",
                        "id_turno": id_turno,
                        "data": str(data_turno),
                        "turno": turno,
                    }
                    row.update(ev)
                    rows.append(row)

                eventi_storico = pd.concat([eventi_storico, pd.DataFrame(rows)], ignore_index=True)
                salva_csv(eventi_storico, EVENTI_FILE, COL_EVENTI)
                aggiorna_lotti_da_eventi()

                reset_buffer()
                st.session_state["salvato"] = True
                st.rerun()

# ============================================================
# LOTTI IN CORSO
# ============================================================

with tab_lotti:
    st.subheader("📦 Lotti in corso e lotti chiusi")

    aggiorna_lotti_da_eventi()
    lotti = prepara_lotti(leggi_lotti())

    if lotti.empty:
        st.info("Nessun lotto registrato.")
    else:
        f1, f2 = st.columns(2)
        with f1:
            stato_filter = st.selectbox("Filtro stato lotto", ["Tutti", "APERTO", "CHIUSO"])
        with f2:
            analisi_filter = st.selectbox("Filtro stato analisi", ["Tutti", "NON_APPLICABILE", "ATTESA_ANALISI", "CONFORME", "NON_CONFORME"])

        lotti_f = lotti.copy()

        if stato_filter != "Tutti":
            lotti_f = lotti_f[lotti_f["stato_lotto"] == stato_filter]

        if analisi_filter != "Tutti":
            lotti_f = lotti_f[lotti_f["stato_analisi"] == analisi_filter]

        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Lotti aperti", len(lotti[lotti["stato_lotto"] == "APERTO"]))
        k2.metric("Lotti attesa analisi", len(lotti[lotti["stato_analisi"] == "ATTESA_ANALISI"]))
        k3.metric("Kg fisici chiusi", f"{lotti['kg_polvere_finale'].sum():.1f}")
        k4.metric("Kg equivalenti 40%", f"{lotti['kg_equivalenti_standard'].sum():.1f}")

        st.dataframe(lotti_f, use_container_width=True)

# ============================================================
# QUALITÀ
# ============================================================

with tab_qualita:
    st.subheader("🧪 Rilascio qualità")

    aggiorna_lotti_da_eventi()
    lotti = prepara_lotti(leggi_lotti())

    attesa = lotti[lotti["stato_analisi"] == "ATTESA_ANALISI"].copy() if not lotti.empty else lotti

    if attesa.empty:
        st.info("Nessun lotto in attesa analisi.")
    else:
        attesa["label"] = (
            attesa["lotto_molle"].astype(str) + " | " +
            attesa["codice_prodotto"].astype(str) + " | " +
            attesa["data_chiusura"].dt.strftime("%d/%m/%Y")
        )

        label = st.selectbox("Seleziona lotto", attesa["label"].tolist())
        lotto_sel = attesa[attesa["label"] == label].iloc[0]

        st.write("Prodotto:", lotto_sel["descrizione_prodotto"])
        st.write("Kg polvere finale:", lotto_sel["kg_polvere_finale"])
        st.write("Kg equivalenti standard 40%:", lotto_sel["kg_equivalenti_standard"])

        with st.form("form_qualita"):
            esito = st.radio("Esito", ["CONFORME", "NON_CONFORME"], horizontal=True)

            if esito == "CONFORME":
                kg_conformi = float(lotto_sel["kg_polvere_finale"])
                kg_nc = 0.0
                causa_nc = ""
                note_nc = ""
                st.metric("Kg conformi", f"{kg_conformi:.2f}")
            else:
                kg_conformi = st.number_input("Kg conformi", min_value=0.0, max_value=float(lotto_sel["kg_polvere_finale"]), step=1.0)
                kg_nc = max(float(lotto_sel["kg_polvere_finale"]) - kg_conformi, 0)
                st.metric("Kg NC", f"{kg_nc:.2f}")
                causa_nc = st.selectbox("Causa NC", CAUSE_NC)
                note_nc = st.text_area("Note NC")

            data_rilascio = st.date_input("Data rilascio analisi")
            salva_q = st.form_submit_button("Salva esito analisi", type="primary")

        if salva_q:
            df = leggi_lotti()
            mask = df["lotto_molle"].astype(str) == str(lotto_sel["lotto_molle"])

            for col, val in {
                "stato_analisi": esito,
                "kg_conformi": kg_conformi,
                "kg_nc": kg_nc,
                "causa_nc": causa_nc,
                "note_nc": note_nc,
                "data_rilascio_analisi": str(data_rilascio),
            }.items():
                df[col] = df[col].astype("object")
                df.loc[mask, col] = str(val)

            salva_csv(df, LOTTI_FILE, COL_LOTTI)
            st.session_state["salvato"] = True
            st.rerun()

# ============================================================
# CRUSCOTTO
# ============================================================

with tab_cruscotto:
    st.subheader("📊 Cruscotto OEE")

    aggiorna_lotti_da_eventi()
    eventi = prepara_eventi(leggi_eventi())
    lotti = prepara_lotti(leggi_lotti())

    if eventi.empty:
        st.info("Nessun dato disponibile.")
    else:
        kpi = calcola_kpi(eventi, lotti)

        a, b = st.columns([1.2, 1])

        with a:
            st.plotly_chart(gauge_oee(kpi["oee"]), use_container_width=True)

        with b:
            st.metric("Disponibilità operativa", f"{kpi['availability']:.1%}")
            st.metric("Disponibilità tecnica", f"{kpi['availability_technical']:.1%}")
            st.metric("Performance equivalente", f"{kpi['performance_eq']:.1%}")
            st.metric("Qualità", f"{kpi['quality']:.1%}")

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Kg fisici", f"{kpi['kg_fisici']:.1f}")
        m2.metric("Kg equivalenti 40%", f"{kpi['kg_equiv']:.1f}")
        m3.metric("Kg secco puro", f"{kpi['kg_puro']:.1f}")
        m4.metric("Taglio medio", f"{kpi['taglio_medio']:.1f}%")

        st.divider()

        c1, c2 = st.columns(2)

        with c1:
            fermi = eventi[eventi["tipo_evento"] != "Produzione"]
            if fermi.empty:
                st.info("Nessun fermo registrato.")
            else:
                fermi_g = fermi.groupby("tipo_evento", as_index=False)["durata_h"].sum()
                st.plotly_chart(px.bar(fermi_g, x="tipo_evento", y="durata_h", title="Ore fermo per causale"), use_container_width=True)

        with c2:
            if lotti.empty:
                st.info("Nessun lotto.")
            else:
                lotti_g = lotti.groupby("stato_analisi", as_index=False)["lotto_molle"].count()
                st.plotly_chart(px.bar(lotti_g, x="stato_analisi", y="lotto_molle", title="Lotti per stato qualità"), use_container_width=True)

        st.divider()

        excel_data = crea_excel_completo()
        st.download_button(
            label="📥 Scarica Excel completo",
            data=excel_data,
            file_name="oee_spray_dryer_export.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
        )

# ============================================================
# ASSUNZIONI E FORMULE
# ============================================================

with tab_formule:
    st.subheader("📖 Assunzioni e formule")

    image_path = ASSETS_DIR / "oee_reference.jpeg"
    if image_path.exists():
        st.image(str(image_path), caption="Schema generale OEE - Availability × Performance × Quality", use_container_width=True)

    st.markdown("""
## 1. Formula generale OEE

`OEE = Disponibilità × Performance × Qualità`

---

## 2. Disponibilità

`Disponibilità operativa = (Tempo pianificato - Tutti i fermi) / Tempo pianificato`

Il tempo pianificato è pari a **8 ore per turno**.

Sono considerati fermi operativi:
- Attesa prodotto
- Attesa analisi
- Cambio lotto
- Lavaggio
- Guasto
- Manutenzione programmata
- Manutenzione straordinaria
- Pulizia
- Altro

La **Disponibilità tecnica** considera solo:
- Guasto
- Manutenzione straordinaria

---

## 3. Performance equivalente

La produzione fisica non è sempre confrontabile perché i prodotti possono avere percentuali diverse di maltodestrina.

Per questo motivo la dashboard calcola una performance basata sui **kg equivalenti standard al 40% di estratto puro**.

### Standard aziendale

Prodotto standard:

- **40% estratto puro**
- **60% maltodestrina**

### Esempio di equivalenza

Prodotto standard 60/40:

- 100 kg di prodotto standard contengono 40 kg di estratto puro.

Prodotto reale 70/30:

- 100 kg di prodotto reale contengono 30 kg di estratto puro e 70 kg di maltodestrina.

Ci chiediamo:

**A quanti kg di prodotto standard al 40% corrispondono quei 30 kg di puro?**

Nel prodotto standard:

`0,40 × X = 30`

quindi:

`X = 30 / 0,40 = 75`

Conclusione:

**100 kg di prodotto al 70/30 equivalgono a 75 kg di prodotto standard al 60/40**, perché contengono la stessa quantità di estratto puro.

---

## 4. Calcoli lotto

L'operatore inserisce in apertura lotto:

- kg molle
- residuo secco %
- kg maltodestrina aggiunta

La dashboard calcola:

### Kg secco puro

`kg secco puro = kg molle × residuo secco % / 100`

### Kg polvere teorica

`kg polvere teorica = kg secco puro + kg maltodestrina`

### Taglio maltodestrina

`taglio % = kg maltodestrina / kg polvere teorica × 100`

### Estratto puro %

`estratto puro % = kg secco puro / kg polvere teorica × 100`

### Kg equivalenti standard

Alla chiusura del lotto, dopo aver inserito i kg di polvere finale:

`kg equivalenti standard = kg polvere finale × (estratto puro % / 40%)`

---

## 5. Qualità

La qualità viene calcolata solo sui lotti rilasciati dal laboratorio.

`Qualità = kg conformi / kg prodotti analizzati`

---

## 6. OEE finale

`OEE = Disponibilità operativa × Performance equivalente × Qualità`
""")

# ============================================================
# ANAGRAFICA PRODOTTI
# ============================================================

with tab_prodotti:
    st.subheader("📚 Anagrafica prodotti")

    prodotti = leggi_prodotti()
    st.dataframe(prodotti, use_container_width=True)

    with st.form("form_prodotto"):
        codice = st.text_input("Codice prodotto")
        descrizione = st.text_input("Descrizione prodotto")
        capacita = st.number_input("Capacità nominale equivalente kg/h", min_value=0.0, value=20.0, step=1.0)
        salva_p = st.form_submit_button("Salva prodotto", type="primary")

    if salva_p:
        if codice.strip() == "" or descrizione.strip() == "":
            st.error("Inserisci codice e descrizione.")
        else:
            nuovo = pd.DataFrame([{
                "codice_prodotto": codice.strip(),
                "descrizione_prodotto": descrizione.strip(),
                "capacita_kg_h": capacita,
            }])

            prodotti = pd.concat([prodotti, nuovo], ignore_index=True)
            prodotti = prodotti.drop_duplicates(subset=["codice_prodotto"], keep="last")
            salva_csv(prodotti, PRODOTTI_FILE, COL_PRODOTTI)
            st.session_state["salvato"] = True
            st.rerun()

    st.divider()

    st.download_button(
        label="📥 Scarica anagrafica prodotti Excel",
        data=crea_excel_completo(),
        file_name="oee_spray_dryer_anagrafica_e_dati.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="secondary",
    )

# ============================================================
# GESTIONE DATI
# ============================================================

with tab_gestione:
    st.subheader("🔒 Gestione dati riservata")

    password = st.text_input("Password gestione", type="password")

    if password != ADMIN_PASSWORD:
        st.info("Inserisci la password per modificare o cancellare dati già salvati.")
        st.stop()

    st.success("Accesso gestione abilitato.")

    eventi = leggi_eventi()
    lotti = leggi_lotti()

    st.markdown("## Eventi turno")
    st.dataframe(eventi, use_container_width=True)

    if not eventi.empty:
        id_evento = st.selectbox("Evento da eliminare", eventi["id_evento"].astype(str).tolist())
        if st.button("Elimina evento selezionato", type="secondary"):
            eventi = eventi[eventi["id_evento"].astype(str) != str(id_evento)]
            salva_csv(eventi, EVENTI_FILE, COL_EVENTI)
            aggiorna_lotti_da_eventi()
            st.session_state["salvato"] = True
            st.rerun()

    st.markdown("## Lotti")
    st.dataframe(lotti, use_container_width=True)

    if not lotti.empty:
        lotto_del = st.selectbox("Lotto da eliminare", lotti["lotto_molle"].astype(str).tolist())
        if st.button("Elimina lotto e relativi eventi", type="secondary"):
            lotti = lotti[lotti["lotto_molle"].astype(str) != str(lotto_del)]
            eventi = eventi[eventi["lotto_molle"].astype(str) != str(lotto_del)]
            salva_csv(lotti, LOTTI_FILE, COL_LOTTI)
            salva_csv(eventi, EVENTI_FILE, COL_EVENTI)
            st.session_state["salvato"] = True
            st.rerun()

    st.divider()

    st.markdown("## Export e ripristino dati")

    excel_data = crea_excel_completo()
    st.download_button(
        label="📥 Scarica Excel completo",
        data=excel_data,
        file_name="oee_spray_dryer_export.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary",
    )

    eventi_xlsx = BytesIO()
    with pd.ExcelWriter(eventi_xlsx, engine="openpyxl") as writer:
        leggi_eventi().to_excel(writer, sheet_name="Eventi turno", index=False)
    eventi_xlsx.seek(0)

    st.download_button(
        label="📥 Scarica solo eventi Excel",
        data=eventi_xlsx,
        file_name="oee_spray_dryer_eventi.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="secondary",
    )

    uploaded = st.file_uploader(
        "Carica Excel di backup per ripristino",
        type=["xlsx"],
        help="Puoi caricare l'export completo generato dalla dashboard. Il ripristino è protetto da password."
    )

    if uploaded is not None:
        try:
            imported = importa_excel(uploaded)

            st.info(
                "File letto correttamente. Contenuto trovato: "
                + ", ".join(imported.keys())
            )

            conferma_import = st.checkbox(
                "Confermo di voler sostituire i dati attuali con quelli del file caricato"
            )

            if st.button("Ripristina dati da Excel", type="primary"):
                if not conferma_import:
                    st.error("Per procedere devi confermare la sostituzione dei dati.")
                    st.stop()

                if "eventi" in imported:
                    salva_csv(imported["eventi"], EVENTI_FILE, COL_EVENTI)

                if "lotti" in imported:
                    salva_csv(imported["lotti"], LOTTI_FILE, COL_LOTTI)

                if "prodotti" in imported:
                    salva_csv(imported["prodotti"], PRODOTTI_FILE, COL_PRODOTTI)

                aggiorna_lotti_da_eventi()
                st.session_state["salvato"] = True
                st.rerun()

        except Exception as e:
            st.error(f"Errore durante la lettura del file Excel: {e}")

    st.divider()

    if st.button("Cancella tutto lo storico eventi", type="secondary"):
        pd.DataFrame(columns=COL_EVENTI).to_csv(EVENTI_FILE, index=False)
        pd.DataFrame(columns=COL_LOTTI).to_csv(LOTTI_FILE, index=False)
        st.session_state["salvato"] = True
        st.rerun()
