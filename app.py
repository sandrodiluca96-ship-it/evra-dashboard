
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
    2022: "#5B8FF9", "2022": "#5B8FF9",
    2023: "#61DDAA", "2023": "#61DDAA",
    2024: "#7A8799", "2024": "#7A8799",
    2025: "#E8684A", "2025": "#E8684A",
    2026: "#F6BD16", "2026": "#F6BD16",
    2027: "#9270CA", "2027": "#9270CA",
    2028: "#FF9D4D", "2028": "#FF9D4D",
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

div[data-testid="stTextInput"] input {
    background-color: #ffffff !important;
    color: #111827 !important;
    border: 1px solid #e5e7eb !important;
}
div[data-testid="stTextInput"] input::placeholder {
    color: #6b7280 !important;
}
div[data-testid="stSelectbox"] > div > div {
    background-color: #ffffff !important;
    color: #111827 !important;
}
div[data-testid="stMultiSelect"] > div > div {
    background-color: #ffffff !important;
    color: #111827 !important;
}

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
    df["Anno"] = df[col].dt.year.astype("Int64")
    df["Anno_Label"] = df["Anno"].astype(str)
    df["Mese_Num"] = df[col].dt.month.astype("Int64")
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
    code = str(code).strip().upper()
    txt = f"{code} {desc} {gruppo}".lower()

    esclusioni = [
        "cespite", "ac-cespite", "attrezzatura", "attrezz", "industriale",
        "macchina", "macchin", "servizio", "manutenz", "ricambio",
        "impianto", "consulenza", "trasporto", "noleggio",
        "materiale laboratorio", "dpi", "imballo", "confezion",
        "analisi", "mescolazione", "lavorazione", "lavaggio"
    ]

    if (
        code.startswith("AC") or
        code.startswith("LV") or
        code.startswith("MAR") or
        code.startswith("MLI") or
        any(x in txt for x in esclusioni)
    ):
        return "Escludi"

    # Regola stretta: includo solo ciò che è tecnicamente pertinente.
    if code.startswith("MDR"):
        return "Droghe"
    if code.startswith("ME"):
        if "maltodestrina" in txt or "malto" in txt:
            return "Carrier - Maltodestrina"
        return "Materie prime / eccipienti"
    if code.startswith(("F", "W", "Y", "A", "S", "T", "V")):
        return "Estratti"

    return "Escludi"

    if code.startswith("MDR"):
        return "Droghe"
    if code.startswith("ME"):
        if "maltodestrina" in txt or "malto" in txt:
            return "Carrier - Maltodestrina"
        return "Materie prime / eccipienti"
    if code.startswith(("F","W","Y","A","S","T","V")):
        return "Estratti"

    return "Escludi"

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

def make_option_label(code, desc):
    code = str(code).strip()
    desc = str(desc).strip()
    return f"{code} | {desc}" if desc else code

def select_code_from_df(df, code_col, desc_col, label, key):
    if df.empty:
        return None
    opts_df = df[[code_col, desc_col]].drop_duplicates().copy()
    opts_df["_label"] = opts_df.apply(lambda r: make_option_label(r[code_col], r[desc_col]), axis=1)
    opts = sorted(opts_df["_label"].dropna().unique())
    if not opts:
        return None
    selected_label = st.selectbox(
        label,
        opts,
        index=None,
        placeholder="Scrivi codice o descrizione...",
        key=key,
        help="Digita parte del codice o della descrizione: l'elenco si filtra automaticamente."
    )
    return selected_label.split(" | ")[0] if selected_label else None

def line_by_year(df, x_col, y_col, title, custom_cols=None, height=420):
    custom_cols = custom_cols or []
    if df.empty:
        st.warning("Nessun dato disponibile.")
        return
    d = df.copy()
    d[x_col] = d[x_col].astype(int).astype(str)
    fig = px.line(
        d.sort_values(x_col),
        x=x_col,
        y=y_col,
        markers=True,
        title=title,
        custom_data=custom_cols
    )
    if custom_cols:
        hover = "".join([f"<br>{col}: %{{customdata[{i}]}}" for i, col in enumerate(custom_cols)])
        fig.update_traces(hovertemplate="<b>%{x}</b><br>Valore: %{y:,.2f}" + hover + "<extra></extra>")
    fig.update_xaxes(type="category")
    layout(fig, height)
    st.plotly_chart(fig, use_container_width=True)

