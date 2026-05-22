import duckdb
import requests
import zipfile
import shutil
import os
import tempfile

# --- Configuration ---
DVF_URL = "https://www.data.gouv.fr/api/1/datasets/r/902db087-b0eb-4cbb-a968-0b499bde5bc4"
DB_FILE = "real_estate_bi.duckdb" # La base complète fera plusieurs gigaoctets

def load_full_dvf_to_duckdb():
    temp_dir = tempfile.gettempdir()
    zip_path = os.path.join(temp_dir, "archive_dvf.zip")
    txt_path = os.path.join(temp_dir, "valeurs_foncieres.txt")
    
    print("1. Téléchargement de l'archive sur le disque local temporaire...")
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

    print("3. Connexion à DuckDB...")
    con = duckdb.connect(DB_FILE)
    con.execute("DROP TABLE IF EXISTS dvf_raw;")

    print("4. Intégration de TOUTES les données de France...")
    print("Cette étape va prendre un peu de temps (plusieurs millions de lignes)...")
    safe_txt_path = txt_path.replace('\\', '/')
    
    # Création de la table complète (sans la clause WHERE)
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

    # Vérification du volume total
    count = con.execute("SELECT COUNT(*) FROM dvf_raw").fetchone()[0]
    print(f"\nSuccès ! {count} lignes ont été insérées au total.")
    
    print("\nAperçu des colonnes :")
    apercu_query = """
    SELECT "Valeur fonciere", "Code departement", "Code commune", "Type local", "Surface reelle bati" 
    FROM dvf_raw 
    LIMIT 5
    """
    print(con.execute(apercu_query).df())
    
    con.close()

    print("\n5. Nettoyage : Suppression des fichiers temporaires...")
    if os.path.exists(zip_path): os.remove(zip_path)
    if os.path.exists(txt_path): os.remove(txt_path)
    print("Terminé ! Votre base France entière est prête.")

if __name__ == "__main__":
    load_full_dvf_to_duckdb()

    #sfd