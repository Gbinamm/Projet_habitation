"""
jointure_transport.py
-----------------------------------------------------------------------------
Crée la table finale 'dvf_enrichi' croisant :
  - DVF (toutes les mutations résidentielles déduplyquées et filtrées)
  - PEB (zones de bruit aéroport)
  - Transport tram/métro/train (arrêt le plus proche + densité par rayon)

Pré-requis :
  - integration_des_donnees.py  → dvf_avec_peb (DVF + zone PEB)
  - integration_transport.py    → transport_stops_clean

Optimisation clé : pour la jointure de proximité (chaque transaction × chaque
arrêt), on utilise une bounding box (~5km) avant le calcul de distance.
Sans ça, 100k DVF × 10k stops = 1 milliard de calculs → infaisable.
Avec, on tombe à quelques millions de calculs → quelques secondes.
"""
from __future__ import annotations
import duckdb

DB_FILE = "immo_et_bruit.duckdb"

# Rayons (en mètres) pour compter les arrêts à proximité
RAYONS_M = [500, 1000, 2000]


def check_prerequis(con) -> bool:
    requises = ["dvf_avec_peb", "transport_stops_clean"]
    presentes = {r[0] for r in con.execute("""
        SELECT table_name FROM information_schema.tables
    """).fetchall()}
    manquantes = [t for t in requises if t not in presentes]
    if manquantes:
        print(f"ERREUR : tables manquantes : {manquantes}")
        print("Lance d'abord integration_des_donnees.py et integration_transport.py")
        return False
    return True


def creer_dvf_enrichi(con) -> None:
    """Construit dvf_enrichi (DVF + PEB + indicateurs transport)."""
    print("\n--- Construction de 'dvf_enrichi' ---")

    con.execute("INSTALL spatial; LOAD spatial;")
    con.execute("DROP TABLE IF EXISTS dvf_enrichi;")

    # ------------------------------------------------------------------------
    # Étape 1 : pour chaque transaction, distance à l'arrêt le plus proche
    # ------------------------------------------------------------------------
    # Bounding box ±0.05° latitude (~5.5 km) et ±0.07° longitude (~5 km à la
    # latitude de la France) pour ne calculer ST_Distance que sur les paires
    # candidates raisonnables. Sans la box, on ferait N×M = milliards d'ops.
    print("1. Calcul de l'arrêt tram/métro/train le plus proche...")
    con.execute("""
    CREATE TEMP TABLE _nearest AS
    WITH cand AS (
        SELECT
            d.id_mutation,
            s.stop_name,
            s.modes,
            -- Reprojection Lambert 93 pour avoir une distance en MÈTRES
            ST_Distance(
                ST_Transform(ST_Point(d.longitude, d.latitude),
                             'EPSG:4326', 'EPSG:2154'),
                ST_Transform(ST_Point(s.longitude, s.latitude),
                             'EPSG:4326', 'EPSG:2154')
            ) AS distance_m
        FROM dvf_avec_peb d
        JOIN transport_stops_clean s
          ON s.latitude  BETWEEN d.latitude  - 0.05 AND d.latitude  + 0.05
         AND s.longitude BETWEEN d.longitude - 0.07 AND d.longitude + 0.07
    ),
    ranked AS (
        SELECT *,
               ROW_NUMBER() OVER (PARTITION BY id_mutation
                                  ORDER BY distance_m) AS rk
        FROM cand
    )
    SELECT id_mutation,
           stop_name           AS arret_plus_proche,
           modes               AS mode_arret_plus_proche,
           ROUND(distance_m)   AS distance_arret_m
    FROM ranked WHERE rk = 1;
    """)

    n_proche = con.execute("SELECT COUNT(*) FROM _nearest").fetchone()[0]
    print(f"   -> {n_proche:,} transactions ont un arrêt à <5 km")

    # ------------------------------------------------------------------------
    # Étape 2 : densité d'arrêts dans plusieurs rayons (500m / 1km / 2km)
    # ------------------------------------------------------------------------
    print(f"2. Comptage des arrêts dans les rayons {RAYONS_M} m...")
    rayons_sql = ", ".join(
        f"COUNT(*) FILTER (WHERE distance_m <= {r}) AS nb_arrets_{r}m"
        for r in RAYONS_M
    )
    con.execute(f"""
    CREATE TEMP TABLE _counts AS
    WITH cand AS (
        SELECT
            d.id_mutation,
            ST_Distance(
                ST_Transform(ST_Point(d.longitude, d.latitude),
                             'EPSG:4326', 'EPSG:2154'),
                ST_Transform(ST_Point(s.longitude, s.latitude),
                             'EPSG:4326', 'EPSG:2154')
            ) AS distance_m
        FROM dvf_avec_peb d
        JOIN transport_stops_clean s
          ON s.latitude  BETWEEN d.latitude  - 0.05 AND d.latitude  + 0.05
         AND s.longitude BETWEEN d.longitude - 0.07 AND d.longitude + 0.07
    )
    SELECT id_mutation, {rayons_sql}
    FROM cand GROUP BY id_mutation;
    """)

    # ------------------------------------------------------------------------
    # Étape 3 : table finale
    # ------------------------------------------------------------------------
    print("3. Assemblage final dvf_enrichi...")
    counts_cols = ", ".join(
        f"COALESCE(c.nb_arrets_{r}m, 0) AS nb_arrets_{r}m" for r in RAYONS_M
    )
    con.execute(f"""
    CREATE TABLE dvf_enrichi AS
    SELECT
        d.id_mutation,
        d.date_mutation,
        d.type_local,
        d.surface_reelle_bati,
        d.nombre_pieces_principales,
        d.valeur_fonciere,
        d.prix_m2,
        d.adresse,
        d.code_commune,
        d.nom_commune,
        d.longitude,
        d.latitude,
        d.peb_zone,
        n.arret_plus_proche,
        n.mode_arret_plus_proche,
        n.distance_arret_m,
        {counts_cols}
    FROM dvf_avec_peb d
    LEFT JOIN _nearest n ON d.id_mutation = n.id_mutation
    LEFT JOIN _counts  c ON d.id_mutation = c.id_mutation
    """)

    total = con.execute("SELECT COUNT(*) FROM dvf_enrichi").fetchone()[0]
    print(f"   -> {total:,} lignes dans dvf_enrichi")


