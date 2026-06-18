
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

# -----------------------------
# STILE DARK
# -----------------------------
st.markdown("""
<style>
:root {
    --bg: #0b1020;
    --panel: #12182a;
    --panel2: #171f34;
    --border: #26314d;
    --text: #eef2ff;
    --muted: #9aa4bf;
    --green: #68d391;
    --blue: #63b3ed;
    --yellow: #f6d365;
    --red: #fc8181;
}
.stApp {
    background: radial-gradient(circle at top left, #172033 0%, #0b1020 40%, #080c17 100%);
    color: var(--text);
}
.block-container {
    padding-top: 1.2rem;
    padding-bottom: 2rem;
}
h1, h2, h3 {
    color: #eef2ff;
}
div[data-testid="stMetric"] {
    background: rgba(18, 24, 42, 0.95);
    border: 1px solid #26314d;
    padding: 18px;
    border-radius: 18px;
    box-shadow: 0 8px 28px rgba(0,0,0,0.25);
}
div[data-testid="stMetricLabel"] {
    color: #9aa4bf;
}
div[data-testid="stMetricValue"] {
    color: #eef2ff;
}
section[data-testid="stSidebar"] {
    background: #0a0f1e;
    border-right: 1px solid #26314d;
}
.stTabs [data-baseweb="tab-list"] {
    gap: 8px;
}
.stTabs [data-baseweb="tab"] {
    background: #12182a;
    border: 1px solid #26314d;
    border-radius: 999px;
    color: #eef2ff;
    padding: 8px 18px;
}
.stTabs [aria-selected="true"] {
    background: #1f4e78 !important;
}
.dataframe {
    border-radius: 12px;
}
.small-note {
    color: #9aa4bf;
    font-size: 0.9rem;
}
.card {
    background: rgba(18, 24, 42, 0.95);
    border: 1px solid #26314d;
    border-radius: 18px;
    padding: 18px;
    margin-bottom: 16px;
}
.badge {
    display: inline-block;
    border-radius: 999px;
    padding: 4px 10px;
    margin: 2px;
    background: #172b4d;
    color: #9bdcff;
    border: 1px solid #29527a;
    font-size: 0.8rem;
}
</style>
""", unsafe_allow_html=True)

DATA_DIR = Path(__file__).parent / "data"
COMMESSE_PATH = DATA_DIR / "commesse.xlsx"
REPARTI_PATH = DATA_DIR / "reparti.xlsx"


# -----------------------------
# FUNZIONI
# -----------------------------
def clean_code(s):
    return "" if pd.isna(s) else str(s).strip()


def is_semilav(code):
    return str(code).startswith(("W", "Y"))


def is_mdr(code):
    return str(code).startswith("MDR")


def is_malto(code, desc):
    text = (str(code) + " " + str(desc)).lower()
    return str(code).startswith("MECMLT") or "maltodestrina" in text or "malto" in text


def famiglia(code):
    code = str(code)
    if code.startswith(("WSD", "YSD", "WGL", "YGL", "WLC", "YLC")):
        return "Semilavorato"
    if code.startswith(("ASD", "SSD", "AGL", "ALC")):
        return "Estratti secchi / PF"
    if code.startswith(("FEF", "FMM", "FTM")):
        return "Fluidi / Tinture"
    if code.startswith(("MLI", "MLL")):
        return "Puree"
    if code.startswith(("VSD", "VGL")):
        return "Miscele"
    if code.startswith("MDR"):
        return "Droghe vegetali"
    if code.startswith("MEC"):
        return "Eccipienti / carrier"
    if code.startswith("MES"):
        return "Materie prime / attivi"
    return "Altro"


def extract_der(desc):
    s = str(desc).replace(",", ".")
    m = re.search(r"(\d+(?:\.\d+)?)\s*[-–]\s*(\d+(?:\.\d+)?)\s*:\s*1", s, re.I)
    if m:
        return (float(m.group(1)) + float(m.group(2))) / 2
    m = re.search(r"(\d+(?:\.\d+)?)\s*:\s*1", s, re.I)
    if m:
        return float(m.group(1))
    return np.nan


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
    rep = pd.read_excel(path)
    for c in rep.columns:
        if rep[c].dtype == object:
            rep[c] = rep[c].fillna("").astype(str).str.strip()
    return rep


