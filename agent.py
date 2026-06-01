"""
agent.py
-----------------------------------------------------------------------------
Le "cerveau" du chatbot : reçoit un message, appelle Groq, exécute les outils
DuckDB que Groq demande, et renvoie une réponse en langage naturel.

Architecture :
  1. User envoie un message
  2. Groq LLM analyse → décide quel(s) outil(s) appeler
  3. On exécute les outils (qui interrogent DuckDB)
  4. On renvoie les résultats à Groq
  5. Groq formule la réponse finale en français

Tu peux relancer plusieurs cycles si Groq enchaîne plusieurs appels d'outils.
"""
from __future__ import annotations
import os
import json
from groq import Groq
from dotenv import load_dotenv

from tools import TOOLS_SCHEMA, TOOL_FUNCTIONS

# Charge la clé API depuis .env
load_dotenv()
client = Groq(api_key=os.environ["GROQ_API_KEY"])

# Modèle Groq à utiliser
# llama-3.3-70b-versatile = grand modèle, qualité top, gratuit sur Groq
# Si trop lent : llama-3.1-8b-instant (plus petit, plus rapide)
MODEL = "llama-3.3-70b-versatile"

# Limite de cycles outil → évite les boucles infinies
MAX_TOOL_ITERATIONS = 5


SYSTEM_PROMPT = """
Tu es un assistant immobilier spécialisé sur le département de la
Loire-Atlantique (44), en France.

==== DOMAINE STRICT ====
Tu réponds UNIQUEMENT aux questions sur l'immobilier en Loire-Atlantique :
prix au m², recherche de biens, comparaison de communes, impact du bruit
aéroport, conseils d'achat, etc.

Si on te pose une question hors-sujet (météo, recettes, mathématiques,
politique, autres régions...), tu réponds poliment :
« Je suis spécialisé dans l'immobilier en Loire-Atlantique. Je peux
vous aider sur les prix, la recherche de biens, ou les zones de bruit
aéroport. »

==== UTILISATION DES OUTILS ====
Tu as accès à des outils qui interrogent une base de données réelle de
transactions immobilières (DVF Etalab, 2021-2025).

RÈGLE ABSOLUE : tu ne dois JAMAIS inventer de chiffres ou de prix.
- Pour répondre à toute question chiffrée, appelle systématiquement
  l'outil approprié.
- Si les outils ne renvoient pas de données, dis-le honnêtement :
  « Je n'ai pas cette information dans la base. »
- Ne dis JAMAIS « le prix moyen est environ X » sans avoir interrogé
  la base.

==== STYLE ====
- Réponses en français, claires, concises.
- Utilise des €/m² pour les prix au mètre carré.
- Quand tu donnes plusieurs chiffres, fais des listes lisibles.
- Tu peux poser des questions pour préciser (commune, type, budget...)
  si la demande est ambiguë.
- Ne mentionne JAMAIS les noms techniques des outils (stats_prix etc).

==== EXEMPLES ====

User : "Bonjour"
Toi  : "Bonjour ! Je suis votre assistant immobilier pour la
       Loire-Atlantique. Je peux vous aider à évaluer un prix,
       chercher des biens, ou comparer des communes.
       Que puis-je faire pour vous ?"

User : "C'est combien à Nantes ?"
Toi  : [appelle stats_prix(nom_commune="Nantes")]
       "À Nantes, le prix médian est de X €/m² (sur Y ventes).
        Voulez-vous des stats par type de bien (maison/appartement) ?"

User : "Quelle est la météo demain ?"
Toi  : "Je suis spécialisé dans l'immobilier en Loire-Atlantique..."
"""


def chat(user_message: str, history: list[dict] | None = None) -> tuple[str, list[dict]]:
    """Envoie un message au chatbot et récupère la réponse.

    Args:
        user_message: le texte tapé par l'utilisateur
        history: la liste des messages précédents (None = nouvelle conversation)

    Returns:
        (réponse_du_bot, nouvel_historique)
    """
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": user_message})

    # Boucle d'appel d'outils : Groq peut demander à appeler plusieurs
    # outils en cascade avant de répondre.
    for iteration in range(MAX_TOOL_ITERATIONS):
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=TOOLS_SCHEMA,
            tool_choice="auto",       # Groq décide tout seul
            temperature=0.2,          # bas = réponses plus prévisibles
        )

        msg = response.choices[0].message

        # Cas 1 : pas d'appel d'outil → c'est la réponse finale
        if not msg.tool_calls:
            messages.append({"role": "assistant", "content": msg.content})
            # On renvoie l'historique sans le system prompt
            new_history = messages[1:]
            return msg.content, new_history

        # Cas 2 : Groq veut appeler un ou plusieurs outils
        messages.append({
            "role": "assistant",
            "content": msg.content,
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    }
                } for tc in msg.tool_calls
            ]
        })

        # On exécute chaque appel d'outil et on renvoie le résultat au LLM
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

    # Si on atteint la limite : on prend la dernière réponse texte
    return ("Désolé, j'ai eu un problème pour traiter votre demande. "
            "Pouvez-vous reformuler ?"), messages[1:]


if __name__ == "__main__":
    # Test en ligne de commande
    print("Chatbot immobilier — Loire-Atlantique")
    print("Tape 'quit' pour quitter\n")
    history = []
    while True:
        user_input = input("Vous: ").strip()
        if user_input.lower() in ("quit", "exit", "q"):
            break
        if not user_input:
            continue
        try:
            reply, history = chat(user_input, history)
            print(f"\nBot: {reply}\n")
        except Exception as e:
            print(f"Erreur: {e}\n")
