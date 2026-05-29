"""
integration_des_donnees.py
-----------------------------------------------------------------------------
Intégration DVF + PEB dans la base DuckDB.

Changements par rapport à la version précédente :
  - Source DVF : on passe sur la DVF GÉOLOCALISÉE d'Etalab.
    Avantages : longitude/latitude déjà incluses (plus besoin de la BAN !),
    encodage UTF-8 propre, types corrects, 1 fichier par département par année.
    → On peut traiter TOUTES les adresses, pas seulement 1000.
  - Filtrage Loire-Atlantique (dépt 44) configurable
  - Déduplication par id_mutation (DVF a plusieurs lignes par vente à cause
    des parcelles cadastrales) — on garde une ligne par mutation
  - Filtres qualité documentés (prix > 1000€, surface > 9m², etc.)
  - PEB : ajout du LEFT JOIN pour garder les biens hors zone (sinon on perd
    99% de l'échantillon dans toute analyse comparative)
  - Téléchargement robuste aux 404 (années non disponibles ignorées)
"""
from __future__ import annotations
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

# Périmètre : codes département à traiter (Loire-Atlantique = 44)
DEPARTEMENTS = ["44"]

# Années à charger. La DVF Etalab garde une fenêtre glissante de 5 ans —
# au 29 mai 2026, seules 2021 → 2025 sont disponibles.
# Le 404 est de toute façon géré silencieusement, donc tu peux laisser
# 2020 ici si tu veux : il sera ignoré poliment.
ANNEES = [2021, 2022, 2023, 2024, 2025]

# URL DVF géolocalisée Etalab — 1 fichier .csv.gz par année par département
DVF_URL_TEMPLATE = (
    "https://files.data.gouv.fr/geo-dvf/latest/csv/{year}/departements/{dept}.csv.gz"
)

# URLs des zones PEB de la DGAC (Plan d'Exposition au Bruit)
# Note : zone A non incluse ici car pas dans le jeu de données initial.
# Si tu trouves l'URL de zone A sur data.gouv.fr, ajoute-la simplement.
PEB_ZONE_URLS = {
    "B": "https://www.data.gouv.fr/api/1/datasets/r/ea77a7b5-0298-49ed-b3ff-caae3b15d022",
    "C": "https://www.data.gouv.fr/api/1/datasets/r/a7f30166-3319-428e-a08e-700e3c0a3755",
    "D": "https://www.data.gouv.fr/api/1/datasets/r/78087339-b725-4825-a9f7-8d4ef92b2963",
}


