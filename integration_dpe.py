"""
integration_dpe.py
-----------------------------------------------------------------------------
Intégration des DPE (Diagnostic de Performance Énergétique) depuis l'API
ADEME dans DuckDB.

Source  : data.ademe.fr — DPE logements existants V2
API     : https://data.ademe.fr/data-fair/api/v1/datasets/meg-83tjwtg8dyz4vv7h1dqe/lines

Stratégie :
  - Téléchargement département par département
  - Pagination par curseur (champ "next" de l'API) pour dépasser la limite des 10 000
  - Cache CSV.gz local → relance sans re-télécharger
  - Checkpoint : un fichier par département → reprise possible si crash
"""
from __future__ import annotations
import csv
import gzip
import time
import sys
from pathlib import Path

import duckdb
import requests

# ============================================================================
# Configuration
# ============================================================================
DB_FILE  = "immo_et_bruit.duckdb"
RAW_DIR  = Path("raw_dpe")
API_URL  = "https://data.ademe.fr/data-fair/api/v1/datasets/meg-83tjwtg8dyz4vv7h1dqe/lines"

from dotenv import load_dotenv
import os

load_dotenv()

_raw = os.getenv("DEPARTEMENTS", "44,49,53,72,85")

if _raw.strip().upper() == "ALL":
    DEPARTEMENTS_DPE = (
        [str(i).zfill(2) for i in range(1, 20)]
        + ["2A", "2B"]
        + [str(i) for i in range(21, 96)]
    )
else:
    DEPARTEMENTS_DPE = [d.strip() for d in _raw.split(",")]
PAGE_SIZE = 1000   
PAUSE_S   = 0.15   
TIMEOUT_S = 60     

# Colonnes de la base V2
LISTE_COLONNES = [
    "numero_dpe",
    "date_etablissement_dpe",
    "etiquette_dpe",
    "etiquette_ges",
    "conso_5_usages_par_m2_ep",
    "surface_habitable_immeuble",
    "type_batiment",
    "periode_construction",
    "code_postal_ban",
    "code_departement_ban",
    "nom_commune_ban",
    "adresse_ban",
    "coordonnee_cartographique_x_ban",
    "coordonnee_cartographique_y_ban",
]
COLONNES_API = ",".join(LISTE_COLONNES)

# ============================================================================
# Téléchargement
# ============================================================================
def telecharger_dept(dept: str) -> Path | None:
    """Télécharge tous les DPE d'un département via la pagination dynamique 'next'."""
    RAW_DIR.mkdir(exist_ok=True)
    dest = RAW_DIR / f"dpe_{dept}.csv.gz"

    if dest.exists() and dest.stat().st_size > 100:
        return dest  # Le fichier est déjà complet en cache

    total_rows = 0
    writer     = None
    gz         = None

    # Première URL d'initialisation pour le département
    url_courante = f"{API_URL}?size={PAGE_SIZE}&select={COLONNES_API}&qs=code_departement_ban:{dept}"

    try:
        gz = gzip.open(dest, "wt", newline="", encoding="utf-8")
        writer = csv.DictWriter(gz, fieldnames=LISTE_COLONNES, extrasaction='ignore')
        writer.writeheader()

        # Tant qu'il y a une URL valide à interroger (pagination)
        while url_courante:
            for attempt in range(3):
                try:
                    r = requests.get(url_courante, timeout=TIMEOUT_S)
                    if not r.ok:
                        print(f"\n   [!] Erreur API {r.status_code} : {r.text}")
                    r.raise_for_status()
                    data = r.json()
                    break
                except Exception as e:
                    if attempt == 2:
                        raise
                    time.sleep(3 * (attempt + 1))

            results = data.get("results", [])
            if not results:
                break

            writer.writerows(results)
            total_rows += len(results)

            if total_rows % 10000 == 0:
                print(f"     ... {total_rows:,} DPE")

            # La magie de l'API : elle nous donne le lien direct de la page suivante !
            # Cela permet de sauter la limite des 10 000
            url_courante = data.get("next") 
            
            time.sleep(PAUSE_S)

    except Exception as e:
        if gz:
            gz.close()
            gz = None
        dest.unlink(missing_ok=True) # On supprime le fichier cassé
        raise e
    finally:
        if gz:
            gz.close()

    if total_rows == 0:
        dest.unlink(missing_ok=True)
        return None

    return dest


