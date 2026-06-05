"""
agent.py — Nimbus
-----------------------------------------------------------------------------
Cerveau du chatbot : Groq LLM + outils DuckDB.
"""
from __future__ import annotations
import os, json
from groq import Groq
from dotenv import load_dotenv
from tools import TOOLS_SCHEMA, TOOL_FUNCTIONS

load_dotenv()
client = Groq(api_key=os.environ["GROQ_API_KEY"])

MODEL               = "llama-3.3-70b-versatile"
MAX_TOOL_ITERATIONS = 5

SYSTEM_PROMPT = """
Tu es Nimbus, un assistant immobilier spécialisé sur la Bretagne et les
départements voisins (Ille-et-Vilaine 35, Finistère 29, Morbihan 56,
Côtes-d'Armor 22, Loire-Atlantique 44).

==== DOMAINE ====
Tu réponds aux questions sur l'immobilier dans cette zone :
prix au m², recherche de biens, comparaison de communes, performance
énergétique (DPE), accessibilité transport, impact bruit aéroport (PEB),
conseils d'achat/vente.

Si la question est hors-sujet (météo, recettes, politique, autres régions…),
réponds : « Je suis spécialisé dans l'immobilier breton. Je peux vous aider
sur les prix, la recherche de biens, le DPE ou les transports. »

==== RÈGLE ABSOLUE ====
Ne jamais inventer de chiffres. Pour toute donnée chiffrée, appelle l'outil
approprié. Si les outils ne renvoient rien, dis-le honnêtement.

==== OUTILS DISPONIBLES ====
- stats_prix          → prix médian, fourchette, volume de ventes
- rechercher_biens    → exemples concrets selon critères (budget, surface…)
- evaluer_prix        → verdict bon prix / dans le marché / surcoté
- comparer_communes   → comparaison côte à côte (prix, DPE, transport)
- stats_transport     → accessibilité transport en commun
- stats_dpe           → performance énergétique (passoires, conso)
- impact_bruit_aeroport → zones PEB, impact sur les prix
- lister_communes     → vérifier qu'une commune existe dans la base

==== STYLE ====
- Français, clair, concis. Utilise €/m² pour les prix.
- Listes lisibles quand tu donnes plusieurs chiffres.
- Ne mentionne jamais les noms techniques des outils.
- Tu peux demander des précisions si la demande est ambiguë.
"""


def chat(user_message: str, history: list[dict] | None = None) -> tuple[str, list[dict]]:
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": user_message})

    for _ in range(MAX_TOOL_ITERATIONS):
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=TOOLS_SCHEMA,
            tool_choice="auto",
            temperature=0.2,
        )
        msg = response.choices[0].message

        if not msg.tool_calls:
            messages.append({"role": "assistant", "content": msg.content})
            return msg.content, messages[1:]

        messages.append({
            "role": "assistant",
            "content": msg.content,
            "tool_calls": [
                {"id": tc.id, "type": "function",
                 "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                for tc in msg.tool_calls
            ]
        })

        for tc in msg.tool_calls:
            fn_name = tc.function.name
            try:
                args = json.loads(tc.function.arguments)
            except json.JSONDecodeError:
                args = {}

            print(f"  [tool] {fn_name}({args})")

            if fn_name not in TOOL_FUNCTIONS:
                result = {"erreur": f"Outil inconnu : {fn_name}"}
            else:
                try:
                    result = TOOL_FUNCTIONS[fn_name](**args)
                except Exception as e:
                    result = {"erreur": f"{type(e).__name__}: {e}"}

            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "name": fn_name,
                "content": json.dumps(result, ensure_ascii=False, default=str),
            })

    return ("Désolé, je n'ai pas pu traiter cette demande. "
            "Pouvez-vous reformuler ?"), messages[1:]


if __name__ == "__main__":
    print("Nimbus — assistant immobilier breton")
    print("Tape 'quit' pour quitter\n")
    history = []
    while True:
        user_input = input("Vous : ").strip()
        if user_input.lower() in ("quit", "exit", "q"):
            break
        if not user_input:
            continue
        try:
            reply, history = chat(user_input, history)
            print(f"\nNimbus : {reply}\n")
        except Exception as e:
            print(f"Erreur : {e}\n")