def bilan(con) -> None:
    print("\n" + "=" * 60)
    print("    BILAN — dvf_enrichi    ")
    print("=" * 60)

    print("\n• Répartition PEB :")
    print(con.execute("""
        SELECT COALESCE(peb_zone, 'Hors PEB') AS zone,
               COUNT(*) AS n_ventes,
               ROUND(MEDIAN(prix_m2)) AS prix_m2_med
        FROM dvf_enrichi GROUP BY 1 ORDER BY 1
    """).df().to_string(index=False))

    print("\n• Effet 'distance gare/tram' sur le prix médian :")
    print(con.execute("""
        SELECT
            CASE
                WHEN distance_arret_m < 500       THEN '0-500m'
                WHEN distance_arret_m < 1000      THEN '500m-1km'
                WHEN distance_arret_m < 2000      THEN '1-2km'
                WHEN distance_arret_m < 5000      THEN '2-5km'
                ELSE                                   '> 5km / aucun'
            END AS distance_bucket,
            type_local,
            COUNT(*) AS n_ventes,
            ROUND(MEDIAN(prix_m2)) AS prix_m2_med
        FROM dvf_enrichi
        GROUP BY 1, 2 ORDER BY 2,
            CASE distance_bucket
                WHEN '0-500m' THEN 1 WHEN '500m-1km' THEN 2
                WHEN '1-2km' THEN 3 WHEN '2-5km' THEN 4 ELSE 5 END
    """).df().to_string(index=False))


if __name__ == "__main__":
    con = duckdb.connect(DB_FILE)
    if not check_prerequis(con):
        con.close()
        exit(1)
    creer_dvf_enrichi(con)
    bilan(con)
    con.close()
    print("\nTable dvf_enrichi prête.")
