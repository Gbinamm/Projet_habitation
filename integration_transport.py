"""
integration_transport.py
-----------------------------------------------------------------------------
Intégration des arrêts de transport en commun depuis les fichiers GTFS
référencés sur le Point d'Accès National (PAN) transport.data.gouv.fr.

FILTRE : on garde TRAM, MÉTRO, TRAIN et BUS.
  route_type GTFS :
    0 = Tram
    1 = Métro (Subway)
    2 = Rail (TER, TGV, RER, Transilien...)
    3 = Bus               <- CONSERVÉ
    4 = Ferry             <- ignoré
    5 = Cable tram        <- ignoré
    6 = Aerial lift       <- ignoré
    7 = Funicular         <- ignoré

Source de l'info : routes.txt + trips.txt + stop_times.txt + stops.txt dans
chaque archive GTFS. C'est plus lourd que de juste lire stops.txt, mais c'est
la seule façon fiable de filtrer par mode de transport.

Optimisation : on saute entièrement les GTFS qui n'ont AUCUNE route de type
0/1/2/3.
"""
from __future__ import annotations
import duckdb
import requests
import zipfile
import io
import pandas as pd
import sys

# ============================================================================
# Configuration
# ============================================================================
DB_FILE = "immo_et_bruit.duckdb"

# API du Point d'Accès National (catalogue des datasets de transport)
PAN_API_URL = "https://transport.data.gouv.fr/api/datasets"

# Types de transport à conserver — TRAM, METRO, RAIL (= train), BUS
ROUTE_TYPES_VOULUS = {0, 1, 2, 3}

# Limite de datasets GTFS à traiter (None = tous, ex: 20 pour tester)
LIMITE_DATASETS_GTFS = None

# Timeout pour le téléchargement de chaque GTFS (certains sont gros)
GTFS_TIMEOUT_S = 180


# ============================================================================
# 1. Catalogue PAN
# ============================================================================
def get_pan_catalogue(con) -> None:
    """Récupère la liste des datasets transport publiés sur le PAN."""
    print("\n--- Catalogue PAN (transport.data.gouv.fr) ---")

    if _table_exists(con, "transport_catalogue"):
        print("1. La table 'transport_catalogue' existe déjà, on passe.")
        return

    print("1. Appel à l'API PAN...")
    response = requests.get(PAN_API_URL, timeout=60)
    response.raise_for_status()
    datasets = response.json()
    print(f"   -> {len(datasets)} datasets récupérés")

    # On extrait pour chaque dataset l'URL GTFS si elle existe
    rows = []
    for ds in datasets:
        resources = ds.get("resources", [])
        gtfs_url = next(
            (r["url"] for r in resources
             if r.get("format", "").upper() == "GTFS"
             and r.get("url")
             and r.get("is_available", True)),
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
            "gtfs_url":     gtfs_url,
            "updated":      ds.get("updated", ""),
        })

    df = pd.DataFrame(rows)
    con.execute("CREATE TABLE transport_catalogue AS SELECT * FROM df")

    gtfs_count = con.execute(
        "SELECT COUNT(*) FROM transport_catalogue WHERE gtfs_url IS NOT NULL"
    ).fetchone()[0]
    print(f"2. {gtfs_count} datasets ont une URL GTFS exploitable.")


