
from pathlib import Path
import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="EVRA Dashboard", page_icon="🌿", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
.stApp {background: radial-gradient(circle at top left, #162238 0%, #0b1020 45%, #070b14 100%); color: #eef2ff;}
.block-container { padding-top: 1rem; padding-bottom: 2rem; }
h1, h2, h3 { color: #eef2ff; }
div[data-testid="stMetric"] {background: rgba(18,24,42,.96); border:1px solid #26314d; padding:16px; border-radius:18px;}
section[data-testid="stSidebar"] {background:#090e1c; border-right:1px solid #26314d;}
.stTabs [data-baseweb="tab"] {background:#12182a; border:1px solid #26314d; border-radius:999px; color:#eef2ff; padding:8px 16px;}
.stTabs [aria-selected="true"] {background:#1f4e78 !important;}
.small-note { color:#9aa4bf; font-size:.9rem; }
</style>
""", unsafe_allow_html=True)

DATA_DIR = Path(__file__).parent / "data"
COMMESSE_PATH = DATA_DIR / "commesse.xlsx"
REPARTI_PATH = DATA_DIR / "reparti.xlsx"
LOGO_PATH = Path(__file__).parent / "assets" / "evra_logo.svg"

MONTH_MAP = {1:"Gen",2:"Feb",3:"Mar",4:"Apr",5:"Mag",6:"Giu",7:"Lug",8:"Ago",9:"Set",10:"Ott",11:"Nov",12:"Dic"}
MONTH_ORDER = list(MONTH_MAP.values())

def is_semilav(code): return str(code).startswith(("W","Y"))
def is_mdr(code): return str(code).startswith("MDR")
def is_malto(code, desc):
    s = (str(code)+" "+str(desc)).lower()
    return str(code).startswith("MECMLT") or "maltodestrina" in s or "malto" in s

def famiglia(code):
    code = str(code)
    if code.startswith(("W","Y")): return "Semilavorato"
    if code.startswith("F"): return "Fluido"
    if code.startswith("V"): return "Conto lavoro"
    if code.startswith(("A","S","T")): return "Estratto secco finito"
    if code.startswith("MDR"): return "Droga vegetale"
    if code.startswith("ME"): return "Materia prima / carrier"
    return "Altro"

def uso(code):
    code = str(code)
    if not code: return "ND"
    if code[-1] == "A": return "Alimentare"
    if code[-1] == "C": return "Cosmetico"
    if code[-1] == "P": return "Feed"
    return "ND"

def titolato(desc): return "%" in str(desc)

def normalize_reparto(desc):
    d = str(desc).strip().lower()
    if "gran" in d: return "Granulazione"
    if "misc" in d or "mescol" in d: return "Miscelazione"
    if "atom" in d or "spray" in d: return "Atomizzazione"
    if "micr" in d: return "Micronizzazione"
    if "fluid" in d or "flui" in d: return "Fluidi"
    if "estr" in d: return "Estrazione"
    return str(desc).strip() if str(desc).strip() else "ND"

def exclude_reparto(desc):
    d = str(desc).lower()
    return ("past" in d) or ("concent" in d)

def fmt(v):
    try: return f"{float(v):,.0f}".replace(",", ".")
    except Exception: return "0"

def add_month(df, col="Data"):
    df = df.copy()
    df["Anno"] = df[col].dt.year
    df["Mese_Num"] = df[col].dt.month
    df["Mese_Nome"] = df["Mese_Num"].map(MONTH_MAP)
    df["Mese"] = df[col].dt.to_period("M").astype(str)
    return df

def layout(fig, h=420):
    fig.update_layout(template="plotly_dark", height=h, margin=dict(l=10,r=10,t=55,b=10))
    return fig

@st.cache_data(show_spinner=False)
def load_commesse(path):
    df = pd.read_excel(path)
    for c in ["CODART","ARDESART","LOTTO_FINITO","COD_COMP","DES_COMP","LOTTO"]:
        if c in df.columns: df[c] = df[c].fillna("").astype(str).str.strip()
    df["DATA_COM"] = pd.to_datetime(df["DATA_COM"], errors="coerce")
    for c in ["QTA_FINITO","QTA_LOTTO","MOL_QTAKG","MOL_RESIDUO","MOL_TAGLIO"]:
        if c in df.columns: df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
    return df

@st.cache_data(show_spinner=False)
def load_reparti(path):
    if not path.exists(): return pd.DataFrame()
    df = pd.read_excel(path)
    for c in df.columns:
        if df[c].dtype == object: df[c] = df[c].fillna("").astype(str).str.strip()
    return df

@st.cache_data(show_spinner=False)
def build(comm, rep):
    lots = comm.groupby(["CODART","LOTTO_FINITO"], as_index=False).agg(
        Descrizione=("ARDESART","first"), Data=("DATA_COM","max"), Kg=("QTA_FINITO","first")
    )
    lots = add_month(lots, "Data")
    lots["Famiglia"] = lots["CODART"].apply(famiglia)
    lots["Uso"] = lots["CODART"].apply(uso)
    lots["Titolato"] = lots["Descrizione"].apply(titolato)

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
                if secco > 0: resa = secco/mdr
        if pd.isna(resa) and mdr > 0:
            resa = (qta-malto)/mdr
            if resa < 0: resa = np.nan

        rec.append({"Codice":code,"Descrizione":desc,"Lotto":lotto,"Data":data,"Kg":qta,"Malto_Qty":malto,"Taglio_Malto":taglio,"Mass_Yield":resa})
    sem_lotti = pd.DataFrame(rec)
    if len(sem_lotti):
        sem_lotti = add_month(sem_lotti, "Data")
        sem_master = sem_lotti.groupby("Codice", as_index=False).agg(
            Descrizione=("Descrizione","first"), Kg=("Kg","sum"), Malto_Qty=("Malto_Qty","sum"),
            N_Lotti=("Lotto","nunique"), Taglio_Malto=("Taglio_Malto","mean"), Mass_Yield=("Mass_Yield","mean")
        )
    else:
        sem_master = pd.DataFrame(columns=["Codice","Descrizione","Kg","Malto_Qty","N_Lotti","Taglio_Malto","Mass_Yield"])

    sem_taglio = sem_master.set_index("Codice")["Taglio_Malto"].to_dict() if len(sem_master) else {}

    # PF latest formulation
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
            if pd.isna(t): t = .60
            malto_sem += r["Pct_Utilizzo"] * t
        pf_rows.append({"Codice":code,"Descrizione":desc,"Lotto":lotto,"Kg_Lotto":kg,"Famiglia":famiglia(code),"Uso":uso(code),
                        "Titolato":"%" in str(desc),"Semilav_%":sem_pct,"Malto_Diretta_%":malto_dir,
                        "Malto_da_Semilav_%":malto_sem,"Malto_Totale_%":malto_dir+malto_sem,"Semilavorati":" | ".join(sorted(set(sem_codes)))})
    pf_form = pd.DataFrame(pf_rows)

    # PF malto trend
    tr = []
    for (code, lotto), g in detail.groupby(["CODART","LOTTO_FINITO"]):
        fam = famiglia(code)
        if fam not in ["Estratto secco finito","Conto lavoro","Fluido"]: continue
        data = g["Data"].max()
        kg = g["Kg_PF"].iloc[0]
        desc = g["Descrizione_PF"].iloc[0]
        md = g.loc[g["Malto_Diretta"], "Kg_Componente"].sum()
        ms = 0
        for _, r in g[g["Semilavorato"]].iterrows():
            t = sem_taglio.get(r["COD_COMP"], np.nan)
            if pd.isna(t): t = .60
            ms += r["Kg_Componente"] * t
        tr.append({"Codice":code,"Descrizione":desc,"Lotto":lotto,"Data":data,"Anno":data.year if pd.notna(data) else np.nan,
                   "Kg_PF":kg,"Famiglia":fam,"Malto_Diretta_Kg":md,"Malto_da_Semilav_Kg":ms,
                   "Malto_Totale_Kg":md+ms,"Malto_Totale_%":(md+ms)/kg if kg else np.nan})
    pf_malto_trend = pd.DataFrame(tr)

    if len(sem_lotti):
        sem_malto_trend = sem_lotti.groupby("Anno", as_index=False).agg(
            Kg_Semilavorato=("Kg","sum"), Malto_Kg=("Malto_Qty","sum"), Taglio_Medio=("Taglio_Malto","mean"), N_Lotti=("Lotto","nunique")
        )
        sem_malto_trend["Malto_%_Ponderata"] = np.where(sem_malto_trend["Kg_Semilavorato"]>0, sem_malto_trend["Malto_Kg"]/sem_malto_trend["Kg_Semilavorato"], np.nan)
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
            tmp["Kg_Lavorato"] = pd.to_numeric(tmp[qty_col], errors="coerce").fillna(0) if qty_col else 0
            tmp["Commessa"] = tmp[comm_col].astype(str).str.strip() if comm_col else ""
            rep_rows.append(tmp[["Reparto","Codice","Descrizione","Commessa","Data","Kg_Lavorato"]])
    mdr = comm[comm["COD_COMP"].apply(is_mdr)].copy()
    if len(mdr):
        rep_rows.append(pd.DataFrame({"Reparto":"Estrazione","Codice":mdr["COD_COMP"],"Descrizione":mdr["DES_COMP"],
                                      "Commessa":mdr["LOTTO_FINITO"],"Data":mdr["DATA_COM"],"Kg_Lavorato":mdr["QTA_LOTTO"]}))
    if rep_rows:
        rep_work = pd.concat(rep_rows, ignore_index=True).dropna(subset=["Data"])
        rep_work = add_month(rep_work, "Data")
        rep_summary = rep_work.groupby("Reparto", as_index=False).agg(Kg_Lavorato=("Kg_Lavorato","sum"), N_Codici=("Codice","nunique"), N_Commesse=("Commessa","nunique"))
        rep_year = rep_work.groupby(["Reparto","Anno"], as_index=False).agg(Kg_Lavorato=("Kg_Lavorato","sum"), N_Codici=("Codice","nunique"), N_Commesse=("Commessa","nunique"))
        rep_month_year = rep_work.groupby(["Reparto","Anno","Mese_Num","Mese_Nome"], as_index=False).agg(Kg_Lavorato=("Kg_Lavorato","sum"), N_Codici=("Codice","nunique"), N_Commesse=("Commessa","nunique"))
    else:
        rep_work = pd.DataFrame(columns=["Reparto","Codice","Descrizione","Commessa","Data","Kg_Lavorato","Anno","Mese_Num","Mese_Nome"])
        rep_summary = pd.DataFrame(columns=["Reparto","Kg_Lavorato","N_Codici","N_Commesse"])
        rep_year = pd.DataFrame(columns=["Reparto","Anno","Kg_Lavorato","N_Codici","N_Commesse"])
        rep_month_year = pd.DataFrame(columns=["Reparto","Anno","Mese_Num","Mese_Nome","Kg_Lavorato","N_Codici","N_Commesse"])

    return lots, sem_master, sem_lotti, pf_form, pf_malto_trend, sem_malto_trend, rep_work, rep_summary, rep_year, rep_month_year

def top_bar(df, x, y, title, hover_cols=None, height=400):
    hover_cols = hover_cols or []
    fig = px.bar(df.sort_values(x, ascending=True), x=x, y=y, orientation="h", title=title, text_auto=".2s", custom_data=hover_cols)
    if hover_cols:
        hover = "".join([f"<br>{col}: %{{customdata[{i}]}}" for i, col in enumerate(hover_cols)])
        fig.update_traces(hovertemplate="<b>%{y}</b><br>Valore: %{x:,.2f}"+hover+"<extra></extra>")
    layout(fig, height)
    fig.update_layout(yaxis_title="")
    st.plotly_chart(fig, use_container_width=True)

def plot_monthly(df, title, y="Kg_Lavorato"):
    if df.empty:
        st.warning("Nessun dato mensile disponibile.")
        return
    df = df.sort_values(["Anno","Mese_Num"])
    fig = px.line(df, x="Mese_Nome", y=y, color="Anno", markers=True, category_orders={"Mese_Nome":MONTH_ORDER},
                  title=title, custom_data=[c for c in ["Anno","Mese_Nome","N_Commesse","N_Codici"] if c in df.columns])
    fig.update_traces(hovertemplate="<b>%{x} %{customdata[0]}</b><br>Valore: %{y:,.2f}<extra></extra>")
    layout(fig, 430)
    st.plotly_chart(fig, use_container_width=True)

def reparto_section(rep, rep_work, rep_year, rep_month_year):
    rw = rep_work[rep_work["Reparto"] == rep].copy()
    ry = rep_year[rep_year["Reparto"] == rep].copy()
    rm = rep_month_year[rep_month_year["Reparto"] == rep].copy()
    st.subheader(rep)
    if rw.empty:
        st.warning("Nessun dato disponibile.")
        return
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Kg lavorati", fmt(rw["Kg_Lavorato"].sum()))
    c2.metric("N° commesse", fmt(rw["Commessa"].nunique()))
    c3.metric("N° codici", fmt(rw["Codice"].nunique()))
    c4.metric("Kg medi/commessa", fmt(rw.groupby("Commessa")["Kg_Lavorato"].sum().mean()))
    l,r = st.columns(2)
    with l:
        fig = px.bar(ry.sort_values("Anno"), x="Anno", y="Kg_Lavorato", title=f"{rep} - lavorato annuo", text_auto=".2s")
        layout(fig, 390)
        st.plotly_chart(fig, use_container_width=True)
    with r:
        top = rw.groupby(["Codice","Descrizione"], as_index=False).agg(Kg_Lavorato=("Kg_Lavorato","sum"), N_Commesse=("Commessa","nunique")).sort_values("Kg_Lavorato", ascending=False).head(15)
        top_bar(top, "Kg_Lavorato", "Codice", f"{rep} - top codici", ["Descrizione","N_Commesse"], 390)
    plot_monthly(rm, f"{rep} - trend mensile per anno")
    with st.expander(f"Dettaglio dati {rep}"):
        st.dataframe(rw.sort_values("Data", ascending=False), use_container_width=True, height=330)

def family_section(title, fam, lots):
    data = lots[lots["Famiglia"] == fam].copy()
    st.subheader(title)
    if data.empty:
        st.warning("Nessun dato disponibile.")
        return
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Kg prodotti", fmt(data["Kg"].sum()))
    c2.metric("N° lotti", fmt(data["LOTTO_FINITO"].nunique()))
    c3.metric("N° codici", fmt(data["CODART"].nunique()))
    c4.metric("Kg medi/lotto", fmt(data["Kg"].mean()))
    month = data.groupby(["Anno","Mese_Num","Mese_Nome"], as_index=False).agg(Kg=("Kg","sum"), N_Lotti=("LOTTO_FINITO","nunique"), N_Codici=("CODART","nunique"))
    l,r = st.columns(2)
    with l:
        fig = px.line(month.sort_values(["Anno","Mese_Num"]), x="Mese_Nome", y="Kg", color="Anno", markers=True,
                      category_orders={"Mese_Nome":MONTH_ORDER}, title=f"{title} - trend mensile per anno",
                      custom_data=["Anno","N_Lotti","N_Codici"])
        fig.update_traces(hovertemplate="<b>%{x} %{customdata[0]}</b><br>Kg: %{y:,.2f}<br>Lotti: %{customdata[1]}<br>Codici: %{customdata[2]}<extra></extra>")
        layout(fig, 390)
        st.plotly_chart(fig, use_container_width=True)
    with r:
        top = data.groupby(["CODART","Descrizione"], as_index=False).agg(Kg=("Kg","sum"), N_Lotti=("LOTTO_FINITO","nunique"), Uso=("Uso","first"), Titolato=("Titolato","first")).sort_values("Kg", ascending=False).head(15)
        top_bar(top, "Kg", "CODART", f"{title} - top codici", ["Descrizione","N_Lotti","Uso","Titolato"], 390)
    st.dataframe(data[["CODART","Descrizione","LOTTO_FINITO","Data","Kg","Famiglia","Uso","Titolato"]].sort_values("Data", ascending=False), use_container_width=True, height=300)

if not COMMESSE_PATH.exists():
    st.error("File commesse non trovato in data/commesse.xlsx")
    st.stop()

comm = load_commesse(COMMESSE_PATH)
rep = load_reparti(REPARTI_PATH)
lots, sem_master, sem_lotti, pf_form, pf_malto_trend, sem_malto_trend, rep_work, rep_summary, rep_year, rep_month_year = build(comm, rep)


if LOGO_PATH.exists():
    st.sidebar.image(str(LOGO_PATH), use_container_width=True)
st.sidebar.title("EVRA Dashboard")

years = sorted([int(y) for y in lots["Anno"].dropna().unique()])
sel_years = st.sidebar.multiselect("Anno produzione", years, default=years)
fams = sorted(lots["Famiglia"].dropna().unique())
sel_fams = st.sidebar.multiselect("Famiglia articolo", fams, default=fams)
filtered_lots = lots[lots["Anno"].isin(sel_years) & lots["Famiglia"].isin(sel_fams)].copy()


header_col1, header_col2 = st.columns([1, 5])
with header_col1:
    if LOGO_PATH.exists():
        st.image(str(LOGO_PATH), use_container_width=True)
with header_col2:
    st.title("EVRA Dashboard")
st.markdown('<span class="small-note">Nei grafici è mostrato solo il codice; passando con il cursore compaiono descrizione e altri dettagli.</span>', unsafe_allow_html=True)

c1,c2,c3,c4,c5,c6 = st.columns(6)
c1.metric("Kg prodotti", fmt(filtered_lots["Kg"].sum()))
c2.metric("N° lotti", fmt(filtered_lots["LOTTO_FINITO"].nunique()))
c3.metric("N° articoli", fmt(filtered_lots["CODART"].nunique()))
c4.metric("Kg lavorati reparti", fmt(rep_summary["Kg_Lavorato"].sum()) if len(rep_summary) else "ND")
c5.metric("Taglio malto medio", f"{sem_master['Taglio_Malto'].mean()*100:.1f}%" if len(sem_master) else "ND")
c6.metric("Mass Yield media", f"{sem_master['Mass_Yield'].mean()*100:.1f}%" if len(sem_master) else "ND")

tab_exec, tab_rep, tab_fam, tab_sem, tab_form, tab_search = st.tabs(["Executive","Reparti","Famiglie prodotto","Semilavorati","Formulazioni","Ricerca codice"])

with tab_exec:
    l,r = st.columns(2)
    with l:
        fam = filtered_lots.groupby("Famiglia", as_index=False)["Kg"].sum().sort_values("Kg", ascending=True)
        fig = px.bar(fam, x="Kg", y="Famiglia", orientation="h", title="Kg prodotti per famiglia", text_auto=".2s")
        layout(fig, 430); st.plotly_chart(fig, use_container_width=True)
    with r:
        if len(rep_summary):
            fig = px.bar(rep_summary.sort_values("Kg_Lavorato", ascending=True), x="Kg_Lavorato", y="Reparto", orientation="h", title="Kg lavorati per reparto", text_auto=".2s")
            layout(fig, 430); st.plotly_chart(fig, use_container_width=True)
    st.markdown("### Top 20 codici prodotti")
    top = filtered_lots.groupby(["CODART","Descrizione","Famiglia"], as_index=False).agg(Kg=("Kg","sum"), N_Lotti=("LOTTO_FINITO","nunique")).sort_values("Kg", ascending=False).head(20)
    st.dataframe(top, use_container_width=True, height=390)

with tab_rep:
    st.header("Sezioni per singolo reparto")
    order = ["Estrazione","Atomizzazione","Granulazione","Miscelazione","Fluidi","Micronizzazione"]
    available = [x for x in order if x in set(rep_work["Reparto"].dropna())]
    extra = [x for x in sorted(rep_work["Reparto"].dropna().unique()) if x not in available and x != "ND"]
    reps = available + extra
    if reps:
        selected = st.radio("Scegli reparto", reps, horizontal=True)
        reparto_section(selected, rep_work, rep_year, rep_month_year)
        st.markdown("---")
        st.subheader("Confronto reparti")
        metric = st.radio("Metrica confronto", ["Kg_Lavorato","N_Commesse","N_Codici"], horizontal=True, format_func=lambda x: {"Kg_Lavorato":"Kg lavorati","N_Commesse":"N° commesse","N_Codici":"N° codici"}[x])
        fig = px.bar(rep_year, x="Anno", y=metric, color="Reparto", barmode="group", title="Confronto annuo reparti")
        layout(fig, 520); st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("Nessun reparto disponibile.")

with tab_fam:
    st.header("Sezioni per famiglia prodotto")
    ftabs = st.tabs(["Fluidi","Estratto secco finito","Semilavorati","Conto lavoro"])
    with ftabs[0]: family_section("Fluidi", "Fluido", lots)
    with ftabs[1]: family_section("Estratto secco finito", "Estratto secco finito", lots)
    with ftabs[2]: family_section("Semilavorati", "Semilavorato", lots)
    with ftabs[3]: family_section("Conto lavoro", "Conto lavoro", lots)

with tab_sem:
    st.subheader("Semilavorati")
    l,r = st.columns(2)
    with l:
        plot = sem_master.dropna(subset=["Taglio_Malto","Mass_Yield"])
        if len(plot):
            fig = px.scatter(plot, x="Taglio_Malto", y="Mass_Yield", size="Kg", hover_name="Codice", custom_data=["Descrizione","Kg","N_Lotti"], title="Taglio malto vs Mass Yield")
            fig.update_traces(hovertemplate="<b>%{hovertext}</b><br>Descrizione: %{customdata[0]}<br>Kg: %{customdata[1]:,.2f}<br>Lotti: %{customdata[2]}<br>Taglio: %{x:.1%}<br>Mass Yield: %{y:.1%}<extra></extra>")
            fig.update_xaxes(tickformat=".0%"); fig.update_yaxes(tickformat=".0%")
            layout(fig, 430); st.plotly_chart(fig, use_container_width=True)
    with r:
        top = sem_master.sort_values("Kg", ascending=False).head(15)
        top_bar(top, "Kg", "Codice", "Top semilavorati", ["Descrizione","N_Lotti","Taglio_Malto","Mass_Yield"], 430)
    f = st.text_input("Filtra semilavorato")
    view = sem_master.copy()
    if f:
        q = f.lower()
        view = view[view["Codice"].str.lower().str.contains(q) | view["Descrizione"].str.lower().str.contains(q)]
    st.dataframe(view.sort_values("Kg", ascending=False), use_container_width=True, height=500)

with tab_form:
    st.subheader("Formulazioni e utilizzo maltodestrina")
    st.markdown("### Trend utilizzo malto nei prodotti finiti")
    if len(pf_malto_trend):
        pf_year = pf_malto_trend.groupby(["Anno","Famiglia"], as_index=False).agg(Kg_PF=("Kg_PF","sum"), Malto_Diretta_Kg=("Malto_Diretta_Kg","sum"), Malto_da_Semilav_Kg=("Malto_da_Semilav_Kg","sum"), Malto_Totale_Kg=("Malto_Totale_Kg","sum"))
        pf_year["Malto_Totale_%"] = np.where(pf_year["Kg_PF"]>0, pf_year["Malto_Totale_Kg"]/pf_year["Kg_PF"], np.nan)
        fig = px.line(pf_year, x="Anno", y="Malto_Totale_%", color="Famiglia", markers=True, title="Malto totale medio ponderato per anno - prodotti finiti", custom_data=["Kg_PF","Malto_Totale_Kg","Malto_Diretta_Kg","Malto_da_Semilav_Kg"])
        fig.update_traces(hovertemplate="<b>%{fullData.name} - %{x}</b><br>Malto totale: %{y:.1%}<br>Kg PF: %{customdata[0]:,.2f}<br>Kg malto totale: %{customdata[1]:,.2f}<br>Kg malto diretta: %{customdata[2]:,.2f}<br>Kg malto da semilav: %{customdata[3]:,.2f}<extra></extra>")
        fig.update_yaxes(tickformat=".0%")
        layout(fig, 430); st.plotly_chart(fig, use_container_width=True)
        pf_long = pf_year.melt(id_vars=["Anno","Famiglia"], value_vars=["Malto_Diretta_Kg","Malto_da_Semilav_Kg"], var_name="Tipo malto", value_name="Kg")
        fig = px.bar(pf_long, x="Anno", y="Kg", color="Tipo malto", facet_col="Famiglia", title="Kg malto diretta vs malto da semilavorato")
        layout(fig, 430); st.plotly_chart(fig, use_container_width=True)

    st.markdown("### Trend utilizzo malto nei semilavorati")
    if len(sem_malto_trend):
        fig = px.line(sem_malto_trend.sort_values("Anno"), x="Anno", y="Malto_%_Ponderata", markers=True, title="Taglio malto medio ponderato dei semilavorati per anno", custom_data=["Kg_Semilavorato","Malto_Kg","N_Lotti"])
        fig.update_traces(hovertemplate="<b>%{x}</b><br>Taglio ponderato: %{y:.1%}<br>Kg semilavorato: %{customdata[0]:,.2f}<br>Kg malto: %{customdata[1]:,.2f}<br>Lotti: %{customdata[2]}<extra></extra>")
        fig.update_yaxes(tickformat=".0%")
        layout(fig, 430); st.plotly_chart(fig, use_container_width=True)

    st.markdown("### Distribuzione tagli malto semilavorati")
    dist = sem_master.dropna(subset=["Taglio_Malto"]).copy()
    if len(dist):
        fig = px.histogram(dist, x="Taglio_Malto", nbins=25, title="Distribuzione dei tagli malto calcolati sui semilavorati")
        fig.update_xaxes(tickformat=".0%")
        layout(fig, 430); st.plotly_chart(fig, use_container_width=True)
        top = dist.sort_values("Taglio_Malto", ascending=False).head(20)
        top_bar(top, "Taglio_Malto", "Codice", "Top semilavorati per taglio malto", ["Descrizione","Kg","N_Lotti","Mass_Yield"], 520)
    st.markdown("### Tabella formulazioni ultima produzione")
    st.dataframe(pf_form.sort_values("Malto_Totale_%", ascending=False), use_container_width=True, height=420)

with tab_search:
    st.subheader("Ricerca codice")
    code = st.text_input("Codice o descrizione")
    if code:
        q = code.lower()
        art = lots[lots["CODART"].str.lower().str.contains(q) | lots["Descrizione"].str.lower().str.contains(q)]
        form = pf_form[pf_form["Codice"].str.lower().str.contains(q) | pf_form["Descrizione"].str.lower().str.contains(q)]
        sem = sem_master[sem_master["Codice"].str.lower().str.contains(q) | sem_master["Descrizione"].str.lower().str.contains(q)]
        repv = rep_work[rep_work["Codice"].str.lower().str.contains(q) | rep_work["Descrizione"].str.lower().str.contains(q)]
        st.markdown("### Produzioni")
        st.dataframe(art[["CODART","Descrizione","LOTTO_FINITO","Data","Kg","Famiglia","Uso","Titolato"]].sort_values("Data", ascending=False), use_container_width=True, height=240)
        st.markdown("### Formulazione ultima produzione")
        st.dataframe(form, use_container_width=True, height=180)
        st.markdown("### Semilavorati")
        st.dataframe(sem, use_container_width=True, height=180)
        st.markdown("### Lavorazioni")
        st.dataframe(repv.sort_values("Data", ascending=False), use_container_width=True, height=260)
    else:
        st.info("Inserire un codice o parte della descrizione.")
