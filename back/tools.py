"""
tools.py — Nimbus
-----------------------------------------------------------------------------
Outils DuckDB exposés au LLM (Groq). Chaque fonction renvoie un dict
JSON-sérialisable. Le LLM lit les données et formule la réponse.

Table principale : dvf_enrichi (395k lignes, 5 depts Bretagne + Loire-Atl.)
"""
from __future__ import annotations
import duckdb
from pathlib import Path
from typing import Optional

# Chemin absolu → fonctionne quel que soit le répertoire de lancement
DB_PATH = str(Path(__file__).resolve().parent.parent / "immo_et_bruit.duckdb")


# ── Helpers ──────────────────────────────────────────────────────────────────
def _connect():
    return duckdb.connect(DB_PATH, read_only=True)

def _table_exists(con, name: str) -> bool:
    return con.execute(f"""
        SELECT COUNT(*) FROM information_schema.tables
        WHERE table_name = '{name}'
    """).fetchone()[0] > 0

def _best_dvf_table(con) -> Optional[str]:
    for t in ["dvf_enrichi", "dvf_avec_peb", "dvf_raw"]:
        if _table_exists(con, t):
            return t
    return None

def _columns(con, table: str) -> set[str]:
    return {r[0] for r in con.execute(f"""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = '{table}'
    """).fetchall()}

def _s(val: str) -> str:
    """Échappe les apostrophes pour éviter les injections SQL."""
    return val.replace("'", "''")


# ── OUTIL 1 : lister_communes ────────────────────────────────────────────────
def lister_communes(limite: int = 50) -> dict:
    """Liste les communes disponibles triées par volume de ventes."""
    con = _connect()
    table = _best_dvf_table(con)
    if not table:
        return {"erreur": "Aucune table DVF dans la base"}

    rows = con.execute(f"""
        SELECT nom_commune, code_departement, COUNT(*) AS n_ventes
        FROM {table}
        WHERE nom_commune IS NOT NULL
        GROUP BY nom_commune, code_departement
        ORDER BY n_ventes DESC
        LIMIT {limite}
    """).fetchall()
    con.close()
    return {
        "communes": [{"nom": r[0], "departement": r[1], "n_ventes": r[2]} for r in rows]
    }


# ── OUTIL 2 : stats_prix ─────────────────────────────────────────────────────
def stats_prix(
    nom_commune: str,
    type_local: Optional[str] = None,
    annee_min: Optional[int] = None,
) -> dict:
    """Statistiques de prix pour une commune : médiane, fourchette, surface."""
    con = _connect()
    table = _best_dvf_table(con)
    if not table:
        return {"erreur": "Aucune table DVF dans la base"}

    where = [f"nom_commune ILIKE '%{_s(nom_commune)}%'",
             "prix_m2 BETWEEN 100 AND 30000"]
    if type_local:
        where.append(f"type_local = '{type_local}'")
    if annee_min:
        where.append(f"annee >= {annee_min}")

    r = con.execute(f"""
        SELECT
            COUNT(*)                               AS n_ventes,
            ROUND(MEDIAN(prix_m2))                 AS prix_m2_median,
            ROUND(MEDIAN(valeur_fonciere))          AS prix_vente_median,
            ROUND(QUANTILE_CONT(prix_m2, 0.25))    AS p25,
            ROUND(QUANTILE_CONT(prix_m2, 0.75))    AS p75,
            ROUND(AVG(surface_reelle_bati))        AS surface_moy,
            MIN(annee), MAX(annee)
        FROM {table}
        WHERE {" AND ".join(where)}
    """).fetchone()
    con.close()

    if not r or r[0] == 0:
        return {"trouve": False,
                "message": f"Aucune vente trouvée pour {nom_commune}"}

    return {
        "trouve": True,
        "commune": nom_commune,
        "type_local": type_local or "tous types",
        "n_ventes": r[0],
        "prix_m2_median": r[1],
        "prix_vente_median": r[2],
        "fourchette_prix_m2_p25_p75": f"{r[3]} — {r[4]} €/m²",
        "surface_moyenne_m2": r[5],
        "periode": f"{r[6]}–{r[7]}",
    }


