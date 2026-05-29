import streamlit as st
from core.database import get_connection

@st.cache_data(ttl=3600)
def get_prix_par_commune(type_local: str, annee: int):
    con = get_connection()
    return con.execute("""
        SELECT
            code_commune,
            nom_commune,
            ROUND(AVG(prix_m2), 0)  AS prix_moyen,
            MEDIAN(prix_m2)          AS prix_median,
            COUNT(*)                 AS nb_transactions
        FROM dvf_raw
        WHERE type_local = ?
          AND YEAR(date_mutation) = ?
          AND prix_m2 BETWEEN 100 AND 30000
        GROUP BY code_commune, nom_commune
        HAVING nb_transactions >= 5
    """, [type_local, annee]).df()

@st.cache_data(ttl=3600)
def get_annees_disponibles():
    con = get_connection()
    return con.execute("""
        SELECT DISTINCT YEAR(date_mutation) AS annee
        FROM dvf_raw
        ORDER BY annee DESC
    """).df()["annee"].tolist()

@st.cache_data(ttl=3600)
def get_estimation(commune: str, surface: float,
                   nb_pieces: int, type_local: str):
    con = get_connection()
    return con.execute("""
        SELECT
            MEDIAN(prix_m2)                    AS prix_median_m2,
            PERCENTILE_CONT(0.25) WITHIN GROUP
                (ORDER BY prix_m2)             AS q1,
            PERCENTILE_CONT(0.75) WITHIN GROUP
                (ORDER BY prix_m2)             AS q3,
            COUNT(*)                           AS nb_comparables
        FROM dvf_raw
        WHERE nom_commune = ?
          AND type_local  = ?
          AND surface_reelle_bati BETWEEN ? AND ?
          AND nombre_pieces_principales BETWEEN ? AND ?
          AND YEAR(date_mutation) >= YEAR(CURRENT_DATE) - 2
          AND prix_m2 BETWEEN 100 AND 30000
    """, [
        commune, type_local,
        surface * 0.7, surface * 1.3,
        nb_pieces - 1, nb_pieces + 1
    ]).df()