@st.cache_data(show_spinner=False)
def build_model(comm, rep):
    # Produzioni uniche
    lots = comm.groupby(["CODART", "LOTTO_FINITO"], as_index=False).agg(
        Descrizione=("ARDESART", "first"),
        Data=("DATA_COM", "max"),
        Kg=("QTA_FINITO", "first"),
    )
    lots["Anno"] = lots["Data"].dt.year
    lots["Mese"] = lots["Data"].dt.to_period("M").astype(str)
    lots["Famiglia"] = lots["CODART"].apply(famiglia)
    lots["DER"] = lots["Descrizione"].apply(extract_der)

    # Dettaglio componenti
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

    # Calcolo semilavorati
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
        fonte_yield = "ND"

        # Metodo 1: dal 2026 molle * RS / droga
        if pd.notna(data) and data.year >= 2026 and mdr_qty > 0 and {"MOL_QTAKG", "MOL_RESIDUO"}.issubset(g.columns):
            mol = g[["MOL_QTAKG", "MOL_RESIDUO"]].drop_duplicates()
            mol = mol[(mol["MOL_QTAKG"] > 0) & (mol["MOL_RESIDUO"] > 0)]
            if len(mol):
                rs = mol["MOL_RESIDUO"].astype(float)
                rs_frac = np.where(rs > 1, rs / 100, rs)
                secco_eq = (mol["MOL_QTAKG"].astype(float).values * rs_frac).sum()
                if secco_eq > 0:
                    mass_yield = secco_eq / mdr_qty
                    fonte_yield = "MOLLE_RS"

        # Metodo 2: storico da BOM
        if pd.isna(mass_yield) and mdr_qty > 0:
            mass_yield = (qta_fin - malto_qty) / mdr_qty
            if mass_yield < 0:
                mass_yield = np.nan
                fonte_yield = "ND"
            else:
                fonte_yield = "BOM"

        sem_records.append({
            "Codice": code,
            "Descrizione": desc,
            "Lotto": lotto,
            "Data": data,
            "Kg": qta_fin,
            "Taglio_Malto": taglio,
            "Mass_Yield": mass_yield,
            "Fonte_Yield": fonte_yield,
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
            Fonte_Yield=("Fonte_Yield", lambda x: " / ".join(sorted(set([str(v) for v in x if str(v) != "ND"]))) if any(str(v) != "ND" for v in x) else "ND"),
        )
    else:
        sem_master = pd.DataFrame(columns=["Codice", "Descrizione", "Kg", "N_Lotti", "Taglio_Malto", "Mass_Yield", "DER", "Fonte_Yield"])

    # Formulazioni PF: ultima produzione
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
            if pd.notna(taglio):
                malto_sem += r["Pct_Utilizzo"] * taglio

        pf_rows.append({
            "Codice": code,
            "Descrizione": desc,
            "Lotto": lotto,
            "Kg_Lotto": kg_pf,
            "Semilav_%": sem_pct,
            "Malto_Diretta_%": malto_dir,
            "Malto_da_Semilav_%": malto_sem,
            "Malto_Totale_%": malto_dir + malto_sem,
            "DER": extract_der(desc),
            "Semilavorati": " | ".join(sorted(set(sem_codes))),
        })

    pf_form = pd.DataFrame(pf_rows)

    # Reparti
    rep_summary = pd.DataFrame()
    rep_map = pd.DataFrame()
    if rep is not None and len(rep):
        art_col = next((c for c in rep.columns if "Articolo" in c and "Caricato" in c), None)
        desc_lav_col = next((c for c in rep.columns if "Descrizione" in c and "Lavorazione" in c), None)
        cod_comm_col = next((c for c in rep.columns if "Commessa" in c), None)

        if art_col and desc_lav_col:
            rep_summary = rep.groupby(desc_lav_col, as_index=False).agg(
                N_Righe=(art_col, "size"),
                N_Articoli=(art_col, "nunique"),
            ).sort_values("N_Righe", ascending=False)
            rep_summary = rep_summary.rename(columns={desc_lav_col: "Reparto"})

            rep_map = rep.groupby(art_col, as_index=False).agg(
                Reparti=(desc_lav_col, lambda x: " | ".join(sorted(set([str(v) for v in x if str(v).strip()])))),
                N_Lavorazioni=(desc_lav_col, "nunique"),
            ).rename(columns={art_col: "Codice"})

    return lots, detail, sem_master, sem_lotti, pf_form, rep_summary, rep_map


# -----------------------------
# CARICAMENTO
# -----------------------------
if not COMMESSE_PATH.exists():
    st.error("File commesse non trovato nella cartella data.")
    st.stop()

comm = load_commesse(COMMESSE_PATH)
rep = load_reparti(REPARTI_PATH)
lots, detail, sem_master, sem_lotti, pf_form, rep_summary, rep_map = build_model(comm, rep)

# -----------------------------
# SIDEBAR
# -----------------------------
st.sidebar.title("🌿 EVRA Dashboard")
st.sidebar.caption("Produzione • Reparti • Formulazioni • Semilavorati")

years = sorted([int(y) for y in lots["Anno"].dropna().unique()])
selected_years = st.sidebar.multiselect("Anno", years, default=years)

families = sorted(lots["Famiglia"].dropna().unique())
selected_fam = st.sidebar.multiselect("Famiglia", families, default=families)

filtered_lots = lots[lots["Anno"].isin(selected_years) & lots["Famiglia"].isin(selected_fam)].copy()

st.sidebar.markdown("---")
st.sidebar.markdown("**File caricati**")
st.sidebar.write(f"Commesse: `{COMMESSE_PATH.name}`")
st.sidebar.write(f"Reparti: `{REPARTI_PATH.name if REPARTI_PATH.exists() else 'non presente'}`")

# -----------------------------
# HEADER
# -----------------------------
st.title("EVRA Production & Formulation Dashboard")
st.markdown('<span class="small-note">Dashboard web calcolata automaticamente da esplosione commesse e storico lavorazioni.</span>', unsafe_allow_html=True)

# -----------------------------
# KPI
# -----------------------------
c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("Kg prodotti", f"{filtered_lots['Kg'].sum():,.0f}".replace(",", "."))
c2.metric("N° lotti", f"{filtered_lots['LOTTO_FINITO'].nunique():,}".replace(",", "."))
c3.metric("N° articoli", f"{filtered_lots['CODART'].nunique():,}".replace(",", "."))
c4.metric("Semilavorati", f"{sem_master['Codice'].nunique():,}".replace(",", "."))
c5.metric("Taglio malto medio", f"{sem_master['Taglio_Malto'].mean()*100:.1f}%" if len(sem_master) else "ND")
c6.metric("Mass Yield media", f"{sem_master['Mass_Yield'].mean()*100:.1f}%" if len(sem_master) else "ND")

# -----------------------------
# TABS
# -----------------------------
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "Executive",
    "Produzione",
    "Reparti",
    "Semilavorati",
    "Formulazioni",
    "Ricerca codice",
])