# ============================================================================
# 2. Filtrage GTFS — extraction des stops tram/métro/train/bus
# ============================================================================
def _extraire_stops_filtres(gtfs_bytes: bytes) -> pd.DataFrame | None:
    """Pour un GTFS donné (zip en bytes), retourne uniquement les stops
    desservis par au moins une route de type 0/1/2/3. Retourne None si le GTFS
    ne contient aucune route de ces types (on skip)."""
    with zipfile.ZipFile(io.BytesIO(gtfs_bytes)) as z:
        noms = z.namelist()

        # Pré-check : pas de routes.txt -> GTFS invalide
        if "routes.txt" not in noms:
            return None

        # ----- Étape 1 : routes filtrées par route_type -----
        with z.open("routes.txt") as f:
            routes = pd.read_csv(f, dtype=str)
        routes["route_type"] = pd.to_numeric(routes["route_type"], errors="coerce")
        routes_gardees = routes[routes["route_type"].isin(ROUTE_TYPES_VOULUS)]
        if routes_gardees.empty:
            # Aucun tram/métro/train/bus dans ce réseau -> on skip entièrement
            return None
        route_ids = set(routes_gardees["route_id"])
        route_type_map = dict(zip(routes_gardees["route_id"],
                                  routes_gardees["route_type"]))

        # ----- Étape 2 : trips correspondant à ces routes -----
        if "trips.txt" not in noms:
            return None
        with z.open("trips.txt") as f:
            trips = pd.read_csv(f, dtype=str, usecols=["route_id", "trip_id"])
        trips_gardes = trips[trips["route_id"].isin(route_ids)]
        if trips_gardes.empty:
            return None
        trip_to_route = dict(zip(trips_gardes["trip_id"], trips_gardes["route_id"]))
        trip_ids = set(trip_to_route.keys())

        # ----- Étape 3 : stop_ids desservis par ces trips -----
        # stop_times.txt peut être très gros, on charge juste 2 colonnes
        if "stop_times.txt" not in noms:
            return None
        with z.open("stop_times.txt") as f:
            stop_times = pd.read_csv(f, dtype=str, usecols=["trip_id", "stop_id"])
        stop_times_gardes = stop_times[stop_times["trip_id"].isin(trip_ids)]
        if stop_times_gardes.empty:
            return None

        # On garde le mapping stop_id -> ensemble des route_types desservis
        stop_times_gardes = stop_times_gardes.merge(
            pd.Series(trip_to_route, name="route_id").reset_index().rename(
                columns={"index": "trip_id"}),
            on="trip_id", how="left"
        )
        stop_times_gardes["route_type"] = stop_times_gardes["route_id"].map(route_type_map)
        stop_modes = stop_times_gardes.groupby("stop_id")["route_type"].apply(
            lambda s: ",".join(sorted({str(int(x)) for x in s if pd.notna(x)}))
        ).to_dict()
        stop_ids = set(stop_modes.keys())

        # ----- Étape 4 : stops avec coordonnées + parent stations -----
        if "stops.txt" not in noms:
            return None
        with z.open("stops.txt") as f:
            stops = pd.read_csv(f, dtype=str)

        stops_gardes = stops[stops["stop_id"].isin(stop_ids)].copy()

        # On rajoute les parent stations (gare centrale qui regroupe plusieurs quais)
        if "parent_station" in stops_gardes.columns:
            parent_ids = set(stops_gardes["parent_station"].dropna()) - {""}
            parents = stops[stops["stop_id"].isin(parent_ids)]
            stops_gardes = pd.concat([stops_gardes, parents], ignore_index=True)
            stops_gardes = stops_gardes.drop_duplicates("stop_id")

        # On rattache le type de transport
        stops_gardes["route_types"] = stops_gardes["stop_id"].map(stop_modes)

        return stops_gardes


def load_stops_filtres(con) -> None:
    """Boucle sur les GTFS du catalogue, garde uniquement les stops
    tram/métro/train/bus et consolide dans 'transport_stops_raw'."""
    print("\n--- Extraction des stops tram/métro/train/bus depuis les GTFS ---")

    if _table_exists(con, "transport_stops_raw"):
        print("1. La table 'transport_stops_raw' existe déjà, on passe.")
        return

    df_cat = con.execute("""
        SELECT dataset_id, titre, region, aom_nom, gtfs_url
        FROM transport_catalogue
        WHERE gtfs_url IS NOT NULL
    """).df()

    if LIMITE_DATASETS_GTFS:
        df_cat = df_cat.head(LIMITE_DATASETS_GTFS)

    total = len(df_cat)
    print(f"1. {total} GTFS à examiner...")

    all_stops = []
    n_keep, n_skip, n_error = 0, 0, 0

    for idx, row in df_cat.iterrows():
        label = row["aom_nom"] or row["titre"] or row["dataset_id"]
        label = label[:50]
        try:
            resp = requests.get(row["gtfs_url"], timeout=GTFS_TIMEOUT_S)
            resp.raise_for_status()

            stops_df = _extraire_stops_filtres(resp.content)
            if stops_df is None:
                n_skip += 1
                # On affiche seulement 1 ligne sur 20 pour pas spammer
                if idx % 20 == 0:
                    print(f"   [{idx+1}/{total}] skip  {label} (pas de rail/métro/tram/bus)")
                continue

            stops_df["dataset_id"] = row["dataset_id"]
            stops_df["region"]     = row["region"]
            stops_df["aom_nom"]    = row["aom_nom"]
            all_stops.append(stops_df)
            n_keep += 1
            print(f"   [{idx+1}/{total}] ✓ {label} ({len(stops_df)} stops)")

        except Exception as e:
            n_error += 1
            print(f"   [{idx+1}/{total}] ✗ {label} — {type(e).__name__}")

    if not all_stops:
        print("   -> Aucun stop tram/métro/train/bus trouvé.")
        return

    df_all = pd.concat(all_stops, ignore_index=True)

    # Colonnes standard à garantir
    for col in ["stop_id", "stop_name", "stop_lat", "stop_lon",
                "location_type", "parent_station", "route_types"]:
        if col not in df_all.columns:
            df_all[col] = None

    print(f"\n2. Bilan : {n_keep} GTFS conservés, {n_skip} skipped (sans mode valide), "
          f"{n_error} erreurs")
    print(f"   {len(df_all):,} stops bruts")

    con.execute("CREATE TABLE transport_stops_raw AS SELECT * FROM df_all")