# ── OUTIL 3 : rechercher_biens ───────────────────────────────────────────────
def rechercher_biens(
    nom_commune: Optional[str] = None,
    type_local: Optional[str] = None,
    budget_max: Optional[int] = None,
    budget_min: Optional[int] = None,
    surface_min: Optional[int] = None,
    nb_pieces_min: Optional[int] = None,
    hors_peb: bool = False,
    limite: int = 8,
) -> dict:
    """Recherche multicritère. Renvoie stats + exemples concrets."""
    con = _connect()
    table = _best_dvf_table(con)
    if not table:
        return {"erreur": "Aucune table DVF dans la base"}

    cols = _columns(con, table)
    where = ["prix_m2 BETWEEN 100 AND 30000"]
    if nom_commune:
        where.append(f"nom_commune ILIKE '%{_s(nom_commune)}%'")
    if type_local:
        where.append(f"type_local = '{type_local}'")
    if budget_max:
        where.append(f"valeur_fonciere <= {budget_max}")
    if budget_min:
        where.append(f"valeur_fonciere >= {budget_min}")
    if surface_min:
        where.append(f"surface_reelle_bati >= {surface_min}")
    if nb_pieces_min:
        where.append(f"nombre_pieces_principales >= {nb_pieces_min}")
    if hors_peb and "peb_zone" in cols:
        where.append("peb_zone IS NULL")

    w = " AND ".join(where)

    stats = con.execute(f"""
        SELECT COUNT(*), ROUND(MEDIAN(valeur_fonciere)), ROUND(MEDIAN(prix_m2))
        FROM {table} WHERE {w}
    """).fetchone()

    if not stats or stats[0] == 0:
        con.close()
        return {"n_resultats": 0,
                "message": "Aucun bien — essayez d'élargir les critères."}

    # Colonnes enrichies disponibles
    extra_select = ""
    extra_keys   = []
    if "distance_arret_m" in cols:
        extra_select += ", ROUND(distance_arret_m) AS dist_arret"
        extra_keys.append("distance_arret_m")
    if "classe_dpe_dominante" in cols:
        extra_select += ", classe_dpe_dominante AS dpe"
        extra_keys.append("dpe")
    if "peb_zone" in cols:
        extra_select += ", peb_zone"
        extra_keys.append("peb_zone")

    rows = con.execute(f"""
        SELECT nom_commune, type_local, valeur_fonciere,
               surface_reelle_bati, nombre_pieces_principales,
               prix_m2, CAST(date_mutation AS VARCHAR)
               {extra_select}
        FROM {table} WHERE {w}
        ORDER BY date_mutation DESC
        LIMIT {limite}
    """).fetchall()
    con.close()

    base_keys = ["commune","type","prix","surface_m2","pieces","prix_m2","date"]
    all_keys  = base_keys + extra_keys

    return {
        "n_resultats": stats[0],
        "prix_median": stats[1],
        "prix_m2_median": stats[2],
        "exemples": [dict(zip(all_keys, r)) for r in rows],
    }


# ── OUTIL 4 : evaluer_prix ───────────────────────────────────────────────────
def evaluer_prix(
    nom_commune: str,
    type_local: str,
    surface: int,
    prix_propose: int,
) -> dict:
    """Verdict sur un prix proposé vs le marché réel."""
    con = _connect()
    table = _best_dvf_table(con)
    if not table:
        return {"erreur": "Aucune table DVF dans la base"}

    r = con.execute(f"""
        SELECT COUNT(*),
               ROUND(MEDIAN(prix_m2)),
               ROUND(QUANTILE_CONT(prix_m2, 0.25)),
               ROUND(QUANTILE_CONT(prix_m2, 0.75))
        FROM {table}
        WHERE nom_commune ILIKE '%{_s(nom_commune)}%'
          AND type_local = '{type_local}'
          AND prix_m2 BETWEEN 100 AND 30000
    """).fetchone()
    con.close()

    if not r or r[0] < 5:
        return {"evaluable": False,
                "message": f"Pas assez de comparables à {nom_commune}"}

    n, med, p25, p75 = r
    ppm = round(prix_propose / surface)
    ecart = round(100 * (ppm - med) / med)

    if ppm < p25:
        verdict = "Très bon prix — sous le marché"
    elif ppm <= p75:
        verdict = "Dans la fourchette du marché"
    else:
        verdict = "Surcoté — au-dessus du marché"

    return {
        "evaluable": True,
        "commune": nom_commune, "type_local": type_local,
        "prix_propose": prix_propose,
        "prix_m2_propose": ppm,
        "prix_m2_median_marche": med,
        "fourchette_p25_p75": f"{p25} — {p75} €/m²",
        "n_comparables": n,
        "verdict": verdict,
        "ecart_vs_median": f"{'+' if ecart>=0 else ''}{ecart}%",
    }


