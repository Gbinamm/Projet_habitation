import duckdb
import requests
import zipfile
import shutil
import os
import tempfile
import json
import pandas as pd

# --- Configuration 
DVF_URL = "https://www.data.gouv.fr/api/1/datasets/r/902db087-b0eb-4cbb-a968-0b499bde5bc4"
DB_FILE = "real_estate_bi.duckdb"

# Configuration Géocodage
API_BAN_URL = "https://api-adresse.data.gouv.fr/search/"
LIMITE_LIGNES = 1000

# URLs des zones PEB de la DGAC
PEB_ZONE_URLS = {
    "B": "https://www.data.gouv.fr/api/1/datasets/r/ea77a7b5-0298-49ed-b3ff-caae3b15d022",
    "C": "https://www.data.gouv.fr/api/1/datasets/r/a7f30166-3319-428e-a08e-700e3c0a3755",
    "D": "https://www.data.gouv.fr/api/1/datasets/r/78087339-b725-4825-a9f7-8d4ef92b2963",
}

def load_full_dvf_to_duckdb(con):
    """Charge les données DVF dans DuckDB"""
    print("\n--- Intégration des données DVF (Transactions) ---")
    table_exists = con.execute("SELECT count(*) FROM information_schema.tables WHERE table_name = 'dvf_raw'").fetchone()[0]
    if table_exists > 0:
        print("1. La table 'dvf_raw' existe déjà, on passe l'intégration DVF.")
        return

    temp_dir = tempfile.gettempdir()
    zip_path = os.path.join(temp_dir, "archive_dvf.zip")
    txt_path = os.path.join(temp_dir, "valeurs_foncieres.txt")

    print("1. Téléchargement de l'archive DVF...")
    with requests.get(DVF_URL, stream=True) as r:
        r.raise_for_status()
        with open(zip_path, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
                
    print("2. Extraction du fichier texte...")
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        fichiers = zip_ref.namelist()
        with zip_ref.open(fichiers[0]) as source, open(txt_path, "wb") as cible:
            shutil.copyfileobj(source, cible)

    print("3. Intégration de TOUTES les données DVF de France...")
    safe_txt_path = txt_path.replace('\\', '/')
    
    query = f"""
    CREATE TABLE dvf_raw AS
    SELECT * FROM read_csv_auto(
        '{safe_txt_path}',
        delim='|',
        header=True,
        decimal_separator=',', 
        ignore_errors=True,
        all_varchar=True,
        null_padding=True,
        strict_mode=False
    );
    """
    con.execute(query)

    if os.path.exists(zip_path): os.remove(zip_path)
    if os.path.exists(txt_path): os.remove(txt_path)
    print("   -> Intégration DVF terminée.")

def load_peb_to_duckdb(con):
    """Télécharge les zones PEB, les fusionne et les intègre via l'extension spatiale"""
    print("\n--- Intégration des données PEB (Bruit DGAC) ---")
    table_exists = con.execute("SELECT count(*) FROM information_schema.tables WHERE table_name = 'peb_raw'").fetchone()[0]
    if table_exists > 0:
        print("1. La table 'peb_raw' existe déjà, on passe l'intégration PEB.")
        return

    print("1. Activation de l'extension spatiale...")
    con.execute("INSTALL spatial; LOAD spatial;")

    all_features = []
    
    # Récupération et ajout du tag de zone pour chaque fichier
    for zone, url in PEB_ZONE_URLS.items():
        print(f"2. Téléchargement de la zone {zone}...")
        response = requests.get(url, timeout=60)
        response.raise_for_status()

        features = response.json().get("features", [])
        for feature in features:
            if "properties" not in feature:
                feature["properties"] = {}
            feature["properties"]["peb_zone"] = zone
            
        all_features.extend(features)
        print(f"   -> Zone {zone} : {len(features)} polygones récupérés.")

    print("3. Fusion et création du GeoJSON temporaire...")
    with tempfile.NamedTemporaryFile(suffix=".geojson", mode="w", delete=False) as f:
        json.dump({"type": "FeatureCollection", "features": all_features}, f)
        temp_path = f.name

    print("4. Intégration géospatiale dans 'peb_raw'...")
    safe_temp_path = temp_path.replace('\\', '/')
    con.execute(f"CREATE TABLE peb_raw AS SELECT * FROM ST_Read('{safe_temp_path}')")

    # Nettoyage
    os.unlink(temp_path)

    # Vérification
    counts = con.execute("SELECT peb_zone, COUNT(*) FROM peb_raw GROUP BY peb_zone ORDER BY peb_zone").fetchall()
    print("   -> Bilan de l'intégration PEB :")
    for zone, count in counts:
        print(f"      - Zone {zone} : {count} zones insérées.")


def lier_dvf_et_peb(con):
    """Géolocalise un échantillon de DVF et fait la jointure avec le PEB"""
    print("\n--- Croisement DVF et PEB (Géocodage via BAN) ---")
    
    print(f"1. Extraction de {LIMITE_LIGNES} adresses complètes depuis DVF...")
    query_dvf = f"""
    SELECT 
        "Valeur fonciere",
        "Type local",
        CONCAT_WS(' ', "No voie", "Type de voie", "Voie", "Code departement") AS adresse_recherche
    FROM dvf_raw
    WHERE "Voie" IS NOT NULL
    LIMIT {LIMITE_LIGNES}
    """
    df_dvf = con.execute(query_dvf).df()

    print("2. Appel à l'API Adresse (Cette étape prend quelques secondes)...")
    resultats = []
    
    for index, row in df_dvf.iterrows():
        adresse = row['adresse_recherche']
        reponse = requests.get(API_BAN_URL, params={"q": adresse, "limit": 1})
        
        lat, lon = None, None
        if reponse.status_code == 200:
            data = reponse.json()
            if data['features']:
                coords = data['features'][0]['geometry']['coordinates']
                lon, lat = coords[0], coords[1]
        
        resultats.append({
            "Valeur fonciere": row['Valeur fonciere'],
            "Type local": row['Type local'],
            "adresse": adresse,
            "longitude": lon,
            "latitude": lat
        })
    
    df_gps = pd.DataFrame(resultats)
    df_gps = df_gps.dropna(subset=['longitude', 'latitude'])
    
    print(f"   -> {len(df_gps)} adresses géolocalisées avec succès !")

    print("3. Création de la table temporaire 'dvf_echantillon_gps'...")
    con.execute("DROP TABLE IF EXISTS dvf_echantillon_gps;")
    con.execute("CREATE TABLE dvf_echantillon_gps AS SELECT * FROM df_gps;")

    print("4. EXÉCUTION DE LA JOINTURE SPATIALE 🚀...")
    # On active spatial au cas où l'étape PEB aurait été sautée
    con.execute("INSTALL spatial; LOAD spatial;")
    
    query_jointure = """
    SELECT 
        d."Valeur fonciere",
        d."Type local",
        d.adresse,
        p.peb_zone
    FROM dvf_echantillon_gps d
    JOIN peb_raw p 
      ON ST_Contains(p.geom, ST_Point(d.longitude, d.latitude));
    """
    
    df_final = con.execute(query_jointure).df()
    
    print("\n==================================================")
    print("      RÉSULTAT DU CROISEMENT IMMOBILIER/BRUIT     ")
    print("==================================================")
    if len(df_final) > 0:
        print(df_final.to_string(index=False))
    else:
        print("Aucun bien de cet échantillon n'est situé dans une zone")
        print("de bruit d'aéroport (Zones B, C ou D).")
    print("==================================================")


if __name__ == "__main__":
    print("Ouverture de la base de données DuckDB...")
    con = duckdb.connect(DB_FILE)
    
    # Ingestions (Stage 1)
    load_full_dvf_to_duckdb(con)
    load_peb_to_duckdb(con)
    
    # Jointure (Stage 2)
    lier_dvf_et_peb(con)
    
    con.close()
    print("\nScript de pipeline terminé avec succès !")