def annual_line(df, x_col, y_col, title, custom_cols=None, height=420):
    custom_cols = custom_cols or []
    if df.empty:
        st.warning("Nessun dato disponibile.")
        return
    d = df.copy()
    d[x_col] = d[x_col].astype(int).astype(str)
    fig = px.line(d.sort_values(x_col), x=x_col, y=y_col, markers=True, title=title, custom_data=custom_cols)
    if custom_cols:
        hover = "".join([f"<br>{col}: %{{customdata[{i}]}}" for i, col in enumerate(custom_cols)])
        fig.update_traces(hovertemplate="<b>%{x}</b><br>Valore: %{y:,.2f}" + hover + "<extra></extra>")
    fig.update_xaxes(type="category")
    layout(fig, height)
    st.plotly_chart(fig, use_container_width=True)


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
    df = df.copy()
    df["Anno"] = df["Anno"].astype("Int64")
    df["Anno_Label"] = df["Anno"].astype(str)
    df = df.sort_values(["Anno","Mese_Num"])
    cum_col = f"{y}_Cumulato"
    df[cum_col] = df.groupby("Anno")[y].cumsum()
    color_col = "Anno_Label"
    fig = px.line(
        df, x="Mese_Nome", y=cum_col, color=color_col,
        color_discrete_map=YEAR_COLORS,
        markers=True,
        category_orders={"Mese_Nome": MONTH_ORDER},
        title=title.replace("Trend", "Cumulativo").replace("trend", "cumulativo"),
        custom_data=hover_cols + [y]
    )
    if hover_cols:
        raw_idx = len(hover_cols)
        hover = "".join([f"<br>{col}: %{{customdata[{i}]}}" for i, col in enumerate(hover_cols)])
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

    # Ulteriore controllo difensivo: restano solo MDR, ME e codici estratto/prodotto.
    cod = df["MVCODART"].astype(str).str.upper().str.strip()
    mask_codici_validi = (
        cod.str.startswith("MDR") |
        cod.str.startswith("ME") |
        cod.str.startswith(("F","W","Y","A","S","T","V"))
    )
    df = df[mask_codici_validi].copy()
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


def build_drug_yield(comm):
    sem = comm[comm["CODART"].apply(is_semilav)].copy()
    rows = []
    if sem.empty:
        return pd.DataFrame()

    for (sem_code, lotto), g in sem.groupby(["CODART","LOTTO_FINITO"]):
        qta_sem = float(g["QTA_FINITO"].iloc[0]) if len(g) else 0
        data = g["DATA_COM"].max()
        anno = int(data.year) if pd.notna(data) else None

        malto_qty = g[g.apply(lambda r: is_malto(r["COD_COMP"], r["DES_COMP"]), axis=1)]["QTA_LOTTO"].sum()
        taglio = malto_qty / qta_sem if qta_sem > 0 else np.nan

        mdr_rows = g[g["COD_COMP"].apply(is_mdr)].copy()
        if mdr_rows.empty:
            continue

        for _, mdr in mdr_rows.iterrows():
            droga_kg = float(mdr.get("QTA_LOTTO", 0) or 0)
            if droga_kg <= 0:
                continue

            mass_yield = np.nan
            if pd.notna(data) and data.year >= 2026 and {"MOL_QTAKG","MOL_RESIDUO"}.issubset(g.columns):
                mol = g[["MOL_QTAKG","MOL_RESIDUO"]].drop_duplicates()
                mol = mol[(mol["MOL_QTAKG"] > 0) & (mol["MOL_RESIDUO"] > 0)]
                if len(mol):
                    rs = mol["MOL_RESIDUO"].astype(float)
                    rs = np.where(rs > 1, rs / 100, rs)
                    secco = (mol["MOL_QTAKG"].astype(float).values * rs).sum()
                    if secco > 0:
                        mass_yield = secco / droga_kg

            if pd.isna(mass_yield):
                mass_yield = (qta_sem - malto_qty) / droga_kg
                if mass_yield < 0:
                    mass_yield = np.nan

            rows.append({
                "Anno": anno,
                "Data": data,
                "Droga_Codice": str(mdr.get("COD_COMP","")).strip(),
                "Droga_Descrizione": str(mdr.get("DES_COMP","")).strip(),
                "Semilavorato_Codice": sem_code,
                "Semilavorato_Descrizione": str(g["ARDESART"].iloc[0]) if len(g) else "",
                "Lotto": lotto,
                "Droga_Kg": droga_kg,
                "Kg_Semilav": qta_sem,
                "Malto_Kg": malto_qty,
                "Mass_Yield": mass_yield,
                "Taglio_Malto": taglio,
                "Mass_Yield_%": mass_yield * 100 if pd.notna(mass_yield) else np.nan,
                "Taglio_Malto_%": taglio * 100 if pd.notna(taglio) else np.nan,
            })

    return pd.DataFrame(rows)

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
        sem_master = pd.DataFrame(columns=["Codice","Descrizione","Kg","Malto_Qty","N_Lotti","Taglio_Malto","Mass_Yield","Droga_Codice","Droga_Descrizione","Droga_Kg"])

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
drug_yield = build_drug_yield(comm)

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
    "Formulazioni",
    "Acquisti",
    "Vendite",
    "Ricerca codice"
])

