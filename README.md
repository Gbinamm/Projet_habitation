# Nimbus 🪺 — Analyse du marché immobilier breton

> **Question centrale : pour un prix, une localisation et des caractéristiques données — est-ce un bon deal ?**

Outil de Business Intelligence immobilier basé sur les données publiques françaises (DVF, DPE, PEB, transport). Interface React + API FastAPI + base DuckDB. Couvre les départements 22, 29, 35, 44 et 56.

---

## Prérequis

- Python 3.10+
- Node.js 20+
- Git

---

## Installation

### 1. Cloner le repo

```bash
git clone https://github.com/Gbinamm/Projet_habitation
cd Projet_habitation
```

### 2. Backend Python

```bash
python -m venv venv

# Windows
venv\Scripts\activate
# Mac / Linux
source venv/bin/activate

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
uvicorn main:app --reload
```
→ API : `http://localhost:8000`
→ Docs : `http://localhost:8000/docs`

**Terminal 2 — Frontend**
```bash
cd front-react
npm run dev
```
→ Interface : `http://localhost:5173`

---

## Lancer avec Docker

```bash
# Premier lancement (build + démarrage)
docker compose up --build

# Lancement normal
docker compose up

# En arrière-plan
docker compose up -d

# Arrêter
docker compose down

# Logs en temps réel
docker compose logs -f backend
```

→ Frontend : `http://localhost`
→ Backend : `http://localhost:8000`

---

## Alimenter la base de données

La base `immo_et_bruit.duckdb` n'est pas versionnée. Pour la générer :

```bash
# 1. Données DVF + PEB
python integration_des_donnees.py

# 2. Données DPE
python integration_dpe.py

# 3. Données transport (GTFS)
python integration_transport.py

# 4. Jointure spatiale transport ↔ DVF
python jointure_transport.py
```

> ⚠️ Sans la base, l'app tourne en **mode démonstration** avec des données fictives. Tout fonctionne, les chiffres ne sont pas réels.

---

## Structure du projet

```
Projet_habitation/
├── back/                          # API FastAPI
│   ├── main.py                    # Endpoints données + chatbot + GeoJSON
│   ├── agent.py                   # Logique chatbot (Groq LLM)
│   ├── tools.py                   # 8 outils DuckDB exposés au LLM
│   └── core/
│       └── recup_donnees.py       # Connexion DuckDB + mock données
│
├── front-react/                   # Interface React (Vite)
│   └── src/
│       ├── pages/
│       │   ├── Recherche.jsx      # Recherche filtrée de biens
│       │   ├── Carte.jsx          # Carte choroplèthe + zoom offres
│       │   ├── Stats.jsx          # Analyses du marché (SVG natif)
│       │   └── Chatbot.jsx        # Assistant immobilier Nimbus
│       ├── components/
│       │   ├── FilterBar.jsx      # Filtres avec combobox commune
│       │   └── BienCard.jsx       # Carte d'une offre
│       └── api/
│           └── client.js          # Appels API axios
│
├── integration_des_donnees.py     # Pipeline DVF + PEB
├── integration_dpe.py             # Pipeline DPE (ADEME)
├── integration_transport.py       # Pipeline transport (GTFS)
├── jointure_transport.py          # Jointure spatiale transport ↔ DVF
├── Dockerfile.backend
├── Dockerfile.frontend
├── docker-compose.yml
├── requirements.txt
└── .env                           # ← à créer (non versionné)
```

---

## Pages de l'application

| Page | Description |
|---|---|
| **Recherche** | Filtres multicritères (commune, type, surface, prix, DPE, transport), métriques de marché, tri des résultats |
| **Carte des prix** | Choroplèthe par commune → clic → zoom + points individuels par offre |
| **Analyses** | Évolution des prix, effet transport, zones PEB, DPE vs prix, top/flop communes |
| **Assistant** | Chatbot Groq branché sur la base DuckDB, 8 outils (prix, recherche, évaluation, comparaison...) |

---

## Endpoints API principaux

| Endpoint | Description |
|---|---|
| `GET /api/communes` | Liste des communes |
| `GET /api/annees` | Années disponibles |
| `GET /api/biens` | Offres filtrées |
| `GET /api/stats` | Stats agrégées d'une commune |
| `GET /api/carte/commune` | Points individuels d'une commune |
| `GET /api/geojson` | Contours GeoJSON enrichis (mis en cache) |
| `GET /api/stats/global` | Données agrégées page Analyses |
| `POST /chat` | Chatbot |

---

## Stack technique

| Couche | Technologie |
|---|---|
| Base de données | DuckDB |
| API | FastAPI + Uvicorn |
| Requêtes async | httpx |
| LLM Chatbot | Groq (llama-3.3-70b) |
| Frontend | React 19 + Vite |
| Cartes | Leaflet + react-leaflet |
| Graphiques | SVG natif (zéro dépendance) |
| Données | DVF Etalab · DPE ADEME · PEB GéoRisques · GTFS PAN |

---

## Problèmes fréquents

**`ModuleNotFoundError`**
```bash
pip install -r requirements.txt
```

**`Cannot open database`**
La base DuckDB n'existe pas — lancer les scripts d'intégration ou laisser le mode démo se déclencher.

**`GROQ_API_KEY not found`**
Le `.env` doit être à la racine de `Projet_habitation/`, pas dans `back/`.

**Port 8000 déjà utilisé**
```bash
uvicorn main:app --reload --port 8001
```
Mettre à jour `src/api/client.js` : `baseURL: 'http://localhost:8001'`

**White screen sur la page Analyses**
Ne pas installer Recharts (conflit React 19). La page utilise du SVG natif, aucune dépendance supplémentaire nécessaire.

**Carte sans couleurs (polygones gris)**
Le backend doit pouvoir contacter `geo.api.gouv.fr` au premier appel sur `/api/geojson`. Vérifier la connexion internet. Les logs backend affichent `[geojson] Jointure : X/Y communes enrichies`.