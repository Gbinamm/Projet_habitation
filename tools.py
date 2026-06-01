"""
tools.py
-----------------------------------------------------------------------------
Outils que le chatbot peut utiliser pour interroger la base DuckDB.

Chaque fonction renvoie un dict JSON-sérialisable que le LLM va lire pour
formuler sa réponse. On ne renvoie JAMAIS de prose au LLM — juste des faits
chiffrés et structurés. C'est lui qui mettra en forme.

Les fonctions détectent automatiquement les tables disponibles dans la base.
Si une table n'existe pas encore (ex: transport_stops_clean pas créée),
les outils correspondants renvoient un message clair au lieu de planter.
"""
from __future__ import annotations
import duckdb
from pathlib import Path
from typing import Optional

DB_PATH = "immo_et_bruit.duckdb"


# ============================================================================
# Helpers
# ============================================================================
def _connect():
    """Connexion en lecture seule — thread-safe pour Streamlit."""
    return duckdb.connect(DB_PATH, read_only=True)


def _table_exists(con, name: str) -> bool:
    return con.execute(f"""
        SELECT COUNT(*) FROM information_schema.tables
        WHERE table_name = '{name}'
    """).fetchone()[0] > 0


def _best_dvf_table(con) -> Optional[str]:
    """Renvoie le nom de la meilleure table DVF dispo dans la base.
    Préférence : dvf_enrichi > dvf_avec_peb > dvf_raw."""
    for candidate in ["dvf_enrichi", "dvf_avec_peb", "dvf_raw"]:
        if _table_exists(con, candidate):
            return candidate
    return None


# ============================================================================
# OUTIL 1 : Liste des communes disponibles
# ============================================================================
def lister_communes(limite: int = 50) -> dict:
    """Renvoie les communes avec des transactions, triées par volume.
    Utile pour vérifier qu'une commune mentionnée par l'user existe."""
    con = _connect()
    table = _best_dvf_table(con)
    if not table:
        return {"erreur": "Aucune table DVF dans la base"}

    rows = con.execute(f"""
        SELECT nom_commune, COUNT(*) AS n_ventes
        FROM {table}
        GROUP BY nom_commune
        ORDER BY n_ventes DESC
        LIMIT {limite}
    """).fetchall()
    con.close()

    return {
        "table_source": table,
        "communes": [{"nom": r[0], "n_ventes": r[1]} for r in rows]
    }


# ============================================================================
# OUTIL 2 : Statistiques de prix par commune et type
# ============================================================================
def stats_prix(
    nom_commune: str,
    type_local: Optional[str] = None,
    annee_min: Optional[int] = None
) -> dict:
    """Statistiques de prix pour une commune et un type de bien.

    Args:
        nom_commune: nom exact de la commune (ex: 'Nantes')
        type_local: 'Maison' ou 'Appartement' (None = tous)
        annee_min: ne garder que les ventes à partir de cette année

    Renvoie : nombre de ventes, prix médian, fourchette (P25-P75),
    prix moyen au m².
    """
    con = _connect()
    table = _best_dvf_table(con)
    if not table:
        return {"erreur": "Aucune table DVF dans la base"}

    # Construction dynamique du WHERE
    where = [f"nom_commune ILIKE '%{nom_commune.replace(chr(39), chr(39)*2)}%'"]
    if type_local:
        where.append(f"type_local = '{type_local}'")
    if annee_min:
        where.append(f"EXTRACT(YEAR FROM date_mutation) >= {annee_min}")

    where_sql = " AND ".join(where)

    result = con.execute(f"""
        SELECT
            COUNT(*)                              AS n_ventes,
            ROUND(MEDIAN(prix_m2))                AS prix_m2_median,
            ROUND(MEDIAN(valeur_fonciere))        AS prix_vente_median,
            ROUND(QUANTILE_CONT(prix_m2, 0.25))   AS prix_m2_p25,
            ROUND(QUANTILE_CONT(prix_m2, 0.75))   AS prix_m2_p75,
            ROUND(AVG(surface_reelle_bati))       AS surface_moy
        FROM {table}
        WHERE {where_sql}
    """).fetchone()
    con.close()

    if not result or result[0] == 0:
        return {
            "trouve": False,
            "message": f"Aucune vente trouvée pour {nom_commune} "
                       f"(type={type_local}, depuis {annee_min})"
        }

    return {
        "trouve": True,
        "commune": nom_commune,
        "type_local": type_local or "tous types",
        "n_ventes": result[0],
        "prix_m2_median": result[1],
        "prix_vente_median": result[2],
        "fourchette_prix_m2": f"{result[3]} - {result[4]}",
        "surface_moyenne_m2": result[5],
    }


