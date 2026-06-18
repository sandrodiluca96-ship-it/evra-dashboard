
from pathlib import Path
import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="EVRA Dashboard", page_icon="🌿", layout="wide", initial_sidebar_state="expanded")

# -----------------------------
# Paths
# -----------------------------
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
ASSETS_DIR = BASE_DIR / "assets"

COMMESSE_PATH = DATA_DIR / "commesse.xlsx"
REPARTI_PATH = DATA_DIR / "reparti.xlsx"
ACQUISTI_PATH = DATA_DIR / "acquisti.xlsx"
VENDITE_PATH = DATA_DIR / "vendite.xlsx"
LOGO_PATH = ASSETS_DIR / "evra_logo.svg"

MONTH_MAP = {1:"Gen",2:"Feb",3:"Mar",4:"Apr",5:"Mag",6:"Giu",7:"Lug",8:"Ago",9:"Set",10:"Ott",11:"Nov",12:"Dic"}
MONTH_ORDER = list(MONTH_MAP.values())

YEAR_COLORS = {
    2022: "#5B8FF9",
    2023: "#61DDAA",
    2024: "#F6BD16",
    2025: "#E8684A",
    2026: "#6DC8EC",
    2027: "#9270CA",
    2028: "#FF9D4D",
}

# -----------------------------
# Style
# -----------------------------
st.markdown("""
<style>
.stApp {
    background: radial-gradient(circle at top left, #162238 0%, #0b1020 45%, #070b14 100%);
    color: #eef2ff;
}
.block-container { padding-top: 1rem; padding-bottom: 2rem; }
h1, h2, h3 { color: #eef2ff; }

div[data-testid="stMetric"] {
    background: rgba(18,24,42,.96);
    border: 1px solid #26314d;
    padding: 16px;
    border-radius: 18px;
    box-shadow: 0 8px 24px rgba(0,0,0,.25);
}
section[data-testid="stSidebar"] {
    background:#090e1c;
    border-right:1px solid #26314d;
}
.stTabs [data-baseweb="tab"] {
    background:#12182a;
    border:1px solid #26314d;
    border-radius:999px;
    color:#eef2ff;
    padding:8px 16px;
}
.stTabs [aria-selected="true"] { background:#1b3554 !important; }

.kpi-card {
    padding: 18px;
    border-radius: 18px;
    background: linear-gradient(180deg, rgba(18,24,42,.98), rgba(12,18,32,.98));
    box-shadow: 0 8px 22px rgba(0,0,0,.24);
    min-height: 110px;
}
.kpi-label { color:#9aa4bf; font-size:13px; margin-bottom:8px; }
.kpi-value { color:#eef2ff; font-size:28px; font-weight:700; }
.kpi-sub { color:#9aa4bf; font-size:12px; margin-top:4px; }
.green { border:1px solid #355f4f; }
.blue { border:1px solid #354b78; }
.orange { border:1px solid #a36a2a; }
.magenta { border:1px solid #80516d; }
.cyan { border:1px solid #3f6473; }
.purple { border:1px solid #70558e; }

.logo-card {
    background:#ffffff;
    border-radius: 14px;
    padding: 10px;
    margin-bottom: 10px;
}
.small-note { color:#9aa4bf; font-size:.9rem; }
</style>
""", unsafe_allow_html=True)

# -----------------------------
# Utils
# -----------------------------
def fmt(v):
    try:
        return f"{float(v):,.0f}".replace(",", ".")
    except Exception:
        return "0"

def money(v):
    try:
        return "€ " + f"{float(v):,.0f}".replace(",", ".")
    except Exception:
        return "€ 0"

def pct(v):
    if pd.isna(v):
        return "ND"
    return f"{float(v)*100:.1f}%"

def safe_num(s):
    return pd.to_numeric(s, errors="coerce").fillna(0)

def add_month(df, col="Data"):
    df = df.copy()
    df["Anno"] = df[col].dt.year
    df["Mese_Num"] = df[col].dt.month
    df["Mese_Nome"] = df["Mese_Num"].map(MONTH_MAP)
    df["Mese"] = df[col].dt.to_period("M").astype(str)
    return df

def is_semilav(code):
    return str(code).startswith(("W","Y"))

def is_mdr(code):
    return str(code).startswith("MDR")

def is_malto(code, desc):
    s = (str(code)+" "+str(desc)).lower()
    return str(code).startswith("MECMLT") or "maltodestrina" in s or "malto" in s

def famiglia(code):
    code = str(code)
    if code.startswith(("W","Y")):
        return "Semilavorato"
    if code.startswith("F"):
        return "Fluido"
    if code.startswith("V"):
        return "Conto lavoro"
    if code.startswith(("A","S","T")):
        return "Estratto secco finito"
    if code.startswith("MDR"):
        return "Droga vegetale"
    if code.startswith("ME"):
        return "Materia prima / carrier"
    return "Altro"

def uso(code):
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

def acquisto_categoria(code, desc="", gruppo=""):
    code = str(code)
    txt = f"{code} {desc} {gruppo}".lower()

    if code.startswith("MDR"):
        return "Droghe"
    if code.startswith("ME"):
        if "maltodestrina" in txt or "malto" in txt:
            return "Carrier - Maltodestrina"
        return "Carrier / eccipienti"
    if code.startswith(("F","W","Y","A","S","T","V")):
        return "Estratti"
    if "estratto" in txt or "e.s." in txt or "tintura" in txt:
        return "Estratti"
    return "Escludi"

def normalize_reparto(desc):
    d = str(desc).strip().lower()
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
    return str(desc).strip() if str(desc).strip() else "ND"

def exclude_reparto(desc):
    d = str(desc).lower()
    return ("past" in d) or ("concent" in d)

