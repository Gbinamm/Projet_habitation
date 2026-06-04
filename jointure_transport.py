"""
jointure_transport.py
-----------------------------------------------------------------------------
Crée la table finale 'dvf_enrichi' croisant :
  - DVF + PEB          (dvf_avec_peb)
  - Transport          (transport_stops_clean)
  - DPE                (dpe_commune)

Colonnes ajoutées par rapport à la version précédente :
  - nature_mutation     (depuis dvf_avec_peb)
  - surface_terrain     (depuis dvf_avec_peb)
  - nom_aeroport        (depuis peb_raw — quel aéroport génère le bruit)
  - n_dpe               (depuis dpe_commune — fiabilité des stats DPE)
  - reseaux_transport   (depuis transport_stops_clean — nom du réseau)

Corrections :
  - DISTINCT ON remplacé par ROW_NUMBER() OVER (syntaxe DuckDB correcte)

Optimisations :
  1. Traitement par batch de départements pour contrôler la RAM
  2. Bounding box ±0.05°/±0.07° avant ST_Distance
  3. Jointure DPE par commune (pas par DPE individuel)
  4. Reprojection Lambert 93 pour distances en mètres
"""
from __future__ import annotations
import duckdb

DB_FILE  = "immo_et_bruit.duckdb"
RAYONS_M = [500, 1000, 2000]

# Réduis à 5 si tu manques de RAM (8 Go), garde 10 pour 16 Go
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
    if "dpe_commune" not in presentes:
        print("INFO : 'dpe_commune' absente — enrichissement DPE ignoré.")
    return True


def _table_exists(con, name: str) -> bool:
    return con.execute(f"""
        SELECT COUNT(*) FROM information_schema.tables
        WHERE table_name = '{name}'
    """).fetchone()[0] > 0