# ============================================================================
# 3. Stops nettoyés et dédoublonnés
# ============================================================================
def creer_stops_clean(con) -> None:
    """Crée 'transport_stops_clean' :
      - filtre les coordonnées valides
      - dédoublonne (un même stop peut apparaître dans plusieurs datasets)
      - traduit route_type en libellé lisible
    """
    print("\n--- Création de 'transport_stops_clean' ---")

    if _table_exists(con, "transport_stops_clean"):
        print("   La table existe déjà, on passe.")
        return

    if not _table_exists(con, "transport_stops_raw"):
        print("   -> transport_stops_raw absente, impossible de continuer.")
        return

    con.execute("""
    CREATE TABLE transport_stops_clean AS
    WITH base AS (
        SELECT
            stop_id,
            stop_name,
            TRY_CAST(stop_lat AS DOUBLE) AS latitude,
            TRY_CAST(stop_lon AS DOUBLE) AS longitude,
            route_types,
            -- libellé lisible du ou des modes desservis
            CASE
                WHEN route_types LIKE '%2%' THEN 'Train'
                WHEN route_types LIKE '%1%' THEN 'Métro'
                WHEN route_types LIKE '%0%' THEN 'Tram'
                WHEN route_types LIKE '%3%' THEN 'Bus'
                ELSE 'Autre'
            END AS mode_principal,
            location_type,
            dataset_id,
            region,
            aom_nom
        FROM transport_stops_raw
        WHERE TRY_CAST(stop_lat AS DOUBLE) IS NOT NULL
          AND TRY_CAST(stop_lon AS DOUBLE) IS NOT NULL
          AND TRY_CAST(stop_lat AS DOUBLE) BETWEEN 41 AND 52
          AND TRY_CAST(stop_lon AS DOUBLE) BETWEEN -5 AND 10
    )
    -- Dédoublonnage : un même stop peut apparaître dans plusieurs datasets.
    -- On groupe par (nom, latitude arrondie au 4ème chiffre, longitude idem)
    -- pour identifier les stops identiques entre datasets.
    SELECT
        ANY_VALUE(stop_id)        AS stop_id,
        stop_name,
        ROUND(latitude,  4)       AS latitude,
        ROUND(longitude, 4)       AS longitude,
        STRING_AGG(DISTINCT mode_principal, ', ') AS modes,
        STRING_AGG(DISTINCT aom_nom, ', ')        AS reseaux
    FROM base
    GROUP BY stop_name, ROUND(latitude, 4), ROUND(longitude, 4)
    """)

    bilan = con.execute("""
        SELECT modes, COUNT(*) AS n
        FROM transport_stops_clean
        GROUP BY modes ORDER BY n DESC
    """).fetchall()
    print("   Répartition par mode :")
    for modes, n in bilan:
        print(f"      {modes:<30s} {n:>6,} stops")


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
    print("  Pipeline Transport (tram/métro/train/bus) -> DuckDB")
    print("=" * 60)

    # Ajout du gestionnaire d'erreur DBeaver / Lock
    try:
        con = duckdb.connect(DB_FILE)
    except duckdb.IOException as e:
        if "utilisé par un autre processus" in str(e) or "already open" in str(e):
            print("\n❌ ERREUR : La base de données est actuellement bloquée.")
            print("💡 SOLUTION : Retourne dans DBeaver, fais un clic droit sur ta base et clique sur 'Déconnecter'. Relance ensuite le script.")
            sys.exit(1)
        else:
            raise e
            
    get_pan_catalogue(con)
    load_stops_filtres(con)
    creer_stops_clean(con)
    con.close()

    print("\nPipeline transport terminé.")