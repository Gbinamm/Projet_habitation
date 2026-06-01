"""
integration_des_donnees.py
-----------------------------------------------------------------------------
Intégration DVF + PEB dans la base DuckDB.
 
Changements par rapport à la version précédente :
  - Source DVF : on passe sur la DVF GÉOLOCALISÉE d'Etalab.
    Avantages : longitude/latitude déjà incluses (plus besoin de la BAN !),
    encodage UTF-8 propre, types corrects, 1 fichier par département par année.
    → On peut traiter TOUTES les adresses, pas seulement 1000.
  - Filtrage configurable : 44 seul, Pays de la Loire, ou France entière
  - Déduplication par id_mutation (DVF a plusieurs lignes par vente à cause
    des parcelles cadastrales) — on garde une ligne par mutation
  - Filtres qualité documentés (prix > 1000€, surface > 9m², etc.)
  - PEB : ajout du LEFT JOIN pour garder les biens hors zone (sinon on perd
    99% de l'échantillon dans toute analyse comparative)
  - Téléchargement robuste aux 404 (années non disponibles ignorées)
  - Option --reset pour vider la base avant rechargement
"""
from __future__ import annotations
import argparse
import duckdb
import requests
import json
import os
import tempfile
from pathlib import Path
 
# ============================================================================
# Configuration
# ============================================================================
DB_FILE = "immo_et_bruit.duckdb"
 
# ----------------------------------------------------------------------------
# PÉRIMÈTRE GÉOGRAPHIQUE — décommente le périmètre voulu
# ----------------------------------------------------------------------------
 
# Option 1 : Loire-Atlantique uniquement (rapide, ~2 min, ~60k mutations)
# DEPARTEMENTS = ["44"]
 
# Option 2 : Pays de la Loire (~10 min, ~300k mutations)
# DEPARTEMENTS = ["44", "49", "53", "72", "85"]
 
# Option 3 : Grand Ouest (~25 min, ~700k mutations)
# DEPARTEMENTS = ["44", "49", "53", "72", "85",
#                 "35", "22", "29", "56",
#                 "14", "50", "61", "76", "27"]
 
# Option 4 : France entière (~1-2h, ~5M mutations, ~3 Go disque)
DEPARTEMENTS = (
    [str(i).zfill(2) for i in range(1, 20)]   # 01 → 19
    + ["2A", "2B"]                              # Corse
    + [str(i) for i in range(21, 96)]           # 21 → 95
)
 
# ----------------------------------------------------------------------------
 
# Années à charger — fenêtre glissante de 5 ans sur Etalab
ANNEES = [2021, 2022, 2023, 2024, 2025]
 
# URL DVF géolocalisée Etalab
DVF_URL_TEMPLATE = (
    "https://files.data.gouv.fr/geo-dvf/latest/csv/{year}/departements/{dept}.csv.gz"
)
 
# URLs zones PEB DGAC
PEB_ZONE_URLS = {
    "B": "https://www.data.gouv.fr/api/1/datasets/r/ea77a7b5-0298-49ed-b3ff-caae3b15d022",
    "C": "https://www.data.gouv.fr/api/1/datasets/r/a7f30166-3319-428e-a08e-700e3c0a3755",
    "D": "https://www.data.gouv.fr/api/1/datasets/r/78087339-b725-4825-a9f7-8d4ef92b2963",
}
 
 
# ============================================================================
# 0. Reset — vide la base avant rechargement
# ============================================================================
def reset_base(con) -> None:
    """Supprime toutes les tables DVF pour repartir de zéro.
    Utile quand on change de périmètre géographique."""
    print("\n--- Reset de la base ---")
    for t in ["dvf_avec_peb", "dvf_raw", "peb_raw"]:
        con.execute(f"DROP TABLE IF EXISTS {t}")
        print(f"   -> Table '{t}' supprimée")
    print("   Base vidée. Prêt pour un nouveau chargement.\n")
 
 