# ============================================================================
# OUTIL 3 : Rechercher des biens selon critères
# ============================================================================
def rechercher_biens(
    nom_commune: Optional[str] = None,
    type_local: Optional[str] = None,
    budget_max: Optional[int] = None,
    budget_min: Optional[int] = None,
    surface_min: Optional[int] = None,
    nb_pieces_min: Optional[int] = None,
    hors_peb: bool = False,
    limite: int = 10
) -> dict:
    """Recherche multicritère dans les transactions.

    Renvoie quelques exemples concrets + des stats agrégées.
    """
    con = _connect()
    table = _best_dvf_table(con)
    if not table:
        return {"erreur": "Aucune table DVF dans la base"}

    where = ["1=1"]
    if nom_commune:
        where.append(f"nom_commune ILIKE '%{nom_commune.replace(chr(39), chr(39)*2)}%'")
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
    if hors_peb and "peb_zone" in _columns(con, table):
        where.append("peb_zone IS NULL")

    where_sql = " AND ".join(where)

    # Stats globales
    stats = con.execute(f"""
        SELECT
            COUNT(*) AS n,
            ROUND(MEDIAN(valeur_fonciere)) AS prix_median,
            ROUND(MEDIAN(prix_m2))         AS prix_m2_median
        FROM {table} WHERE {where_sql}
    """).fetchone()

    if stats[0] == 0:
        con.close()
        return {
            "n_resultats": 0,
            "message": "Aucun bien ne correspond à ces critères. "
                       "Essayez d'élargir le budget ou la zone."
        }

    # Quelques exemples
    has_peb = "peb_zone" in _columns(con, table)
    peb_col = ", peb_zone" if has_peb else ""

    exemples = con.execute(f"""
        SELECT
            nom_commune, type_local, valeur_fonciere, surface_reelle_bati,
            nombre_pieces_principales, prix_m2, date_mutation
            {peb_col}
        FROM {table} WHERE {where_sql}
        ORDER BY date_mutation DESC
        LIMIT {limite}
    """).fetchall()
    con.close()

    exemples_list = []
    for r in exemples:
        e = {
            "commune": r[0],
            "type": r[1],
            "prix": int(r[2]),
            "surface_m2": int(r[3]) if r[3] else None,
            "pieces": r[4],
            "prix_m2": int(r[5]) if r[5] else None,
            "date": str(r[6]),
        }
        if has_peb:
            e["zone_peb"] = r[7] if r[7] else "hors zone"
        exemples_list.append(e)

    return {
        "n_resultats": stats[0],
        "prix_median": stats[1],
        "prix_m2_median": stats[2],
        "exemples": exemples_list,
    }


