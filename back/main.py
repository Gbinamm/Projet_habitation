"""
main.py
-----------------------------------------------------------------------------
Backend unifié FastAPI :
  - Endpoints données immobilières (communes, biens, carte, stats)
  - Endpoints chatbot (agent Groq + DuckDB)

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
    version="1.0.0",
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
    return {"status": "ok", "service": "ImmoBI API"}


@app.get("/health")
def health():
    try:
        con = get_connection()
        n = con.execute("SELECT COUNT(*) FROM dvf_raw").fetchone()[0]
        return {"status": "healthy", "n_transactions": n}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"DB inaccessible: {e}")


# ============================================================================
# ENDPOINTS DONNÉES
# ============================================================================

@app.get("/api/communes")
def get_communes():
    con = get_connection()
    rows = con.execute("""
        SELECT DISTINCT nom_commune FROM dvf_raw
        WHERE nom_commune IS NOT NULL ORDER BY nom_commune
    """).fetchall()
    return [r[0] for r in rows]


@app.get("/api/annees")
def get_annees():
    con = get_connection()
    rows = con.execute("""
        SELECT DISTINCT YEAR(date_mutation) AS annee
        FROM dvf_raw ORDER BY annee DESC
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
    con = get_connection()

    annees = con.execute("""
        SELECT DISTINCT YEAR(date_mutation) AS annee
        FROM dvf_raw ORDER BY annee DESC LIMIT 2
    """).fetchall()
    annees_str = ", ".join(str(r[0]) for r in annees)

    dpe_order  = {"A":1,"B":2,"C":3,"D":4,"E":5,"F":6,"G":7,"":99}
    dpe_values = [k for k,v in dpe_order.items()
                  if v <= dpe_order.get(dpe_max, 99) and k != ""]

    filters = [
        f"d.nom_commune = '{commune}'",
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
    order = {
        "deal":      "vs_marche ASC",
        "prix-asc":  "d.valeur_fonciere ASC",
        "prix-desc": "d.valeur_fonciere DESC",
        "surf-desc": "d.surface_reelle_bati DESC",
    }.get(tri, "vs_marche ASC")

    rows = con.execute(f"""
    WITH medians AS (
        SELECT nom_commune, type_local, MEDIAN(prix_m2) AS prix_median_commune
        FROM dvf_raw
        WHERE YEAR(date_mutation) IN ({annees_str})
          AND prix_m2 BETWEEN 100 AND 30000
        GROUP BY nom_commune, type_local
    )
    SELECT
        d.nom_commune, d.type_local,
        d.surface_reelle_bati                                       AS surface,
        d.nombre_pieces_principales                                 AS pieces,
        d.valeur_fonciere                                           AS prix,
        ROUND(d.prix_m2, 0)                                         AS prix_m2,
        d.dpe_classe                                                AS dpe,
        CAST(d.date_mutation AS VARCHAR)                            AS date_mutation,
        ROUND((d.prix_m2 - m.prix_median_commune)
              / NULLIF(m.prix_median_commune, 0) * 100, 1)          AS vs_marche
    FROM dvf_raw d
    LEFT JOIN medians m ON d.nom_commune = m.nom_commune
                       AND d.type_local  = m.type_local
    WHERE {where}
    ORDER BY {order}
    LIMIT {limit}
    """).fetchall()

    keys = ["commune","type_local","surface","pieces",
            "prix","prix_m2","dpe","date","vs_marche"]
    return [dict(zip(keys, r)) for r in rows]


@app.get("/api/stats")
def get_stats(commune: str):
    con = get_connection()
    row = con.execute("""
        SELECT
            COUNT(*)                         AS nb,
            ROUND(MEDIAN(valeur_fonciere),0) AS prix_median,
            ROUND(MEDIAN(prix_m2),0)         AS prix_median_m2,
            ROUND(AVG(surface_reelle_bati),0) AS surface_moyenne
        FROM dvf_raw
        WHERE nom_commune = ?
          AND prix_m2 BETWEEN 100 AND 30000
    """, [commune]).fetchone()
    return {
        "nb":              row[0],
        "prix_median":     row[1],
        "prix_median_m2":  row[2],
        "surface_moyenne": row[3],
    }


@app.get("/api/carte")
def get_carte(type_local: str = "Tous", annee: int = 2024):
    con = get_connection()
    filters = [
        f"YEAR(date_mutation) = {annee}",
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
            ROUND(AVG(latitude), 4)   AS lat,
            ROUND(AVG(longitude), 4)  AS lng,
            ROUND(MEDIAN(prix_m2), 0) AS prix_median_m2,
            ROUND(AVG(prix_m2), 0)    AS prix_moyen_m2,
            COUNT(*)                  AS nb_transactions
        FROM dvf_raw
        WHERE {where}
        GROUP BY nom_commune
        HAVING COUNT(*) >= 3
        ORDER BY nb_transactions DESC
    """).fetchall()

    keys = ["commune","lat","lng","prix_median_m2","prix_moyen_m2","nb_transactions"]
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
            detail=f"Erreur agent: {type(e).__name__}: {e}"
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
