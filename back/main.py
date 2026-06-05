"""
main.py
-----------------------------------------------------------------------------
Backend unifié FastAPI :
  - Endpoints données immobilières (communes, biens, carte, stats)
  - Endpoints chatbot (agent Groq + DuckDB)

Table principale : dvf_enrichi
Lance avec : uvicorn main:app --reload --port 8000
Docs auto  : http://localhost:8000/docs
"""
from __future__ import annotations
import uuid
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

from core.recup_donnees import get_connection
from agent import chat

# ============================================================================
# App
# ============================================================================
app = FastAPI(
    title="ImmoBI API",
    description="API unifiée — données immobilières + chatbot",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# Stockage conversations en mémoire
# ============================================================================
CONVERSATIONS: dict[str, list[dict]] = {}

# Ordre DPE pour filtrage
DPE_ORDER = {"A": 1, "B": 2, "C": 3, "D": 4, "E": 5, "F": 6, "G": 7, "": 99}


# ============================================================================
# Modèles Pydantic
# ============================================================================
class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None

class ChatResponse(BaseModel):
    reply: str
    session_id: str
    history_length: int


# ============================================================================
# Health check
# ============================================================================
@app.get("/")
def root():
    return {"status": "ok", "service": "ImmoBI API v2"}


@app.get("/health")
def health():
    try:
        con = get_connection()
        n = con.execute("SELECT COUNT(*) FROM dvf_enrichi").fetchone()[0]
        return {"status": "healthy", "n_transactions": n}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"DB inaccessible: {e}")


# ============================================================================
# ENDPOINTS DONNÉES
# ============================================================================

@app.get("/api/communes")
def get_communes():
    """Liste des communes disponibles dans dvf_enrichi."""
    con = get_connection()
    rows = con.execute("""
        SELECT DISTINCT nom_commune
        FROM dvf_enrichi
        WHERE nom_commune IS NOT NULL
        ORDER BY nom_commune
    """).fetchall()
    return [r[0] for r in rows]


@app.get("/api/annees")
def get_annees():
    """Années disponibles dans dvf_enrichi (colonne annee précalculée)."""
    con = get_connection()
    rows = con.execute("""
        SELECT DISTINCT annee
        FROM dvf_enrichi
        WHERE annee IS NOT NULL
        ORDER BY annee DESC
    """).fetchall()
    return [r[0] for r in rows]


