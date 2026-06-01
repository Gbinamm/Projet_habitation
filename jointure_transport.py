"""
jointure_transport.py
-----------------------------------------------------------------------------
Crée la table finale 'dvf_enrichi' croisant :
  - DVF + PEB          (dvf_avec_peb)
  - Transport          (transport_stops_clean)
  - DPE                (dpe_commune)

Optimisations France entière (~5M mutations) :
  1. Traitement par batch de départements pour contrôler la RAM
  2. Bounding box ±0.05°/±0.07° avant ST_Distance (réduit 5M×100k → gérable)
  3. Jointure DPE par commune (pas par DPE individuel) → rapide
  4. Reprojection Lambert 93 pour distances en mètres
"""
from __future__ import annotations
import duckdb

DB_FILE  = "immo_et_bruit.duckdb"
RAYONS_M = [500, 1000, 2000]

# Nombre de départements traités en même temps pour la jointure spatiale.
# Réduis à 5 si tu manques de RAM (8 Go), garde 10 pour 16 Go.
BATCH_SIZE = 10


# ============================================================================
# Vérification des prérequis
# ============================================================================
def check_prerequis(con) -> bool:
    requises = ["dvf_avec_peb", "transport_stops_clean"]
    presentes = {r[0] for r in con.execute(
        "SELECT table_name FROM information_schema.tables"
    ).fetchall()}
    manquantes = [t for t in requises if t not in presentes]
    if manquantes:
        print(f"ERREUR : tables manquantes → {manquantes}")
        print("Lance d'abord integration_des_donnees.py et integration_transport.py")
        return False

    # DPE optionnel — on prévient mais on continue sans
    if "dpe_commune" not in presentes:
        print("INFO : 'dpe_commune' absente — enrichissement DPE ignoré.")
        print("       Lance integration_dpe.py pour l'ajouter.")
    return True


def _table_exists(con, name: str) -> bool:
    return con.execute(f"""
        SELECT COUNT(*) FROM information_schema.tables
        WHERE table_name = '{name}'
    """).fetchone()[0] > 0


# ============================================================================
# Étape 1 : Transport (arrêt le plus proche + densité)
# Pour la France entière on traite par batch de départements.
# ============================================================================
def _creer_transport_enrichi(con) -> None:
    """Calcule pour chaque mutation :
      - l'arrêt le plus proche (nom + mode + distance)
      - le nombre d'arrêts dans 500m / 1km / 2km
    Traite par batch de départements pour contrôler la RAM.
    Résultat dans la table TEMP _transport.
    """
    print("\n1. Enrichissement transport (arrêt proche + densité)...")

    con.execute("INSTALL spatial; LOAD spatial;")

    # Récupère la liste des départements présents dans dvf_avec_peb
    depts = [r[0] for r in con.execute("""
        SELECT DISTINCT code_departement
        FROM dvf_avec_peb
        WHERE code_departement IS NOT NULL
        ORDER BY code_departement
    """).fetchall()]

    print(f"   {len(depts)} département(s) à traiter en batches de {BATCH_SIZE}...")

    # Crée la table résultat TEMP vide
    con.execute("""
    CREATE OR REPLACE TEMP TABLE _transport (
        id_mutation          VARCHAR,
        arret_plus_proche    VARCHAR,
        mode_arret           VARCHAR,
        distance_arret_m     DOUBLE,
        nb_arrets_500m       INTEGER,
        nb_arrets_1000m      INTEGER,
        nb_arrets_2000m      INTEGER
    )
    """)

    rayons_sql = ", ".join(
        f"COUNT(*) FILTER (WHERE dist_m <= {r}) AS nb_arrets_{r}m"
        for r in RAYONS_M
    )

    # Traitement par batch
    batches = [depts[i:i+BATCH_SIZE] for i in range(0, len(depts), BATCH_SIZE)]

    for bi, batch in enumerate(batches, 1):
        batch_str = "', '".join(batch)
        print(f"   Batch {bi}/{len(batches)} : depts {batch}")

        con.execute(f"""
        INSERT INTO _transport
        WITH
        -- Paires candidates via bounding box (évite le produit cartésien complet)
        cand AS (
            SELECT
                d.id_mutation,
                s.stop_name,
                s.modes,
                ST_Distance(
                    ST_Transform(ST_Point(d.longitude, d.latitude),
                                 'EPSG:4326', 'EPSG:2154'),
                    ST_Transform(ST_Point(s.longitude, s.latitude),
                                 'EPSG:4326', 'EPSG:2154')
                ) AS dist_m
            FROM dvf_avec_peb d
            JOIN transport_stops_clean s
              ON s.latitude  BETWEEN d.latitude  - 0.05 AND d.latitude  + 0.05
             AND s.longitude BETWEEN d.longitude - 0.07 AND d.longitude + 0.07
            WHERE d.code_departement IN ('{batch_str}')
        ),
        -- Arrêt le plus proche par mutation
        nearest AS (
            SELECT DISTINCT ON (id_mutation)
                id_mutation,
                stop_name   AS arret_plus_proche,
                modes       AS mode_arret,
                ROUND(dist_m) AS distance_arret_m
            FROM cand
            ORDER BY id_mutation, dist_m
        ),
        -- Comptage par rayon
        counts AS (
            SELECT id_mutation, {rayons_sql}
            FROM cand GROUP BY id_mutation
        )
        SELECT
            n.id_mutation,
            n.arret_plus_proche,
            n.mode_arret,
            n.distance_arret_m,
            COALESCE(c.nb_arrets_500m,  0),
            COALESCE(c.nb_arrets_1000m, 0),
            COALESCE(c.nb_arrets_2000m, 0)
        FROM nearest n
        LEFT JOIN counts c USING (id_mutation)
        """)

    n = con.execute("SELECT COUNT(*) FROM _transport").fetchone()[0]
    print(f"   → {n:,} mutations enrichies transport")


