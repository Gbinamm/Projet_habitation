"""
recup_donnees.py
-----------------------------------------------------------------------------
Connexion à la base DuckDB immo_et_bruit.duckdb
Table principale : dvf_enrichi (395 001 lignes)

Colonnes disponibles :
  DVF core    : id_mutation, date_mutation, annee, nature_mutation, type_local,
                surface_reelle_bati, nombre_pieces_principales, surface_terrain,
                valeur_fonciere, prix_m2, adresse, code_commune, code_departement,
                nom_commune, longitude, latitude
  PEB         : peb_zone, nom_aeroport
  Transport   : arret_plus_proche, mode_transport_proche, reseaux_transport,
                distance_arret_m, nb_arrets_500m, nb_arrets_1000m, nb_arrets_2000m
  DPE         : pct_passoires, pct_bons_dpe, classe_dpe_dominante,
                conso_med_kwh_m2, n_dpe
"""
from __future__ import annotations
import duckdb
import pandas as pd
import numpy as np
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent.parent / "immo_et_bruit.duckdb"

_connection = None


def get_connection():
    global _connection
    if _connection is not None:
        return _connection

    if not DB_PATH.exists():
        print(f"⚠️  Base réelle introuvable ({DB_PATH}) — mode démonstration")
        _connection = _create_mock_db()
    else:
        _connection = duckdb.connect(str(DB_PATH), read_only=True)

    return _connection


def _create_mock_db():
    con = duckdb.connect(":memory:")
    rng = np.random.default_rng(42)
    n = 50_000

    communes = [
        ("35238", "35", "Rennes"),
        ("56260", "56", "Vannes"),
        ("44109", "44", "Nantes"),
        ("29019", "29", "Brest"),
        ("22278", "22", "Saint-Brieuc"),
        ("35047", "35", "Bruz"),
        ("56118", "56", "Lorient"),
        ("29232", "29", "Quimper"),
    ]
    codes, depts, noms = zip(*communes)
    idx = rng.integers(0, len(communes), n)

    types    = rng.choice(["Appartement", "Maison"], n, p=[0.6, 0.4])
    surfaces = rng.integers(20, 200, n).astype(float)
    prix_m2  = rng.normal(3200, 800, n).clip(500, 12000)
    dates    = pd.date_range("2019-01-01", "2024-12-31", periods=n)

    df = pd.DataFrame({
        # DVF core
        "id_mutation":               [f"MUT{i:07d}" for i in range(n)],
        "date_mutation":             dates,
        "annee":                     dates.year.tolist(),
        "nature_mutation":           rng.choice(["Vente", "Vente en l'état futur d'achèvement"], n, p=[0.95, 0.05]).tolist(),
        "type_local":                types.tolist(),
        "surface_reelle_bati":       surfaces.tolist(),
        "nombre_pieces_principales": rng.integers(1, 7, n).tolist(),
        "surface_terrain":           np.where(types == "Maison", rng.integers(100, 2000, n).astype(float), np.nan).tolist(),
        "valeur_fonciere":           (surfaces * prix_m2).round(0).tolist(),
        "prix_m2":                   prix_m2.round(0).tolist(),
        "adresse":                   [f"{int(rng.integers(1,100))} Rue de la Paix" for _ in range(n)],
        "code_commune":              [codes[i] for i in idx],
        "code_departement":          [depts[i] for i in idx],
        "nom_commune":               [noms[i]  for i in idx],
        "latitude":                  rng.uniform(47.2, 48.7, n).tolist(),
        "longitude":                 rng.uniform(-4.5, -1.0, n).tolist(),
        # PEB
        "peb_zone":                  rng.choice(["A", "B", "C", "D", None], n, p=[0.05, 0.10, 0.10, 0.05, 0.70]).tolist(),
        "nom_aeroport":              rng.choice(["Aéroport Nantes Atlantique", "Aéroport Rennes", None], n, p=[0.08, 0.05, 0.87]).tolist(),
        # Transport
        "arret_plus_proche":         [f"Arrêt {int(rng.integers(1, 200))}" for _ in range(n)],
        "mode_transport_proche":     rng.choice(["bus", "tram", "metro", "train"], n, p=[0.6, 0.2, 0.1, 0.1]).tolist(),
        "reseaux_transport":         rng.choice(["STAR", "TAN", "CTRL", "SNCF"], n, p=[0.3, 0.3, 0.2, 0.2]).tolist(),
        "distance_arret_m":          rng.integers(50, 5000, n).astype(float).tolist(),
        "nb_arrets_500m":            rng.integers(0, 10, n).tolist(),
        "nb_arrets_1000m":           rng.integers(0, 25, n).tolist(),
        "nb_arrets_2000m":           rng.integers(0, 60, n).tolist(),
        # DPE
        "pct_passoires":             rng.uniform(0, 0.5, n).round(3).tolist(),
        "pct_bons_dpe":              rng.uniform(0.1, 0.8, n).round(3).tolist(),
        "classe_dpe_dominante":      rng.choice(["A","B","C","D","E","F","G", None], n, p=[0.05,0.10,0.20,0.25,0.20,0.10,0.05,0.05]).tolist(),
        "conso_med_kwh_m2":          rng.uniform(50, 450, n).round(1).tolist(),
        "n_dpe":                     rng.integers(10, 500, n).tolist(),
    })

    con.register("df_mock", df)
    con.execute("CREATE TABLE dvf_enrichi AS SELECT * FROM df_mock")
    con.unregister("df_mock")

    return con
