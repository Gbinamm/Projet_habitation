import streamlit as st
import streamlit.components.v1 as components
import json, base64
from core.recup_donnees import get_connection

st.set_page_config(layout="wide", page_title="Recherche", page_icon="🔍")

st.markdown("""
<style>
#MainMenu, header, footer { visibility: hidden; }
.block-container { padding-top: 1.2rem !important; }
/* Supprime les labels vides qui prennent de la place */
div[data-testid="stWidgetLabel"]:empty { display: none; }
</style>
""", unsafe_allow_html=True)


# ── Données ───────────────────────────────────────────────────────────────────

@st.cache_data(ttl=3600)
def get_communes():
    con = get_connection()
    return con.execute("""
        SELECT DISTINCT nom_commune FROM dvf_raw
        WHERE nom_commune IS NOT NULL ORDER BY nom_commune
    """).df()["nom_commune"].tolist()

@st.cache_data(ttl=3600)
def get_annees():
    con = get_connection()
    return con.execute("""
        SELECT DISTINCT YEAR(date_mutation) AS annee
        FROM dvf_raw ORDER BY annee DESC
    """).df()["annee"].tolist()

@st.cache_data(ttl=3600)
def get_biens(communes, type_local, pieces_min, surf_min, surf_max,
              prix_min, prix_max, dpe_max, annees_ref, limit=60):
    con = get_connection()
    communes_str = ", ".join(f"'{c}'" for c in communes)
    annees_str   = ", ".join(str(a) for a in annees_ref)
    dpe_order    = {"A":1,"B":2,"C":3,"D":4,"E":5,"F":6,"G":7,"":99}
    dpe_values   = [k for k,v in dpe_order.items()
                    if v <= dpe_order.get(dpe_max, 99) and k != ""]
    filters = [
        f"d.nom_commune IN ({communes_str})",
        f"YEAR(d.date_mutation) IN ({annees_str})",
        "d.prix_m2 BETWEEN 100 AND 30000",
        "d.surface_reelle_bati IS NOT NULL",
        "d.valeur_fonciere IS NOT NULL",
    ]
    if type_local != "Tous":
        filters.append(f"d.type_local = '{type_local}'")
    if pieces_min and pieces_min > 0:
        filters.append(f"d.nombre_pieces_principales >= {pieces_min}")
    if surf_min and surf_min > 0:
        filters.append(f"d.surface_reelle_bati >= {surf_min}")
    if surf_max and surf_max > 0:
        filters.append(f"d.surface_reelle_bati <= {surf_max}")
    if prix_min and prix_min > 0:
        filters.append(f"d.valeur_fonciere >= {prix_min}")
    if prix_max and prix_max > 0:
        filters.append(f"d.valeur_fonciere <= {prix_max}")
    if dpe_values:
        vals = ", ".join(f"'{v}'" for v in dpe_values)
        filters.append(f"(d.dpe_classe IN ({vals}) OR d.dpe_classe IS NULL)")

    where = " AND ".join(filters)
    return con.execute(f"""
    WITH medians AS (
        SELECT nom_commune, type_local, MEDIAN(prix_m2) AS prix_median_commune
        FROM dvf_raw WHERE YEAR(date_mutation) IN ({annees_str})
          AND prix_m2 BETWEEN 100 AND 30000
        GROUP BY nom_commune, type_local
    )
    SELECT d.nom_commune, d.type_local,
        d.surface_reelle_bati AS surface,
        d.nombre_pieces_principales AS pieces,
        d.valeur_fonciere AS prix,
        ROUND(d.prix_m2,0) AS prix_m2,
        d.dpe_classe AS dpe,
        d.date_mutation,
        ROUND((d.prix_m2-m.prix_median_commune)
              /NULLIF(m.prix_median_commune,0)*100,1) AS vs_marche
    FROM dvf_raw d
    LEFT JOIN medians m ON d.nom_commune=m.nom_commune
                       AND d.type_local=m.type_local
    WHERE {where}
    ORDER BY vs_marche ASC
    LIMIT {limit}
    """).df()


# ── Chargement initial ────────────────────────────────────────────────────────

communes_dispo = get_communes()
annees_dispo   = get_annees()


# ── LIGNE 1 : mode + commune + périmètre + rechercher ────────────────────────

col_mode, col_commune, col_rayon, col_btn = st.columns([1.2, 2.5, 2, 1.2])

with col_mode:
    mode = st.radio("", ["Achat", "Location"], horizontal=True,
                    label_visibility="collapsed")