# ── OUTIL 5 : impact_bruit_aeroport ─────────────────────────────────────────
def impact_bruit_aeroport(nom_commune: Optional[str] = None) -> dict:
    """Compare prix dans/hors zone PEB (bruit aéroport)."""
    con = _connect()
    table = _best_dvf_table(con)
    if not table:
        return {"erreur": "Aucune table DVF dans la base"}
    if "peb_zone" not in _columns(con, table):
        con.close()
        return {"erreur": "Données PEB non disponibles dans cette table"}

    where = f"WHERE nom_commune ILIKE '%{_s(nom_commune)}%'" if nom_commune else ""
    rows = con.execute(f"""
        SELECT COALESCE(peb_zone, 'Hors PEB') AS zone,
               COUNT(*), ROUND(MEDIAN(prix_m2))
        FROM {table} {where}
        GROUP BY 1 ORDER BY 1
    """).fetchall()
    con.close()

    return {
        "commune": nom_commune or "Toute la zone",
        "repartition": [{"zone": r[0], "n_ventes": r[1], "prix_m2_median": r[2]}
                        for r in rows],
    }


# ── OUTIL 6 : comparer_communes ──────────────────────────────────────────────
def comparer_communes(communes: list[str], type_local: str = "Appartement") -> dict:
    """Comparaison côte à côte de plusieurs communes."""
    con = _connect()
    table = _best_dvf_table(con)
    if not table:
        return {"erreur": "Aucune table DVF dans la base"}

    cols = _columns(con, table)
    has_transport = "distance_arret_m" in cols
    has_dpe       = "classe_dpe_dominante" in cols

    results = []
    for c in communes:
        extra = ""
        if has_transport:
            extra += ", ROUND(MEDIAN(distance_arret_m)) AS dist_arret_med"
        if has_dpe:
            extra += ", MODE(classe_dpe_dominante) AS dpe_dominant"

        r = con.execute(f"""
            SELECT COUNT(*),
                   ROUND(MEDIAN(prix_m2)),
                   ROUND(AVG(surface_reelle_bati))
                   {extra}
            FROM {table}
            WHERE nom_commune ILIKE '%{_s(c)}%'
              AND type_local = '{type_local}'
              AND prix_m2 BETWEEN 100 AND 30000
        """).fetchone()

        d = {"commune": c, "n_ventes": r[0],
             "prix_m2_median": r[1], "surface_moyenne": r[2]}
        idx = 3
        if has_transport:
            d["distance_arret_mediane_m"] = r[idx]; idx += 1
        if has_dpe:
            d["dpe_dominant"] = r[idx]
        results.append(d)

    con.close()
    return {"type_local": type_local, "comparaison": results}


# ── OUTIL 7 : stats_transport ────────────────────────────────────────────────
def stats_transport(nom_commune: str) -> dict:
    """Accessibilité transport d'une commune : distance arrêt, densité réseau."""
    con = _connect()
    table = _best_dvf_table(con)
    if not table:
        return {"erreur": "Aucune table DVF dans la base"}
    if "distance_arret_m" not in _columns(con, table):
        con.close()
        return {"erreur": "Données transport non disponibles"}

    r = con.execute(f"""
        SELECT
            ROUND(MEDIAN(distance_arret_m))   AS dist_med,
            ROUND(MIN(distance_arret_m))      AS dist_min,
            ROUND(QUANTILE_CONT(distance_arret_m, 0.75)) AS dist_p75,
            ROUND(AVG(nb_arrets_500m), 1)     AS moy_arrets_500m,
            ROUND(AVG(nb_arrets_1000m), 1)    AS moy_arrets_1km,
            MODE(reseaux_transport)            AS reseau_principal,
            COUNT(*)
        FROM {table}
        WHERE nom_commune ILIKE '%{_s(nom_commune)}%'
          AND distance_arret_m IS NOT NULL
    """).fetchone()
    con.close()

    if not r or r[6] == 0:
        return {"trouve": False, "message": f"Pas de données transport pour {nom_commune}"}

    return {
        "commune": nom_commune,
        "distance_arret_mediane_m": r[0],
        "distance_arret_min_m": r[1],
        "distance_arret_p75_m": r[2],
        "moyenne_arrets_dans_500m": r[3],
        "moyenne_arrets_dans_1km": r[4],
        "reseau_principal": r[5],
        "n_biens": r[6],
    }


