import duckdb
import requests
import zipfile
import shutil
import os
import tempfile

# --- Configuration ---
DVF_URL = "https://www.data.gouv.fr/api/1/datasets/r/902db087-b0eb-4cbb-a968-0b499bde5bc4"
DB_FILE = "real_estate_bi.duckdb" # Sera créé sur votre espace H:
DEPARTEMENT_CIBLE = '56' # Filtrage sur le Morbihan pour économiser l'espace

def load_dvf_to_duckdb():
    # On demande à Windows où se trouve son dossier temporaire (généralement sur le C:)
    temp_dir = tempfile.gettempdir()
    zip_path = os.path.join(temp_dir, "archive_dvf.zip")
    txt_path = os.path.join(temp_dir, "valeurs_foncieres.txt")
    
    print(f"1. Téléchargement de l'archive sur le disque local temporaire...")
    with requests.get(DVF_URL, stream=True) as r:
        r.raise_for_status()
        with open(zip_path, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
                
    print("2. Extraction du fichier texte...")
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        fichiers = zip_ref.namelist()
        # Extraction séquentielle vers le C:
        with zip_ref.open(fichiers[0]) as source, open(txt_path, "wb") as cible:
            shutil.copyfileobj(source, cible)

    print("3. Connexion à DuckDB (sur votre espace réseau H:)...")
    con = duckdb.connect(DB_FILE)
    con.execute("DROP TABLE IF EXISTS dvf_raw;")

    print(f"4. Intégration et filtrage (Uniquement le département {DEPARTEMENT_CIBLE})...")
    # DuckDB préfère les slashs (/) plutôt que les antislashs (\) de Windows pour les chemins
    safe_txt_path = txt_path.replace('\\', '/')
    
    # On ajoute la clause WHERE pour diviser la taille par 100
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
    )
    WHERE starts_with(Code_commune, '{DEPARTEMENT_CIBLE}');
    """
    con.execute(query)

    count = con.execute("SELECT COUNT(*) FROM dvf_raw").fetchone()[0]
    print(f"\nSuccès ! {count} lignes ont été insérées pour ce département.")
    
    print("\nAperçu des colonnes :")
    print(con.execute("SELECT Valeur_fonciere, Code_commune, Type_local, Surface_reelle_bati FROM dvf_raw LIMIT 5").df())
    
    con.close()

    print("\n5. Nettoyage : Suppression des fichiers géants du disque local...")
    # On efface les traces pour ne pas encombrer l'ordinateur
    if os.path.exists(zip_path): os.remove(zip_path)
    if os.path.exists(txt_path): os.remove(txt_path)
    print("Terminé. L'espace réseau est préservé !")

if __name__ == "__main__":
    load_dvf_to_duckdb()