# ============================================================================
# OUTIL 4 : Évaluer un prix (l'estimateur)
# ============================================================================
def evaluer_prix(
    nom_commune: str,
    type_local: str,
    surface: int,
    prix_propose: int
) -> dict:
    """Compare un prix proposé au marché récent de la commune.
    Renvoie un verdict : bon prix / dans le marché / surcoté."""
    con = _connect()
    table = _best_dvf_table(con)
    if not table:
        return {"erreur": "Aucune table DVF dans la base"}

    prix_m2_propose = prix_propose / surface

    result = con.execute(f"""
        SELECT
            COUNT(*),
            ROUND(MEDIAN(prix_m2)),
            ROUND(QUANTILE_CONT(prix_m2, 0.25)),
            ROUND(QUANTILE_CONT(prix_m2, 0.75))
        FROM {table}
        WHERE nom_commune ILIKE '%{nom_commune.replace(chr(39), chr(39)*2)}%'
          AND type_local = '{type_local}'
    """).fetchone()
    con.close()

    if not result or result[0] < 5:
        return {
            "evaluable": False,
            "message": f"Pas assez de comparables à {nom_commune} pour {type_local}"
        }

    n, med, p25, p75 = result

    if prix_m2_propose < p25:
        verdict = "Bon prix — sous le marché"
        ecart_pct = round(100 * (prix_m2_propose - med) / med)
    elif prix_m2_propose <= p75:
        verdict = "Dans la fourchette du marché"
        ecart_pct = round(100 * (prix_m2_propose - med) / med)
    else:
        verdict = "Surcoté — au-dessus du marché"
        ecart_pct = round(100 * (prix_m2_propose - med) / med)

    return {
        "evaluable": True,
        "commune": nom_commune,
        "type_local": type_local,
        "prix_propose": prix_propose,
        "prix_m2_propose": round(prix_m2_propose),
        "prix_m2_median_marche": med,
        "fourchette_marche_p25_p75": f"{p25} - {p75}",
        "n_comparables": n,
        "verdict": verdict,
        "ecart_pct_vs_median": ecart_pct,
    }


# ============================================================================
# OUTIL 5 : Impact de la zone PEB (bruit aéroport)
# ============================================================================
def impact_bruit_aeroport(nom_commune: Optional[str] = None) -> dict:
    """Compare le prix médian dans/hors zone PEB.
    Si commune précisée, focalisé sur elle. Sinon, vue globale."""
    con = _connect()
    table = _best_dvf_table(con)
    if not table:
        return {"erreur": "Aucune table DVF dans la base"}

    if "peb_zone" not in _columns(con, table):
        con.close()
        return {"erreur": "Données PEB pas encore intégrées dans la base"}

    where = ""
    if nom_commune:
        where = f"WHERE nom_commune ILIKE '%{nom_commune.replace(chr(39), chr(39)*2)}%'"

    rows = con.execute(f"""
        SELECT
            COALESCE(peb_zone, 'Hors PEB') AS zone,
            COUNT(*) AS n,
            ROUND(MEDIAN(prix_m2)) AS prix_m2_median
        FROM {table}
        {where}
        GROUP BY 1
        ORDER BY 1
    """).fetchall()
    con.close()

    if not rows:
        return {"erreur": "Aucune donnée"}

    return {
        "commune": nom_commune or "Loire-Atlantique (global)",
        "repartition": [
            {"zone": r[0], "n_ventes": r[1], "prix_m2_median": r[2]}
            for r in rows
        ]
    }


# ============================================================================
# OUTIL 6 : Comparer plusieurs communes
# ============================================================================
def comparer_communes(communes: list[str], type_local: str = "Appartement") -> dict:
    """Comparaison côte à côte de plusieurs communes."""
    con = _connect()
    table = _best_dvf_table(con)
    if not table:
        return {"erreur": "Aucune table DVF dans la base"}

    results = []
    for c in communes:
        c_safe = c.replace("'", "''")
        r = con.execute(f"""
            SELECT
                COUNT(*) AS n,
                ROUND(MEDIAN(prix_m2)) AS med,
                ROUND(AVG(surface_reelle_bati)) AS surf_moy
            FROM {table}
            WHERE nom_commune ILIKE '%{c_safe}%'
              AND type_local = '{type_local}'
        """).fetchone()
        results.append({
            "commune": c,
            "n_ventes": r[0],
            "prix_m2_median": r[1],
            "surface_moyenne": r[2],
        })
    con.close()

    return {"type_local": type_local, "comparaison": results}


