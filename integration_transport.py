import duckdb
import requests
import zipfile
import shutil
import os
import tempfile
import io
import pandas as pd

# --- Configuration ---
DB_FILE = "immo_et_bruit.duckdb"

# API du Point d'Accès National (retourne la liste complète des datasets)
PAN_API_URL = "https://transport.data.gouv.fr/api/datasets"

# Jeu de données "Arrêts de transport en France" sur transport.data.gouv.fr
# URL directe vérifiée le 29/05/2026 — resource id 81333
ARRETS_CSV_URL = "https://transport.data.gouv.fr/resources/81333/download"

# Types de transport à conserver (laisser [] pour tout garder)
# Valeurs possibles : 'metro', 'bus', 'tram', 'rail', 'ferry', 'funicular'
MODES_TRANSPORT = []

# Limite de datasets GTFS à traiter (None = tous, ex: 5 pour tester)
LIMITE_DATASETS_GTFS = 5


def get_pan_catalogue(con):
    """
    Récupère la liste complète des datasets depuis l'API PAN
    et la stocke dans DuckDB pour référence.
    L'API retourne directement un tableau JSON sans pagination.
    """
    print("\n--- Récupération du catalogue via l'API PAN ---")

    table_exists = con.execute(
        "SELECT count(*) FROM information_schema.tables WHERE table_name = 'transport_catalogue'"
    ).fetchone()[0]

    if table_exists > 0:
        print("1. La table 'transport_catalogue' existe déjà, on passe.")
        return

    print("1. Appel à https://transport.data.gouv.fr/api/datasets ...")
    response = requests.get(PAN_API_URL, timeout=60)
    response.raise_for_status()
    datasets = response.json()  # liste de dicts

    print(f"   -> {len(datasets)} datasets récupérés depuis le PAN.")

    rows = []
    for ds in datasets:
        resources = ds.get("resources", [])

        # Récupère la première URL GTFS disponible
        gtfs_url = next(
            (r["url"] for r in resources
             if r.get("format", "").upper() == "GTFS" and r.get("url") and r.get("is_available", True)),
            None
        )
        # Récupère la première URL GeoJSON disponible
        geojson_url = next(
            (r["url"] for r in resources
             if r.get("format", "").upper() == "GEOJSON" and r.get("url") and r.get("is_available", True)),
            None
        )

        aom = ds.get("aom") or {}
        rows.append({
            "dataset_id":   ds.get("datagouv_id", ""),
            "slug":         ds.get("slug", ""),
            "titre":        ds.get("title", ""),
            "type":         ds.get("type", ""),
            "region":       aom.get("region_name", ""),
            "aom_nom":      aom.get("nom", ""),
            "licence":      ds.get("licence", ""),
            "nb_resources": len(resources),
            "gtfs_url":     gtfs_url,
            "geojson_url":  geojson_url,
            "updated":      ds.get("updated", ""),
        })

    df_catalogue = pd.DataFrame(rows)
    con.execute("CREATE TABLE transport_catalogue AS SELECT * FROM df_catalogue")

    # Résumé par type
    print("   -> Répartition par type de dataset :")
    bilan = con.execute(
        "SELECT type, COUNT(*) AS nb FROM transport_catalogue GROUP BY type ORDER BY nb DESC LIMIT 10"
    ).fetchall()
    for t, nb in bilan:
        print(f"      {(t or 'N/A'):<35} {nb:>5}")

    gtfs_count = con.execute(
        "SELECT COUNT(*) FROM transport_catalogue WHERE gtfs_url IS NOT NULL"
    ).fetchone()[0]
    print(f"   -> {gtfs_count} datasets avec une URL GTFS exploitable.")


