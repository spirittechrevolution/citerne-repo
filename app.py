"""
app.py — Interface Streamlit pour le calcul de jaugeage de citerne.

Lancement :
    streamlit run app.py
"""

import io
import math

import pandas as pd
import streamlit as st

from calcul_jaugeage import CiterneVertical, export_excel, hauteur_pour_volume

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
    Vcyl  = math.pi * citerne.R**2 * citerne.HT / 1e6
    Vdome = citerne._V_dome_complet() / 1e6
    data_zones = {
        "Zone": ["Corps cylindrique (fond plat)", "Fond bombé supérieur", "**TOTAL**"],
        "Hauteur (mm)": [
            f"0 → {citerne.HT:.0f}",
            f"{citerne.HT:.0f} → {citerne.HF:.0f}  (h_dome = {citerne.h_dome:.0f} mm)",
            "",
        ],
        "Volume (L)": [f"{Vcyl:,.1f}", f"{Vdome:,.1f}", f"**{Vcyl+Vdome:,.1f}**"],
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
# Recherche par hauteur → volume
# -----------------------------------------------------------------------
st.subheader("Recherche : Hauteur → Volume")
h_search = st.number_input("Hauteur (mm) :",
                            min_value=0, max_value=int(HF), value=1000, step=1,
                            key="search_h")
row = df[df["Hauteur (mm)"] == h_search]
if not row.empty:
    r = row.iloc[0]
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Volume brut (L)",       f"{r['Volume (L)']:,.2f}")
    c2.metric("Vol. utilisable (L)",   f"{r['Vol. utilisable (L)']:,.2f}")
    c3.metric("Volume (m³)",           f"{r['Volume (m³)']:,.4f}")
    c4.metric("Volume (mm³)",          f"{r['Volume (L)'] * 1_000_000:,.0f}")
    c5.metric("ΔV (L/mm)",            f"{r['ΔV (L/mm)']:,.2f}")
    st.caption(f"Zone : {r['Zone']}")

st.divider()

# -----------------------------------------------------------------------
# Recherche par volume → hauteur  (RECHERCHE INVERSE)
# -----------------------------------------------------------------------
st.subheader("Recherche : Volume → Hauteur")

col_unite, col_val = st.columns([1, 3])
with col_unite:
    unite = st.radio("Unité", ["Litres (L)", "Mètres³ (m³)", "Millimètres³ (mm³)"], index=0, key="unite_inv")
with col_val:
    if unite.startswith("Litres"):
        unite_code = "L"
        V_max_affiche = citerne.volume_L(HF)
        step_val = 100.0
        label_vol = "Volume en litres (L) :"
        fmt = "%.2f"
    elif unite.startswith("Mètres"):
        unite_code = "m3"
        V_max_affiche = citerne.volume_m3(HF)
        step_val = 1.0
        label_vol = "Volume en mètres cubes (m³) :"
        fmt = "%.4f"
    else:
        unite_code = "mm3"
        V_max_affiche = citerne.volume_mm3(HF)
        step_val = 1_000_000.0
        label_vol = "Volume en millimètres cubes (mm³) :"
        fmt = "%.0f"

    vol_saisi = st.number_input(
        label_vol,
        min_value=0.0,
        max_value=float(V_max_affiche),
        value=0.0,
        step=step_val,
        format=fmt,
        key="search_vol",
    )

if vol_saisi > 0:
    res = hauteur_pour_volume(citerne, vol_saisi, unite=unite_code)
    st.success(f"Hauteur correspondante : **{res['hauteur_mm']:,.1f} mm**")
    r1, r2, r3, r4 = st.columns(4)
    r1.metric("Hauteur (mm)",       f"{res['hauteur_mm']:,.1f}")
    r2.metric("Volume exact (L)",   f"{res['volume_L']:,.2f}")
    r3.metric("Volume exact (m³)",  f"{res['volume_m3']:,.4f}")
    r4.metric("Volume exact (mm³)", f"{res['volume_mm3']:,.0f}")
    st.caption(f"Zone : {res['zone']}")

    if res["hauteur_mm"] <= H_mort:
        st.warning(f"Ce volume est dans la zone morte (H ≤ {H_mort} mm) — Vol. utilisable = 0 L")

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