with col_commune:
    commune = st.selectbox("", communes_dispo, label_visibility="collapsed")

with col_rayon:
    rayon = st.selectbox(
        "",
        options=[0, 5, 10, 20, 50],
        format_func=lambda x: "📍 Commune uniquement" if x == 0 else f"📍 +{x} km autour",
        label_visibility="collapsed",
    )

with col_btn:
    rechercher = st.button("🔍  Rechercher", use_container_width=True, type="primary")

communes_filtre = [commune] if rayon == 0 else communes_dispo

st.divider()

# ── LIGNE 2 : filtres avancés avec inputs propres ─────────────────────────────

f0, f1, f2, f3, f4, f5, f6, f7 = st.columns(
    [1, 0.7, 0.6, 0.6, 0.6, 0.6, 0.6, 1.2]
)

with f0:
    type_local = st.selectbox("Type de bien", ["Tous", "Appartement", "Maison"])

with f1:
    pieces_min = st.selectbox("Pièces min",
        options=[None, 1, 2, 3, 4, 5],
        format_func=lambda x: "Toutes" if x is None else f"{x}+",
    )

with f2:
    surf_min = st.number_input("Surface min m²", min_value=0, value=None,
                               placeholder="Min", step=5, label_visibility="visible")
with f3:
    surf_max = st.number_input("Surface max m²", min_value=0, value=None,
                               placeholder="Max", step=5, label_visibility="visible")

budget_label_min = "Budget min €" if mode == "Achat" else "Loyer min €/mois"
budget_label_max = "Budget max €" if mode == "Achat" else "Loyer max €/mois"

with f4:
    prix_min = st.number_input(budget_label_min, min_value=0, value=None,
                               placeholder="Min", step=1000, label_visibility="visible")
with f5:
    prix_max = st.number_input(budget_label_max, min_value=0, value=None,
                               placeholder="Max", step=1000, label_visibility="visible")

with f6:
    dpe_max = st.selectbox("DPE max",
        options=["Tous", "A", "B", "C", "D", "E", "F", "G"])
    dpe_max_val = "" if dpe_max == "Tous" else dpe_max

with f7:
    annees_ref = st.multiselect("Années réf.", annees_dispo,
        default=annees_dispo[:2] if len(annees_dispo) >= 2 else annees_dispo)
    if not annees_ref:
        annees_ref = annees_dispo[:1]

st.divider()


# ── Requête ───────────────────────────────────────────────────────────────────

if rechercher or "df_resultats" not in st.session_state:
    with st.spinner("Recherche en cours..."):
        st.session_state["df_resultats"] = get_biens(
            communes=communes_filtre,
            type_local=type_local,
            pieces_min=pieces_min,
            surf_min=surf_min,
            surf_max=surf_max,
            prix_min=prix_min,
            prix_max=prix_max,
            dpe_max=dpe_max_val,
            annees_ref=annees_ref,
        )

df = st.session_state["df_resultats"]
nb     = len(df)
med    = int(df["prix"].median())    if nb else 0
med_m2 = int(df["prix_m2"].median()) if nb else 0
bonnes = int((df["vs_marche"] < -5).sum()) if nb and "vs_marche" in df.columns else 0


# ── Métriques + tri ───────────────────────────────────────────────────────────

m1, m2, m3, m4, _, tri_col = st.columns([1, 1.2, 1.2, 1, 2, 1.8])
m1.metric("Annonces",         f"{nb}")
m2.metric("Prix médian",      f"{med:,} €".replace(",", "\u202f"))
m3.metric("Médian / m²",      f"{med_m2:,} €/m²".replace(",", "\u202f"))
m4.metric("Bonnes affaires",  f"{bonnes} / {nb}")

with tri_col:
    tri_label = st.selectbox("", [
        "Meilleures affaires d'abord",
        "Prix croissant", "Prix décroissant", "Surface décroissante",
    ], label_visibility="collapsed")

if nb == 0:
    st.info("Aucun résultat — essayez d'élargir les filtres.")
    st.stop()

# Tri côté Python
if   tri_label == "Prix croissant":       df = df.sort_values("prix")
elif tri_label == "Prix décroissant":     df = df.sort_values("prix", ascending=False)
elif tri_label == "Surface décroissante": df = df.sort_values("surface", ascending=False)
else:                                     df = df.sort_values("vs_marche", na_position="last")


# ── Cards ─────────────────────────────────────────────────────────────────────