def load_arrets_nationaux(con):
    """
    Télécharge le CSV national agrégé des arrêts de transport
    depuis data.gouv.fr et l'intègre dans DuckDB.
    Ce fichier regroupe tous les points d'arrêt issus des GTFS référencés sur le PAN.
    """
    print("\n--- Intégration des arrêts nationaux (CSV agrégé) ---")

    table_exists = con.execute(
        "SELECT count(*) FROM information_schema.tables WHERE table_name = 'arrets_raw'"
    ).fetchone()[0]

    if table_exists > 0:
        print("1. La table 'arrets_raw' existe déjà, on passe l'intégration.")
        return

    print(f"1. Téléchargement du CSV des arrêts depuis :\n   {ARRETS_CSV_URL}")
    temp_dir = tempfile.gettempdir()
    csv_path = os.path.join(temp_dir, "arrets_transport_france.csv")

    with requests.get(ARRETS_CSV_URL, stream=True, timeout=180) as r:
        r.raise_for_status()
        with open(csv_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)

    file_size_mb = os.path.getsize(csv_path) / (1024 * 1024)
    print(f"   -> Fichier téléchargé ({file_size_mb:.1f} Mo)")

    print("2. Intégration dans DuckDB (table 'arrets_raw')...")
    safe_csv_path = csv_path.replace("\\", "/")

    con.execute(f"""
    CREATE TABLE arrets_raw AS
    SELECT * FROM read_csv_auto(
        '{safe_csv_path}',
        header=True,
        ignore_errors=True,
        null_padding=True
    );
    """)

    if os.path.exists(csv_path):
        os.remove(csv_path)

    count = con.execute("SELECT COUNT(*) FROM arrets_raw").fetchone()[0]
    print(f"   -> {count:,} arrêts intégrés dans 'arrets_raw'.")

    # Aperçu des colonnes disponibles
    cols = con.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'arrets_raw'").fetchall()
    print(f"   -> Colonnes : {', '.join(c[0] for c in cols)}")


def load_stops_depuis_gtfs(con):
    """
    Parcourt les datasets GTFS du catalogue PAN, télécharge chaque zip,
    extrait stops.txt et consolide tout dans la table 'stops_gtfs'.
    C'est la source la plus riche : nom, coordonnées, type d'arrêt, accessibilité.
    """
    print("\n--- Intégration des stops depuis les fichiers GTFS ---")

    table_exists = con.execute(
        "SELECT count(*) FROM information_schema.tables WHERE table_name = 'stops_gtfs'"
    ).fetchone()[0]

    if table_exists > 0:
        print("1. La table 'stops_gtfs' existe déjà, on passe.")
        return

    catalogue_exists = con.execute(
        "SELECT count(*) FROM information_schema.tables WHERE table_name = 'transport_catalogue'"
    ).fetchone()[0]

    if not catalogue_exists:
        print("   -> Catalogue absent. Appelez d'abord get_pan_catalogue().")
        return

    df_cat = con.execute("""
        SELECT dataset_id, titre, region, aom_nom, gtfs_url
        FROM transport_catalogue
        WHERE gtfs_url IS NOT NULL
    """).df()

    if LIMITE_DATASETS_GTFS:
        df_cat = df_cat.head(LIMITE_DATASETS_GTFS)

    total = len(df_cat)
    print(f"1. {total} datasets GTFS à traiter (limite={LIMITE_DATASETS_GTFS or 'aucune'})...")

    all_stops = []
    errors = 0

    for idx, row in df_cat.iterrows():
        label = row["aom_nom"] or row["titre"] or row["dataset_id"]
        try:
            resp = requests.get(row["gtfs_url"], timeout=60, stream=True)
            resp.raise_for_status()

            with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
                if "stops.txt" not in z.namelist():
                    print(f"   [{idx+1}/{total}] ⚠ {label} — pas de stops.txt dans le zip")
                    continue
                with z.open("stops.txt") as f:
                    df_stops = pd.read_csv(f, dtype=str, on_bad_lines="skip")
                    df_stops["dataset_id"]  = row["dataset_id"]
                    df_stops["region"]      = row["region"]
                    df_stops["aom_nom"]     = row["aom_nom"]
                    all_stops.append(df_stops)

            print(f"   [{idx+1}/{total}] ✓ {label} ({len(df_stops)} stops)")

        except Exception as e:
            errors += 1
            print(f"   [{idx+1}/{total}] ✗ {label} — {e}")

    if not all_stops:
        print("   -> Aucun stop récupéré.")
        return

    df_all = pd.concat(all_stops, ignore_index=True)

    # Colonnes standard GTFS stops.txt — on garantit leur présence
    for col in ["stop_id", "stop_name", "stop_lat", "stop_lon",
                "location_type", "wheelchair_boarding", "stop_code", "platform_code"]:
        if col not in df_all.columns:
            df_all[col] = None

    print(f"\n2. Consolidation : {len(df_all):,} stops au total ({errors} erreurs sur {total}).")
    con.execute("CREATE TABLE stops_gtfs AS SELECT * FROM df_all")

    # Répartition par région
    print("   -> Top régions :")
    bilan = con.execute("""
        SELECT region, COUNT(*) AS nb_stops
        FROM stops_gtfs
        GROUP BY region
        ORDER BY nb_stops DESC
        LIMIT 10
    """).fetchall()
    for region, nb in bilan:
        print(f"      {(region or 'N/A'):<35} {nb:>10,} stops")


