"""
app.py
-----------------------------------------------------------------------------
Interface chatbot Streamlit.

Lance avec :  streamlit run app.py
Puis ouvre dans le navigateur : http://localhost:8501
"""
import streamlit as st
from agent import chat

# ============================================================================
# Configuration page
# ============================================================================
st.set_page_config(
    page_title="Assistant Immo 44",
    page_icon="🏠",
    layout="centered"
)

# ============================================================================
# Sidebar
# ============================================================================
with st.sidebar:
    st.title("🏠 Assistant Immo")
    st.markdown("**Loire-Atlantique (44)**")
    st.markdown("---")
    st.markdown("""
    Cet assistant interroge la base DVF (transactions immobilières
    2021-2025) pour répondre à vos questions sur l'immobilier
    en Loire-Atlantique.

    **Exemples de questions :**
    - Quel est le prix moyen à Nantes ?
    - Compare Nantes, Rezé et Vertou
    - Je cherche un appart 3 pièces à 280k
    - 250 000€ pour 65m² à Saint-Herblain c'est correct ?
    - Quel est l'impact du bruit à Bouguenais ?
    """)
    st.markdown("---")
    if st.button("🗑️ Nouvelle conversation"):
        st.session_state.history = []
        st.session_state.messages = []
        st.rerun()

# ============================================================================
# État de la session
# ============================================================================
if "messages" not in st.session_state:
    st.session_state.messages = []
if "history" not in st.session_state:
    st.session_state.history = []

# ============================================================================
# Affichage des messages
# ============================================================================
st.title("Assistant Immo Loire-Atlantique")

# Message d'accueil
if not st.session_state.messages:
    with st.chat_message("assistant"):
        st.markdown(
            "Bonjour ! Je suis votre assistant pour l'immobilier en "
            "Loire-Atlantique. Posez-moi une question sur les prix, "
            "la recherche de biens, ou la comparaison de communes."
        )

# Historique
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ============================================================================
# Saisie utilisateur
# ============================================================================
if user_input := st.chat_input("Votre question..."):
    # Affiche le message utilisateur immédiatement
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    # Appel au chatbot avec indicateur de chargement
    with st.chat_message("assistant"):
        with st.spinner("Je consulte la base..."):
            try:
                reply, new_history = chat(user_input, st.session_state.history)
                st.session_state.history = new_history
                st.markdown(reply)
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": reply
                })
            except Exception as e:
                error_msg = f"Erreur : {e}"
                st.error(error_msg)
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": error_msg
                })