with tab1:
    st.subheader("Executive summary")
    left, right = st.columns([1.2, 1])
    with left:
        fam = filtered_lots.groupby("Famiglia", as_index=False)["Kg"].sum().sort_values("Kg", ascending=False)
        fig = px.bar(fam, x="Kg", y="Famiglia", orientation="h", title="Kg prodotti per famiglia", text_auto=".2s")
        fig.update_layout(template="plotly_dark", height=420, margin=dict(l=10, r=10, t=50, b=10))
        st.plotly_chart(fig, use_container_width=True)
    with right:
        top = filtered_lots.groupby(["CODART", "Descrizione"], as_index=False)["Kg"].sum().sort_values("Kg", ascending=False).head(15)
        fig = px.bar(top, x="Kg", y="CODART", orientation="h", hover_data=["Descrizione"], title="Top 15 articoli")
        fig.update_layout(template="plotly_dark", height=420, margin=dict(l=10, r=10, t=50, b=10))
        st.plotly_chart(fig, use_container_width=True)

with tab2:
    st.subheader("Produzione")
    monthly = filtered_lots.groupby("Mese", as_index=False)["Kg"].sum().sort_values("Mese")
    fig = px.bar(monthly, x="Mese", y="Kg", title="Trend mensile produzione")
    fig.update_layout(template="plotly_dark", height=420)
    st.plotly_chart(fig, use_container_width=True)

    top_table = filtered_lots.groupby(["CODART", "Descrizione", "Famiglia"], as_index=False).agg(
        Kg=("Kg", "sum"),
        N_Lotti=("LOTTO_FINITO", "nunique"),
    ).sort_values("Kg", ascending=False)
    st.dataframe(top_table, use_container_width=True, height=460)