# ============================================================================
# Étape 2 : DPE (jointure par commune + type)
# Stratégie : on joint dvf_avec_peb ↔ dpe_commune sur
#   UPPER(dvf.nom_commune) = dpe_commune.nom_commune
#   + correspondance type_local ↔ type_batiment
# C'est une jointure statistique par commune, pas par adresse.
# ============================================================================
def _creer_dpe_enrichi(con) -> None:
    """Jointure DVF ↔ DPE par commune + type de bien.
    Résultat dans la table TEMP _dpe."""
    print("\n2. Enrichissement DPE (par commune × type)...")

    if not _table_exists(con, "dpe_commune"):
        print("   'dpe_commune' absente — étape DPE ignorée.")
        con.execute("""
        CREATE OR REPLACE TEMP TABLE _dpe (
            id_mutation         VARCHAR,
            pct_passoires       DOUBLE,
            pct_bons_dpe        DOUBLE,
            classe_dpe_dominante VARCHAR,
            conso_med_kwh_m2    DOUBLE
        )
        """)
        return

    con.execute("""
    CREATE OR REPLACE TEMP TABLE _dpe AS
    SELECT
        d.id_mutation,
        dpe.pct_passoires,
        dpe.pct_bons_dpe,
        dpe.classe_dpe_dominante,
        dpe.conso_med_kwh_m2
    FROM dvf_avec_peb d
    LEFT JOIN dpe_commune dpe
      ON UPPER(TRIM(d.nom_commune)) = dpe.nom_commune
     AND (
           (d.type_local = 'Maison'      AND dpe.type_batiment = 'maison')
        OR (d.type_local = 'Appartement' AND dpe.type_batiment = 'appartement')
     )
    """)

    n_avec_dpe = con.execute(
        "SELECT COUNT(*) FROM _dpe WHERE pct_passoires IS NOT NULL"
    ).fetchone()[0]
    n_total = con.execute("SELECT COUNT(*) FROM _dpe").fetchone()[0]
    print(f"   → {n_avec_dpe:,} / {n_total:,} mutations avec données DPE "
          f"({100*n_avec_dpe//n_total}%)")


# ============================================================================
# Étape 3 : Assemblage final dvf_enrichi
# ============================================================================
def _assembler_dvf_enrichi(con) -> None:
    print("\n3. Assemblage final → dvf_enrichi...")

    con.execute("DROP TABLE IF EXISTS dvf_enrichi;")

    con.execute("""
    CREATE TABLE dvf_enrichi AS
    SELECT
        -- === DVF core ===
        d.id_mutation,
        d.date_mutation,
        EXTRACT(YEAR FROM d.date_mutation)::INTEGER  AS annee,
        d.type_local,
        d.surface_reelle_bati,
        d.nombre_pieces_principales,
        d.valeur_fonciere,
        d.prix_m2,
        d.adresse,
        d.code_commune,
        d.code_departement,
        d.nom_commune,
        d.longitude,
        d.latitude,

        -- === PEB ===
        d.peb_zone,

        -- === Transport ===
        t.arret_plus_proche,
        t.mode_arret                                 AS mode_transport_proche,
        t.distance_arret_m,
        COALESCE(t.nb_arrets_500m,  0)               AS nb_arrets_500m,
        COALESCE(t.nb_arrets_1000m, 0)               AS nb_arrets_1000m,
        COALESCE(t.nb_arrets_2000m, 0)               AS nb_arrets_2000m,

        -- === DPE (stats de la commune) ===
        dpe.pct_passoires,
        dpe.pct_bons_dpe,
        dpe.classe_dpe_dominante,
        dpe.conso_med_kwh_m2

    FROM dvf_avec_peb d
    LEFT JOIN _transport t   ON d.id_mutation = t.id_mutation
    LEFT JOIN _dpe       dpe ON d.id_mutation = dpe.id_mutation
    """)

    total = con.execute("SELECT COUNT(*) FROM dvf_enrichi").fetchone()[0]
    print(f"   → {total:,} lignes dans dvf_enrichi")