# Executive
with tabs[0]:
    l,r = st.columns(2)
    with l:
        fam = filtered_lots.groupby("Famiglia", as_index=False)["Kg"].sum().sort_values("Kg", ascending=True)
        fig = px.bar(fam, x="Kg", y="Famiglia", orientation="h", title="Kg prodotti per famiglia", text_auto=".2s")
        layout(fig, 430); st.plotly_chart(fig, use_container_width=True)
    with r:
        if len(filtered_rep_summary):
            fig = px.bar(filtered_rep_summary.sort_values("Kg_Lavorato", ascending=True), x="Kg_Lavorato", y="Reparto", orientation="h", title="Kg lavorati per reparto", text_auto=".2s")
            layout(fig, 430); st.plotly_chart(fig, use_container_width=True)

    st.markdown("### Top 20 produzioni per famiglia")
    c1, c2 = st.columns(2)
    with c1:
        top_fluidi = filtered_lots[filtered_lots["Famiglia"]=="Fluido"].groupby(["CODART","Descrizione"], as_index=False).agg(
            Kg=("Kg","sum"), N_Lotti=("LOTTO_FINITO","nunique")
        ).sort_values("Kg", ascending=False).head(20)
        top_bar(top_fluidi, "Kg", "CODART", "Top 20 estratti fluidi", ["Descrizione","N_Lotti"], 520)
    with c2:
        top_secchi = filtered_lots[filtered_lots["Famiglia"]=="Estratto secco finito"].groupby(["CODART","Descrizione"], as_index=False).agg(
            Kg=("Kg","sum"), N_Lotti=("LOTTO_FINITO","nunique")
        ).sort_values("Kg", ascending=False).head(20)
        top_bar(top_secchi, "Kg", "CODART", "Top 20 estratti secchi finiti", ["Descrizione","N_Lotti"], 520)

    st.markdown("### Ricerca produzione codice")
    prod_search_base = filtered_lots.copy()
    codice_sel = select_code_from_df(prod_search_base, "CODART", "Descrizione", "Cerca codice o descrizione", "exec_code_select_single")
    if codice_sel:
        prod_code = prod_search_base[prod_search_base["CODART"] == codice_sel]
        annual = prod_code.groupby(["Anno"], as_index=False).agg(Kg=("Kg","sum"), N_Lotti=("LOTTO_FINITO","nunique"))
        line_by_year(annual, "Anno", "Kg", f"Produzione annua - {codice_sel}", ["N_Lotti"], 420)
        st.dataframe(prod_code[["CODART","Descrizione","LOTTO_FINITO","Data","Kg","Famiglia","Uso","Titolato"]].sort_values("Data", ascending=False), use_container_width=True, height=260)

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

        if selected == "Estrazione" and len(drug_yield):
            st.markdown("### Mass Yield e taglio malto per droga lavorata")

            dy = drug_yield.dropna(subset=["Mass_Yield_%"]).copy()
            droga_sel = select_code_from_df(
                dy,
                "Droga_Codice",
                "Droga_Descrizione",
                "Cerca codice o descrizione droga",
                "estrazione_droga_select"
            )

            if droga_sel:
                dy = dy[dy["Droga_Codice"] == droga_sel].copy()

            yearly_drug = dy.groupby(["Anno","Droga_Codice","Droga_Descrizione"], as_index=False).agg(
                Mass_Yield_Medio=("Mass_Yield_%","mean"),
                Taglio_Malto_Medio=("Taglio_Malto_%","mean"),
                Droga_Kg=("Droga_Kg","sum"),
                Kg_Semilav=("Kg_Semilav","sum"),
                N_Lotti=("Lotto","nunique")
            ).dropna(subset=["Anno"])

            if len(yearly_drug):
                cmy1, cmy2 = st.columns(2)
                with cmy1:
                    fig = px.line(
                        yearly_drug.sort_values("Anno"),
                        x="Anno",
                        y="Mass_Yield_Medio",
                        color="Droga_Codice" if not droga_sel else None,
                        markers=True,
                        title="Trend annuo Mass Yield medio per droga",
                        custom_data=["Droga_Descrizione","Droga_Kg","Kg_Semilav","N_Lotti"]
                    )
                    fig.update_traces(hovertemplate="<b>%{x}</b><br>Mass Yield: %{y:.1f}%<br>Droga: %{customdata[0]}<br>Kg droga: %{customdata[1]:,.2f}<br>Kg semilav: %{customdata[2]:,.2f}<br>Lotti: %{customdata[3]}<extra></extra>")
                    fig.update_yaxes(ticksuffix="%")
                    fig.update_xaxes(type="category")
                    layout(fig, 430)
                    st.plotly_chart(fig, use_container_width=True)

                with cmy2:
                    fig = px.line(
                        yearly_drug.sort_values("Anno"),
                        x="Anno",
                        y="Taglio_Malto_Medio",
                        color="Droga_Codice" if not droga_sel else None,
                        markers=True,
                        title="Trend annuo taglio malto medio per droga",
                        custom_data=["Droga_Descrizione","Droga_Kg","Kg_Semilav","N_Lotti"]
                    )
                    fig.update_traces(hovertemplate="<b>%{x}</b><br>Taglio malto: %{y:.1f}%<br>Droga: %{customdata[0]}<br>Kg droga: %{customdata[1]:,.2f}<br>Kg semilav: %{customdata[2]:,.2f}<br>Lotti: %{customdata[3]}<extra></extra>")
                    fig.update_yaxes(ticksuffix="%")
                    fig.update_xaxes(type="category")
                    layout(fig, 430)
                    st.plotly_chart(fig, use_container_width=True)

            st.markdown("### Tabella per codice droga lavorata")
            drug_table = dy.groupby(["Droga_Codice","Droga_Descrizione"], as_index=False).agg(
                Mass_Yield_Medio=("Mass_Yield_%","mean"),
                Taglio_Malto_Medio=("Taglio_Malto_%","mean"),
                Droga_Kg=("Droga_Kg","sum"),
                Kg_Semilav=("Kg_Semilav","sum"),
                N_Semilav=("Semilavorato_Codice","nunique"),
                N_Lotti=("Lotto","nunique")
            ).sort_values("Droga_Kg", ascending=False)

            st.dataframe(
                drug_table,
                use_container_width=True,
                height=360,
                column_config={
                    "Mass_Yield_Medio": st.column_config.NumberColumn("Mass Yield medio", format="%.1f%%"),
                    "Taglio_Malto_Medio": st.column_config.NumberColumn("Taglio medio malto", format="%.1f%%"),
                    "Droga_Kg": st.column_config.NumberColumn("Kg droga", format="%.0f"),
                    "Kg_Semilav": st.column_config.NumberColumn("Kg semilav", format="%.0f"),
                }
            )

            st.markdown("### Dettaglio semilavorati collegati alla droga")
            detail_cols = [
                "Droga_Codice","Droga_Descrizione","Semilavorato_Codice",
                "Semilavorato_Descrizione","Lotto","Data","Kg_Semilav",
                "Droga_Kg","Mass_Yield_%","Taglio_Malto_%"
            ]
            detail_cols = [c for c in detail_cols if c in dy.columns]
            st.dataframe(
                dy[detail_cols].sort_values("Data", ascending=False),
                use_container_width=True,
                height=360,
                column_config={
                    "Mass_Yield_%": st.column_config.NumberColumn("Mass Yield", format="%.1f%%"),
                    "Taglio_Malto_%": st.column_config.NumberColumn("Taglio malto", format="%.1f%%"),
                    "Kg_Semilav": st.column_config.NumberColumn("Kg semilav", format="%.0f"),
                    "Droga_Kg": st.column_config.NumberColumn("Kg droga", format="%.0f"),
                }
            )

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
            month["Anno_Label"] = month["Anno"].astype(int).astype(str)
            l,r = st.columns(2)
            with l:
                monthly_year_line(month, f"{title} - cumulativo mensile per anno", "Kg", ["Anno","N_Lotti","N_Codici"])
            with r:
                top = data.groupby(["CODART","Descrizione"], as_index=False).agg(
                    Kg=("Kg","sum"),
                    N_Lotti=("LOTTO_FINITO","nunique"),
                    Uso=("Uso","first"),
                    Titolato=("Titolato","first")
                ).sort_values("Kg", ascending=False).head(15)
                top_bar(top, "Kg", "CODART", f"{title} - top codici", ["Descrizione","N_Lotti","Uso","Titolato"], 430)
            st.markdown("### Dettaglio codice")
            codice_fam = select_code_from_df(data, "CODART", "Descrizione", "Cerca codice o descrizione", f"family_code_{fam}")
            if codice_fam:
                code_data = data[data["CODART"] == codice_fam]
                ann = code_data.groupby("Anno", as_index=False).agg(Kg=("Kg","sum"), N_Lotti=("LOTTO_FINITO","nunique"))
                line_by_year(ann, "Anno", "Kg", f"Produzione annua - {codice_fam}", ["N_Lotti"], 390)
                st.dataframe(code_data[["CODART","Descrizione","LOTTO_FINITO","Data","Kg","Famiglia","Uso","Titolato"]].sort_values("Data", ascending=False), use_container_width=True, height=260)