@app.get("/api/biens")
def get_biens(
    commune:    str,
    type_local: str             = "Tous",
    pieces_min: int             = 0,
    surf_min:   Optional[float] = None,
    surf_max:   Optional[float] = None,
    prix_min:   Optional[float] = None,
    prix_max:   Optional[float] = None,
    dpe_max:    str             = "",
    tri:        str             = "deal",
    limit:      int             = 60,
):
    """
    Biens filtrés avec score vs_marche et données enrichies
    (transport, DPE, PEB).
    """
    con = get_connection()

    # 2 dernières années disponibles
    annees = con.execute("""
        SELECT DISTINCT annee FROM dvf_enrichi
        ORDER BY annee DESC LIMIT 2
    """).fetchall()
    annees_str = ", ".join(str(r[0]) for r in annees)

    # Filtre DPE
    dpe_values = [
        k for k, v in DPE_ORDER.items()
        if v <= DPE_ORDER.get(dpe_max, 99) and k != ""
    ]

    filters = [
        f"d.nom_commune = '{commune}'",
        f"d.annee IN ({annees_str})",
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
        filters.append(
            f"(d.classe_dpe_dominante IN ({vals}) OR d.classe_dpe_dominante IS NULL)"
        )

    where = " AND ".join(filters)
    order = {
        "deal":      "vs_marche ASC",
        "prix-asc":  "d.valeur_fonciere ASC",
        "prix-desc": "d.valeur_fonciere DESC",
        "surf-desc": "d.surface_reelle_bati DESC",
    }.get(tri, "vs_marche ASC")

    rows = con.execute(f"""
    WITH medians AS (
        SELECT nom_commune, type_local,
               MEDIAN(prix_m2) AS prix_median_commune
        FROM dvf_enrichi
        WHERE annee IN ({annees_str})
          AND prix_m2 BETWEEN 100 AND 30000
        GROUP BY nom_commune, type_local
    )
    SELECT
        d.id_mutation,
        d.nom_commune,
        d.type_local,
        d.surface_reelle_bati                                        AS surface,
        d.surface_terrain,
        d.nombre_pieces_principales                                  AS pieces,
        d.valeur_fonciere                                            AS prix,
        ROUND(d.prix_m2, 0)                                          AS prix_m2,
        d.adresse,
        CAST(d.date_mutation AS VARCHAR)                             AS date_mutation,
        d.annee,
        -- DPE
        d.classe_dpe_dominante                                       AS dpe,
        d.pct_passoires,
        d.pct_bons_dpe,
        d.conso_med_kwh_m2,
        d.n_dpe,
        -- Transport
        d.arret_plus_proche,
        d.mode_transport_proche,
        d.reseaux_transport,
        ROUND(d.distance_arret_m, 0)                                 AS distance_arret_m,
        d.nb_arrets_500m,
        d.nb_arrets_1000m,
        d.nb_arrets_2000m,
        -- PEB
        d.peb_zone,
        d.nom_aeroport,
        -- Score marché
        ROUND(
            (d.prix_m2 - m.prix_median_commune)
            / NULLIF(m.prix_median_commune, 0) * 100,
        1) AS vs_marche
    FROM dvf_enrichi d
    LEFT JOIN medians m
           ON d.nom_commune = m.nom_commune
          AND d.type_local  = m.type_local
    WHERE {where}
    ORDER BY {order}
    LIMIT {limit}
    """).fetchall()

    keys = [
        "id_mutation", "commune", "type_local", "surface", "surface_terrain",
        "pieces", "prix", "prix_m2", "adresse", "date", "annee",
        "dpe", "pct_passoires", "pct_bons_dpe", "conso_med_kwh_m2", "n_dpe",
        "arret_plus_proche", "mode_transport_proche", "reseaux_transport",
        "distance_arret_m", "nb_arrets_500m", "nb_arrets_1000m", "nb_arrets_2000m",
        "peb_zone", "nom_aeroport",
        "vs_marche",
    ]
    return [dict(zip(keys, r)) for r in rows]


@app.get("/api/stats")
def get_stats(commune: str):
    """
    Statistiques agrégées pour une commune :
    prix, surface, DPE, transport.
    """
    con = get_connection()
    row = con.execute("""
        SELECT
            COUNT(*)                              AS nb,
            ROUND(MEDIAN(valeur_fonciere), 0)     AS prix_median,
            ROUND(MEDIAN(prix_m2), 0)             AS prix_median_m2,
            ROUND(AVG(surface_reelle_bati), 0)    AS surface_moyenne,
            ROUND(MEDIAN(distance_arret_m), 0)    AS distance_arret_mediane,
            ROUND(AVG(nb_arrets_500m), 1)         AS moy_arrets_500m,
            ROUND(AVG(pct_passoires) * 100, 1)    AS pct_passoires_moyen,
            ROUND(AVG(pct_bons_dpe)  * 100, 1)    AS pct_bons_dpe_moyen,
            MODE(classe_dpe_dominante)             AS dpe_dominant,
            MODE(reseaux_transport)                AS reseau_principal,
            COUNT(*) FILTER (WHERE peb_zone IS NOT NULL) AS nb_en_peb
        FROM dvf_enrichi
        WHERE nom_commune = ?
          AND prix_m2 BETWEEN 100 AND 30000
    """, [commune]).fetchone()

    return {
        "nb":                    row[0],
        "prix_median":           row[1],
        "prix_median_m2":        row[2],
        "surface_moyenne":       row[3],
        "distance_arret_mediane":row[4],
        "moy_arrets_500m":       row[5],
        "pct_passoires_moyen":   row[6],
        "pct_bons_dpe_moyen":    row[7],
        "dpe_dominant":          row[8],
        "reseau_principal":      row[9],
        "nb_en_peb":             row[10],
    }


@app.get("/api/carte")
def get_carte(type_local: str = "Tous", annee: int = 2024):
    """
    Données agrégées par commune pour la carte,
    incluant score transport et DPE moyen.
    """
    con = get_connection()
    filters = [
        f"annee = {annee}",
        "prix_m2 BETWEEN 100 AND 30000",
        "latitude IS NOT NULL",
        "longitude IS NOT NULL",
    ]
    if type_local != "Tous":
        filters.append(f"type_local = '{type_local}'")
    where = " AND ".join(filters)

    rows = con.execute(f"""
        SELECT
            nom_commune,
            ROUND(AVG(latitude),  4)              AS lat,
            ROUND(AVG(longitude), 4)              AS lng,
            ROUND(MEDIAN(prix_m2), 0)             AS prix_median_m2,
            ROUND(AVG(prix_m2), 0)                AS prix_moyen_m2,
            COUNT(*)                              AS nb_transactions,
            ROUND(MEDIAN(distance_arret_m), 0)    AS distance_arret_mediane,
            ROUND(AVG(nb_arrets_1000m), 1)        AS moy_arrets_1km,
            ROUND(AVG(pct_passoires) * 100, 1)    AS pct_passoires,
            MODE(classe_dpe_dominante)             AS dpe_dominant,
            COUNT(*) FILTER (WHERE peb_zone IS NOT NULL) AS nb_en_peb
        FROM dvf_enrichi
        WHERE {where}
        GROUP BY nom_commune
        HAVING COUNT(*) >= 3
        ORDER BY nb_transactions DESC
    """).fetchall()

    keys = [
        "commune", "lat", "lng",
        "prix_median_m2", "prix_moyen_m2", "nb_transactions",
        "distance_arret_mediane", "moy_arrets_1km",
        "pct_passoires", "dpe_dominant", "nb_en_peb",
    ]
    return [dict(zip(keys, r)) for r in rows]


# ============================================================================
# ENDPOINTS CHATBOT
# ============================================================================

@app.post("/chat", response_model=ChatResponse)
def chat_endpoint(req: ChatRequest):
    session_id = req.session_id or str(uuid.uuid4())
    history    = CONVERSATIONS.get(session_id, [])
    try:
        reply, new_history = chat(req.message, history)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erreur agent: {type(e).__name__}: {e}",
        )
    CONVERSATIONS[session_id] = new_history
    return ChatResponse(
        reply=reply,
        session_id=session_id,
        history_length=len(new_history),
    )


@app.get("/conversation/{session_id}")
def get_conversation(session_id: str):
    if session_id not in CONVERSATIONS:
        raise HTTPException(status_code=404, detail="Session inconnue")
    return {"session_id": session_id, "messages": CONVERSATIONS[session_id]}


@app.delete("/conversation/{session_id}")
def delete_conversation(session_id: str):
    CONVERSATIONS.pop(session_id, None)
    return {"status": "deleted", "session_id": session_id}
