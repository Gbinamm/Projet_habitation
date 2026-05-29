import streamlit as st

st.set_page_config(
    page_title="Immo BI",
    page_icon="🏠",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("🏠 Analyse du marché immobilier français")
st.markdown("""
Bienvenue. Utilisez le menu à gauche pour naviguer entre les analyses.

**Question centrale : pour un prix, une localisation et des caractéristiques
données — est-ce un bon deal ?**
""")

# Vérification que la base est accessible
try:
    from core.recup_donnees import get_connection
    con = get_connection()
    nb = con.execute("SELECT COUNT(*) FROM dvf_raw").fetchone()[0]
    st.success(f"✅ Base connectée — {nb:,} transactions disponibles")
except Exception as e:
    st.error(f"❌ Impossible de se connecter à la base : {e}")