# Formulazioni
with tabs[3]:
    st.subheader("Formulazioni e utilizzo maltodestrina")

    pf_form_no_fluid = pf_form[(pf_form["Famiglia"] == "Estratto secco finito")].copy()
    pf_trend_no_fluid = pf_malto_trend[(pf_malto_trend["Famiglia"] == "Estratto secco finito")].copy()

    st.markdown("### Trend % utilizzo malto nei prodotti finiti")
    if len(pf_trend_no_fluid):
        pf_pct = pf_trend_no_fluid.dropna(subset=["Anno"]).copy()
        pf_pct = pf_pct.groupby("Anno", as_index=False).agg(
            Malto_Totale_Media=("Malto_Totale_%","mean"),
            Malto_Diretta_Media=("Malto_Diretta_Kg","sum"),
            Malto_da_Semilav_Media=("Malto_da_Semilav_Kg","sum"),
            N_Lotti=("Lotto","nunique")
        )
        fig = px.line(
            pf_pct.sort_values("Anno"),
            x="Anno",
            y="Malto_Totale_Media",
            markers=True,
            title="Media aritmetica % malto totale - prodotti finiti",
            custom_data=["N_Lotti"]
        )
        fig.update_traces(hovertemplate="<b>%{x}</b><br>Malto medio: %{y:.1%}<br>Lotti: %{customdata[0]}<extra></extra>")
        fig.update_yaxes(tickformat=".0%")
        layout(fig, 420)
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("### Trend % utilizzo malto nei semilavorati")
    if len(sem_lotti):
        sem_pct = sem_lotti.dropna(subset=["Anno","Taglio_Malto"]).copy()
        sem_pct = sem_pct.groupby("Anno", as_index=False).agg(
            Taglio_Malto_Medio=("Taglio_Malto","mean"),
            N_Lotti=("Lotto","nunique")
        )
        fig = px.line(
            sem_pct.sort_values("Anno"),
            x="Anno",
            y="Taglio_Malto_Medio",
            markers=True,
            title="Media aritmetica % malto - semilavorati",
            custom_data=["N_Lotti"]
        )
        fig.update_traces(hovertemplate="<b>%{x}</b><br>Taglio medio: %{y:.1%}<br>Lotti: %{customdata[0]}<extra></extra>")
        fig.update_yaxes(tickformat=".0%")
        layout(fig, 420)
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("### Kg malto diretta vs malto da semilavorato")
    if len(pf_trend_no_fluid):
        pf_year = pf_trend_no_fluid.groupby("Anno", as_index=False).agg(
            Malto_Diretta_Kg=("Malto_Diretta_Kg","sum"),
            Malto_da_Semilav_Kg=("Malto_da_Semilav_Kg","sum"),
        )
        pf_long = pf_year.melt(id_vars=["Anno"], value_vars=["Malto_Diretta_Kg","Malto_da_Semilav_Kg"], var_name="Tipo malto", value_name="Kg")
        fig = px.bar(pf_long, x="Anno", y="Kg", color="Tipo malto", title="Kg malto diretta vs malto da semilavorato - estratti secchi finiti", barmode="stack")
        layout(fig, 430)
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("### Ricerca formulazione per codice")
    form_view = pf_form_no_fluid.copy()
    codice_form = select_code_from_df(form_view, "Codice", "Descrizione", "Cerca codice o descrizione", "form_code_select")
    if codice_form:
        row = form_view[form_view["Codice"] == codice_form].sort_values("Malto_Totale_%", ascending=False).head(1)
        if len(row):
            r0 = row.iloc[0]
            c1,c2,c3,c4 = st.columns(4)
            c1.metric("Malto totale", f"{r0['Malto_Totale_%']*100:.1f}%")
            c2.metric("Malto diretta", f"{r0['Malto_Diretta_%']*100:.1f}%")
            c3.metric("Malto da semilav", f"{r0['Malto_da_Semilav_%']*100:.1f}%")
            c4.metric("Semilav totale", f"{r0['Semilav_%']*100:.1f}%")
            st.dataframe(row[["Codice","Descrizione","Lotto","Kg_Lotto","Malto_Totale_%","Malto_Diretta_%","Malto_da_Semilav_%","Semilav_%","Semilavorati"]], use_container_width=True, height=130)