# ── OUTIL 8 : stats_dpe ──────────────────────────────────────────────────────
def stats_dpe(nom_commune: str, type_local: Optional[str] = None) -> dict:
    """Performance énergétique d'une commune : % passoires, DPE dominant, conso."""
    con = _connect()
    table = _best_dvf_table(con)
    if not table:
        return {"erreur": "Aucune table DVF dans la base"}
    if "classe_dpe_dominante" not in _columns(con, table):
        con.close()
        return {"erreur": "Données DPE non disponibles"}

    where = [f"nom_commune ILIKE '%{_s(nom_commune)}%'"]
    if type_local:
        where.append(f"type_local = '{type_local}'")
    w = " AND ".join(where)

    r = con.execute(f"""
        SELECT
            MODE(classe_dpe_dominante)            AS dpe_dominant,
            ROUND(AVG(pct_passoires)*100, 1)      AS pct_passoires,
            ROUND(AVG(pct_bons_dpe)*100, 1)       AS pct_bons_dpe,
            ROUND(AVG(conso_med_kwh_m2), 0)       AS conso_moy_kwh_m2,
            COUNT(*)
        FROM {table}
        WHERE {w}
          AND classe_dpe_dominante IS NOT NULL
    """).fetchone()
    con.close()

    if not r or r[4] == 0:
        return {"trouve": False, "message": f"Pas de données DPE pour {nom_commune}"}

    return {
        "commune": nom_commune,
        "type_local": type_local or "tous types",
        "dpe_dominant": r[0],
        "pct_passoires_thermiques": f"{r[1]}%",
        "pct_bons_dpe_AB_C": f"{r[2]}%",
        "conso_moyenne_kwh_m2": r[3],
        "n_biens": r[4],
    }


# ── Schémas exposés au LLM ───────────────────────────────────────────────────
TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "lister_communes",
            "description": "Liste les communes disponibles dans la base avec leur volume de transactions.",
            "parameters": {
                "type": "object",
                "properties": {"limite": {"type": "integer", "default": 50}},
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "stats_prix",
            "description": "Prix au m², fourchette et volume de ventes pour une commune. À appeler dès que l'utilisateur demande un prix ou une estimation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "nom_commune": {"type": "string"},
                    "type_local":  {"type": "string", "enum": ["Maison", "Appartement"]},
                    "annee_min":   {"type": "integer"},
                },
                "required": ["nom_commune"],
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "rechercher_biens",
            "description": "Recherche multicritère de biens (commune, budget, surface, pièces, DPE, transport). Renvoie des exemples concrets.",
            "parameters": {
                "type": "object",
                "properties": {
                    "nom_commune":   {"type": "string"},
                    "type_local":    {"type": "string", "enum": ["Maison", "Appartement"]},
                    "budget_max":    {"type": "integer"},
                    "budget_min":    {"type": "integer"},
                    "surface_min":   {"type": "integer"},
                    "nb_pieces_min": {"type": "integer"},
                    "hors_peb":      {"type": "boolean"},
                    "limite":        {"type": "integer", "default": 8},
                },
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "evaluer_prix",
            "description": "Évalue si un prix est cohérent avec le marché local. Verdict : bon prix / dans le marché / surcoté.",
            "parameters": {
                "type": "object",
                "properties": {
                    "nom_commune":   {"type": "string"},
                    "type_local":    {"type": "string", "enum": ["Maison", "Appartement"]},
                    "surface":       {"type": "integer"},
                    "prix_propose":  {"type": "integer"},
                },
                "required": ["nom_commune", "type_local", "surface", "prix_propose"],
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "impact_bruit_aeroport",
            "description": "Compare les prix dans et hors zones PEB (bruit aéroport). Optionnellement focalisé sur une commune.",
            "parameters": {
                "type": "object",
                "properties": {
                    "nom_commune": {"type": "string"},
                },
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "comparer_communes",
            "description": "Compare plusieurs communes côte à côte : prix, volume, surface, transport, DPE.",
            "parameters": {
                "type": "object",
                "properties": {
                    "communes":   {"type": "array", "items": {"type": "string"}},
                    "type_local": {"type": "string", "enum": ["Maison", "Appartement"], "default": "Appartement"},
                },
                "required": ["communes"],
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "stats_transport",
            "description": "Accessibilité transport en commun d'une commune : distance médiane aux arrêts, densité du réseau, réseau principal.",
            "parameters": {
                "type": "object",
                "properties": {
                    "nom_commune": {"type": "string"},
                },
                "required": ["nom_commune"],
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "stats_dpe",
            "description": "Performance énergétique d'une commune : DPE dominant, % passoires thermiques, % bons DPE, consommation moyenne.",
            "parameters": {
                "type": "object",
                "properties": {
                    "nom_commune": {"type": "string"},
                    "type_local":  {"type": "string", "enum": ["Maison", "Appartement"]},
                },
                "required": ["nom_commune"],
            }
        }
    },
]

TOOL_FUNCTIONS = {
    "lister_communes":       lister_communes,
    "stats_prix":            stats_prix,
    "rechercher_biens":      rechercher_biens,
    "evaluer_prix":          evaluer_prix,
    "impact_bruit_aeroport": impact_bruit_aeroport,
    "comparer_communes":     comparer_communes,
    "stats_transport":       stats_transport,
    "stats_dpe":             stats_dpe,
}