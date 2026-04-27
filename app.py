"""
app.py — Interface Streamlit pour le calcul de jaugeage de citerne.

Lancement :
    streamlit run app.py
"""

import io
import math

import pandas as pd
import streamlit as st

from calcul_jaugeage import CiterneVertical, export_excel

# -----------------------------------------------------------------------
# Configuration de la page
# -----------------------------------------------------------------------
st.set_page_config(
    page_title="Jaugeage de Citerne",
    page_icon="🛢",
    layout="wide",
)

st.title("🛢 Calcul de Jaugeage — Citerne Cylindrique Verticale")
st.markdown("Génère le **tableau de jaugeage mm par mm** et le fichier Excel à télécharger.")

# -----------------------------------------------------------------------
# Barre latérale : paramètres
# -----------------------------------------------------------------------
st.sidebar.header("Paramètres de la citerne")

appellation   = st.sidebar.text_input("Appellation", value="BAC R6")
diametre      = st.sidebar.number_input("Diamètre intérieur φ (mm)", value=12_000, step=100, min_value=100)
HF            = st.sidebar.number_input("Hauteur totale fond à fond HF (mm)", value=12_080, step=10, min_value=100)
HT            = st.sidebar.number_input("Hauteur corps cylindrique HT (mm)", value=10_630, step=10, min_value=10)
H_mort        = st.sidebar.number_input("Hauteur volume mort (mm)", value=50, step=10, min_value=0)
H_aspiration  = st.sidebar.number_input("Hauteur aspiration (mm)", value=3_500, step=100, min_value=0)

st.sidebar.markdown("---")
st.sidebar.caption("Tuyaux (informatif)")
st.sidebar.text("Aspiration : φ=545 mm, L=8 670 mm")
st.sidebar.text("Entrée     : φ=360 mm, L=6 230 mm")

# -----------------------------------------------------------------------
# Validation
# -----------------------------------------------------------------------
h_fond = (HF - HT) / 2.0

if HT >= HF:
    st.error("❌ HT doit être inférieur à HF.")
    st.stop()

if H_mort > HF or H_aspiration > HF:
    st.error("❌ H_mort et H_aspiration doivent être ≤ HF.")
    st.stop()

# -----------------------------------------------------------------------
# Calcul
# -----------------------------------------------------------------------
citerne = CiterneVertical(diametre, HF, HT, appellation)

with st.spinner("Calcul du tableau en cours…"):
    df = citerne.build_jaugeage(H_mort=H_mort)

# -----------------------------------------------------------------------
# Métriques clés
# -----------------------------------------------------------------------
st.subheader("Volumes clés")

col1, col2, col3, col4 = st.columns(4)
col1.metric("Volume total calculé",
            f"{citerne.volume_L(HF):,.0f} L",
            f"{citerne.volume_m3(HF):,.2f} m³")
col2.metric("Volume mort (fond mort)",
            f"{citerne.volume_L(H_mort):,.0f} L",
            f"H = {H_mort} mm")
col3.metric("Volume à l'aspiration",
            f"{citerne.volume_L(H_aspiration):,.0f} L",
            f"H = {H_aspiration} mm")
col4.metric("Volume utile",
            f"{citerne.volume_L(HF) - citerne.volume_L(H_mort):,.0f} L",
            "aspiration → plein")

# -----------------------------------------------------------------------
# Détail des zones
# -----------------------------------------------------------------------
with st.expander("Détail des zones géométriques"):
    Vfb  = citerne._V_fond_complet() / 1e6
    Vcyl = math.pi * citerne.R**2 * citerne.HT / 1e6
    data_zones = {
        "Zone": ["Fond bas (elliptique)", "Corps cylindrique", "Fond haut (elliptique)", "**TOTAL**"],
        "Hauteur (mm)": [f"0 → {citerne.h_fond:.0f}", f"{citerne.h_fond:.0f} → {citerne.h_fond+citerne.HT:.0f}", f"{citerne.h_fond+citerne.HT:.0f} → {citerne.HF:.0f}", ""],
        "Volume (L)": [f"{Vfb:,.1f}", f"{Vcyl:,.1f}", f"{Vfb:,.1f}", f"**{Vfb+Vcyl+Vfb:,.1f}**"],
    }
    st.table(pd.DataFrame(data_zones))

# -----------------------------------------------------------------------
# Aperçu du tableau
# -----------------------------------------------------------------------
st.subheader("Aperçu du tableau de jaugeage")

tab1, tab2, tab3 = st.tabs(["Premières lignes", "Autour volume mort", "Autour aspiration"])

with tab1:
    st.dataframe(df.head(30), use_container_width=True)

with tab2:
    mask = (df["Hauteur (mm)"] >= max(0, H_mort - 10)) & (df["Hauteur (mm)"] <= H_mort + 10)
    st.dataframe(df[mask], use_container_width=True)

with tab3:
    mask2 = (df["Hauteur (mm)"] >= max(0, H_aspiration - 10)) & (df["Hauteur (mm)"] <= H_aspiration + 10)
    st.dataframe(df[mask2], use_container_width=True)

# -----------------------------------------------------------------------
# Recherche rapide par hauteur
# -----------------------------------------------------------------------
st.subheader("Recherche rapide")
h_search = st.number_input("Entrez une hauteur (mm) pour voir le volume correspondant :",
                            min_value=0, max_value=int(HF), value=1000, step=1)
row = df[df["Hauteur (mm)"] == h_search]
if not row.empty:
    r = row.iloc[0]
    c1, c2, c3 = st.columns(3)
    c1.metric("Volume (L)",  f"{r['Volume (L)']:,.2f}")
    c2.metric("Volume (m³)", f"{r['Volume (m³)']:,.4f}")
    c3.metric("ΔV (L/mm)",   f"{r['ΔV (L/mm)']:,.2f}")

# -----------------------------------------------------------------------
# Génération et téléchargement Excel
# -----------------------------------------------------------------------
st.subheader("Téléchargement")

@st.cache_data(show_spinner="Génération du fichier Excel…")
def generer_excel(diametre, HF, HT, appellation, H_mort, H_aspiration):
    c = CiterneVertical(diametre, HF, HT, appellation)
    d = c.build_jaugeage(H_mort=H_mort)
    buf = export_excel(c, d, H_mort=H_mort, H_aspiration=H_aspiration, output=None)
    return buf.getvalue()

excel_bytes = generer_excel(diametre, HF, HT, appellation, H_mort, H_aspiration)

st.download_button(
    label="📥 Télécharger le tableau de jaugeage (Excel)",
    data=excel_bytes,
    file_name=f"Jaugeage_{appellation.replace(' ', '_')}.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    type="primary",
    use_container_width=True,
)

st.caption(
    f"Le fichier contient {int(HF)+1:,} lignes (0 à {int(HF)} mm) "
    "avec 3 feuilles : Jaugeage · Paramètres · Points Clés."
)