# ============================================================================
# 1. DVF — téléchargement + chargement
# ============================================================================
def load_dvf(con, departements: list[str], annees: list[int]) -> None:
    """Télécharge et charge la DVF géolocalisée. Dédoublonne par id_mutation."""
    print("\n--- Intégration DVF géolocalisée ---")
    print(f"    Périmètre : {len(departements)} département(s)")
 
    if _table_exists(con, "dvf_raw"):
        print("1. La table 'dvf_raw' existe déjà, on passe l'intégration DVF.")
        return
 
    raw_dir = Path("raw_dvf")
    raw_dir.mkdir(exist_ok=True)
 
    # ------------------------------------------------------------------------
    # Étape 1 : téléchargement
    # ------------------------------------------------------------------------
    fichiers = []
    total_combos = len(departements) * len(annees)
    idx = 0
 
    for dept in departements:
        for year in annees:
            idx += 1
            url = DVF_URL_TEMPLATE.format(year=year, dept=dept)
            dest = raw_dir / f"dvf_{dept}_{year}.csv.gz"
 
            if dest.exists() and dest.stat().st_size > 0:
                print(f"   [{idx}/{total_combos}] [cache] {dest.name}")
                fichiers.append(dest)
                continue
 
            print(f"   [{idx}/{total_combos}] Téléchargement {dest.name}...")
            try:
                with requests.get(url, stream=True, timeout=120) as r:
                    r.raise_for_status()
                    with open(dest, "wb") as f:
                        for chunk in r.iter_content(8192):
                            f.write(chunk)
                print(f"     -> {dest.stat().st_size / 1e6:.1f} Mo")
                fichiers.append(dest)
            except requests.HTTPError as e:
                if e.response.status_code == 404:
                    print(f"     -> 404 ignoré (non disponible sur Etalab)")
                    dest.unlink(missing_ok=True)
                    continue
                raise
 
    if not fichiers:
        print("ERREUR : aucun fichier DVF n'a pu être téléchargé.")
        return
 
    print(f"\n   {len(fichiers)} fichiers téléchargés.")
 
    # ------------------------------------------------------------------------
    # Étape 2 : chargement DuckDB avec dédoublonnage
    # ------------------------------------------------------------------------
    print("2. Création de la table 'dvf_raw' avec dédoublonnage...")
    glob_pattern = str(raw_dir / "dvf_*.csv.gz")
 
    con.execute(f"""
    CREATE TABLE dvf_raw AS
    WITH brut AS (
        SELECT *
        FROM read_csv_auto(
            '{glob_pattern}',
            union_by_name=true,
            ignore_errors=true
        )
    ),
    filtre AS (
        SELECT *
        FROM brut
        WHERE nature_mutation IN ('Vente', 'Vente en l''état futur')
          AND type_local       IN ('Maison', 'Appartement')
          AND valeur_fonciere  >= 1000
          AND surface_reelle_bati BETWEEN 9 AND 1000
          AND longitude IS NOT NULL
          AND latitude  IS NOT NULL
    )
    SELECT
        id_mutation,
        ANY_VALUE(date_mutation)                          AS date_mutation,
        ANY_VALUE(nature_mutation)                        AS nature_mutation,
        MAX(valeur_fonciere)                              AS valeur_fonciere,
        ANY_VALUE(type_local)                             AS type_local,
        SUM(surface_reelle_bati)                          AS surface_reelle_bati,
        MAX(nombre_pieces_principales)                    AS nombre_pieces_principales,
        SUM(COALESCE(surface_terrain, 0))                 AS surface_terrain,
        ANY_VALUE(code_commune)                           AS code_commune,
        ANY_VALUE(nom_commune)                            AS nom_commune,
        ANY_VALUE(code_departement)                       AS code_departement,
        ANY_VALUE(adresse_numero) || ' ' ||
            COALESCE(ANY_VALUE(adresse_suffixe), '') || ' ' ||
            COALESCE(ANY_VALUE(adresse_nom_voie), '')     AS adresse,
        AVG(longitude)                                    AS longitude,
        AVG(latitude)                                     AS latitude,
        ROUND(MAX(valeur_fonciere) / SUM(surface_reelle_bati), 0) AS prix_m2
    FROM filtre
    GROUP BY id_mutation
    """)
 
    # ------------------------------------------------------------------------
    # Étape 3 : filtre outliers P1-P99
    # ------------------------------------------------------------------------
    print("3. Filtrage des outliers de prix/m² (P1-P99 par type de bien)...")
    con.execute("""
    CREATE OR REPLACE TABLE dvf_raw AS
    WITH bornes AS (
        SELECT
            type_local,
            QUANTILE_CONT(prix_m2, 0.01) AS p1,
            QUANTILE_CONT(prix_m2, 0.99) AS p99
        FROM dvf_raw
        GROUP BY type_local
    )
    SELECT d.*
    FROM dvf_raw d
    JOIN bornes b USING (type_local)
    WHERE d.prix_m2 BETWEEN b.p1 AND b.p99
    """)
 
    total = con.execute("SELECT COUNT(*) FROM dvf_raw").fetchone()[0]
    print(f"\n   -> {total:,} mutations résidentielles dans 'dvf_raw'")
 
    for row in con.execute("""
        SELECT code_departement, type_local, COUNT(*) AS n,
               ROUND(MEDIAN(prix_m2)) AS med
        FROM dvf_raw
        GROUP BY code_departement, type_local
        ORDER BY code_departement, type_local
    """).fetchall():
        print(f"      dept {row[0]}  {row[1]:<12s} {row[2]:>7,} ventes"
              f"  | médiane {row[3]:,.0f} €/m²")
 
 
