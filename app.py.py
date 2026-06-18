
import re
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(
    page_title="EVRA Dashboard",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
.stApp {
    background: radial-gradient(circle at top left, #162238 0%, #0b1020 45%, #070b14 100%);
    color: #eef2ff;
}
.block-container { padding-top: 1rem; padding-bottom: 2rem; }
h1, h2, h3 { color: #eef2ff; }
div[data-testid="stMetric"] {
    background: rgba(18, 24, 42, 0.96);
    border: 1px solid #26314d;
    padding: 16px;
    border-radius: 18px;
    box-shadow: 0 8px 24px rgba(0,0,0,0.25);
}
div[data-testid="stMetricLabel"] { color: #9aa4bf; }
div[data-testid="stMetricValue"] { color: #eef2ff; }
section[data-testid="stSidebar"] {
    background: #090e1c;
    border-right: 1px solid #26314d;
}
.stTabs [data-baseweb="tab"] {
    background: #12182a;
    border: 1px solid #26314d;
    border-radius: 999px;
    color: #eef2ff;
    padding: 8px 16px;
}
.stTabs [aria-selected="true"] { background: #1f4e78 !important; }
.small-note { color:#9aa4bf; font-size:0.9rem; }
</style>
""", unsafe_allow_html=True)

DATA_DIR = Path(__file__).parent / "data"
COMMESSE_PATH = DATA_DIR / "commesse.xlsx"
REPARTI_PATH = DATA_DIR / "reparti.xlsx"


# -----------------------------
# Helpers
# -----------------------------
def is_semilav(code):
    return str(code).startswith(("W", "Y"))

def is_mdr(code):
    return str(code).startswith("MDR")

def is_malto(code, desc):
    text = (str(code) + " " + str(desc)).lower()
    return str(code).startswith("MECMLT") or "maltodestrina" in text or "malto" in text

def uso_da_suffisso(code):
    code = str(code)
    if not code:
        return "ND"
    if code[-1] == "A":
        return "Alimentare"
    if code[-1] == "C":
        return "Cosmetico"
    if code[-1] == "P":
        return "Feed"
    return "ND"

def famiglia(code):
    code = str(code)
    if code.startswith(("W", "Y")):
        return "Semilavorato"
    if code.startswith("F"):
        return "Fluido"
    if code.startswith("V"):
        return "Conto lavoro"
    if code.startswith(("A", "S", "T")):
        return "Estratto secco finito"
    if code.startswith("MDR"):
        return "Droga vegetale"
    if code.startswith("ME"):
        return "Materia prima / carrier"
    return "Altro"

def titolato(desc):
    return "%" in str(desc)

def extract_der(desc):
    s = str(desc).replace(",", ".")
    m = re.search(r"(\d+(?:\.\d+)?)\s*[-–]\s*(\d+(?:\.\d+)?)\s*:\s*1", s, re.I)
    if m:
        return (float(m.group(1)) + float(m.group(2))) / 2
    m = re.search(r"(\d+(?:\.\d+)?)\s*:\s*1", s, re.I)
    if m:
        return float(m.group(1))
    return np.nan

def normalize_reparto(desc):
    d = str(desc).strip().lower()
    if not d:
        return "ND"
    if "gran" in d:
        return "Granulazione"
    if "misc" in d or "mescol" in d:
        return "Miscelazione"
    if "atom" in d or "spray" in d:
        return "Atomizzazione"
    if "micr" in d:
        return "Micronizzazione"
    if "fluid" in d or "flui" in d:
        return "Fluidi"
    if "estr" in d:
        return "Estrazione"
    return str(desc).strip()

def is_excluded_reparto(desc):
    d = str(desc).lower()
    return ("past" in d) or ("concent" in d)

def format_kg(v):
    try:
        return f"{float(v):,.0f}".replace(",", ".")
    except Exception:
        return "0"

def percent_fmt(v):
    if pd.isna(v):
        return "ND"
    return f"{float(v)*100:.1f}%"

@st.cache_data(show_spinner=False)
def load_commesse(path):
    df = pd.read_excel(path)
    for c in ["CODART", "ARDESART", "LOTTO_FINITO", "COD_COMP", "DES_COMP", "LOTTO"]:
        if c in df.columns:
            df[c] = df[c].fillna("").astype(str).str.strip()
    df["DATA_COM"] = pd.to_datetime(df["DATA_COM"], errors="coerce")
    for c in ["QTA_FINITO", "QTA_LOTTO", "MOL_QTAKG", "MOL_RESIDUO", "MOL_TAGLIO"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
    return df

@st.cache_data(show_spinner=False)
def load_reparti(path):
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_excel(path)
    for c in df.columns:
        if df[c].dtype == object:
            df[c] = df[c].fillna("").astype(str).str.strip()
    return df

@st.cache_data(show_spinner=False)
def build_model(comm, rep):
    lots = comm.groupby(["CODART", "LOTTO_FINITO"], as_index=False).agg(
        Descrizione=("ARDESART", "first"),
        Data=("DATA_COM", "max"),
        Kg=("QTA_FINITO", "first"),
    )
    lots["Anno"] = lots["Data"].dt.year
    lots["Mese"] = lots["Data"].dt.to_period("M").astype(str)
    lots["Famiglia"] = lots["CODART"].apply(famiglia)
    lots["Uso"] = lots["CODART"].apply(uso_da_suffisso)
    lots["DER"] = lots["Descrizione"].apply(extract_der)
    lots["Titolato"] = lots["Descrizione"].apply(titolato)

    detail = comm.groupby(["CODART", "LOTTO_FINITO", "COD_COMP"], as_index=False).agg(
        Descrizione_PF=("ARDESART", "first"),
        Descrizione_Componente=("DES_COMP", "first"),
        Data=("DATA_COM", "max"),
        Kg_PF=("QTA_FINITO", "first"),
        Kg_Componente=("QTA_LOTTO", "sum"),
    )
    detail["Pct_Utilizzo"] = np.where(detail["Kg_PF"] > 0, detail["Kg_Componente"] / detail["Kg_PF"], np.nan)
    detail["Semilavorato"] = detail["COD_COMP"].apply(is_semilav)
    detail["Malto_Diretta"] = detail.apply(lambda r: is_malto(r["COD_COMP"], r["Descrizione_Componente"]), axis=1)

    # Semilavorati
    sem_src = comm[comm["CODART"].apply(is_semilav)].copy()
    sem_records = []
    for (code, lotto), g in sem_src.groupby(["CODART", "LOTTO_FINITO"]):
        qta_fin = float(g["QTA_FINITO"].iloc[0]) if len(g) else 0
        desc = g["ARDESART"].iloc[0] if len(g) else ""
        data = g["DATA_COM"].max()
        malto_qty = g[g.apply(lambda r: is_malto(r["COD_COMP"], r["DES_COMP"]), axis=1)]["QTA_LOTTO"].sum()
        mdr_qty = g[g["COD_COMP"].apply(is_mdr)]["QTA_LOTTO"].sum()

        taglio = np.nan
        if qta_fin > 0:
            taglio = min(malto_qty / qta_fin, 0.98)

        mass_yield = np.nan
        if pd.notna(data) and data.year >= 2026 and mdr_qty > 0 and {"MOL_QTAKG", "MOL_RESIDUO"}.issubset(g.columns):
            mol = g[["MOL_QTAKG", "MOL_RESIDUO"]].drop_duplicates()
            mol = mol[(mol["MOL_QTAKG"] > 0) & (mol["MOL_RESIDUO"] > 0)]
            if len(mol):
                rs = mol["MOL_RESIDUO"].astype(float)
                rs_frac = np.where(rs > 1, rs / 100, rs)
                secco_eq = (mol["MOL_QTAKG"].astype(float).values * rs_frac).sum()
                if secco_eq > 0:
                    mass_yield = secco_eq / mdr_qty

        if pd.isna(mass_yield) and mdr_qty > 0:
            mass_yield = (qta_fin - malto_qty) / mdr_qty
            if mass_yield < 0:
                mass_yield = np.nan

        sem_records.append({
            "Codice": code,
            "Descrizione": desc,
            "Lotto": lotto,
            "Data": data,
            "Kg": qta_fin,
            "Taglio_Malto": taglio,
            "Mass_Yield": mass_yield,
            "DER": extract_der(desc),
        })

    sem_lotti = pd.DataFrame(sem_records)
    if len(sem_lotti):
        sem_master = sem_lotti.groupby("Codice", as_index=False).agg(
            Descrizione=("Descrizione", "first"),
            Kg=("Kg", "sum"),
            N_Lotti=("Lotto", "nunique"),
            Taglio_Malto=("Taglio_Malto", "mean"),
            Mass_Yield=("Mass_Yield", "mean"),
            DER=("DER", "mean"),
        )
    else:
        sem_master = pd.DataFrame(columns=["Codice", "Descrizione", "Kg", "N_Lotti", "Taglio_Malto", "Mass_Yield", "DER"])

    # PF formulazioni ultima produzione
    sem_taglio = sem_master.set_index("Codice")["Taglio_Malto"].to_dict() if len(sem_master) else {}
    latest = lots.sort_values(["CODART", "Data", "LOTTO_FINITO"], ascending=[True, False, False]).groupby("CODART").head(1)
    latest_detail = detail.merge(latest[["CODART", "LOTTO_FINITO"]], on=["CODART", "LOTTO_FINITO"], how="inner")

    pf_rows = []
    for (code, lotto), g in latest_detail.groupby(["CODART", "LOTTO_FINITO"]):
        desc = g["Descrizione_PF"].iloc[0]
        kg_pf = g["Kg_PF"].iloc[0]
        sem_pct = g.loc[g["Semilavorato"], "Pct_Utilizzo"].sum()
        malto_dir = g.loc[g["Malto_Diretta"], "Pct_Utilizzo"].sum()
        malto_sem = 0
        sem_codes = []
        for _, r in g[g["Semilavorato"]].iterrows():
            sem_codes.append(r["COD_COMP"])
            taglio = sem_taglio.get(r["COD_COMP"], np.nan)
            if pd.isna(taglio):
                taglio = 0.60
            malto_sem += r["Pct_Utilizzo"] * taglio

        pf_rows.append({
            "Codice": code,
            "Descrizione": desc,
            "Lotto": lotto,
            "Kg_Lotto": kg_pf,
            "Famiglia": famiglia(code),
            "Uso": uso_da_suffisso(code),
            "Titolato": "%" in str(desc),
            "DER": extract_der(desc),
            "Semilav_%": sem_pct,
            "Malto_Diretta_%": malto_dir,
            "Malto_da_Semilav_%": malto_sem,
            "Malto_Totale_%": malto_dir + malto_sem,
            "Semilavorati": " | ".join(sorted(set(sem_codes))),
        })

    pf_form = pd.DataFrame(pf_rows)

    # Reparti lavorati
    reparto_rows = []

    if rep is not None and len(rep):
        art_col = next((c for c in rep.columns if "Articolo" in c and "Caricato" in c), None)
        desc_lav_col = next((c for c in rep.columns if "Descrizione" in c and "Lavorazione" in c), None)
        data_rep_col = next((c for c in rep.columns if "Data" in c and "carico" in c), None)
        qty_rep_col = next((c for c in rep.columns if "Quant" in c and "caric" in c), None)
        comm_col = next((c for c in rep.columns if "Commessa" in c), None)

        if art_col and desc_lav_col:
            rep_tmp = rep.copy()
            rep_tmp["Descrizione_Reparto_Originale"] = rep_tmp[desc_lav_col].astype(str).str.strip()
            rep_tmp = rep_tmp[~rep_tmp["Descrizione_Reparto_Originale"].apply(is_excluded_reparto)].copy()
            rep_tmp = rep_tmp[~rep_tmp["Descrizione_Reparto_Originale"].str.lower().str.contains("estr", na=False)].copy()

            rep_tmp["Reparto"] = rep_tmp["Descrizione_Reparto_Originale"].apply(normalize_reparto)
            rep_tmp["Codice"] = rep_tmp[art_col].astype(str).str.strip()
            rep_tmp["Data"] = pd.to_datetime(rep_tmp[data_rep_col], errors="coerce") if data_rep_col else pd.NaT
            rep_tmp["Kg_Lavorato"] = pd.to_numeric(rep_tmp[qty_rep_col], errors="coerce").fillna(0) if qty_rep_col else 0
            rep_tmp["Commessa"] = rep_tmp[comm_col].astype(str).str.strip() if comm_col else ""
            reparto_rows.append(rep_tmp[["Reparto", "Codice", "Commessa", "Data", "Kg_Lavorato"]])

    # Estrazione calcolata da MDR in commesse
    mdr = comm[comm["COD_COMP"].apply(is_mdr)].copy()
    if len(mdr):
        mdr_rep = pd.DataFrame({
            "Reparto": "Estrazione",
            "Codice": mdr["COD_COMP"],
            "Commessa": mdr["LOTTO_FINITO"],
            "Data": mdr["DATA_COM"],
            "Kg_Lavorato": mdr["QTA_LOTTO"],
        })
        reparto_rows.append(mdr_rep)

    if reparto_rows:
        rep_work = pd.concat(reparto_rows, ignore_index=True)
        rep_work = rep_work.dropna(subset=["Data"])
        rep_work["Anno"] = rep_work["Data"].dt.year.astype(int)
        rep_work["Mese"] = rep_work["Data"].dt.to_period("M").astype(str)

        rep_summary = rep_work.groupby("Reparto", as_index=False).agg(
            Kg_Lavorato=("Kg_Lavorato", "sum"),
            N_Righe=("Codice", "size"),
            N_Codici=("Codice", "nunique"),
            N_Commesse=("Commessa", "nunique"),
        ).sort_values("Kg_Lavorato", ascending=False)

        rep_year = rep_work.groupby(["Reparto", "Anno"], as_index=False).agg(
            Kg_Lavorato=("Kg_Lavorato", "sum"),
            N_Codici=("Codice", "nunique"),
            N_Commesse=("Commessa", "nunique"),
        )

        rep_month = rep_work.groupby(["Reparto", "Mese"], as_index=False).agg(
            Kg_Lavorato=("Kg_Lavorato", "sum"),
            N_Codici=("Codice", "nunique"),
            N_Commesse=("Commessa", "nunique"),
        )
    else:
        rep_work = pd.DataFrame(columns=["Reparto", "Codice", "Commessa", "Data", "Kg_Lavorato", "Anno", "Mese"])
        rep_summary = pd.DataFrame(columns=["Reparto", "Kg_Lavorato", "N_Righe", "N_Codici", "N_Commesse"])
        rep_year = pd.DataFrame(columns=["Reparto", "Anno", "Kg_Lavorato", "N_Codici", "N_Commesse"])
        rep_month = pd.DataFrame(columns=["Reparto", "Mese", "Kg_Lavorato", "N_Codici", "N_Commesse"])

    return lots, detail, sem_master, sem_lotti, pf_form, rep_work, rep_summary, rep_year, rep_month


def reparto_section(reparto, rep_work, rep_year, rep_month):
    st.subheader(reparto)

    rw = rep_work[rep_work["Reparto"] == reparto].copy()
    ry = rep_year[rep_year["Reparto"] == reparto].copy()
    rm = rep_month[rep_month["Reparto"] == reparto].copy()

    if rw.empty:
        st.warning(f"Nessun dato disponibile per {reparto}.")
        return

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Kg lavorati", format_kg(rw["Kg_Lavorato"].sum()))
    c2.metric("N° commesse", format_kg(rw["Commessa"].nunique()))
    c3.metric("N° codici", format_kg(rw["Codice"].nunique()))
    c4.metric("Kg medi/commessa", format_kg(rw.groupby("Commessa")["Kg_Lavorato"].sum().mean()))

    left, right = st.columns(2)

    with left:
        fig = px.bar(
            ry.sort_values("Anno"),
            x="Anno",
            y="Kg_Lavorato",
            title=f"{reparto} - lavorato annuo",
            text_auto=".2s",
        )
        fig.update_layout(template="plotly_dark", height=380)
        st.plotly_chart(fig, use_container_width=True)

    with right:
        top = rw.groupby("Codice", as_index=False).agg(Kg_Lavorato=("Kg_Lavorato", "sum")).sort_values("Kg_Lavorato", ascending=False).head(15)
        fig = px.bar(
            top.sort_values("Kg_Lavorato", ascending=True),
            x="Kg_Lavorato",
            y="Codice",
            orientation="h",
            title=f"{reparto} - top codici",
            text_auto=".2s",
        )
        fig.update_layout(template="plotly_dark", height=380)
        st.plotly_chart(fig, use_container_width=True)

    fig = px.line(
        rm.sort_values("Mese"),
        x="Mese",
        y="Kg_Lavorato",
        markers=True,
        title=f"{reparto} - trend mensile",
    )
    fig.update_layout(template="plotly_dark", height=420)
    st.plotly_chart(fig, use_container_width=True)

    with st.expander(f"Dettaglio dati {reparto}"):
        st.dataframe(rw.sort_values("Data", ascending=False), use_container_width=True, height=380)


def family_section(title, family_name, lots, pf_form=None):
    st.subheader(title)

    data = lots[lots["Famiglia"] == family_name].copy()

    if data.empty:
        st.warning(f"Nessun dato disponibile per {title}.")
        return

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Kg prodotti", format_kg(data["Kg"].sum()))
    c2.metric("N° lotti", format_kg(data["LOTTO_FINITO"].nunique()))
    c3.metric("N° codici", format_kg(data["CODART"].nunique()))
    c4.metric("Kg medi/lotto", format_kg(data["Kg"].mean()))

    left, right = st.columns(2)

    with left:
        monthly = data.groupby("Mese", as_index=False)["Kg"].sum().sort_values("Mese")
        fig = px.line(monthly, x="Mese", y="Kg", markers=True, title=f"{title} - trend mensile")
        fig.update_layout(template="plotly_dark", height=380)
        st.plotly_chart(fig, use_container_width=True)

    with right:
        top = data.groupby(["CODART", "Descrizione"], as_index=False)["Kg"].sum().sort_values("Kg", ascending=False).head(15)
        fig = px.bar(top.sort_values("Kg", ascending=True), x="Kg", y="CODART", orientation="h", hover_data=["Descrizione"], title=f"{title} - top codici")
        fig.update_layout(template="plotly_dark", height=380)
        st.plotly_chart(fig, use_container_width=True)

    if family_name == "Estratto secco finito" and pf_form is not None and len(pf_form):
        st.markdown("### Analisi formulativa estratti secchi finiti")
        pf = pf_form[pf_form["Famiglia"] == "Estratto secco finito"].copy()

        left, right = st.columns(2)
        with left:
            fig = px.histogram(pf, x="Malto_Totale_%", nbins=25, title="Distribuzione malto totale stimato")
            fig.update_layout(template="plotly_dark", height=380)
            fig.update_xaxes(tickformat=".0%")
            st.plotly_chart(fig, use_container_width=True)
        with right:
            top_m = pf.sort_values("Malto_Totale_%", ascending=False).head(15)
            fig = px.bar(top_m.sort_values("Malto_Totale_%", ascending=True), x="Malto_Totale_%", y="Codice", orientation="h", title="Top codici per malto totale")
            fig.update_layout(template="plotly_dark", height=380)
            fig.update_xaxes(tickformat=".0%")
            st.plotly_chart(fig, use_container_width=True)

    st.dataframe(data.sort_values("Data", ascending=False), use_container_width=True, height=360)


# -----------------------------
# Load
# -----------------------------
if not COMMESSE_PATH.exists():
    st.error("File commesse non trovato in data/commesse.xlsx")
    st.stop()

comm = load_commesse(COMMESSE_PATH)
rep = load_reparti(REPARTI_PATH)
lots, detail, sem_master, sem_lotti, pf_form, rep_work, rep_summary, rep_year, rep_month = build_model(comm, rep)


# -----------------------------
# Sidebar
# -----------------------------
st.sidebar.title("🌿 EVRA Dashboard")
st.sidebar.caption("Reparti • Famiglie prodotto • Formulazioni")

years = sorted([int(y) for y in lots["Anno"].dropna().unique()])
selected_years = st.sidebar.multiselect("Anno produzione", years, default=years)

families = sorted(lots["Famiglia"].dropna().unique())
selected_fam = st.sidebar.multiselect("Famiglia articolo", families, default=families)

filtered_lots = lots[lots["Anno"].isin(selected_years) & lots["Famiglia"].isin(selected_fam)].copy()

st.sidebar.markdown("---")
st.sidebar.caption("Pastorizzazione e Concentrazione escluse. Granulazione aggregata. Estrazione da scarichi MDR.")


# -----------------------------
# Header
# -----------------------------
st.title("EVRA Production & Formulation Dashboard")
st.markdown('<span class="small-note">Struttura per reparto e per famiglia prodotto. Le quantità sono indicate come lavorato.</span>', unsafe_allow_html=True)

c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("Kg prodotti", format_kg(filtered_lots["Kg"].sum()))
c2.metric("N° lotti", format_kg(filtered_lots["LOTTO_FINITO"].nunique()))
c3.metric("N° articoli", format_kg(filtered_lots["CODART"].nunique()))
c4.metric("Kg lavorati reparti", format_kg(rep_summary["Kg_Lavorato"].sum()) if len(rep_summary) else "ND")
c5.metric("Taglio malto medio", f"{sem_master['Taglio_Malto'].mean()*100:.1f}%" if len(sem_master) else "ND")
c6.metric("Mass Yield media", f"{sem_master['Mass_Yield'].mean()*100:.1f}%" if len(sem_master) else "ND")


tab_exec, tab_rep, tab_fam, tab_sem, tab_form, tab_search = st.tabs([
    "Executive",
    "Reparti",
    "Famiglie prodotto",
    "Semilavorati",
    "Formulazioni",
    "Ricerca codice",
])


with tab_exec:
    st.subheader("Executive summary")

    left, right = st.columns(2)

    with left:
        fam = filtered_lots.groupby("Famiglia", as_index=False)["Kg"].sum().sort_values("Kg", ascending=True)
        fig = px.bar(fam, x="Kg", y="Famiglia", orientation="h", title="Kg prodotti per famiglia", text_auto=".2s")
        fig.update_layout(template="plotly_dark", height=430, margin=dict(l=10, r=10, t=50, b=10))
        st.plotly_chart(fig, use_container_width=True)

    with right:
        if len(rep_summary):
            fig = px.bar(rep_summary.sort_values("Kg_Lavorato", ascending=True), x="Kg_Lavorato", y="Reparto", orientation="h", title="Kg lavorati per reparto", text_auto=".2s")
            fig.update_layout(template="plotly_dark", height=430, margin=dict(l=10, r=10, t=50, b=10))
            st.plotly_chart(fig, use_container_width=True)

    top = filtered_lots.groupby(["CODART", "Descrizione", "Famiglia"], as_index=False)["Kg"].sum().sort_values("Kg", ascending=False).head(20)
    st.markdown("### Top 20 codici prodotti")
    st.dataframe(top, use_container_width=True, height=420)


with tab_rep:
    st.header("Sezioni per singolo reparto")

    reparti_ordine = ["Estrazione", "Atomizzazione", "Granulazione", "Miscelazione", "Fluidi", "Micronizzazione"]
    available = [r for r in reparti_ordine if r in set(rep_work["Reparto"].dropna())]
    extra = [r for r in sorted(rep_work["Reparto"].dropna().unique()) if r not in available and r != "ND"]
    reparti_finali = available + extra

    if not reparti_finali:
        st.warning("Nessun reparto disponibile.")
    else:
        selected_reparto = st.radio("Scegli reparto", reparti_finali, horizontal=True)
        reparto_section(selected_reparto, rep_work, rep_year, rep_month)

        st.markdown("---")
        st.subheader("Confronto reparti")
        metric = st.radio(
            "Metrica confronto",
            ["Kg_Lavorato", "N_Commesse", "N_Codici"],
            horizontal=True,
            format_func=lambda x: {
                "Kg_Lavorato": "Kg lavorati",
                "N_Commesse": "N° commesse",
                "N_Codici": "N° codici",
            }[x],
        )
        fig = px.bar(rep_year, x="Anno", y=metric, color="Reparto", barmode="group", title="Confronto annuo reparti")
        fig.update_layout(template="plotly_dark", height=520)
        st.plotly_chart(fig, use_container_width=True)


with tab_fam:
    st.header("Sezioni per famiglia prodotto")

    fam_tabs = st.tabs(["Fluidi", "Estratto secco finito", "Semilavorati", "Conto lavoro"])

    with fam_tabs[0]:
        family_section("Fluidi", "Fluido", lots)

    with fam_tabs[1]:
        family_section("Estratto secco finito", "Estratto secco finito", lots, pf_form)

    with fam_tabs[2]:
        family_section("Semilavorati", "Semilavorato", lots)

        st.markdown("### Indicatori tecnici semilavorati")
        left, right = st.columns(2)
        with left:
            plot_data = sem_master.dropna(subset=["Taglio_Malto", "Mass_Yield"])
            fig = px.scatter(plot_data, x="Taglio_Malto", y="Mass_Yield", size="Kg", hover_name="Codice", hover_data=["Descrizione", "DER"], title="Taglio malto vs Mass Yield")
            fig.update_layout(template="plotly_dark", height=430)
            fig.update_xaxes(tickformat=".0%")
            fig.update_yaxes(tickformat=".0%")
            st.plotly_chart(fig, use_container_width=True)
        with right:
            top_sem = sem_master.sort_values("Kg", ascending=False).head(15)
            fig = px.bar(top_sem.sort_values("Kg", ascending=True), x="Kg", y="Codice", orientation="h", title="Top semilavorati")
            fig.update_layout(template="plotly_dark", height=430)
            st.plotly_chart(fig, use_container_width=True)

    with fam_tabs[3]:
        family_section("Conto lavoro", "Conto lavoro", lots, pf_form)


with tab_sem:
    st.subheader("Semilavorati")

    f = st.text_input("Filtra semilavorato", key="sem_filter")
    view = sem_master.copy()
    if f:
        q = f.lower()
        view = view[view["Codice"].str.lower().str.contains(q) | view["Descrizione"].str.lower().str.contains(q)]

    st.dataframe(view.sort_values("Kg", ascending=False), use_container_width=True, height=620)


with tab_form:
    st.subheader("Formulazioni ultima produzione")

    f = st.text_input("Filtra prodotto", key="form_filter")
    view = pf_form.copy()
    if f:
        q = f.lower()
        view = view[view["Codice"].str.lower().str.contains(q) | view["Descrizione"].str.lower().str.contains(q)]

    left, right = st.columns(2)

    with left:
        top_malto = pf_form.sort_values("Malto_Totale_%", ascending=False).head(25)
        fig = px.bar(top_malto.sort_values("Malto_Totale_%", ascending=True), x="Malto_Totale_%", y="Codice", orientation="h", title="Top prodotti per malto totale stimato")
        fig.update_layout(template="plotly_dark", height=520)
        fig.update_xaxes(tickformat=".0%")
        st.plotly_chart(fig, use_container_width=True)

    with right:
        fig = px.histogram(pf_form, x="Malto_Totale_%", nbins=30, title="Distribuzione malto totale stimato")
        fig.update_layout(template="plotly_dark", height=520)
        fig.update_xaxes(tickformat=".0%")
        st.plotly_chart(fig, use_container_width=True)

    st.dataframe(view.sort_values("Malto_Totale_%", ascending=False), use_container_width=True, height=500)


with tab_search:
    st.subheader("Ricerca codice")

    code = st.text_input("Codice o descrizione", key="search_code")

    if code:
        q = code.lower()

        art = lots[lots["CODART"].str.lower().str.contains(q) | lots["Descrizione"].str.lower().str.contains(q)]
        form = pf_form[pf_form["Codice"].str.lower().str.contains(q) | pf_form["Descrizione"].str.lower().str.contains(q)]
        sem = sem_master[sem_master["Codice"].str.lower().str.contains(q) | sem_master["Descrizione"].str.lower().str.contains(q)]

        st.markdown("### Produzioni")
        st.dataframe(art.sort_values("Data", ascending=False), use_container_width=True, height=260)

        st.markdown("### Formulazione ultima produzione")
        st.dataframe(form, use_container_width=True, height=180)

        st.markdown("### Semilavorati")
        st.dataframe(sem, use_container_width=True, height=180)

        if len(art):
            selected = art.sort_values("Data", ascending=False).iloc[0]
            st.markdown(f"### Componenti ultimo lotto: `{selected['LOTTO_FINITO']}`")
            comp = detail[(detail["CODART"] == selected["CODART"]) & (detail["LOTTO_FINITO"] == selected["LOTTO_FINITO"])].sort_values("Pct_Utilizzo", ascending=False)
            st.dataframe(comp, use_container_width=True, height=360)

    else:
        st.info("Inserire un codice o parte della descrizione.")
