# ImmoBI — Analyse du marché immobilier français

> **Question centrale : pour un prix, une localisation et des caractéristiques données — est-ce un bon deal ?**

Outil de Business Intelligence immobilier basé sur les données publiques françaises (DVF, DPE, PEB, transport). Interface React + API FastAPI + base DuckDB.

---

## Prérequis

- Python 3.10+
- Node.js 20+
- Git

---

## Installation en 3 étapes

### 1. Cloner le repo

```bash
git clone https://github.com/Gbinamm/Projet_habitation
cd Projet_habitation
```

### 2. Backend Python

```bash
# Créer et activer l'environnement virtuel
python -m venv venv
source venv/Scripts/activate   # Windows Git Bash
# ou
source venv/bin/activate       # Mac / Linux

# Installer les dépendances
pip install -r requirements.txt
```

Créer le fichier `.env` à la racine :
```
GROQ_API_KEY=votre_clé_groq
```

> Clé gratuite sur [console.groq.com](https://console.groq.com)

### 3. Frontend React

```bash
cd front-react
npm install
```

---

## Lancer l'application

Deux terminaux en parallèle :

**Terminal 1 — Backend**
```bash
cd back
source ../venv/Scripts/activate
uvicorn main:app --reload
```
→ API disponible sur `http://localhost:8000`
→ Documentation interactive : `http://localhost:8000/docs`

**Terminal 2 — Frontend**
```bash
cd front-react
npm run dev
```
→ Interface disponible sur `http://localhost:5173`

---

## Alimenter la base de données

La base `immo_et_bruit.duckdb` n'est pas versionnée (données volumineuses). Pour la générer :

```bash
source venv/Scripts/activate

# 1. Données DVF + DPE + PEB
python integration_des_donnees.py

# 2. Données DPE
python integration_dpe.py

# 3. Données transport en commun
python integration_transport.py

# 4. Jointure transport
python jointure_transport.py
```

> ⚠️ Sans la base, l'app tourne en **mode démonstration** avec des données fictives générées automatiquement. Tout fonctionne, les chiffres ne sont pas réels.

---

## Structure du projet

```
Projet_habitation/
├── back/                        # API FastAPI
│   ├── main.py                  # Endpoints données + chatbot
│   ├── agent.py                 # Logique chatbot (Groq LLM)
│   ├── tools.py                 # Outils DuckDB exposés au LLM
│   └── core/
│       └── recup_donnees.py     # Connexion DuckDB
│
├── front-react/                 # Interface React (Vite)
│   └── src/
│       ├── pages/
│       │   ├── Recherche.jsx    # Recherche de biens
│       │   ├── Carte.jsx        # Carte des prix au m²
│       │   └── Chatbot.jsx      # Assistant immobilier
│       ├── components/
│       │   ├── FilterBar.jsx    # Barre de filtres sticky
│       │   └── BienCard.jsx     # Carte d'un bien
│       ├── api/
│       │   └── client.js        # Appels API
│       └── hooks/
│           └── useScrollDirection.js
│
├── data_public/                 # Données publiques légères versionnées
├── integration_des_donnees.py   # Pipeline DVF + DPE + PEB
├── integration_dpe.py           # Pipeline DPE
├── integration_transport.py     # Pipeline transport (PAN GTFS)
├── jointure_transport.py        # Jointure spatiale transport ↔ DVF
├── requirements.txt
└── .env                         # ← à créer localement (non versionné)
```

---

## Problèmes fréquents

**`ModuleNotFoundError: No module named 'xxx'`**
```bash
source venv/Scripts/activate
pip install -r requirements.txt
```

**`Cannot open database ... does not exist`**
La base DuckDB n'existe pas encore — lancer les scripts d'intégration ou laisser le mode démo se déclencher automatiquement.

**`GROQ_API_KEY not found`**
Le fichier `.env` est absent ou mal placé. Il doit être à la racine de `Projet_habitation/`, pas dans `back/`.

**Port 8000 déjà utilisé**
```bash
uvicorn main:app --reload --port 8001
```
Et mettre à jour `src/api/client.js` : `baseURL: 'http://localhost:8001'`

**`npm run dev` — `command not found`**
Node.js n'est pas installé ou pas dans le PATH. Télécharger sur [nodejs.org](https://nodejs.org) (version LTS).

---

## Stack technique

| Couche | Technologie |
|---|---|
| Base de données | DuckDB |
| API | FastAPI + Uvicorn |
| LLM Chatbot | Groq (llama-3.3-70b) |
| Frontend | React 18 + Vite |
| Cartes | Leaflet + react-leaflet |
| Données | DVF Etalab, DPE ADEME, PEB GéoRisques, GTFS PAN |