# ============================================================================
# 2. PEB — zones de bruit DGAC
# ============================================================================
def load_peb(con) -> None:
    """Télécharge et fusionne les zones PEB B/C/D dans une table spatiale."""
    print("\n--- Intégration PEB (zones de bruit aéroport) ---")
 
    if _table_exists(con, "peb_raw"):
        print("1. La table 'peb_raw' existe déjà, on passe.")
        return
 
    print("1. Activation de l'extension spatiale...")
    con.execute("INSTALL spatial; LOAD spatial;")
 
    all_features = []
    for zone, url in PEB_ZONE_URLS.items():
        print(f"2. Téléchargement zone {zone}...")
        response = requests.get(url, timeout=60)
        response.raise_for_status()
        features = response.json().get("features", [])
        for feature in features:
            feature.setdefault("properties", {})
            feature["properties"]["peb_zone"] = zone
        all_features.extend(features)
        print(f"   -> Zone {zone} : {len(features)} polygones")
 
    with tempfile.NamedTemporaryFile(suffix=".geojson", mode="w",
                                     delete=False, encoding="utf-8") as f:
        json.dump({"type": "FeatureCollection", "features": all_features}, f)
        temp_path = f.name
 
    safe_path = temp_path.replace("\\", "/")
    con.execute(f"CREATE TABLE peb_raw AS SELECT * FROM ST_Read('{safe_path}')")
    os.unlink(temp_path)
 
    for zone, n in con.execute("""
        SELECT peb_zone, COUNT(*) FROM peb_raw
        GROUP BY peb_zone ORDER BY peb_zone
    """).fetchall():
        print(f"      Zone {zone} : {n} polygones")
 
 
# ============================================================================
# 3. Jointure DVF ↔ PEB
# ============================================================================
def lier_dvf_peb(con) -> None:
    """Crée 'dvf_avec_peb' : DVF + colonne peb_zone (NULL si hors zone)."""
    print("\n--- Jointure spatiale DVF ↔ PEB ---")
 
    cols = {r[0] for r in con.execute("DESCRIBE dvf_raw").fetchall()}
    if "longitude" not in cols or "id_mutation" not in cols:
        print("ERREUR : 'dvf_raw' n'a pas le bon schéma.")
        print("Lance : python integration_des_donnees.py --reset")
        return
 
    con.execute("INSTALL spatial; LOAD spatial;")
    con.execute("DROP TABLE IF EXISTS dvf_avec_peb;")
 
    con.execute("""
    CREATE TABLE dvf_avec_peb AS
    SELECT d.*, p.peb_zone
    FROM dvf_raw d
    LEFT JOIN peb_raw p
      ON ST_Contains(p.geom, ST_Point(d.longitude, d.latitude))
    """)
 
    for zone, n in con.execute("""
        SELECT COALESCE(peb_zone, 'Hors PEB') AS zone, COUNT(*) AS n
        FROM dvf_avec_peb GROUP BY 1 ORDER BY 1
    """).fetchall():
        print(f"      {zone:<10s} {n:>7,} biens")
 
 
# ============================================================================
# Helpers
# ============================================================================
def _table_exists(con, name: str) -> bool:
    return con.execute(f"""
        SELECT COUNT(*) FROM information_schema.tables
        WHERE table_name = '{name}'
    """).fetchone()[0] > 0
 
 
# ============================================================================
# Main
# ============================================================================
if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--reset",
        action="store_true",
        help="Vide la base avant de recharger (obligatoire si tu changes de périmètre)"
    )
    args = ap.parse_args()
 
    print("=" * 60)
    print("  Pipeline DVF + PEB → DuckDB")
    print("=" * 60)
    print(f"Base          : {DB_FILE}")
    print(f"Départements  : {len(DEPARTEMENTS)} département(s)")
    print(f"Années        : {ANNEES}")
 
    con = duckdb.connect(DB_FILE)
 
    if args.reset:
        reset_base(con)
 
    load_dvf(con, DEPARTEMENTS, ANNEES)
    load_peb(con)
    lier_dvf_peb(con)
    con.close()
 
    print("\nPipeline DVF + PEB terminé.")