# ============================================================================
# 1. DVF — téléchargement + chargement
# ============================================================================
def load_dvf(con, departements: list[str], annees: list[int]) -> None:
    """Télécharge et charge la DVF géolocalisée pour les départements et années
    demandés. Dédoublonne par id_mutation."""
    print("\n--- Intégration DVF géolocalisée ---")

    if _table_exists(con, "dvf_raw"):
        print("1. La table 'dvf_raw' existe déjà, on passe l'intégration DVF.")
        return

    raw_dir = Path("raw_dvf")
    raw_dir.mkdir(exist_ok=True)

    # ------------------------------------------------------------------------
    # Étape 1 : téléchargement de chaque (année, département)
    # ------------------------------------------------------------------------
    fichiers = []
    for dept in departements:
        for year in annees:
            url = DVF_URL_TEMPLATE.format(year=year, dept=dept)
            dest = raw_dir / f"dvf_{dept}_{year}.csv.gz"

            if dest.exists() and dest.stat().st_size > 0:
                print(f"   [cache] {dest.name}")
                fichiers.append(dest)
                continue

            print(f"   Téléchargement {dest.name}...")
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
                    # Année plus disponible sur Etalab (fenêtre glissante de 5 ans)
                    print(f"     -> 404 ignoré (année non disponible sur Etalab)")
                    dest.unlink(missing_ok=True)
                    continue
                raise  # autres erreurs HTTP : on relève

    if not fichiers:
        print("ERREUR : aucun fichier DVF n'a pu être téléchargé.")
        return

    # ------------------------------------------------------------------------
    # Étape 2 : chargement DuckDB avec dédoublonnage par id_mutation
    # ------------------------------------------------------------------------
    # DVF a plusieurs lignes par mutation (une par parcelle). On agrège pour
    # avoir 1 ligne = 1 vente. On garde aussi tous les filtres qualité ici
    # pour ne pas se retrouver avec des valeurs absurdes plus tard.
    print("2. Création de la table 'dvf_raw' avec dédoublonnage...")
    glob_pattern = str(raw_dir / "dvf_*.csv.gz")

    con.execute(f"""
    CREATE TABLE dvf_raw AS
    WITH brut AS (
        SELECT *
        FROM read_csv_auto('{glob_pattern}', union_by_name=true, ignore_errors=true)
    ),
    -- Filtres qualité explicites (documentés et défendables) :
    --   - Ventes uniquement (pas adjudications, échanges, etc.)
    --   - Résidentiel uniquement (Maison ou Appartement)
    --   - Valeur foncière >= 1000€ (exclut les 1€ familiaux)
    --   - Surface bâtie cohérente (9 à 1000 m²)
    --   - Coordonnées GPS présentes
    filtre AS (
        SELECT *
        FROM brut
        WHERE nature_mutation IN ('Vente', 'Vente en l''état futur')
          AND type_local IN ('Maison', 'Appartement')
          AND valeur_fonciere >= 1000
          AND surface_reelle_bati BETWEEN 9 AND 1000
          AND longitude IS NOT NULL
          AND latitude IS NOT NULL
    )
    -- Dédoublonnage : 1 ligne par mutation (somme des surfaces des parcelles,
    -- max de la valeur foncière, moyenne des coordonnées GPS)
    SELECT
        id_mutation,
        ANY_VALUE(date_mutation)                 AS date_mutation,
        ANY_VALUE(nature_mutation)               AS nature_mutation,
        MAX(valeur_fonciere)                     AS valeur_fonciere,
        ANY_VALUE(type_local)                    AS type_local,
        SUM(surface_reelle_bati)                 AS surface_reelle_bati,
        MAX(nombre_pieces_principales)           AS nombre_pieces_principales,
        SUM(COALESCE(surface_terrain, 0))        AS surface_terrain,
        ANY_VALUE(code_commune)                  AS code_commune,
        ANY_VALUE(nom_commune)                   AS nom_commune,
        ANY_VALUE(code_departement)              AS code_departement,
        ANY_VALUE(adresse_numero) || ' ' ||
            COALESCE(ANY_VALUE(adresse_suffixe), '') || ' ' ||
            COALESCE(ANY_VALUE(adresse_nom_voie), '') AS adresse,
        AVG(longitude)                           AS longitude,
        AVG(latitude)                            AS latitude,
        -- Prix au m² calculé directement
        ROUND(MAX(valeur_fonciere) / SUM(surface_reelle_bati), 0) AS prix_m2
    FROM filtre
    GROUP BY id_mutation
    """)

    # ------------------------------------------------------------------------
    # Étape 3 : filtre outliers (prix au m² P1-P99 par type de bien)
    # ------------------------------------------------------------------------
    # On retire les 1% extrêmes par type (Maison/Appartement) pour éviter que
    # les valeurs aberrantes biaisent les analyses statistiques.
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

    # ------------------------------------------------------------------------
    # Résumé
    # ------------------------------------------------------------------------
    total = con.execute("SELECT COUNT(*) FROM dvf_raw").fetchone()[0]
    print(f"\n   -> {total:,} mutations résidentielles dédoublonnées dans 'dvf_raw'")

    repartition = con.execute("""
        SELECT
            code_departement,
            type_local,
            COUNT(*) AS n,
            ROUND(MEDIAN(prix_m2)) AS prix_m2_median
        FROM dvf_raw
        GROUP BY code_departement, type_local
        ORDER BY code_departement, type_local
    """).fetchall()
    for dept, type_l, n, prix in repartition:
        print(f"      dept {dept}  {type_l:<12s} {n:>7,} ventes  | médiane {prix:,.0f} €/m²")


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

    # Téléchargement et fusion des zones B/C/D en un seul GeoJSON
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

    # Écriture GeoJSON temporaire puis lecture spatiale
    with tempfile.NamedTemporaryFile(suffix=".geojson", mode="w",
                                     delete=False, encoding="utf-8") as f:
        json.dump({"type": "FeatureCollection", "features": all_features}, f)
        temp_path = f.name

    safe_path = temp_path.replace("\\", "/")
    con.execute(f"CREATE TABLE peb_raw AS SELECT * FROM ST_Read('{safe_path}')")
    os.unlink(temp_path)

    bilan = con.execute("""
        SELECT peb_zone, COUNT(*) FROM peb_raw GROUP BY peb_zone ORDER BY peb_zone
    """).fetchall()
    print("3. Bilan PEB :")
    for zone, n in bilan:
        print(f"      Zone {zone} : {n} polygones")


# ============================================================================
# 3. Jointure DVF ↔ PEB
# ============================================================================
def lier_dvf_peb(con) -> None:
    """Crée 'dvf_avec_peb' : DVF + colonne peb_zone (NULL si hors zone).
    LEFT JOIN pour GARDER les biens hors PEB (essentiel pour comparer)."""
    print("\n--- Jointure spatiale DVF ↔ PEB ---")

    # Garde-fou : vérifie que dvf_raw a bien le nouveau schéma
    cols = {r[0] for r in con.execute("DESCRIBE dvf_raw").fetchall()}
    if "longitude" not in cols or "id_mutation" not in cols:
        print("ERREUR : 'dvf_raw' n'a pas le bon schéma (ancien script DGFiP brut ?).")
        print("Supprime la base et relance : Remove-Item immo_et_bruit.duckdb")
        return

    con.execute("INSTALL spatial; LOAD spatial;")
    con.execute("DROP TABLE IF EXISTS dvf_avec_peb;")

    con.execute("""
    CREATE TABLE dvf_avec_peb AS
    SELECT
        d.*,
        p.peb_zone
    FROM dvf_raw d
    LEFT JOIN peb_raw p
      ON ST_Contains(p.geom, ST_Point(d.longitude, d.latitude))
    """)

    bilan = con.execute("""
        SELECT COALESCE(peb_zone, 'Hors PEB') AS zone, COUNT(*) AS n
        FROM dvf_avec_peb GROUP BY 1 ORDER BY 1
    """).fetchall()
    print("   Bilan jointure DVF ↔ PEB :")
    for zone, n in bilan:
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
    print("=" * 60)
    print("  Pipeline DVF + PEB → DuckDB")
    print("=" * 60)
    print(f"Base         : {DB_FILE}")
    print(f"Départements : {DEPARTEMENTS}")
    print(f"Années       : {ANNEES}")

    con = duckdb.connect(DB_FILE)
    load_dvf(con, DEPARTEMENTS, ANNEES)
    load_peb(con)
    lier_dvf_peb(con)
    con.close()

    print("\nPipeline DVF + PEB terminé.")
