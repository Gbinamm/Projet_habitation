import duckdb
import streamlit as st
from pathlib import Path
import pandas as pd
import numpy as np

DB_PATH = Path(__file__).resolve().parent.parent.parent / "immo_et_bruit.duckdb"


def _create_mock_db():
    """
    Crée une base en mémoire avec des données fictives
    qui respectent exactement le schéma réel.
    Utilisée automatiquement quand la vraie base est absente.
    """
    con = duckdb.connect(":memory:")
    rng = np.random.default_rng(42)
    n = 50_000

    communes = [
        ("35238", "Rennes"),
        ("56260", "Vannes"),
        ("44109", "Nantes"),
        ("29019", "Brest"),
        ("22278", "Saint-Brieuc"),
        ("35047", "Bruz"),
        ("56118", "Lorient"),
        ("29232", "Quimper"),
    ]
    codes, noms = zip(*communes)
    idx = rng.integers(0, len(communes), n)

    types   = rng.choice(["Appartement", "Maison"], n, p=[0.6, 0.4])
    dpe_val = rng.choice(["A", "B", "C", "D", "E", "F", "G", None], n,
                         p=[0.05, 0.10, 0.20, 0.25, 0.20, 0.10, 0.05, 0.05])
    surfaces = rng.integers(20, 200, n).astype(float)
    prix_m2  = rng.normal(3200, 800, n).clip(500, 12000)

    df_dvf = pd.DataFrame({
        "code_commune":              [codes[i] for i in idx],
        "nom_commune":               [noms[i] for i in idx],
        "type_local":                types,
        "surface_reelle_bati":       surfaces,
        "nombre_pieces_principales": rng.integers(1, 7, n),
        "prix_m2":                   prix_m2,
        "valeur_fonciere":           (surfaces * prix_m2).round(0),
        "date_mutation":             pd.date_range("2019-01-01", "2024-12-31", periods=n),
        "latitude":                  rng.uniform(47.2, 48.7, n),
        "longitude":                 rng.uniform(-4.5, -1.0, n),
        "dpe_classe":                dpe_val,
    })

    df_transport = pd.DataFrame({
        "stop_id":   [f"STOP{i:05d}" for i in range(500)],
        "stop_name": [f"Arrêt {i}" for i in range(500)],
        "latitude":  rng.uniform(47.2, 48.7, 500),
        "longitude": rng.uniform(-4.5, -1.0, 500),
        "region":    rng.choice(["Bretagne", "Pays de la Loire"], 500).tolist(),
        "aom_nom":   rng.choice(["STAR Rennes", "CTRL Vannes", "TAN Nantes"], 500).tolist(),
    })

    # On enregistre les DataFrames comme vues puis on crée les tables
    con.register("df_dvf", df_dvf)
    con.register("df_transport", df_transport)
    con.execute("CREATE TABLE dvf_raw AS SELECT * FROM df_dvf")
    con.execute("CREATE TABLE transport_stops_clean AS SELECT * FROM df_transport")
    con.unregister("df_dvf")
    con.unregister("df_transport")

    return con


@st.cache_resource
def get_connection():
    if not DB_PATH.exists():
        st.warning("⚠️ Base réelle introuvable — mode démonstration avec données fictives")
        return _create_mock_db()
    return duckdb.connect(str(DB_PATH), read_only=True)