# Acquisti
with tabs[4]:
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
        categorie_acq = sorted(filtered_acq["Categoria"].dropna().unique())
        sel_cat_acq = st.multiselect("Tipologia acquisti", categorie_acq, default=categorie_acq, key="cat_acq_cumulativo")
        acq_cum_base = filtered_acq[filtered_acq["Categoria"].isin(sel_cat_acq)].copy()
        month = acq_cum_base.groupby(["Anno","Mese_Num","Mese_Nome"], as_index=False).agg(Kg=("QTAVEN","sum"), Valore=("TOTVEN","sum"), N_Articoli=("MVCODART","nunique"), N_Fornitori=("ANDESCRI","nunique"))
        month = month.sort_values(["Anno","Mese_Num"]).copy()
        month["Anno_Label"] = month["Anno"].astype(int).astype(str)
        month[f"{metric_acq}_Cumulato"] = month.groupby("Anno")[metric_acq].cumsum()
        fig = px.line(
            month,
            x="Mese_Nome",
            y=f"{metric_acq}_Cumulato",
            color="Anno_Label",
            markers=True,
            category_orders={"Mese_Nome":MONTH_ORDER},
            title=f"Cumulativo mensile acquisti - {metric_acq}",
            custom_data=["Anno","N_Articoli","N_Fornitori"]
        )
        fig.update_traces(hovertemplate="<b>%{x} %{customdata[0]}</b><br>Valore: %{y:,.2f}<br>Articoli: %{customdata[1]}<br>Fornitori: %{customdata[2]}<extra></extra>")
        layout(fig, 450)
        st.plotly_chart(fig, use_container_width=True)

        st.markdown("### Trend annuale acquisti")
        annual_acq = acq_cum_base.groupby("Anno", as_index=False).agg(
            Kg=("QTAVEN","sum"), Valore=("TOTVEN","sum"),
            N_Articoli=("MVCODART","nunique"), N_Fornitori=("ANDESCRI","nunique")
        )
        metric_acq_ann = st.radio("Metrica trend annuale acquisti", ["Valore","Kg"], horizontal=True, key="metric_acq_ann")
        annual_line(annual_acq, "Anno", metric_acq_ann, f"Trend annuale acquisti - {metric_acq_ann}", ["N_Articoli","N_Fornitori"], 420)

        st.markdown("### Top articoli acquistati")
        top_art = filtered_acq.groupby(["MVCODART","ARDESART","Categoria"], as_index=False).agg(Kg=("QTAVEN","sum"), Valore=("TOTVEN","sum"), N_Fornitori=("ANDESCRI","nunique")).sort_values("Valore", ascending=False).head(30)
        st.dataframe(top_art, use_container_width=True, height=420)

        st.markdown("### Ricerca articolo acquistato")
        acq_code_view = filtered_acq.copy()
        codice_acq = select_code_from_df(acq_code_view, "MVCODART", "ARDESART", "Cerca codice o descrizione articolo acquistato", "acq_code_select")
        if codice_acq:
                acq_art = acq_code_view[acq_code_view["MVCODART"] == codice_acq].copy()
                cqa, cva, cfa = st.columns(3)
                cqa.metric("Kg acquistati", fmt(acq_art["QTAVEN"].sum()) + " kg")
                cva.metric("Valore", money(acq_art["TOTVEN"].sum()))
                cfa.metric("N° fornitori", fmt(acq_art["ANDESCRI"].nunique()))
                forn = acq_art.groupby("ANDESCRI", as_index=False).agg(Kg=("QTAVEN","sum"), Valore=("TOTVEN","sum")).sort_values("Valore", ascending=False)
                st.dataframe(forn, use_container_width=True, height=220)
                andamento = acq_art.groupby(["Anno","Mese_Num","Mese_Nome"], as_index=False).agg(Kg=("QTAVEN","sum"), Valore=("TOTVEN","sum"))
                met_art_acq = st.radio("Metrica articolo acquistato", ["Valore","Kg"], horizontal=True, key="met_art_acq")
                andamento = andamento.sort_values(["Anno","Mese_Num"]).copy()
                andamento["Anno_Label"] = andamento["Anno"].astype(int).astype(str)
                andamento[f"{met_art_acq}_Cumulato"] = andamento.groupby("Anno")[met_art_acq].cumsum()
                fig = px.line(andamento, x="Mese_Nome", y=f"{met_art_acq}_Cumulato", color="Anno_Label", color_discrete_map=YEAR_COLORS, markers=True, category_orders={"Mese_Nome":MONTH_ORDER}, title=f"Cumulativo acquisti articolo - {codice_acq}", custom_data=["Anno", met_art_acq])
                fig.update_traces(hovertemplate="<b>%{x} %{customdata[0]}</b><br>Cumulato: %{y:,.2f}<br>Mese: %{customdata[1]:,.2f}<extra></extra>")
                layout(fig, 420)
                st.plotly_chart(fig, use_container_width=True)

                annual_art_acq = acq_art.groupby("Anno", as_index=False).agg(Valore=("TOTVEN","sum"), Kg=("QTAVEN","sum"), N_Fornitori=("ANDESCRI","nunique"))
                annual_line(annual_art_acq, "Anno", met_art_acq, f"Trend annuale acquisti articolo - {codice_acq}", ["N_Fornitori"], 360)

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
            fm["Anno_Label"] = fm["Anno"].astype(int).astype(str)
            fm[f"{met_f}_Cumulato"] = fm.groupby("Anno")[met_f].cumsum()
            fig = px.line(fm, x="Mese_Nome", y=f"{met_f}_Cumulato", color="Anno_Label", color_discrete_map=YEAR_COLORS, markers=True, category_orders={"Mese_Nome":MONTH_ORDER}, title=f"Cumulativo fornitore - {fornitore}", custom_data=["Anno","N_Articoli", met_f])
            fig.update_traces(hovertemplate="<b>%{x} %{customdata[0]}</b><br>Cumulato: %{y:,.2f}<br>Mese: %{customdata[2]:,.2f}<br>Articoli: %{customdata[1]}<extra></extra>")
            layout(fig, 420)
            st.plotly_chart(fig, use_container_width=True)

            annual_f = fa.groupby("Anno", as_index=False).agg(Valore=("TOTVEN","sum"), Kg=("QTAVEN","sum"), N_Articoli=("MVCODART","nunique"))
            annual_line(annual_f, "Anno", met_f, f"Trend annuale fornitore - {fornitore}", ["N_Articoli"], 360)