# ============================================================================
# Bilan
# ============================================================================
def bilan(con) -> None:
    print("\n" + "=" * 60)
    print("BILAN — dvf_enrichi")
    print("=" * 60)

    n = con.execute("SELECT COUNT(*) FROM dvf_enrichi").fetchone()[0]
    n_depts = con.execute(
        "SELECT COUNT(DISTINCT code_departement) FROM dvf_enrichi"
    ).fetchone()[0]
    n_transport = con.execute(
        "SELECT COUNT(*) FROM dvf_enrichi WHERE arret_plus_proche IS NOT NULL"
    ).fetchone()[0]
    n_dpe = con.execute(
        "SELECT COUNT(*) FROM dvf_enrichi WHERE pct_passoires IS NOT NULL"
    ).fetchone()[0]
    n_peb = con.execute(
        "SELECT COUNT(*) FROM dvf_enrichi WHERE peb_zone IS NOT NULL"
    ).fetchone()[0]

    print(f"  Mutations totales          : {n:>10,}")
    print(f"  Départements couverts      : {n_depts:>10,}")
    print(f"  Avec données transport     : {n_transport:>10,}  "
          f"({100*n_transport//n if n else 0}%)")
    print(f"  Avec données DPE           : {n_dpe:>10,}  "
          f"({100*n_dpe//n if n else 0}%)")
    print(f"  En zone PEB (bruit aéro)   : {n_peb:>10,}  "
          f"({100*n_peb//n if n else 0}%)")

    print("\nTop 5 communes par volume :")
    print(con.execute("""
        SELECT nom_commune, code_departement,
               COUNT(*) AS n_ventes,
               ROUND(MEDIAN(prix_m2)) AS prix_m2_med,
               ROUND(MEDIAN(distance_arret_m)) AS dist_arret_med_m,
               ANY_VALUE(classe_dpe_dominante) AS dpe_dominant
        FROM dvf_enrichi
        GROUP BY nom_commune, code_departement
        ORDER BY n_ventes DESC LIMIT 5
    """).df().to_string(index=False))

    print("\nEffet distance gare/tram sur prix médian :")
    print(con.execute("""
        SELECT
            CASE WHEN distance_arret_m <  500 THEN '0–500m'
                 WHEN distance_arret_m < 1000 THEN '500m–1km'
                 WHEN distance_arret_m < 2000 THEN '1–2km'
                 WHEN distance_arret_m < 5000 THEN '2–5km'
                 ELSE '> 5km'
            END AS bucket,
            type_local,
            COUNT(*) AS n,
            ROUND(MEDIAN(prix_m2)) AS prix_m2_med
        FROM dvf_enrichi
        WHERE distance_arret_m IS NOT NULL
        GROUP BY 1, 2
        ORDER BY 2,
            CASE bucket WHEN '0–500m' THEN 1 WHEN '500m–1km' THEN 2
                        WHEN '1–2km' THEN 3 WHEN '2–5km' THEN 4 ELSE 5 END
    """).df().to_string(index=False))


# ============================================================================
# Main
# ============================================================================
if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--reset", action="store_true",
                    help="Recrée dvf_enrichi même si elle existe déjà")
    args = ap.parse_args()

    con = duckdb.connect(DB_FILE)

    if not check_prerequis(con):
        con.close()
        exit(1)

    if not args.reset and _table_exists(con, "dvf_enrichi"):
        print("'dvf_enrichi' existe déjà. Lance avec --reset pour recalculer.")
        bilan(con)
        con.close()
        exit(0)

    _creer_transport_enrichi(con)
    _creer_dpe_enrichi(con)
    _assembler_dvf_enrichi(con)
    bilan(con)

    con.close()
    print("\nTable dvf_enrichi prête.")