# ============================================================================
# Chargement dans DuckDB
# ============================================================================
def load_dpe(con) -> None:
    print("\n--- Intégration DPE (ADEME) ---")

    if _table_exists(con, "dpe_raw"):
        print("Table 'dpe_raw' déjà présente, on passe.")
        return

    depts = DEPARTEMENTS_DPE
    print(f"Périmètre : {len(depts)} département(s)")

    fichiers = []
    for i, dept in enumerate(depts, 1):
        print(f"  [{i}/{len(depts)}] Dept {dept}", end=" ", flush=True)
        try:
            path = telecharger_dept(dept)
            if path:
                size_mb = path.stat().st_size / 1e6
                print(f"→ {size_mb:.1f} Mo")
                fichiers.append(path)
            else:
                print("→ vide")
        except Exception as e:
            print(f"→ ERREUR ({type(e).__name__}: {e}) — on continue")

    if not fichiers:
        print("ERREUR : aucun fichier DPE téléchargé.")
        return

    print(f"\nChargement de {len(fichiers)} fichiers dans DuckDB...")
    glob_pattern = str(RAW_DIR / "dpe_*.csv.gz")

    con.execute(f"""
    CREATE TABLE dpe_raw AS
    SELECT
        numero_dpe,
        TRY_CAST(date_etablissement_dpe AS DATE)            AS date_dpe,
        UPPER(TRIM(etiquette_dpe))                          AS etiquette_dpe,
        UPPER(TRIM(etiquette_ges))                          AS etiquette_ges,
        TRY_CAST(conso_5_usages_par_m2_ep AS DOUBLE)        AS conso_ep_kwh_m2,
        TRY_CAST(surface_habitable_immeuble AS DOUBLE)      AS surface_habitable,
        LOWER(TRIM(type_batiment))                          AS type_batiment,
        periode_construction                                AS periode_construction,
        LPAD(CAST(
            TRY_CAST(code_postal_ban AS INTEGER) AS VARCHAR
        ), 5, '0')                                          AS code_postal,
        code_departement_ban                                AS code_departement,
        UPPER(TRIM(nom_commune_ban))                        AS nom_commune,
        adresse_ban                                         AS adresse,
        TRY_CAST(coordonnee_cartographique_x_ban AS DOUBLE) AS longitude,
        TRY_CAST(coordonnee_cartographique_y_ban AS DOUBLE) AS latitude
    FROM read_csv_auto(
        '{glob_pattern}',
        union_by_name = true,
        ignore_errors = true
    )
    WHERE UPPER(TRIM(etiquette_dpe)) IN ('A','B','C','D','E','F','G')
      AND TRY_CAST(surface_habitable_immeuble AS DOUBLE) > 0
    """)

    n = con.execute("SELECT COUNT(*) FROM dpe_raw").fetchone()[0]
    print(f"\n→ {n:,} DPE dans 'dpe_raw'")


def creer_dpe_commune(con) -> None:
    print("\n--- dpe_commune (stats par commune × type) ---")

    if _table_exists(con, "dpe_commune"):
        print("Table 'dpe_commune' déjà présente, on passe.")
        return

    con.execute("""
    CREATE TABLE dpe_commune AS
    SELECT
        nom_commune,
        code_postal,
        code_departement,
        type_batiment,
        COUNT(*)                                                          AS n_dpe,
        ROUND(100.0 * COUNT(*) FILTER (WHERE etiquette_dpe IN ('F','G'))
              / COUNT(*), 1)                                              AS pct_passoires,
        ROUND(100.0 * COUNT(*) FILTER (WHERE etiquette_dpe IN ('A','B'))
              / COUNT(*), 1)                                              AS pct_bons_dpe,
        MODE(etiquette_dpe)                                               AS classe_dpe_dominante,
        ROUND(MEDIAN(conso_ep_kwh_m2))                                    AS conso_med_kwh_m2,
        COUNT(*) FILTER (WHERE etiquette_dpe = 'A')                       AS n_A,
        COUNT(*) FILTER (WHERE etiquette_dpe = 'B')                       AS n_B,
        COUNT(*) FILTER (WHERE etiquette_dpe = 'C')                       AS n_C,
        COUNT(*) FILTER (WHERE etiquette_dpe = 'D')                       AS n_D,
        COUNT(*) FILTER (WHERE etiquette_dpe = 'E')                       AS n_E,
        COUNT(*) FILTER (WHERE etiquette_dpe = 'F')                       AS n_F,
        COUNT(*) FILTER (WHERE etiquette_dpe = 'G')                       AS n_G
    FROM dpe_raw
    WHERE nom_commune IS NOT NULL
    GROUP BY nom_commune, code_postal, code_departement, type_batiment
    HAVING COUNT(*) >= 3
    """)

    n = con.execute("SELECT COUNT(*) FROM dpe_commune").fetchone()[0]
    print(f"→ {n:,} lignes dans 'dpe_commune'")


def _table_exists(con, name: str) -> bool:
    return con.execute(f"SELECT COUNT(*) FROM information_schema.tables WHERE table_name = '{name}'").fetchone()[0] > 0


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--reset", action="store_true")
    args = ap.parse_args()

    print("=" * 60)
    print("  Pipeline DPE → DuckDB")
    print("=" * 60)

    try:
        con = duckdb.connect(DB_FILE)
    except duckdb.IOException as e:
        if "utilisé par un autre processus" in str(e) or "already open" in str(e):
            print("\n❌ ERREUR : La base de données est actuellement bloquée.")
            sys.exit(1)
        else:
            raise e

    if args.reset:
        for t in ["dpe_commune", "dpe_raw", "dvf_enrichi"]:
            con.execute(f"DROP TABLE IF EXISTS {t}")

    load_dpe(con)
    creer_dpe_commune(con)
    con.close()
    print("\nPipeline DPE terminé.")