# Vendite
with tabs[5]:
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
        metric_v = st.radio("Metrica vendite", ["Fatturato","Kg"], horizontal=True, help="Puoi visualizzare sia fatturato sia quantità venduta.")
        month = month.sort_values(["Anno","Mese_Num"]).copy()
        month["Anno_Label"] = month["Anno"].astype(int).astype(str)
        month[f"{metric_v}_Cumulato"] = month.groupby("Anno")[metric_v].cumsum()
        fig = px.line(
            month,
            x="Mese_Nome",
            y=f"{metric_v}_Cumulato",
            color="Anno_Label",
            markers=True,
            category_orders={"Mese_Nome":MONTH_ORDER},
            title=f"Cumulativo mensile vendite - {metric_v}",
            custom_data=["Anno","N_Clienti","N_Codici"]
        )
        fig.update_traces(hovertemplate="<b>%{x} %{customdata[0]}</b><br>Valore: %{y:,.2f}<br>Clienti: %{customdata[1]}<br>Codici: %{customdata[2]}<extra></extra>")
        layout(fig, 480)
        st.plotly_chart(fig, use_container_width=True)

        st.markdown("### Trend annuale vendite")
        annual_ven = filtered_ven.groupby("Anno", as_index=False).agg(
            Kg=("QTA","sum"), Fatturato=("IMPORTO","sum"),
            N_Clienti=("RAGSOC","nunique"), N_Codici=("CODART","nunique")
        )
        metric_v_ann = st.radio("Metrica trend annuale vendite", ["Fatturato","Kg"], horizontal=True, key="metric_v_ann")
        annual_line(annual_ven, "Anno", metric_v_ann, f"Trend annuale vendite - {metric_v_ann}", ["N_Clienti","N_Codici"], 420)

        st.markdown("### Top 20 vendite per famiglia")
        tv1, tv2 = st.columns(2)
        with tv1:
            top_fluidi_v = filtered_ven[filtered_ven["Famiglia"]=="Fluido"].groupby(["CODART","DESART","Famiglia"], as_index=False).agg(
                Kg=("QTA","sum"), Fatturato=("IMPORTO","sum"), N_Clienti=("RAGSOC","nunique")
            ).sort_values("Fatturato", ascending=False).head(20)
            top_bar(top_fluidi_v, "Fatturato", "CODART", "Top 20 fluidi venduti", ["DESART","Kg","N_Clienti"], 520)
        with tv2:
            top_secchi_v = filtered_ven[filtered_ven["Famiglia"]=="Estratto secco finito"].groupby(["CODART","DESART","Famiglia"], as_index=False).agg(
                Kg=("QTA","sum"), Fatturato=("IMPORTO","sum"), N_Clienti=("RAGSOC","nunique")
            ).sort_values("Fatturato", ascending=False).head(20)
            top_bar(top_secchi_v, "Fatturato", "CODART", "Top 20 estratti secchi finiti venduti", ["DESART","Kg","N_Clienti"], 520)

        st.markdown("### Ricerca articolo venduto")
        ven_code_view = filtered_ven.copy()
        codice_ven = select_code_from_df(ven_code_view, "CODART", "DESART", "Cerca codice o descrizione articolo venduto", "ven_code_select")
        if codice_ven:
                ven_art = ven_code_view[ven_code_view["CODART"] == codice_ven].copy()
                cvq, cvf, cvp, cvc = st.columns(4)
                cvq.metric("Kg venduti", fmt(ven_art["QTA"].sum()) + " kg")
                cvf.metric("Fatturato", money(ven_art["IMPORTO"].sum()))
                prezzo_medio_art = ven_art["IMPORTO"].sum()/ven_art["QTA"].sum() if ven_art["QTA"].sum() else 0
                cvp.metric("Prezzo medio €/kg", f"{prezzo_medio_art:,.2f}".replace(",", "."))
                cvc.metric("N° clienti", fmt(ven_art["RAGSOC"].nunique()))
                clienti_art = ven_art.groupby("RAGSOC", as_index=False).agg(Kg=("QTA","sum"), Fatturato=("IMPORTO","sum")).sort_values("Fatturato", ascending=False)
                st.dataframe(clienti_art, use_container_width=True, height=220)
                andamento = ven_art.groupby(["Anno","Mese_Num","Mese_Nome"], as_index=False).agg(Kg=("QTA","sum"), Fatturato=("IMPORTO","sum"))
                andamento["Prezzo_medio"] = np.where(andamento["Kg"] > 0, andamento["Fatturato"]/andamento["Kg"], np.nan)
                met_art_ven = st.radio("Metrica articolo venduto", ["Fatturato","Kg","Prezzo_medio"], horizontal=True, key="met_art_ven", help="Puoi scegliere fatturato, quantità o prezzo medio €/kg.")
                andamento = andamento.sort_values(["Anno","Mese_Num"]).copy()
                andamento["Anno_Label"] = andamento["Anno"].astype(int).astype(str)
                if met_art_ven != "Prezzo_medio":
                    andamento[f"{met_art_ven}_Cumulato"] = andamento.groupby("Anno")[met_art_ven].cumsum()
                    ycol = f"{met_art_ven}_Cumulato"
                    titolo = f"Cumulativo vendite articolo - {codice_ven}"
                else:
                    ycol = "Prezzo_medio"
                    titolo = f"Andamento prezzo medio articolo - {codice_ven}"
                fig = px.line(andamento, x="Mese_Nome", y=ycol, color="Anno_Label", color_discrete_map=YEAR_COLORS, markers=True, category_orders={"Mese_Nome":MONTH_ORDER}, title=titolo, custom_data=["Anno", met_art_ven])
                fig.update_traces(hovertemplate="<b>%{x} %{customdata[0]}</b><br>Valore: %{y:,.2f}<br>Mese: %{customdata[1]:,.2f}<extra></extra>")
                layout(fig, 420)
                st.plotly_chart(fig, use_container_width=True)

                if met_art_ven != "Prezzo_medio":
                    annual_art_ven = ven_art.groupby("Anno", as_index=False).agg(Fatturato=("IMPORTO","sum"), Kg=("QTA","sum"), N_Clienti=("RAGSOC","nunique"))
                    annual_line(annual_art_ven, "Anno", met_art_ven, f"Trend annuale vendite articolo - {codice_ven}", ["N_Clienti"], 360)
                else:
                    annual_art_ven = ven_art.groupby("Anno", as_index=False).agg(Fatturato=("IMPORTO","sum"), Kg=("QTA","sum"), N_Clienti=("RAGSOC","nunique"))
                    annual_art_ven["Prezzo_medio"] = np.where(annual_art_ven["Kg"] > 0, annual_art_ven["Fatturato"]/annual_art_ven["Kg"], np.nan)
                    annual_line(annual_art_ven, "Anno", "Prezzo_medio", f"Trend annuale prezzo medio articolo - {codice_ven}", ["N_Clienti"], 360)

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
            met_c = st.radio("Metrica dettaglio cliente", ["Fatturato","Kg"], horizontal=True, key="met_cliente_vendite", help="Puoi visualizzare sia fatturato sia quantità venduta.")
            cm = cm.sort_values(["Anno","Mese_Num"]).copy()
            cm["Anno_Label"] = cm["Anno"].astype(int).astype(str)
            cm[f"{met_c}_Cumulato"] = cm.groupby("Anno")[met_c].cumsum()
            fig = px.line(cm, x="Mese_Nome", y=f"{met_c}_Cumulato", color="Anno_Label", color_discrete_map=YEAR_COLORS, markers=True, category_orders={"Mese_Nome":MONTH_ORDER}, title=f"Cumulativo cliente - {cliente}", custom_data=["Anno","N_Codici", met_c])
            fig.update_traces(hovertemplate="<b>%{x} %{customdata[0]}</b><br>Cumulato: %{y:,.2f}<br>Mese: %{customdata[2]:,.2f}<br>Codici: %{customdata[1]}<extra></extra>")
            layout(fig, 420)
            st.plotly_chart(fig, use_container_width=True)


# Search
with tabs[6]:
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