def layout(fig, h=420):
    fig.update_layout(
        template="plotly_dark",
        height=h,
        margin=dict(l=10,r=10,t=55,b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    return fig

def kpi_card(label, value, sub="", color="blue"):
    st.markdown(f"""
    <div class="kpi-card {color}">
      <div class="kpi-label">{label}</div>
      <div class="kpi-value">{value}</div>
      <div class="kpi-sub">{sub}</div>
    </div>
    """, unsafe_allow_html=True)

def top_bar(df, x, y, title, hover_cols=None, height=420):
    hover_cols = hover_cols or []
    if df.empty:
        st.warning("Nessun dato disponibile.")
        return
    fig = px.bar(
        df.sort_values(x, ascending=True),
        x=x, y=y,
        orientation="h",
        title=title,
        text_auto=".2s",
        custom_data=hover_cols
    )
    if hover_cols:
        hover = "".join([f"<br>{col}: %{{customdata[{i}]}}" for i, col in enumerate(hover_cols)])
        fig.update_traces(hovertemplate="<b>%{y}</b><br>Valore: %{x:,.2f}"+hover+"<extra></extra>")
    layout(fig, height)
    fig.update_layout(yaxis_title="")
    st.plotly_chart(fig, use_container_width=True)

def monthly_year_line(df, title, y, hover_cols=None):
    hover_cols = hover_cols or []
    if df.empty:
        st.warning("Nessun dato disponibile.")
        return
    df = df.sort_values(["Anno","Mese_Num"]).copy()
    cum_col = f"{y}_Cumulato"
    df[cum_col] = df.groupby("Anno")[y].cumsum()
    fig = px.line(
        df, x="Mese_Nome", y=cum_col, color="Anno",
        color_discrete_map=YEAR_COLORS,
        markers=True,
        category_orders={"Mese_Nome": MONTH_ORDER},
        title=title.replace("Trend", "Cumulativo").replace("trend", "cumulativo"),
        custom_data=hover_cols + [y]
    )
    if hover_cols:
        hover = "".join([f"<br>{col}: %{{customdata[{i}]}}" for i, col in enumerate(hover_cols)])
        raw_idx = len(hover_cols)
        fig.update_traces(hovertemplate="<b>%{x}</b><br>Cumulato: %{y:,.2f}<br>Mese: %{customdata["+str(raw_idx)+"]:,.2f}"+hover+"<extra></extra>")
    else:
        fig.update_traces(hovertemplate="<b>%{x}</b><br>Cumulato: %{y:,.2f}<extra></extra>")
    layout(fig, 430)
    st.plotly_chart(fig, use_container_width=True)

# -----------------------------
# Loaders
# -----------------------------
@st.cache_data(show_spinner=False)
def load_commesse(path):
    df = pd.read_excel(path)
    for c in ["CODART","ARDESART","LOTTO_FINITO","COD_COMP","DES_COMP","LOTTO"]:
        if c in df.columns:
            df[c] = df[c].fillna("").astype(str).str.strip()
    df["DATA_COM"] = pd.to_datetime(df["DATA_COM"], errors="coerce")
    for c in ["QTA_FINITO","QTA_LOTTO","MOL_QTAKG","MOL_RESIDUO","MOL_TAGLIO"]:
        if c in df.columns:
            df[c] = safe_num(df[c])
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
def load_acquisti(path):
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_excel(path)
    for c in ["MVCODART","ARDESART","ANDESCRI","ARGRUMER","ARDESSUP"]:
        if c in df.columns:
            df[c] = df[c].fillna("").astype(str).str.strip()
    df["MVDATDOC"] = pd.to_datetime(df["MVDATDOC"], errors="coerce")
    df["QTAVEN"] = safe_num(df["QTAVEN"])
    df["TOTVEN"] = safe_num(df["TOTVEN"])
    df["Categoria"] = df.apply(lambda r: acquisto_categoria(r.get("MVCODART",""), r.get("ARDESART",""), r.get("ARGRUMER","")), axis=1)
    df = df[df["Categoria"] != "Escludi"].copy()
    df = add_month(df.rename(columns={"MVDATDOC":"Data"}), "Data")
    return df

@st.cache_data(show_spinner=False)
def load_vendite(path):
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_excel(path)
    for c in ["CODART","DESART","RAGSOC","GMDESCRI","NAZIONE"]:
        if c in df.columns:
            df[c] = df[c].fillna("").astype(str).str.strip()
    df["DATDOC"] = pd.to_datetime(df["DATDOC"], errors="coerce")
    df["QTA"] = safe_num(df["QTA"])
    df["IMPORTO"] = safe_num(df["IMPORTO"])
    df["Famiglia"] = df["CODART"].apply(famiglia)
    df["Uso"] = df["CODART"].apply(uso)
    df = add_month(df.rename(columns={"DATDOC":"Data"}), "Data")
    df["Prezzo_medio"] = np.where(df["QTA"] > 0, df["IMPORTO"] / df["QTA"], np.nan)
    return df

# -----------------------------
# Data model
# -----------------------------
@st.cache_data(show_spinner=False)
def build_production(comm, rep):
    lots = comm.groupby(["CODART","LOTTO_FINITO"], as_index=False).agg(
        Descrizione=("ARDESART","first"),
        Data=("DATA_COM","max"),
        Kg=("QTA_FINITO","first")
    )
    lots = add_month(lots, "Data")
    lots["Famiglia"] = lots["CODART"].apply(famiglia)
    lots["Uso"] = lots["CODART"].apply(uso)
    lots["Titolato"] = lots["Descrizione"].astype(str).str.contains("%", regex=False)

    detail = comm.groupby(["CODART","LOTTO_FINITO","COD_COMP"], as_index=False).agg(
        Descrizione_PF=("ARDESART","first"),
        Descrizione_Componente=("DES_COMP","first"),
        Data=("DATA_COM","max"),
        Kg_PF=("QTA_FINITO","first"),
        Kg_Componente=("QTA_LOTTO","sum")
    )
    detail["Pct_Utilizzo"] = np.where(detail["Kg_PF"]>0, detail["Kg_Componente"]/detail["Kg_PF"], np.nan)
    detail["Semilavorato"] = detail["COD_COMP"].apply(is_semilav)
    detail["Malto_Diretta"] = detail.apply(lambda r: is_malto(r["COD_COMP"], r["Descrizione_Componente"]), axis=1)

    # Semilavorati
    sem = comm[comm["CODART"].apply(is_semilav)].copy()
    rec = []
    for (code, lotto), g in sem.groupby(["CODART","LOTTO_FINITO"]):
        qta = float(g["QTA_FINITO"].iloc[0]) if len(g) else 0
        desc = g["ARDESART"].iloc[0] if len(g) else ""
        data = g["DATA_COM"].max()
        malto = g[g.apply(lambda r: is_malto(r["COD_COMP"], r["DES_COMP"]), axis=1)]["QTA_LOTTO"].sum()
        mdr = g[g["COD_COMP"].apply(is_mdr)]["QTA_LOTTO"].sum()

        taglio = min(malto/qta, .98) if qta > 0 else np.nan

        resa = np.nan
        if pd.notna(data) and data.year >= 2026 and mdr > 0 and {"MOL_QTAKG","MOL_RESIDUO"}.issubset(g.columns):
            mol = g[["MOL_QTAKG","MOL_RESIDUO"]].drop_duplicates()
            mol = mol[(mol["MOL_QTAKG"]>0) & (mol["MOL_RESIDUO"]>0)]
            if len(mol):
                rs = mol["MOL_RESIDUO"].astype(float)
                rs = np.where(rs > 1, rs/100, rs)
                secco = (mol["MOL_QTAKG"].astype(float).values * rs).sum()
                if secco > 0:
                    resa = secco / mdr
        if pd.isna(resa) and mdr > 0:
            resa = (qta-malto)/mdr
            if resa < 0:
                resa = np.nan

        rec.append({
            "Codice":code,"Descrizione":desc,"Lotto":lotto,"Data":data,
            "Kg":qta,"Malto_Qty":malto,"Taglio_Malto":taglio,"Mass_Yield":resa
        })

    sem_lotti = pd.DataFrame(rec)
    if len(sem_lotti):
        sem_lotti = add_month(sem_lotti, "Data")
        sem_master = sem_lotti.groupby("Codice", as_index=False).agg(
            Descrizione=("Descrizione","first"),
            Kg=("Kg","sum"),
            Malto_Qty=("Malto_Qty","sum"),
            N_Lotti=("Lotto","nunique"),
            Taglio_Malto=("Taglio_Malto","mean"),
            Mass_Yield=("Mass_Yield","mean")
        )
    else:
        sem_master = pd.DataFrame(columns=["Codice","Descrizione","Kg","Malto_Qty","N_Lotti","Taglio_Malto","Mass_Yield"])

    sem_taglio = sem_master.set_index("Codice")["Taglio_Malto"].to_dict() if len(sem_master) else {}

    # PF ultima formulazione
    latest = lots.sort_values(["CODART","Data","LOTTO_FINITO"], ascending=[True,False,False]).groupby("CODART").head(1)
    ld = detail.merge(latest[["CODART","LOTTO_FINITO"]], on=["CODART","LOTTO_FINITO"], how="inner")
    pf_rows = []
    for (code, lotto), g in ld.groupby(["CODART","LOTTO_FINITO"]):
        desc = g["Descrizione_PF"].iloc[0]
        kg = g["Kg_PF"].iloc[0]
        sem_pct = g.loc[g["Semilavorato"], "Pct_Utilizzo"].sum()
        malto_dir = g.loc[g["Malto_Diretta"], "Pct_Utilizzo"].sum()
        malto_sem = 0
        sem_codes = []
        for _, r in g[g["Semilavorato"]].iterrows():
            sem_codes.append(r["COD_COMP"])
            t = sem_taglio.get(r["COD_COMP"], np.nan)
            if pd.isna(t):
                t = .60
            malto_sem += r["Pct_Utilizzo"] * t

        pf_rows.append({
            "Codice":code,"Descrizione":desc,"Lotto":lotto,"Kg_Lotto":kg,
            "Famiglia":famiglia(code),"Uso":uso(code),"Titolato":"%" in str(desc),
            "Semilav_%":sem_pct,"Malto_Diretta_%":malto_dir,
            "Malto_da_Semilav_%":malto_sem,"Malto_Totale_%":malto_dir+malto_sem,
            "Semilavorati":" | ".join(sorted(set(sem_codes)))
        })
    pf_form = pd.DataFrame(pf_rows)

    # Trend malto PF
    tr = []
    for (code, lotto), g in detail.groupby(["CODART","LOTTO_FINITO"]):
        fam = famiglia(code)
        if fam not in ["Estratto secco finito","Conto lavoro"]:
            continue
        data = g["Data"].max()
        kg = g["Kg_PF"].iloc[0]
        desc = g["Descrizione_PF"].iloc[0]
        md = g.loc[g["Malto_Diretta"], "Kg_Componente"].sum()
        ms = 0
        for _, r in g[g["Semilavorato"]].iterrows():
            t = sem_taglio.get(r["COD_COMP"], np.nan)
            if pd.isna(t):
                t = .60
            ms += r["Kg_Componente"] * t
        tr.append({
            "Codice":code,"Descrizione":desc,"Lotto":lotto,"Data":data,
            "Anno":data.year if pd.notna(data) else np.nan,
            "Kg_PF":kg,"Famiglia":fam,
            "Malto_Diretta_Kg":md,
            "Malto_da_Semilav_Kg":ms,
            "Malto_Totale_Kg":md+ms,
            "Malto_Totale_%":(md+ms)/kg if kg else np.nan
        })
    pf_malto_trend = pd.DataFrame(tr)

    if len(sem_lotti):
        sem_malto_trend = sem_lotti.groupby("Anno", as_index=False).agg(
            Kg_Semilavorato=("Kg","sum"),
            Malto_Kg=("Malto_Qty","sum"),
            Taglio_Medio=("Taglio_Malto","mean"),
            N_Lotti=("Lotto","nunique")
        )
        sem_malto_trend["Malto_%_Ponderata"] = np.where(
            sem_malto_trend["Kg_Semilavorato"]>0,
            sem_malto_trend["Malto_Kg"]/sem_malto_trend["Kg_Semilavorato"],
            np.nan
        )
    else:
        sem_malto_trend = pd.DataFrame(columns=["Anno","Kg_Semilavorato","Malto_Kg","Taglio_Medio","N_Lotti","Malto_%_Ponderata"])

    # Reparti
    rep_rows = []
    if rep is not None and len(rep):
        art_col = next((c for c in rep.columns if "Articolo" in c and "Caricato" in c), None)
        lav_col = next((c for c in rep.columns if "Descrizione" in c and "Lavorazione" in c), None)
        data_col = next((c for c in rep.columns if "Data" in c and "carico" in c), None)
        qty_col = next((c for c in rep.columns if "Quant" in c and "caric" in c), None)
        comm_col = next((c for c in rep.columns if "Commessa" in c), None)
        desc_col = next((c for c in rep.columns if c == "Descrizione"), None)
        if art_col and lav_col:
            tmp = rep.copy()
            tmp["Lav_Orig"] = tmp[lav_col].astype(str).str.strip()
            tmp = tmp[~tmp["Lav_Orig"].apply(exclude_reparto)]
            tmp = tmp[~tmp["Lav_Orig"].str.lower().str.contains("estr", na=False)]
            tmp["Reparto"] = tmp["Lav_Orig"].apply(normalize_reparto)
            tmp["Codice"] = tmp[art_col].astype(str).str.strip()
            tmp["Descrizione"] = tmp[desc_col].astype(str).str.strip() if desc_col else ""
            tmp["Data"] = pd.to_datetime(tmp[data_col], errors="coerce") if data_col else pd.NaT
            tmp["Kg_Lavorato"] = safe_num(tmp[qty_col]) if qty_col else 0
            tmp["Commessa"] = tmp[comm_col].astype(str).str.strip() if comm_col else ""
            rep_rows.append(tmp[["Reparto","Codice","Descrizione","Commessa","Data","Kg_Lavorato"]])

    # Estrazione da MDR
    mdr = comm[comm["COD_COMP"].apply(is_mdr)].copy()
    if len(mdr):
        rep_rows.append(pd.DataFrame({
            "Reparto":"Estrazione",
            "Codice":mdr["COD_COMP"],
            "Descrizione":mdr["DES_COMP"],
            "Commessa":mdr["LOTTO_FINITO"],
            "Data":mdr["DATA_COM"],
            "Kg_Lavorato":mdr["QTA_LOTTO"]
        }))

    if rep_rows:
        rep_work = pd.concat(rep_rows, ignore_index=True).dropna(subset=["Data"])
        rep_work = add_month(rep_work, "Data")
        rep_summary = rep_work.groupby("Reparto", as_index=False).agg(
            Kg_Lavorato=("Kg_Lavorato","sum"),
            N_Codici=("Codice","nunique"),
            N_Commesse=("Commessa","nunique")
        )
        rep_year = rep_work.groupby(["Reparto","Anno"], as_index=False).agg(
            Kg_Lavorato=("Kg_Lavorato","sum"),
            N_Codici=("Codice","nunique"),
            N_Commesse=("Commessa","nunique")
        )
        rep_month_year = rep_work.groupby(["Reparto","Anno","Mese_Num","Mese_Nome"], as_index=False).agg(
            Kg_Lavorato=("Kg_Lavorato","sum"),
            N_Codici=("Codice","nunique"),
            N_Commesse=("Commessa","nunique")
        )
    else:
        rep_work = pd.DataFrame(columns=["Reparto","Codice","Descrizione","Commessa","Data","Kg_Lavorato","Anno","Mese_Num","Mese_Nome"])
        rep_summary = pd.DataFrame(columns=["Reparto","Kg_Lavorato","N_Codici","N_Commesse"])
        rep_year = pd.DataFrame(columns=["Reparto","Anno","Kg_Lavorato","N_Codici","N_Commesse"])
        rep_month_year = pd.DataFrame(columns=["Reparto","Anno","Mese_Num","Mese_Nome","Kg_Lavorato","N_Codici","N_Commesse"])

    return lots, detail, sem_master, sem_lotti, pf_form, pf_malto_trend, sem_malto_trend, rep_work, rep_summary, rep_year, rep_month_year

# -----------------------------
# Load data
# -----------------------------
if not COMMESSE_PATH.exists():
    st.error("File commesse non trovato.")
    st.stop()

comm = load_commesse(COMMESSE_PATH)
rep = load_reparti(REPARTI_PATH)
acq = load_acquisti(ACQUISTI_PATH)
ven = load_vendite(VENDITE_PATH)
lots, detail, sem_master, sem_lotti, pf_form, pf_malto_trend, sem_malto_trend, rep_work, rep_summary, rep_year, rep_month_year = build_production(comm, rep)

# -----------------------------
# Sidebar
# -----------------------------
if LOGO_PATH.exists():
    st.sidebar.markdown('<div class="logo-card">', unsafe_allow_html=True)
    st.sidebar.image(str(LOGO_PATH), use_container_width=True)
    st.sidebar.markdown('</div>', unsafe_allow_html=True)
st.sidebar.title("EVRA Dashboard 🌿")

all_year_values = []
if "Anno" in lots.columns:
    all_year_values += [int(y) for y in lots["Anno"].dropna().unique()]
if len(ven) and "Anno" in ven.columns:
    all_year_values += [int(y) for y in ven["Anno"].dropna().unique()]
if len(acq) and "Anno" in acq.columns:
    all_year_values += [int(y) for y in acq["Anno"].dropna().unique()]
years = sorted(set(all_year_values))
sel_years = st.sidebar.multiselect("Anno analisi", years, default=years)

fams = sorted(lots["Famiglia"].dropna().unique())
sel_fams = st.sidebar.multiselect("Famiglia articolo", fams, default=fams)

filtered_lots = lots[lots["Anno"].isin(sel_years) & lots["Famiglia"].isin(sel_fams)].copy()
filtered_rep_work = rep_work[rep_work["Anno"].isin(sel_years)].copy() if len(rep_work) else rep_work.copy()
filtered_rep_summary = filtered_rep_work.groupby("Reparto", as_index=False).agg(
    Kg_Lavorato=("Kg_Lavorato","sum"),
    N_Codici=("Codice","nunique"),
    N_Commesse=("Commessa","nunique")
) if len(filtered_rep_work) else rep_summary.copy()

filtered_acq = acq[acq["Anno"].isin(sel_years)].copy() if len(acq) and "Anno" in acq.columns else acq.copy()
filtered_ven = ven[ven["Anno"].isin(sel_years)].copy() if len(ven) and "Anno" in ven.columns else ven.copy()

# -----------------------------
# Header
# -----------------------------
h1, h2 = st.columns([1,5])
with h1:
    if LOGO_PATH.exists():
        st.markdown('<div class="logo-card">', unsafe_allow_html=True)
        st.image(str(LOGO_PATH), use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)
with h2:
    st.title("EVRA Dashboard 🌿")

# Home KPI richiesti
qta_finiti = filtered_lots[filtered_lots["Famiglia"].isin(["Estratto secco finito","Conto lavoro"])]["Kg"].sum()
qta_semilav = filtered_lots[filtered_lots["Famiglia"]=="Semilavorato"]["Kg"].sum()
qta_fluidi = filtered_lots[filtered_lots["Famiglia"]=="Fluido"]["Kg"].sum()
qta_droga = filtered_rep_work[filtered_rep_work["Reparto"]=="Estrazione"]["Kg_Lavorato"].sum() if len(filtered_rep_work) else 0

k1,k2,k3,k4 = st.columns(4)
with k1: kpi_card("Qtà finiti", f"{fmt(qta_finiti)} kg", "Estratti secchi finiti + conto lavoro", "green")
with k2: kpi_card("Qtà semilav", f"{fmt(qta_semilav)} kg", "Semilavorati W/Y prodotti", "blue")
with k3: kpi_card("Qtà fluidi", f"{fmt(qta_fluidi)} kg", "Prodotti fluidi", "cyan")
with k4: kpi_card("Qtà droga estratta", f"{fmt(qta_droga)} kg", "Scarichi MDR da commesse", "magenta")

if len(filtered_ven) or len(filtered_acq):
    k5,k6,k7,k8 = st.columns(4)
    with k5: kpi_card("Qtà venduta", f"{fmt(filtered_ven['QTA'].sum()) if len(filtered_ven) else '0'} kg", "Vendite negli anni selezionati", "orange")
    with k6: kpi_card("Fatturato", money(filtered_ven["IMPORTO"].sum()) if len(filtered_ven) else "€ 0", "Importo venduto", "orange")
    with k7: kpi_card("Qtà acquistata", f"{fmt(filtered_acq['QTAVEN'].sum()) if len(filtered_acq) else '0'} kg", "Solo materie prime ed estratti", "purple")
    with k8: kpi_card("Valore acquisti", money(filtered_acq["TOTVEN"].sum()) if len(filtered_acq) else "€ 0", "Solo categorie tecniche", "purple")

# -----------------------------
# Sections
# -----------------------------
tabs = st.tabs([
    "Executive",
    "Reparti",
    "Famiglie prodotto",
    "Semilavorati",
    "Formulazioni",
    "Acquisti",
    "Vendite",
    "Ricerca codice"
])

# Executive
with tabs[0]:
    left, right = st.columns(2)
    with left:
        fam = filtered_lots.groupby("Famiglia", as_index=False)["Kg"].sum().sort_values("Kg", ascending=True)
        fig = px.bar(fam, x="Kg", y="Famiglia", orientation="h", title="Kg prodotti per famiglia", text_auto=".2s")
        layout(fig, 430)
        st.plotly_chart(fig, use_container_width=True)
    with right:
        if len(filtered_rep_summary):
            fig = px.bar(filtered_rep_summary.sort_values("Kg_Lavorato", ascending=True), x="Kg_Lavorato", y="Reparto", orientation="h", title="Kg lavorati per reparto", text_auto=".2s")
            layout(fig, 430)
            st.plotly_chart(fig, use_container_width=True)

    top = filtered_lots.groupby(["CODART","Descrizione","Famiglia"], as_index=False).agg(
        Kg=("Kg","sum"),
        N_Lotti=("LOTTO_FINITO","nunique")
    ).sort_values("Kg", ascending=False).head(20)
    st.markdown("### Top 20 codici prodotti")
    st.dataframe(top, use_container_width=True, height=390)

# Reparti
with tabs[1]:
    st.header("Sezioni per singolo reparto")
    order = ["Estrazione","Atomizzazione","Granulazione","Miscelazione","Fluidi","Micronizzazione"]
    available = [x for x in order if x in set(rep_work["Reparto"].dropna())]
    extra = [x for x in sorted(rep_work["Reparto"].dropna().unique()) if x not in available and x != "ND"]
    reps = available + extra

    if reps:
        selected = st.radio("Scegli reparto", reps, horizontal=True)
        rw = rep_work[rep_work["Reparto"]==selected].copy()
        ry = rep_year[rep_year["Reparto"]==selected].copy()
        rm = rep_month_year[rep_month_year["Reparto"]==selected].copy()

        c1,c2,c3,c4 = st.columns(4)
        c1.metric("Kg lavorati", fmt(rw["Kg_Lavorato"].sum()))
        c2.metric("N° commesse", fmt(rw["Commessa"].nunique()))
        c3.metric("N° codici", fmt(rw["Codice"].nunique()))
        c4.metric("Kg medi/commessa", fmt(rw.groupby("Commessa")["Kg_Lavorato"].sum().mean()))

        l,r = st.columns(2)
        with l:
            fig = px.bar(ry.sort_values("Anno"), x="Anno", y="Kg_Lavorato", title=f"{selected} - lavorato annuo", text_auto=".2s")
            layout(fig, 390)
            st.plotly_chart(fig, use_container_width=True)
        with r:
            top = rw.groupby(["Codice","Descrizione"], as_index=False).agg(
                Kg_Lavorato=("Kg_Lavorato","sum"),
                N_Commesse=("Commessa","nunique")
            ).sort_values("Kg_Lavorato", ascending=False).head(15)
            top_bar(top, "Kg_Lavorato", "Codice", f"{selected} - top codici", ["Descrizione","N_Commesse"], 390)

        monthly_year_line(rm, f"{selected} - trend mensile per anno", "Kg_Lavorato", ["Anno","N_Commesse","N_Codici"])

        with st.expander(f"Dettaglio dati {selected}"):
            st.dataframe(rw.sort_values("Data", ascending=False), use_container_width=True, height=330)

        st.markdown("---")
        st.subheader("Confronto reparti")
        metric = st.radio(
            "Metrica confronto",
            ["Kg_Lavorato","N_Commesse","N_Codici"],
            horizontal=True,
            format_func=lambda x: {"Kg_Lavorato":"Kg lavorati","N_Commesse":"N° commesse","N_Codici":"N° codici"}[x]
        )
        fig = px.bar(rep_year, x="Anno", y=metric, color="Reparto", barmode="group", title="Confronto annuo reparti")
        layout(fig, 520)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("Nessun reparto disponibile.")

# Famiglie prodotto
with tabs[2]:
    st.header("Sezioni per famiglia prodotto")
    subtabs = st.tabs(["Fluidi","Estratto secco finito","Semilavorati","Conto lavoro"])
    defs = [("Fluidi","Fluido"),("Estratto secco finito","Estratto secco finito"),("Semilavorati","Semilavorato"),("Conto lavoro","Conto lavoro")]
    for tab, (title, fam) in zip(subtabs, defs):
        with tab:
            data = lots[lots["Famiglia"]==fam].copy()
            if data.empty:
                st.warning("Nessun dato disponibile.")
                continue
            a,b,c,d = st.columns(4)
            a.metric("Kg prodotti", fmt(data["Kg"].sum()))
            b.metric("N° lotti", fmt(data["LOTTO_FINITO"].nunique()))
            c.metric("N° codici", fmt(data["CODART"].nunique()))
            d.metric("Kg medi/lotto", fmt(data["Kg"].mean()))
            month = data.groupby(["Anno","Mese_Num","Mese_Nome"], as_index=False).agg(Kg=("Kg","sum"), N_Lotti=("LOTTO_FINITO","nunique"), N_Codici=("CODART","nunique"))
            l,r = st.columns(2)
            with l:
                monthly_year_line(month, f"{title} - trend mensile per anno", "Kg", ["Anno","N_Lotti","N_Codici"])
            with r:
                top = data.groupby(["CODART","Descrizione"], as_index=False).agg(
                    Kg=("Kg","sum"),
                    N_Lotti=("LOTTO_FINITO","nunique"),
                    Uso=("Uso","first"),
                    Titolato=("Titolato","first")
                ).sort_values("Kg", ascending=False).head(15)
                top_bar(top, "Kg", "CODART", f"{title} - top codici", ["Descrizione","N_Lotti","Uso","Titolato"], 430)
            st.dataframe(data[["CODART","Descrizione","LOTTO_FINITO","Data","Kg","Famiglia","Uso","Titolato"]].sort_values("Data", ascending=False), use_container_width=True, height=300)

# Semilavorati
with tabs[3]:
    st.subheader("Semilavorati")
    l,r = st.columns(2)
    with l:
        plot = sem_master.dropna(subset=["Taglio_Malto","Mass_Yield"])
        if len(plot):
            fig = px.scatter(plot, x="Taglio_Malto", y="Mass_Yield", size="Kg", hover_name="Codice", custom_data=["Descrizione","Kg","N_Lotti"], title="Taglio malto vs Mass Yield")
            fig.update_traces(hovertemplate="<b>%{hovertext}</b><br>Descrizione: %{customdata[0]}<br>Kg: %{customdata[1]:,.2f}<br>Lotti: %{customdata[2]}<br>Taglio: %{x:.1%}<br>Mass Yield: %{y:.1%}<extra></extra>")
            fig.update_xaxes(tickformat=".0%")
            fig.update_yaxes(tickformat=".0%")
            layout(fig, 430)
            st.plotly_chart(fig, use_container_width=True)
    with r:
        top = sem_master.sort_values("Kg", ascending=False).head(15)
        top_bar(top, "Kg", "Codice", "Top semilavorati", ["Descrizione","N_Lotti","Taglio_Malto","Mass_Yield"], 430)
    f = st.text_input("Filtra semilavorato")
    view = sem_master.copy()
    if f:
        q = f.lower()
        view = view[view["Codice"].str.lower().str.contains(q) | view["Descrizione"].str.lower().str.contains(q)]
    st.dataframe(view.sort_values("Kg", ascending=False), use_container_width=True, height=500)

# Formulazioni
with tabs[4]:
    st.subheader("Formulazioni e utilizzo maltodestrina")
    st.markdown("### Malto medio ponderato nei prodotti finiti")
    if len(pf_malto_trend):
        pf_year = pf_malto_trend.groupby(["Anno","Famiglia"], as_index=False).agg(
            Kg_PF=("Kg_PF","sum"),
            Malto_Diretta_Kg=("Malto_Diretta_Kg","sum"),
            Malto_da_Semilav_Kg=("Malto_da_Semilav_Kg","sum"),
            Malto_Totale_Kg=("Malto_Totale_Kg","sum")
        )
        pf_year["Malto_Totale_%"] = np.where(pf_year["Kg_PF"]>0, pf_year["Malto_Totale_Kg"]/pf_year["Kg_PF"], np.nan)
        fig = px.line(
            pf_year, x="Anno", y="Malto_Totale_%", color="Famiglia", markers=True,
            title="Malto totale medio ponderato per anno - prodotti finiti",
            custom_data=["Kg_PF","Malto_Totale_Kg","Malto_Diretta_Kg","Malto_da_Semilav_Kg"]
        )
        fig.update_traces(hovertemplate="<b>%{fullData.name} - %{x}</b><br>Malto totale: %{y:.1%}<br>Kg PF: %{customdata[0]:,.2f}<br>Kg malto totale: %{customdata[1]:,.2f}<br>Kg malto diretta: %{customdata[2]:,.2f}<br>Kg malto da semilav: %{customdata[3]:,.2f}<extra></extra>")
        fig.update_yaxes(tickformat=".0%")
        layout(fig, 430)
        st.plotly_chart(fig, use_container_width=True)

        pf_long = pf_year.melt(
            id_vars=["Anno","Famiglia"],
            value_vars=["Malto_Diretta_Kg","Malto_da_Semilav_Kg"],
            var_name="Tipo malto",
            value_name="Kg"
        )
        fig = px.bar(pf_long, x="Anno", y="Kg", color="Tipo malto", facet_col="Famiglia", title="Kg malto diretta vs malto da semilavorato")
        layout(fig, 430)
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("### Malto medio ponderato nei semilavorati")
    if len(sem_malto_trend):
        fig = px.line(
            sem_malto_trend.sort_values("Anno"), x="Anno", y="Malto_%_Ponderata",
            markers=True,
            title="Taglio malto medio ponderato dei semilavorati per anno",
            custom_data=["Kg_Semilavorato","Malto_Kg","N_Lotti"]
        )
        fig.update_traces(hovertemplate="<b>%{x}</b><br>Taglio ponderato: %{y:.1%}<br>Kg semilavorato: %{customdata[0]:,.2f}<br>Kg malto: %{customdata[1]:,.2f}<br>Lotti: %{customdata[2]}<extra></extra>")
        fig.update_yaxes(tickformat=".0%")
        layout(fig, 430)
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("### Cumulativo utilizzo malto nei finiti")
    if len(pf_malto_trend):
        pf_m_month = pf_malto_trend.dropna(subset=["Data"]).copy()
        pf_m_month = add_month(pf_m_month, "Data")
        pf_m_month = pf_m_month.groupby(["Anno","Mese_Num","Mese_Nome"], as_index=False).agg(
            Malto_Totale_Kg=("Malto_Totale_Kg","sum"),
            Malto_Diretta_Kg=("Malto_Diretta_Kg","sum"),
            Malto_da_Semilav_Kg=("Malto_da_Semilav_Kg","sum"),
            Kg_PF=("Kg_PF","sum")
        ).sort_values(["Anno","Mese_Num"])
        pf_m_month["Malto_Totale_Kg_Cumulato"] = pf_m_month.groupby("Anno")["Malto_Totale_Kg"].cumsum()
        pf_m_month["Malto_Diretta_Kg_Cumulato"] = pf_m_month.groupby("Anno")["Malto_Diretta_Kg"].cumsum()
        pf_m_month["Malto_da_Semilav_Kg_Cumulato"] = pf_m_month.groupby("Anno")["Malto_da_Semilav_Kg"].cumsum()

        met_malto_pf = st.radio(
            "Metrica malto finiti",
            ["Malto_Totale_Kg_Cumulato", "Malto_Diretta_Kg_Cumulato", "Malto_da_Semilav_Kg_Cumulato"],
            horizontal=True,
            format_func=lambda x: {
                "Malto_Totale_Kg_Cumulato": "Malto totale",
                "Malto_Diretta_Kg_Cumulato": "Malto diretta",
                "Malto_da_Semilav_Kg_Cumulato": "Malto da semilav",
            }[x],
            key="met_malto_pf"
        )
        fig = px.line(
            pf_m_month,
            x="Mese_Nome",
            y=met_malto_pf,
            color="Anno",
            color_discrete_map=YEAR_COLORS,
            markers=True,
            category_orders={"Mese_Nome":MONTH_ORDER},
            title="Cumulativo malto nei prodotti finiti",
            custom_data=["Anno","Malto_Totale_Kg","Malto_Diretta_Kg","Malto_da_Semilav_Kg","Kg_PF"]
        )
        fig.update_traces(hovertemplate="<b>%{x} %{customdata[0]}</b><br>Cumulato: %{y:,.2f} kg<br>Malto mese totale: %{customdata[1]:,.2f} kg<br>Diretta mese: %{customdata[2]:,.2f} kg<br>Da semilav mese: %{customdata[3]:,.2f} kg<br>Kg PF mese: %{customdata[4]:,.2f}<extra></extra>")
        layout(fig, 430)
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("### Cumulativo utilizzo malto nei semilavorati")
    if len(sem_lotti):
        sem_m_month = sem_lotti.dropna(subset=["Data"]).copy()
        if "Anno" not in sem_m_month.columns:
            sem_m_month = add_month(sem_m_month, "Data")
        sem_m_month = sem_m_month.groupby(["Anno","Mese_Num","Mese_Nome"], as_index=False).agg(
            Malto_Qty=("Malto_Qty","sum"),
            Kg=("Kg","sum"),
            N_Lotti=("Lotto","nunique")
        ).sort_values(["Anno","Mese_Num"])
        sem_m_month["Malto_Qty_Cumulato"] = sem_m_month.groupby("Anno")["Malto_Qty"].cumsum()
        sem_m_month["Kg_Cumulato"] = sem_m_month.groupby("Anno")["Kg"].cumsum()
        sem_m_month["Taglio_Cumulato"] = np.where(sem_m_month["Kg_Cumulato"] > 0, sem_m_month["Malto_Qty_Cumulato"] / sem_m_month["Kg_Cumulato"], np.nan)

        fig = px.line(
            sem_m_month,
            x="Mese_Nome",
            y="Malto_Qty_Cumulato",
            color="Anno",
            color_discrete_map=YEAR_COLORS,
            markers=True,
            category_orders={"Mese_Nome":MONTH_ORDER},
            title="Cumulativo malto nei semilavorati",
            custom_data=["Anno","Malto_Qty","Kg","N_Lotti","Taglio_Cumulato"]
        )
        fig.update_traces(hovertemplate="<b>%{x} %{customdata[0]}</b><br>Malto cumulato: %{y:,.2f} kg<br>Malto mese: %{customdata[1]:,.2f} kg<br>Kg semilav mese: %{customdata[2]:,.2f}<br>Lotti mese: %{customdata[3]}<br>Taglio cumulato: %{customdata[4]:.1%}<extra></extra>")
        layout(fig, 430)
        st.plotly_chart(fig, use_container_width=True)

st.markdown("### Tabella formulazioni ultima produzione")
pf_form_no_fluid = pf_form[pf_form["Famiglia"] != "Fluido"].copy()
st.dataframe(pf_form_no_fluid.sort_values("Malto_Totale_%", ascending=False), use_container_width=True, height=420)

# Acquisti
with tabs[5]:
    st.header("Acquisti")
    if filtered_acq.empty:
        st.warning("File acquisti assente o senza categorie tecniche filtrate per gli anni selezionati.")
    else:
        c1,c2,c3,c4 = st.columns(4)
        c1.metric("Kg acquistati", fmt(filtered_acq["QTAVEN"].sum()) + " kg")
        c2.metric("Valore acquisti", money(filtered_acq["TOTVEN"].sum()))
        c3.metric("N° fornitori", fmt(filtered_acq["ANDESCRI"].nunique()))
        c4.metric("N° articoli", fmt(filtered_acq["MVCODART"].nunique()))

        l,r = st.columns(2)
        with l:
            cat = filtered_acq.groupby("Categoria", as_index=False).agg(Kg=("QTAVEN","sum"), Valore=("TOTVEN","sum")).sort_values("Kg", ascending=True)
            fig = px.bar(cat, x="Kg", y="Categoria", orientation="h", title="Acquisti per categoria tecnica", text_auto=".2s", custom_data=["Valore"])
            fig.update_traces(hovertemplate="<b>%{y}</b><br>Kg: %{x:,.2f}<br>Valore: € %{customdata[0]:,.2f}<extra></extra>")
            layout(fig, 420)
            st.plotly_chart(fig, use_container_width=True)
        with r:
            top_for = filtered_acq.groupby("ANDESCRI", as_index=False).agg(Kg=("QTAVEN","sum"), Valore=("TOTVEN","sum"), N_Articoli=("MVCODART","nunique")).sort_values("Valore", ascending=False).head(15)
            top_bar(top_for, "Valore", "ANDESCRI", "Top fornitori per valore", ["Kg","N_Articoli"], 420)

        st.markdown("### Cumulativo acquisti globale")
        metric_acq = st.radio("Metrica trend acquisti", ["Kg", "Valore"], horizontal=True)
        month = filtered_acq.groupby(["Anno","Mese_Num","Mese_Nome"], as_index=False).agg(Kg=("QTAVEN","sum"), Valore=("TOTVEN","sum"), N_Articoli=("MVCODART","nunique"), N_Fornitori=("ANDESCRI","nunique"))
        month = month.sort_values(["Anno","Mese_Num"]).copy()
        month[f"{metric_acq}_Cumulato"] = month.groupby("Anno")[metric_acq].cumsum()
        fig = px.line(
            month,
            x="Mese_Nome",
            y=f"{metric_acq}_Cumulato",
            color="Anno",
            markers=True,
            category_orders={"Mese_Nome":MONTH_ORDER},
            title=f"Cumulativo mensile acquisti - {metric_acq}",
            custom_data=["Anno","N_Articoli","N_Fornitori"]
        )
        fig.update_traces(hovertemplate="<b>%{x} %{customdata[0]}</b><br>Valore: %{y:,.2f}<br>Articoli: %{customdata[1]}<br>Fornitori: %{customdata[2]}<extra></extra>")
        layout(fig, 450)
        st.plotly_chart(fig, use_container_width=True)

        st.markdown("### Top articoli acquistati")
        top_art = filtered_acq.groupby(["MVCODART","ARDESART","Categoria"], as_index=False).agg(Kg=("QTAVEN","sum"), Valore=("TOTVEN","sum"), N_Fornitori=("ANDESCRI","nunique")).sort_values("Valore", ascending=False).head(30)
        st.dataframe(top_art, use_container_width=True, height=420)

        st.markdown("### Dettaglio fornitore")
        fornitori = sorted(filtered_acq["ANDESCRI"].dropna().unique())
        if fornitori:
            fornitore = st.selectbox("Seleziona fornitore", fornitori, key="fornitore_acquisti")
            fa = filtered_acq[filtered_acq["ANDESCRI"] == fornitore]
            fa_kpi1, fa_kpi2, fa_kpi3 = st.columns(3)
            fa_kpi1.metric("Kg acquistati", fmt(fa["QTAVEN"].sum()) + " kg")
            fa_kpi2.metric("Valore", money(fa["TOTVEN"].sum()))
            fa_kpi3.metric("N° articoli", fmt(fa["MVCODART"].nunique()))
            fm = fa.groupby(["Anno","Mese_Num","Mese_Nome"], as_index=False).agg(Valore=("TOTVEN","sum"), Kg=("QTAVEN","sum"), N_Articoli=("MVCODART","nunique"))
            met_f = st.radio("Metrica dettaglio fornitore", ["Valore","Kg"], horizontal=True, key="met_fornitore_acquisti")
            fm = fm.sort_values(["Anno","Mese_Num"]).copy()
            fm[f"{met_f}_Cumulato"] = fm.groupby("Anno")[met_f].cumsum()
            fig = px.line(fm, x="Mese_Nome", y=f"{met_f}_Cumulato", color="Anno", color_discrete_map=YEAR_COLORS, markers=True, category_orders={"Mese_Nome":MONTH_ORDER}, title=f"Cumulativo fornitore - {fornitore}", custom_data=["Anno","N_Articoli", met_f])
            fig.update_traces(hovertemplate="<b>%{x} %{customdata[0]}</b><br>Cumulato: %{y:,.2f}<br>Mese: %{customdata[2]:,.2f}<br>Articoli: %{customdata[1]}<extra></extra>")
            layout(fig, 420)
            st.plotly_chart(fig, use_container_width=True)

# Vendite
with tabs[6]:
    st.header("Vendite")
    if filtered_ven.empty:
        st.warning("File vendite assente o senza dati per gli anni selezionati.")
    else:
        c1,c2,c3,c4 = st.columns(4)
        c1.metric("Kg venduti", fmt(filtered_ven["QTA"].sum()) + " kg")
        c2.metric("Fatturato", money(filtered_ven["IMPORTO"].sum()))
        c3.metric("N° clienti", fmt(filtered_ven["RAGSOC"].nunique()))
        prezzo = filtered_ven["IMPORTO"].sum()/filtered_ven["QTA"].sum() if filtered_ven["QTA"].sum() else 0
        c4.metric("Prezzo medio €/kg", money(prezzo).replace("€ ",""))

        l,r = st.columns(2)
        with l:
            top_cli = filtered_ven.groupby("RAGSOC", as_index=False).agg(Kg=("QTA","sum"), Fatturato=("IMPORTO","sum"), N_Codici=("CODART","nunique")).sort_values("Fatturato", ascending=False).head(15)
            top_bar(top_cli, "Fatturato", "RAGSOC", "Top clienti per fatturato", ["Kg","N_Codici"], 430)
        with r:
            fam = filtered_ven.groupby("Famiglia", as_index=False).agg(Kg=("QTA","sum"), Fatturato=("IMPORTO","sum"), N_Codici=("CODART","nunique")).sort_values("Fatturato", ascending=True)
            fig = px.bar(fam, x="Fatturato", y="Famiglia", orientation="h", title="Vendite per famiglia", text_auto=".2s", custom_data=["Kg","N_Codici"])
            fig.update_traces(hovertemplate="<b>%{y}</b><br>Fatturato: € %{x:,.2f}<br>Kg: %{customdata[0]:,.2f}<br>Codici: %{customdata[1]}<extra></extra>")
            layout(fig, 430)
            st.plotly_chart(fig, use_container_width=True)

        st.markdown("### Cumulativo vendite globale")
        month = filtered_ven.groupby(["Anno","Mese_Num","Mese_Nome"], as_index=False).agg(Kg=("QTA","sum"), Fatturato=("IMPORTO","sum"), N_Clienti=("RAGSOC","nunique"), N_Codici=("CODART","nunique"))
        metric_v = st.radio("Metrica vendite", ["Fatturato","Kg"], horizontal=True)
        month = month.sort_values(["Anno","Mese_Num"]).copy()
        month[f"{metric_v}_Cumulato"] = month.groupby("Anno")[metric_v].cumsum()
        fig = px.line(
            month,
            x="Mese_Nome",
            y=f"{metric_v}_Cumulato",
            color="Anno",
            markers=True,
            category_orders={"Mese_Nome":MONTH_ORDER},
            title=f"Cumulativo mensile vendite - {metric_v}",
            custom_data=["Anno","N_Clienti","N_Codici"]
        )
        fig.update_traces(hovertemplate="<b>%{x} %{customdata[0]}</b><br>Valore: %{y:,.2f}<br>Clienti: %{customdata[1]}<br>Codici: %{customdata[2]}<extra></extra>")
        layout(fig, 480)
        st.plotly_chart(fig, use_container_width=True)

        st.markdown("### Top articoli venduti")
        top_art = filtered_ven.groupby(["CODART","DESART","Famiglia"], as_index=False).agg(Kg=("QTA","sum"), Fatturato=("IMPORTO","sum"), N_Clienti=("RAGSOC","nunique")).sort_values("Fatturato", ascending=False).head(30)
        st.dataframe(top_art, use_container_width=True, height=420)

        st.markdown("### Dettaglio cliente")
        clienti = sorted(filtered_ven["RAGSOC"].dropna().unique())
        if clienti:
            cliente = st.selectbox("Seleziona cliente", clienti, key="cliente_vendite")
            cv = filtered_ven[filtered_ven["RAGSOC"] == cliente]
            cv_kpi1, cv_kpi2, cv_kpi3 = st.columns(3)
            cv_kpi1.metric("Kg venduti", fmt(cv["QTA"].sum()) + " kg")
            cv_kpi2.metric("Fatturato", money(cv["IMPORTO"].sum()))
            cv_kpi3.metric("N° codici", fmt(cv["CODART"].nunique()))
            cm = cv.groupby(["Anno","Mese_Num","Mese_Nome"], as_index=False).agg(Fatturato=("IMPORTO","sum"), Kg=("QTA","sum"), N_Codici=("CODART","nunique"))
            met_c = st.radio("Metrica dettaglio cliente", ["Fatturato","Kg"], horizontal=True, key="met_cliente_vendite")
            cm = cm.sort_values(["Anno","Mese_Num"]).copy()
            cm[f"{met_c}_Cumulato"] = cm.groupby("Anno")[met_c].cumsum()
            fig = px.line(cm, x="Mese_Nome", y=f"{met_c}_Cumulato", color="Anno", color_discrete_map=YEAR_COLORS, markers=True, category_orders={"Mese_Nome":MONTH_ORDER}, title=f"Cumulativo cliente - {cliente}", custom_data=["Anno","N_Codici", met_c])
            fig.update_traces(hovertemplate="<b>%{x} %{customdata[0]}</b><br>Cumulato: %{y:,.2f}<br>Mese: %{customdata[2]:,.2f}<br>Codici: %{customdata[1]}<extra></extra>")
            layout(fig, 420)
            st.plotly_chart(fig, use_container_width=True)


# Search
with tabs[7]:
    st.header("Ricerca codice / cliente / fornitore")
    q = st.text_input("Cerca")
    if q:
        ql = q.lower()

        st.markdown("### Produzione")
        df = lots[lots["CODART"].str.lower().str.contains(ql) | lots["Descrizione"].str.lower().str.contains(ql)]
        st.dataframe(df[["CODART","Descrizione","LOTTO_FINITO","Data","Kg","Famiglia","Uso","Titolato"]].sort_values("Data", ascending=False), use_container_width=True, height=220)

        st.markdown("### Semilavorati")
        df = sem_master[sem_master["Codice"].str.lower().str.contains(ql) | sem_master["Descrizione"].str.lower().str.contains(ql)]
        st.dataframe(df, use_container_width=True, height=160)

        st.markdown("### Lavorazioni")
        df = rep_work[rep_work["Codice"].str.lower().str.contains(ql) | rep_work["Descrizione"].str.lower().str.contains(ql)]
        st.dataframe(df.sort_values("Data", ascending=False), use_container_width=True, height=200)

        st.markdown("### Vendite")
        if not ven.empty:
            df = ven[ven["CODART"].str.lower().str.contains(ql) | ven["DESART"].str.lower().str.contains(ql) | ven["RAGSOC"].str.lower().str.contains(ql)]
            st.dataframe(df.sort_values("Data", ascending=False), use_container_width=True, height=200)

        st.markdown("### Acquisti")
        if not acq.empty:
            df = acq[acq["MVCODART"].str.lower().str.contains(ql) | acq["ARDESART"].str.lower().str.contains(ql) | acq["ANDESCRI"].str.lower().str.contains(ql)]
            st.dataframe(df.sort_values("Data", ascending=False), use_container_width=True, height=200)
    else:
        st.info("Inserire almeno una parte di codice, descrizione, cliente o fornitore.")