def row_to_dict(row):
    vs = row.get("vs_marche")
    try:
        vs = float(vs)
        if vs < -5:   dc, dl = "good", f"↓ {abs(vs):.0f}% sous le marché"
        elif vs > 5:  dc, dl = "bad",  f"↑ {vs:.0f}% au-dessus"
        else:         dc, dl = "ok",   "≈ Prix dans la moyenne"
    except (TypeError, ValueError):
        dc, dl = "ok", "Prix non comparé"
    return {
        "commune": str(row.get("nom_commune") or ""),
        "type":    str(row.get("type_local")  or "Bien"),
        "surface": int(row["surface"]) if row["surface"] else 0,
        "pieces":  int(row["pieces"])  if row["pieces"]  else 0,
        "prix":    int(row["prix"])    if row["prix"]    else 0,
        "prix_m2": int(row["prix_m2"]) if row["prix_m2"] else 0,
        "dpe":     str(row.get("dpe") or "?"),
        "date":    str(row.get("date_mutation") or "")[:10],
        "dc": dc, "dl": dl,
    }

biens_b64 = base64.b64encode(
    json.dumps([row_to_dict(r) for _, r in df.iterrows()]).encode("utf-8")
).decode("ascii")

components.html(f"""
<style>
*{{box-sizing:border-box;margin:0;padding:0;
   font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif}}
.cards{{display:flex;flex-direction:column;gap:10px;padding:4px 0 24px;}}
.card{{
  display:grid;grid-template-columns:90px 1fr auto;gap:16px;align-items:start;
  background:#fff;border:1px solid #e8e8e8;border-radius:12px;padding:14px 16px;
  transition:border-color .15s,box-shadow .15s;
}}
.card:hover{{border-color:#bbb;box-shadow:0 2px 8px rgba(0,0,0,.07);}}
.thumb{{
  width:90px;height:70px;border-radius:8px;background:#f4f4f4;
  display:flex;align-items:center;justify-content:center;font-size:28px;flex-shrink:0;
}}
.title{{font-size:14px;font-weight:600;margin-bottom:3px;color:#111;}}
.loc{{font-size:12px;color:#888;margin-bottom:8px;}}
.tags{{display:flex;gap:6px;flex-wrap:wrap;}}
.tag{{font-size:11px;padding:3px 9px;border-radius:999px;background:#f0f0f0;color:#555;}}
.dA{{background:#e8f5e9;color:#2e7d32;}}
.dB{{background:#e0f2f1;color:#00695c;}}
.dC{{background:#fff8e1;color:#e65100;}}
.dD{{background:#fce4ec;color:#880e4f;}}
.right{{text-align:right;min-width:140px;}}
.prix{{font-size:18px;font-weight:700;color:#111;white-space:nowrap;}}
.m2{{font-size:12px;color:#999;margin-top:3px;}}
.badge{{display:inline-block;font-size:11px;margin-top:8px;
  padding:4px 10px;border-radius:999px;white-space:nowrap;}}
.good{{background:#e8f5e9;color:#2e7d32;}}
.ok{{background:#fff8e1;color:#e65100;}}
.bad{{background:#fce4ec;color:#880e4f;}}
</style>
<div class="cards" id="cards"></div>
<script>
const D=JSON.parse(atob('{biens_b64}'));
function fmt(n){{return n.toLocaleString('fr-FR');}}
document.getElementById('cards').innerHTML=D.map(d=>{{
  const icon=d.type==='Maison'?'🏠':'🏢';
  const titre=d.type+' '+d.pieces+'P · '+d.surface+'\u202fm²';
  return `<div class="card">
    <div class="thumb">${{icon}}</div>
    <div>
      <div class="title">${{titre}}</div>
      <div class="loc">📍 ${{d.commune}}${{d.date?' · '+d.date:''}}</div>
      <div class="tags">
        <span class="tag">${{d.surface}}\u202fm²</span>
        <span class="tag">${{d.pieces}}\u202fpièce${{d.pieces>1?'s':''}}</span>
        <span class="tag d${{d.dpe}}">DPE\u202f${{d.dpe}}</span>
      </div>
    </div>
    <div class="right">
      <div class="prix">${{fmt(d.prix)}}\u202f€</div>
      <div class="m2">${{fmt(d.prix_m2)}}\u202f€/m²</div>
      <span class="badge ${{d.dc}}">${{d.dl}}</span>
    </div>
  </div>`;
}}).join('');
</script>
""", height=nb * 112 + 40, scrolling=False)