with tab3:
    st.subheader("Reparti / lavorazioni")
    if len(rep_summary):
        fig = px.bar(rep_summary, x="N_Righe", y="Reparto", orientation="h", title="Lavorazioni per reparto")
        fig.update_layout(template="plotly_dark", height=480)
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(rep_summary, use_container_width=True, height=400)
    else:
        st.warning("File reparti non disponibile o colonne non riconosciute.")

with tab4:
    st.subheader("Semilavorati")
    f = st.text_input("Filtra semilavorato", key="sem_filter")
    sem_view = sem_master.copy()
    if f:
        q = f.lower()
        sem_view = sem_view[sem_view["Codice"].str.lower().str.contains(q) | sem_view["Descrizione"].str.lower().str.contains(q)]
    col_a, col_b = st.columns(2)
    with col_a:
        fig = px.scatter(
            sem_master.dropna(subset=["Taglio_Malto", "Mass_Yield"]),
            x="Taglio_Malto",
            y="Mass_Yield",
            size="Kg",
            hover_name="Codice",
            hover_data=["Descrizione", "N_Lotti", "Fonte_Yield", "DER"],
            title="Taglio malto vs Mass Yield",
        )
        fig.update_layout(template="plotly_dark", height=460)
        fig.update_xaxes(tickformat=".0%")
        fig.update_yaxes(tickformat=".0%")
        st.plotly_chart(fig, use_container_width=True)
    with col_b:
        top_sem = sem_master.sort_values("Kg", ascending=False).head(20)
        fig = px.bar(top_sem, x="Kg", y="Codice", orientation="h", title="Top semilavorati per kg prodotti")
        fig.update_layout(template="plotly_dark", height=460)
        st.plotly_chart(fig, use_container_width=True)

    st.dataframe(sem_view.sort_values("Kg", ascending=False), use_container_width=True, height=500)

with tab5:
    st.subheader("Formulazioni ultima produzione")
    f = st.text_input("Filtra prodotto", key="form_filter")
    pf_view = pf_form.copy()
    if f:
        q = f.lower()
        pf_view = pf_view[pf_view["Codice"].str.lower().str.contains(q) | pf_view["Descrizione"].str.lower().str.contains(q)]

    col_a, col_b = st.columns(2)
    with col_a:
        top_malto = pf_form.sort_values("Malto_Totale_%", ascending=False).head(25)
        fig = px.bar(top_malto, x="Malto_Totale_%", y="Codice", orientation="h", title="Top prodotti per malto totale stimato")
        fig.update_layout(template="plotly_dark", height=520)
        fig.update_xaxes(tickformat=".0%")
        st.plotly_chart(fig, use_container_width=True)
    with col_b:
        fig = px.histogram(pf_form, x="Malto_Totale_%", nbins=30, title="Distribuzione malto totale stimato")
        fig.update_layout(template="plotly_dark", height=520)
        fig.update_xaxes(tickformat=".0%")
        st.plotly_chart(fig, use_container_width=True)

    st.dataframe(pf_view.sort_values("Malto_Totale_%", ascending=False), use_container_width=True, height=500)

with tab6:
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
