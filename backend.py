"""
backend.py
-----------------------------------------------------------------------------
API REST FastAPI qui expose le chatbot.
Permet au frontend React de l'appeler via HTTP.

Lance avec :   uvicorn backend:app --reload --port 8000
Puis docs auto : http://localhost:8000/docs
"""
from __future__ import annotations
import uuid
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

from agent import chat

# ============================================================================
# App FastAPI
# ============================================================================
app = FastAPI(
    title="Assistant Immo Loire-Atlantique API",
    description="API REST pour le chatbot immobilier (DuckDB + Groq)",
    version="1.0.0",
)

# CORS — autorise le frontend React à appeler l'API
# En dev, on autorise tout. En prod, mettre l'URL exacte du front.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # ⚠️ en prod : ["https://ton-front.com"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# Stockage des conversations en mémoire
# ============================================================================
# Pour MVP : dict en mémoire. Si le serveur redémarre, les conversations
# sont perdues. Pour faire mieux plus tard : SQLite ou Redis.
CONVERSATIONS: dict[str, list[dict]] = {}


# ============================================================================
# Modèles Pydantic (validation auto des inputs/outputs)
# ============================================================================
class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None     # None = nouvelle conversation

    class Config:
        json_schema_extra = {
            "example": {
                "message": "Quel est le prix moyen à Nantes ?",
                "session_id": None,
            }
        }


class ChatResponse(BaseModel):
    reply: str                # Réponse du bot
    session_id: str           # ID à renvoyer dans le prochain message
    history_length: int       # Nombre de tours dans la conversation


# ============================================================================
# Endpoints
# ============================================================================
@app.get("/")
def root():
    """Health check basique."""
    return {
        "status": "ok",
        "service": "Assistant Immo Loire-Atlantique",
        "endpoints": ["/chat", "/conversation/{session_id}", "/health"],
    }


@app.get("/health")
def health():
    """Vérifie que la base DuckDB est accessible."""
    from tools import _connect, _best_dvf_table
    try:
        con = _connect()
        table = _best_dvf_table(con)
        n = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        con.close()
        return {
            "status": "healthy",
            "table_principale": table,
            "n_transactions": n,
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"DB inaccessible: {e}")


@app.post("/chat", response_model=ChatResponse)
def chat_endpoint(req: ChatRequest):
    """
    Endpoint principal du chatbot.

    - Si session_id absent : nouvelle conversation (un id est généré)
    - Si session_id présent : continue la conversation existante
    """
    # Récupère ou crée la conversation
    session_id = req.session_id or str(uuid.uuid4())
    history = CONVERSATIONS.get(session_id, [])

    # Appelle le chatbot
    try:
        reply, new_history = chat(req.message, history)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erreur agent: {type(e).__name__}: {e}"
        )

    # Sauvegarde l'historique mis à jour
    CONVERSATIONS[session_id] = new_history

    return ChatResponse(
        reply=reply,
        session_id=session_id,
        history_length=len(new_history),
    )


@app.get("/conversation/{session_id}")
def get_conversation(session_id: str):
    """Récupère l'historique d'une conversation (utile pour debug)."""
    if session_id not in CONVERSATIONS:
        raise HTTPException(status_code=404, detail="Session inconnue")
    return {
        "session_id": session_id,
        "messages": CONVERSATIONS[session_id],
    }


@app.delete("/conversation/{session_id}")
def delete_conversation(session_id: str):
    """Supprime une conversation."""
    CONVERSATIONS.pop(session_id, None)
    return {"status": "deleted", "session_id": session_id}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