def creer_table_stops_clean(con):
    """
    Crée 'transport_stops_clean' : table finale nettoyée avec coordonnées
    GPS valides, prête pour jointures spatiales avec dvf_raw et peb_raw.
    """
    print("\n--- Création de la table 'transport_stops_clean' ---")

    table_exists = con.execute(
        "SELECT count(*) FROM information_schema.tables WHERE table_name = 'transport_stops_clean'"
    ).fetchone()[0]

    if table_exists > 0:
        print("   La table 'transport_stops_clean' existe déjà, on passe.")
        return

    gtfs_exists = con.execute(
        "SELECT count(*) FROM information_schema.tables WHERE table_name = 'stops_gtfs'"
    ).fetchone()[0]

    if not gtfs_exists:
        print("   -> Table 'stops_gtfs' absente, impossible de créer la vue.")
        return

    con.execute("""
    CREATE TABLE transport_stops_clean AS
    SELECT
        stop_id,
        stop_name,
        TRY_CAST(stop_lat AS DOUBLE) AS latitude,
        TRY_CAST(stop_lon AS DOUBLE) AS longitude,
        location_type,
        wheelchair_boarding,
        dataset_id,
        region,
        aom_nom
    FROM stops_gtfs
    WHERE TRY_CAST(stop_lat AS DOUBLE) IS NOT NULL
      AND TRY_CAST(stop_lon AS DOUBLE) IS NOT NULL
      AND TRY_CAST(stop_lat AS DOUBLE) BETWEEN -90  AND 90
      AND TRY_CAST(stop_lon AS DOUBLE) BETWEEN -180 AND 180
    """)

    count = con.execute("SELECT COUNT(*) FROM transport_stops_clean").fetchone()[0]
    print(f"   -> {count:,} stops avec coordonnées valides dans 'transport_stops_clean'.")


if __name__ == "__main__":
    print("=" * 58)
    print("   Pipeline Transport en Commun  →  DuckDB")
    print("=" * 58)
    print(f"Base de données : {DB_FILE}\n")

    con = duckdb.connect(DB_FILE)

    # Recrée le catalogue avec la bonne colonne 'dataset_id'
    con.execute("DROP TABLE IF EXISTS transport_catalogue")

    # Étape 1 — Catalogue PAN complet
    get_pan_catalogue(con)

    # Étape 2 — CSV national des arrêts (léger, ~quelques Mo)
    load_arrets_nationaux(con)

    # Étape 3 — Stops détaillés depuis chaque GTFS (long si LIMITE_DATASETS_GTFS=None)
    load_stops_depuis_gtfs(con)

    # Étape 4 — Table finale nettoyée
    creer_table_stops_clean(con)

    # Résumé
    print("\n" + "=" * 58)
    print("   RÉSUMÉ DES TABLES DANS LA BASE")
    print("=" * 58)
    tables = con.execute("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'main'
        ORDER BY table_name
    """).fetchall()
    for (t,) in tables:
        count = con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        print(f"   {t:<40} {count:>12,} lignes")

    con.close()
    print("\nPipeline transport terminé avec succès !")