# ============================================================================
# Étape 1 : Transport (arrêt le plus proche + densité)
# ============================================================================
def _creer_transport_enrichi(con) -> None:
    print("\n1. Enrichissement transport (arrêt proche + densité)...")

    con.execute("INSTALL spatial; LOAD spatial;")

    depts = [r[0] for r in con.execute("""
        SELECT DISTINCT code_departement
        FROM dvf_avec_peb
        WHERE code_departement IS NOT NULL
        ORDER BY code_departement
    """).fetchall()]

    print(f"   {len(depts)} département(s) — batches de {BATCH_SIZE}...")

    con.execute("""
    CREATE OR REPLACE TEMP TABLE _transport (
        id_mutation          VARCHAR,
        arret_plus_proche    VARCHAR,
        mode_arret           VARCHAR,
        reseaux_transport    VARCHAR,
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

    batches = [depts[i:i+BATCH_SIZE] for i in range(0, len(depts), BATCH_SIZE)]

    for bi, batch in enumerate(batches, 1):
        batch_str = "', '".join(batch)
        print(f"   Batch {bi}/{len(batches)} : depts {batch}")

        con.execute(f"""
        INSERT INTO _transport
        WITH
        cand AS (
            SELECT
                d.id_mutation,
                s.stop_name,
                s.modes,
                s.reseaux,
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
        -- ✅ ROW_NUMBER() — syntaxe DuckDB correcte (DISTINCT ON = PostgreSQL)
        nearest AS (
            SELECT
                id_mutation,
                stop_name    AS arret_plus_proche,
                modes        AS mode_arret,
                reseaux      AS reseaux_transport,
                ROUND(dist_m) AS distance_arret_m
            FROM (
                SELECT *,
                    ROW_NUMBER() OVER (
                        PARTITION BY id_mutation
                        ORDER BY dist_m
                    ) AS rk
                FROM cand
            )
            WHERE rk = 1
        ),
        counts AS (
            SELECT id_mutation, {rayons_sql}
            FROM cand GROUP BY id_mutation
        )
        SELECT
            n.id_mutation,
            n.arret_plus_proche,
            n.mode_arret,
            n.reseaux_transport,
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
# Étape 2 : DPE
# ============================================================================
def _creer_dpe_enrichi(con) -> None:
    print("\n2. Enrichissement DPE (par commune × type)...")

    if not _table_exists(con, "dpe_commune"):
        print("   'dpe_commune' absente — étape DPE ignorée.")
        con.execute("""
        CREATE OR REPLACE TEMP TABLE _dpe (
            id_mutation          VARCHAR,
            pct_passoires        DOUBLE,
            pct_bons_dpe         DOUBLE,
            classe_dpe_dominante VARCHAR,
            conso_med_kwh_m2     DOUBLE,
            n_dpe                BIGINT
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
        dpe.conso_med_kwh_m2,
        dpe.n_dpe               -- fiabilité : plus il y en a, mieux c'est
    FROM dvf_avec_peb d
    LEFT JOIN dpe_commune dpe
      ON UPPER(TRIM(d.nom_commune)) = dpe.nom_commune
     AND (
           (d.type_local = 'Maison'      AND dpe.type_batiment = 'maison')
        OR (d.type_local = 'Appartement' AND dpe.type_batiment = 'appartement')
     )
    """)

    n_avec = con.execute(
        "SELECT COUNT(*) FROM _dpe WHERE pct_passoires IS NOT NULL"
    ).fetchone()[0]
    n_total = con.execute("SELECT COUNT(*) FROM _dpe").fetchone()[0]
    print(f"   → {n_avec:,} / {n_total:,} mutations avec DPE "
          f"({100*n_avec//n_total if n_total else 0}%)")


# ============================================================================
# Étape 3 : Nom de l'aéroport depuis peb_raw
# ============================================================================
def _creer_peb_enrichi(con) -> None:
    print("\n3. Enrichissement PEB (nom aéroport)...")

    if not _table_exists(con, "peb_raw"):
        print("   'peb_raw' absente — étape PEB ignorée.")
        con.execute("""
        CREATE OR REPLACE TEMP TABLE _peb_noms (
            peb_zone     VARCHAR,
            nom_aeroport VARCHAR
        )
        """)
        return

    # Une zone peut avoir plusieurs polygones (un par aéroport)
    # On prend le nom le plus fréquent par zone
    con.execute("""
    CREATE OR REPLACE TEMP TABLE _peb_noms AS
    SELECT DISTINCT
        peb_zone,
        MODE(NOM) AS nom_aeroport
    FROM peb_raw
    WHERE peb_zone IS NOT NULL
    GROUP BY peb_zone
    """)

    zones = con.execute("SELECT * FROM _peb_noms").fetchall()
    print(f"   → {len(zones)} zones PEB avec nom d'aéroport")
    for zone, nom in zones:
        print(f"      Zone {zone} : {nom}")


# ============================================================================
# Étape 4 : Assemblage final dvf_enrichi
# ============================================================================
def _assembler_dvf_enrichi(con) -> None:
    print("\n4. Assemblage final → dvf_enrichi...")

    con.execute("DROP TABLE IF EXISTS dvf_enrichi;")

    con.execute("""
    CREATE TABLE dvf_enrichi AS
    SELECT
        -- === DVF core ===
        d.id_mutation,
        d.date_mutation,
        EXTRACT(YEAR FROM d.date_mutation)::INTEGER  AS annee,
        d.nature_mutation,
        d.type_local,
        d.surface_reelle_bati,
        d.nombre_pieces_principales,
        d.surface_terrain,                           -- surface du terrain (maisons)
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
        pn.nom_aeroport,                             -- nom de l'aéroport

        -- === Transport ===
        t.arret_plus_proche,
        t.mode_arret                                 AS mode_transport_proche,
        t.reseaux_transport,                         -- nom du réseau (TAN, SNCF...)
        t.distance_arret_m,
        COALESCE(t.nb_arrets_500m,  0)               AS nb_arrets_500m,
        COALESCE(t.nb_arrets_1000m, 0)               AS nb_arrets_1000m,
        COALESCE(t.nb_arrets_2000m, 0)               AS nb_arrets_2000m,

        -- === DPE ===
        dpe.pct_passoires,
        dpe.pct_bons_dpe,
        dpe.classe_dpe_dominante,
        dpe.conso_med_kwh_m2,
        dpe.n_dpe                                    -- nb DPE (fiabilité stats)

    FROM dvf_avec_peb d
    LEFT JOIN _transport t   ON d.id_mutation  = t.id_mutation
    LEFT JOIN _dpe       dpe ON d.id_mutation  = dpe.id_mutation
    LEFT JOIN _peb_noms  pn  ON d.peb_zone     = pn.peb_zone
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
    if n == 0:
        print("Table vide !")
        return

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
          f"({100*n_transport//n}%)")
    print(f"  Avec données DPE           : {n_dpe:>10,}  "
          f"({100*n_dpe//n}%)")
    print(f"  En zone PEB                : {n_peb:>10,}  "
          f"({100*n_peb//n}%)")

    print("\nColonnes de dvf_enrichi :")
    cols = con.execute("""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name = 'dvf_enrichi'
        ORDER BY ordinal_position
    """).fetchall()
    for col, dtype in cols:
        print(f"  {col:<35} {dtype}")

    print("\nTop 5 communes par volume :")
    print(con.execute("""
        SELECT nom_commune, code_departement,
               COUNT(*) AS n_ventes,
               ROUND(MEDIAN(prix_m2)) AS prix_m2_med,
               ROUND(MEDIAN(distance_arret_m)) AS dist_arret_med_m,
               ANY_VALUE(classe_dpe_dominante) AS dpe_dominant,
               ANY_VALUE(nom_aeroport) AS aeroport_proche
        FROM dvf_enrichi
        GROUP BY nom_commune, code_departement
        ORDER BY n_ventes DESC LIMIT 5
    """).df().to_string(index=False))

    print("\nEffet distance transport sur prix médian :")
    print(con.execute("""
        SELECT
            CASE WHEN distance_arret_m <  500 THEN '0-500m'
                 WHEN distance_arret_m < 1000 THEN '500m-1km'
                 WHEN distance_arret_m < 2000 THEN '1-2km'
                 WHEN distance_arret_m < 5000 THEN '2-5km'
                 ELSE '> 5km'
            END AS bucket,
            type_local,
            COUNT(*) AS n,
            ROUND(MEDIAN(prix_m2)) AS prix_m2_med
        FROM dvf_enrichi
        WHERE distance_arret_m IS NOT NULL
        GROUP BY 1, 2
        ORDER BY 2,
            CASE bucket
                WHEN '0-500m'   THEN 1
                WHEN '500m-1km' THEN 2
                WHEN '1-2km'    THEN 3
                WHEN '2-5km'    THEN 4
                ELSE 5
            END
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
    _creer_peb_enrichi(con)
    _assembler_dvf_enrichi(con)
    bilan(con)

    con.close()
    print("\nTable dvf_enrichi prête.")
