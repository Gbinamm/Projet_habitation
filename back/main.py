"""
main.py — ImmoBI API v3
Lance avec : uvicorn main:app --reload --port 8000
"""
from __future__ import annotations
import uuid, httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional

from core.recup_donnees import get_connection
from agent import chat

app = FastAPI(title="ImmoBI API", version="3.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

CONVERSATIONS: dict[str, list[dict]] = {}
DPE_ORDER = {"A":1,"B":2,"C":3,"D":4,"E":5,"F":6,"G":7,"":99}

# Cache GeoJSON en mémoire (chargé une fois)
_geojson_cache: dict | None = None


# ── Health ──────────────────────────────────────────────────────────────────
@app.get("/")
def root(): return {"status": "ok", "service": "ImmoBI API v3"}

@app.get("/health")
def health():
    try:
        con = get_connection()
        n = con.execute("SELECT COUNT(*) FROM dvf_enrichi").fetchone()[0]
        return {"status": "healthy", "n_transactions": n}
    except Exception as e:
        raise HTTPException(503, f"DB inaccessible: {e}")


# ── /api/geojson ─────────────────────────────────────────────────────────────
@app.get("/api/geojson")
async def get_geojson():
    """
    GeoJSON des contours de communes pour les départements couverts,
    enrichi avec les stats prix depuis dvf_enrichi.
    Mis en cache en mémoire après le premier appel.
    """
    global _geojson_cache
    if _geojson_cache is not None:
        return JSONResponse(_geojson_cache)

    con = get_connection()

    # 1. Récupérer les départements couverts
    depts = [str(r[0]) for r in con.execute("""
        SELECT DISTINCT code_departement FROM dvf_enrichi
        WHERE code_departement IS NOT NULL
        ORDER BY code_departement
    """).fetchall()]

    if not depts:
        raise HTTPException(404, "Aucun département trouvé dans la base")

    # 2. Télécharger les contours depuis l'API geo.api.gouv.fr
    # L'API n'accepte qu'un département à la fois via codeDepartement
    all_features = []
    async with httpx.AsyncClient(timeout=30) as client:
        for dept in depts:
            url = f"https://geo.api.gouv.fr/communes?codeDepartement={dept}&format=geojson&geometry=contour"
            try:
                resp = await client.get(url)
                resp.raise_for_status()
                data = resp.json()
                all_features.extend(data.get("features", []))
            except Exception as e:
                print(f"[geojson] Dept {dept} KO: {e}")

    if not all_features:
        raise HTTPException(502, "Impossible de charger les contours des communes")

    geojson = {"type": "FeatureCollection", "features": all_features}
    print(f"[geojson] {len(all_features)} communes téléchargées pour depts {depts}")

    # 3. Récupérer les stats par commune depuis dvf_enrichi
    rows = con.execute("""
        SELECT
            nom_commune                           AS nom_original,
            UPPER(TRIM(nom_commune))              AS nom_upper,
            CAST(code_commune AS VARCHAR)         AS code,
            ROUND(MEDIAN(prix_m2), 0)             AS prix_median_m2,
            ROUND(AVG(prix_m2), 0)                AS prix_moyen_m2,
            COUNT(*)                              AS nb_ventes,
            MODE(classe_dpe_dominante)             AS dpe_dominant,
            ROUND(MEDIAN(distance_arret_m), 0)    AS dist_arret_med,
            ROUND(AVG(pct_passoires)*100, 1)      AS pct_passoires
        FROM dvf_enrichi
        WHERE prix_m2 BETWEEN 100 AND 30000
        GROUP BY nom_commune, CAST(code_commune AS VARCHAR)
    """).fetchall()

    stats_by_code = {}
    stats_by_nom  = {}
    for nom_orig, nom_up, code, prix_med, prix_moy, nb, dpe, dist, passoires in rows:
        s = {
            "prix_median_m2": prix_med,
            "prix_moyen_m2":  prix_moy,
            "nb_ventes":      nb,
            "dpe_dominant":   dpe,
            "dist_arret_med": dist,
            "pct_passoires":  passoires,
        }
        # Indexer par code (ex: "35238"), par nom majuscule et par nom original
        if code:
            stats_by_code[code]          = s
            stats_by_code[code.zfill(5)] = s
        if nom_up:   stats_by_nom[nom_up]   = s
        if nom_orig: stats_by_nom[nom_orig.strip()] = s

    # 4. Enrichir chaque feature GeoJSON
    matched, total = 0, 0
    for feature in geojson.get("features", []):
        props = feature.get("properties", {})
        code = props.get("code", "")          # ex: "44109" — déjà 5 chiffres
        nom  = props.get("nom", "").strip()   # ex: "Nantes" — même casse que DB
        # Essai 1 : code INSEE (le plus fiable)
        # Essai 2 : nom original (casse mixte identique à DB)
        # Essai 3 : nom en majuscules (fallback)
        s = (stats_by_code.get(code)
             or stats_by_nom.get(nom)
             or stats_by_nom.get(nom.upper())
             or {})
        if s:
            matched += 1
        props.update(s)
        feature["properties"] = props
        total += 1
    print(f"[geojson] Jointure : {matched}/{total} communes enrichies")
    if total > 0:
        sample_geo  = [f["properties"].get("code") for f in geojson["features"][:5]]
        sample_db   = list(stats_by_code.keys())[:5]
        print(f"[geojson] Sample codes GeoJSON : {sample_geo}")
        print(f"[geojson] Sample codes DB      : {sample_db}")

    _geojson_cache = geojson
    return JSONResponse(geojson)


# ── /api/communes ────────────────────────────────────────────────────────────
@app.get("/api/communes")
def get_communes():
    con = get_connection()
    rows = con.execute("""
        SELECT DISTINCT nom_commune FROM dvf_enrichi
        WHERE nom_commune IS NOT NULL ORDER BY nom_commune
    """).fetchall()
    return [r[0] for r in rows]


# ── /api/annees ──────────────────────────────────────────────────────────────
@app.get("/api/annees")
def get_annees():
    con = get_connection()
    rows = con.execute("""
        SELECT DISTINCT annee FROM dvf_enrichi
        WHERE annee IS NOT NULL ORDER BY annee DESC
    """).fetchall()
    return [r[0] for r in rows]


# ── helpers ──────────────────────────────────────────────────────────────────
def _dpe_filter(dpe_max: str, prefix: str = "") -> str | None:
    vals = [k for k, v in DPE_ORDER.items()
            if v <= DPE_ORDER.get(dpe_max, 99) and k != ""]
    if not vals:
        return None
    col = f"{prefix}classe_dpe_dominante" if prefix else "classe_dpe_dominante"
    quoted = ", ".join(f"'{v}'" for v in vals)
    return f"({col} IN ({quoted}) OR {col} IS NULL)"


def _annees_for_commune(con, commune: str) -> str:
    rows = con.execute("""
        SELECT DISTINCT annee FROM dvf_enrichi
        WHERE nom_commune = ?
          AND prix_m2 BETWEEN 100 AND 30000
        ORDER BY annee DESC LIMIT 2
    """, [commune]).fetchall()
    if rows:
        return ", ".join(str(r[0]) for r in rows)
    return "SELECT DISTINCT annee FROM dvf_enrichi"


# ── /api/biens ───────────────────────────────────────────────────────────────
@app.get("/api/biens")
def get_biens(
    commune:    str,
    annee:      int             = 0,
    type_local: str             = "Tous",
    pieces_min: int             = 0,
    surf_min:   Optional[float] = None,
    surf_max:   Optional[float] = None,
    prix_min:   Optional[float] = None,
    prix_max:   Optional[float] = None,
    dpe_max:    str             = "",
    dist_max:   Optional[float] = None,
    tri:        str             = "deal",
    limit:      int             = 100,
):
    con = get_connection()
    annees_str = str(annee) if annee != 0 else _annees_for_commune(con, commune)

    filters = [
        f"d.nom_commune = '{commune}'",
        f"d.annee IN ({annees_str})",
        "d.prix_m2 BETWEEN 100 AND 30000",
        "d.surface_reelle_bati IS NOT NULL",
        "d.valeur_fonciere IS NOT NULL",
    ]
    if type_local != "Tous":
        filters.append(f"d.type_local = '{type_local}'")
    if pieces_min > 0:
        filters.append(f"d.nombre_pieces_principales >= {pieces_min}")
    if surf_min and surf_min > 0:
        filters.append(f"d.surface_reelle_bati >= {surf_min}")
    if surf_max and surf_max > 0:
        filters.append(f"d.surface_reelle_bati <= {surf_max}")
    if prix_min and prix_min > 0:
        filters.append(f"d.valeur_fonciere >= {prix_min}")
    if prix_max and prix_max > 0:
        filters.append(f"d.valeur_fonciere <= {prix_max}")
    if dist_max and dist_max > 0:
        filters.append(f"d.distance_arret_m <= {dist_max}")
    dpe_f = _dpe_filter(dpe_max, prefix="d.")
    if dpe_f:
        filters.append(dpe_f)

    where = " AND ".join(filters)
    order = {
        "deal":      "vs_marche ASC NULLS LAST",
        "prix-asc":  "d.valeur_fonciere ASC",
        "prix-desc": "d.valeur_fonciere DESC",
        "surf-desc": "d.surface_reelle_bati DESC",
        "transport": "d.distance_arret_m ASC NULLS LAST",
    }.get(tri, "vs_marche ASC NULLS LAST")

    rows = con.execute(f"""
    WITH medians AS (
        SELECT nom_commune, type_local, MEDIAN(prix_m2) AS med
        FROM dvf_enrichi
        WHERE annee IN ({annees_str}) AND prix_m2 BETWEEN 100 AND 30000
        GROUP BY nom_commune, type_local
    )
    SELECT
        d.id_mutation, d.nom_commune, d.type_local,
        CAST(d.surface_reelle_bati AS INTEGER)  AS surface,
        CAST(d.surface_terrain AS INTEGER)      AS surface_terrain,
        d.nombre_pieces_principales             AS pieces,
        d.valeur_fonciere                       AS prix,
        ROUND(d.prix_m2, 0)                     AS prix_m2,
        d.adresse, CAST(d.date_mutation AS VARCHAR) AS date_mutation, d.annee,
        d.classe_dpe_dominante AS dpe, d.pct_passoires, d.pct_bons_dpe,
        d.conso_med_kwh_m2, d.n_dpe,
        d.arret_plus_proche, d.mode_transport_proche, d.reseaux_transport,
        ROUND(d.distance_arret_m, 0) AS distance_arret_m,
        d.nb_arrets_500m, d.nb_arrets_1000m, d.nb_arrets_2000m,
        d.peb_zone, d.nom_aeroport,
        ROUND((d.prix_m2 - m.med) / NULLIF(m.med,0) * 100, 1) AS vs_marche
    FROM dvf_enrichi d
    LEFT JOIN medians m ON d.nom_commune = m.nom_commune AND d.type_local = m.type_local
    WHERE {where}
    ORDER BY {order}
    LIMIT {limit}
    """).fetchall()

    keys = [
        "id_mutation","commune","type_local","surface","surface_terrain",
        "pieces","prix","prix_m2","adresse","date","annee",
        "dpe","pct_passoires","pct_bons_dpe","conso_med_kwh_m2","n_dpe",
        "arret_plus_proche","mode_transport_proche","reseaux_transport",
        "distance_arret_m","nb_arrets_500m","nb_arrets_1000m","nb_arrets_2000m",
        "peb_zone","nom_aeroport","vs_marche",
    ]
    return [dict(zip(keys, r)) for r in rows]


# ── /api/stats ───────────────────────────────────────────────────────────────
@app.get("/api/stats")
def get_stats(commune: str, annee: int = 0):
    con = get_connection()
    annees_str = str(annee) if annee != 0 else _annees_for_commune(con, commune)
    row = con.execute(f"""
        SELECT
            COUNT(*), ROUND(MEDIAN(valeur_fonciere),0), ROUND(MEDIAN(prix_m2),0),
            ROUND(AVG(surface_reelle_bati),0), ROUND(MEDIAN(distance_arret_m),0),
            ROUND(AVG(nb_arrets_500m),1), ROUND(AVG(pct_passoires)*100,1),
            ROUND(AVG(pct_bons_dpe)*100,1), MODE(classe_dpe_dominante),
            MODE(reseaux_transport),
            COUNT(*) FILTER (WHERE peb_zone IS NOT NULL)
        FROM dvf_enrichi
        WHERE nom_commune = '{commune}'
          AND annee IN ({annees_str})
          AND prix_m2 BETWEEN 100 AND 30000
    """).fetchone()
    if not row or row[0] == 0:
        return {
            "nb": 0, "prix_median": None, "prix_median_m2": None,
            "surface_moyenne": None, "distance_arret_mediane": None,
            "moy_arrets_500m": None, "pct_passoires_moyen": None,
            "pct_bons_dpe_moyen": None, "dpe_dominant": None,
            "reseau_principal": None, "nb_en_peb": 0,
        }
    return {
        "nb": row[0], "prix_median": row[1], "prix_median_m2": row[2],
        "surface_moyenne": row[3], "distance_arret_mediane": row[4],
        "moy_arrets_500m": row[5], "pct_passoires_moyen": row[6],
        "pct_bons_dpe_moyen": row[7], "dpe_dominant": row[8],
        "reseau_principal": row[9], "nb_en_peb": row[10],
    }


# ── /api/carte/commune ───────────────────────────────────────────────────────
@app.get("/api/carte/commune")
def get_carte_commune(
    commune:    str,
    annee:      int             = 0,
    type_local: str             = "Tous",
    pieces_min: int             = 0,
    surf_min:   Optional[float] = None,
    surf_max:   Optional[float] = None,
    prix_min:   Optional[float] = None,
    prix_max:   Optional[float] = None,
    dpe_max:    str             = "",
    dist_max:   Optional[float] = None,
    limit:      int             = 500,
):
    """Points individuels pour une commune (mode zoom-in)."""
    con = get_connection()
    annees_str = str(annee) if annee != 0 else _annees_for_commune(con, commune)

    filters = [
        f"nom_commune = '{commune}'",
        f"annee IN ({annees_str})",
        "prix_m2 BETWEEN 100 AND 30000",
        "latitude IS NOT NULL", "longitude IS NOT NULL",
        "surface_reelle_bati IS NOT NULL", "valeur_fonciere IS NOT NULL",
    ]
    if type_local != "Tous":
        filters.append(f"type_local = '{type_local}'")
    if pieces_min > 0:
        filters.append(f"nombre_pieces_principales >= {pieces_min}")
    if surf_min and surf_min > 0:
        filters.append(f"surface_reelle_bati >= {surf_min}")
    if surf_max and surf_max > 0:
        filters.append(f"surface_reelle_bati <= {surf_max}")
    if prix_min and prix_min > 0:
        filters.append(f"valeur_fonciere >= {prix_min}")
    if prix_max and prix_max > 0:
        filters.append(f"valeur_fonciere <= {prix_max}")
    if dist_max and dist_max > 0:
        filters.append(f"distance_arret_m <= {dist_max}")
    dpe_f = _dpe_filter(dpe_max)
    if dpe_f:
        filters.append(dpe_f)

    where = " AND ".join(filters)
    rows = con.execute(f"""
        WITH med AS (
            SELECT MEDIAN(prix_m2) AS m
            FROM dvf_enrichi
            WHERE nom_commune = '{commune}'
              AND annee IN ({annees_str})
              AND prix_m2 BETWEEN 100 AND 30000
        )
        SELECT
            id_mutation, nom_commune, type_local,
            CAST(surface_reelle_bati AS INTEGER) AS surface,
            CAST(surface_terrain AS INTEGER)     AS surface_terrain,
            nombre_pieces_principales            AS pieces,
            valeur_fonciere                      AS prix,
            ROUND(prix_m2, 0)                    AS prix_m2,
            adresse, CAST(date_mutation AS VARCHAR) AS date_mutation,
            latitude, longitude,
            classe_dpe_dominante                 AS dpe,
            pct_passoires, pct_bons_dpe, conso_med_kwh_m2,
            arret_plus_proche, mode_transport_proche, reseaux_transport,
            ROUND(distance_arret_m, 0)           AS distance_arret_m,
            nb_arrets_500m, peb_zone, nom_aeroport,
            ROUND((prix_m2 - (SELECT m FROM med)) / NULLIF((SELECT m FROM med),0) * 100, 1) AS vs_marche
        FROM dvf_enrichi
        WHERE {where}
        ORDER BY id_mutation
        LIMIT {limit}
    """).fetchall()

    keys = [
        "id_mutation","commune","type_local","surface","surface_terrain",
        "pieces","prix","prix_m2","adresse","date","lat","lng",
        "dpe","pct_passoires","pct_bons_dpe","conso_med_kwh_m2",
        "arret_plus_proche","mode_transport_proche","reseaux_transport",
        "distance_arret_m","nb_arrets_500m","peb_zone","nom_aeroport","vs_marche",
    ]
    return [dict(zip(keys, r)) for r in rows]


# ── Chatbot ──────────────────────────────────────────────────────────────────
class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None

class ChatResponse(BaseModel):
    reply: str
    session_id: str
    history_length: int

@app.post("/chat", response_model=ChatResponse)
def chat_endpoint(req: ChatRequest):
    session_id = req.session_id or str(uuid.uuid4())
    history = CONVERSATIONS.get(session_id, [])
    try:
        reply, new_history = chat(req.message, history)
    except Exception as e:
        raise HTTPException(500, f"Erreur agent: {type(e).__name__}: {e}")
    CONVERSATIONS[session_id] = new_history
    return ChatResponse(reply=reply, session_id=session_id, history_length=len(new_history))

@app.get("/conversation/{session_id}")
def get_conversation(session_id: str):
    if session_id not in CONVERSATIONS:
        raise HTTPException(404, "Session inconnue")
    return {"session_id": session_id, "messages": CONVERSATIONS[session_id]}

@app.delete("/conversation/{session_id}")
def delete_conversation(session_id: str):
    CONVERSATIONS.pop(session_id, None)
    return {"status": "deleted", "session_id": session_id}


# ── /api/stats/global ────────────────────────────────────────────────────────
@app.get("/api/stats/global")
def get_stats_global():
    """Données agrégées pour la page Statistiques."""
    con = get_connection()

    # 1. Évolution prix médian par année et type
    evolution = con.execute("""
        SELECT annee, type_local,
               ROUND(MEDIAN(prix_m2), 0) AS prix_m2_med,
               COUNT(*) AS n
        FROM dvf_enrichi
        WHERE prix_m2 BETWEEN 100 AND 30000
          AND annee IS NOT NULL
          AND type_local IN ('Maison', 'Appartement')
        GROUP BY annee, type_local
        ORDER BY annee, type_local
    """).fetchall()

    # 2. Effet PEB sur les prix
    peb = con.execute("""
        SELECT
            CASE WHEN peb_zone IS NULL THEN 'Hors zone PEB'
                 ELSE 'En zone PEB (' || peb_zone || ')'
            END AS zone,
            ROUND(MEDIAN(prix_m2), 0) AS prix_m2_med,
            COUNT(*) AS n,
            type_local
        FROM dvf_enrichi
        WHERE prix_m2 BETWEEN 100 AND 30000
          AND type_local IN ('Maison', 'Appartement')
        GROUP BY zone, type_local
        ORDER BY type_local, prix_m2_med DESC
    """).fetchall()

    # 3. Effet transport sur les prix (buckets distance)
    transport = con.execute("""
        SELECT
            CASE
                WHEN distance_arret_m <  300  THEN '< 300 m'
                WHEN distance_arret_m <  500  THEN '300–500 m'
                WHEN distance_arret_m < 1000  THEN '500 m–1 km'
                WHEN distance_arret_m < 2000  THEN '1–2 km'
                ELSE '> 2 km'
            END AS bucket,
            type_local,
            ROUND(MEDIAN(prix_m2), 0) AS prix_m2_med,
            COUNT(*) AS n
        FROM dvf_enrichi
        WHERE prix_m2 BETWEEN 100 AND 30000
          AND distance_arret_m IS NOT NULL
          AND type_local IN ('Maison', 'Appartement')
        GROUP BY bucket, type_local
        ORDER BY type_local,
            CASE bucket
                WHEN '< 300 m'    THEN 1
                WHEN '300–500 m'  THEN 2
                WHEN '500 m–1 km' THEN 3
                WHEN '1–2 km'     THEN 4
                ELSE 5
            END
    """).fetchall()

    # 4. Top/Flop communes par prix médian (min 20 ventes)
    top_communes = con.execute("""
        SELECT nom_commune, type_local,
               ROUND(MEDIAN(prix_m2), 0) AS prix_m2_med,
               COUNT(*) AS n
        FROM dvf_enrichi
        WHERE prix_m2 BETWEEN 100 AND 30000
          AND type_local IN ('Maison', 'Appartement')
        GROUP BY nom_commune, type_local
        HAVING COUNT(*) >= 20
        ORDER BY prix_m2_med DESC
        LIMIT 20
    """).fetchall()

    flop_communes = con.execute("""
        SELECT nom_commune, type_local,
               ROUND(MEDIAN(prix_m2), 0) AS prix_m2_med,
               COUNT(*) AS n
        FROM dvf_enrichi
        WHERE prix_m2 BETWEEN 100 AND 30000
          AND type_local IN ('Maison', 'Appartement')
        GROUP BY nom_commune, type_local
        HAVING COUNT(*) >= 20
        ORDER BY prix_m2_med ASC
        LIMIT 20
    """).fetchall()

    # 5. DPE vs prix
    dpe_prix = con.execute("""
        SELECT classe_dpe_dominante AS dpe,
               type_local,
               ROUND(MEDIAN(prix_m2), 0) AS prix_m2_med,
               COUNT(*) AS n
        FROM dvf_enrichi
        WHERE prix_m2 BETWEEN 100 AND 30000
          AND classe_dpe_dominante IS NOT NULL
          AND classe_dpe_dominante != ''
          AND type_local IN ('Maison', 'Appartement')
        GROUP BY dpe, type_local
        ORDER BY type_local, dpe
    """).fetchall()

    # 6. Résumé global
    resume = con.execute("""
        SELECT
            COUNT(*)                              AS n_total,
            COUNT(DISTINCT nom_commune)           AS n_communes,
            ROUND(MEDIAN(prix_m2), 0)             AS prix_m2_global,
            MIN(annee), MAX(annee),
            COUNT(*) FILTER (WHERE peb_zone IS NOT NULL) AS n_peb,
            ROUND(AVG(pct_passoires)*100, 1)      AS pct_passoires_moy
        FROM dvf_enrichi
        WHERE prix_m2 BETWEEN 100 AND 30000
    """).fetchone()

    return {
        "resume": {
            "n_total": resume[0], "n_communes": resume[1],
            "prix_m2_global": resume[2],
            "annee_min": resume[3], "annee_max": resume[4],
            "n_en_peb": resume[5], "pct_passoires_moy": resume[6],
        },
        "evolution": [
            {"annee": r[0], "type_local": r[1], "prix_m2_med": r[2], "n": r[3]}
            for r in evolution
        ],
        "peb": [
            {"zone": r[0], "prix_m2_med": r[1], "n": r[2], "type_local": r[3]}
            for r in peb
        ],
        "transport": [
            {"bucket": r[0], "type_local": r[1], "prix_m2_med": r[2], "n": r[3]}
            for r in transport
        ],
        "top_communes": [
            {"commune": r[0], "type_local": r[1], "prix_m2_med": r[2], "n": r[3]}
            for r in top_communes
        ],
        "flop_communes": [
            {"commune": r[0], "type_local": r[1], "prix_m2_med": r[2], "n": r[3]}
            for r in flop_communes
        ],
        "dpe_prix": [
            {"dpe": r[0], "type_local": r[1], "prix_m2_med": r[2], "n": r[3]}
            for r in dpe_prix
        ],
    }