# ============================================================================
# Helper interne
# ============================================================================
def _columns(con, table: str) -> set[str]:
    return {r[0] for r in con.execute(f"""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = '{table}'
    """).fetchall()}


# ============================================================================
# Tableau des outils exposés au LLM (format Groq/OpenAI)
# ============================================================================
# Ce TOOLS dictionnaire décrit chaque fonction au LLM en JSON Schema.
# Groq/OpenAI lit ces descriptions pour décider quand appeler quelle fonction.
TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "lister_communes",
            "description": "Liste les communes de Loire-Atlantique disponibles dans la base avec leur volume de transactions. Utile pour vérifier qu'une commune existe.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limite": {"type": "integer", "default": 50}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "stats_prix",
            "description": "Donne les statistiques de prix pour une commune : médiane, fourchette, nombre de ventes. À appeler dès que l'utilisateur demande 'combien coûte' ou 'prix moyen'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "nom_commune": {"type": "string", "description": "Nom de la commune (ex: Nantes)"},
                    "type_local": {"type": "string", "enum": ["Maison", "Appartement"]},
                    "annee_min": {"type": "integer", "description": "Année minimum (ex: 2024 pour les ventes récentes)"}
                },
                "required": ["nom_commune"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "rechercher_biens",
            "description": "Recherche multicritère de biens (commune, budget, surface, pièces...). Renvoie le nombre de résultats + quelques exemples concrets.",
            "parameters": {
                "type": "object",
                "properties": {
                    "nom_commune": {"type": "string"},
                    "type_local": {"type": "string", "enum": ["Maison", "Appartement"]},
                    "budget_max": {"type": "integer"},
                    "budget_min": {"type": "integer"},
                    "surface_min": {"type": "integer"},
                    "nb_pieces_min": {"type": "integer"},
                    "hors_peb": {"type": "boolean", "description": "True pour exclure les zones de bruit aéroport"},
                    "limite": {"type": "integer", "default": 10}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "evaluer_prix",
            "description": "Évalue si un prix proposé est cohérent avec le marché. Renvoie un verdict (bon prix / dans le marché / surcoté).",
            "parameters": {
                "type": "object",
                "properties": {
                    "nom_commune": {"type": "string"},
                    "type_local": {"type": "string", "enum": ["Maison", "Appartement"]},
                    "surface": {"type": "integer"},
                    "prix_propose": {"type": "integer"}
                },
                "required": ["nom_commune", "type_local", "surface", "prix_propose"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "impact_bruit_aeroport",
            "description": "Compare les prix dans/hors zones PEB (bruit aéroport Nantes-Atlantique).",
            "parameters": {
                "type": "object",
                "properties": {
                    "nom_commune": {"type": "string", "description": "Optionnel — focalise sur une commune"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "comparer_communes",
            "description": "Compare plusieurs communes côte à côte (prix, volume, surface).",
            "parameters": {
                "type": "object",
                "properties": {
                    "communes": {"type": "array", "items": {"type": "string"}},
                    "type_local": {"type": "string", "enum": ["Maison", "Appartement"], "default": "Appartement"}
                },
                "required": ["communes"]
            }
        }
    },
]


# Dictionnaire qui mappe le nom du tool à la fonction Python
TOOL_FUNCTIONS = {
    "lister_communes":       lister_communes,
    "stats_prix":            stats_prix,
    "rechercher_biens":      rechercher_biens,
    "evaluer_prix":          evaluer_prix,
    "impact_bruit_aeroport": impact_bruit_aeroport,
    "comparer_communes":     comparer_communes,
}


if __name__ == "__main__":
    # Test rapide
    import json
    print("=== Test des outils ===")
    print(json.dumps(lister_communes(5), indent=2, ensure_ascii=False))
    print(json.dumps(stats_prix("Nantes", "Appartement"), indent=2, ensure_ascii=False))
    print(json.dumps(impact_bruit_aeroport(), indent=2, ensure_ascii=False))
