import duckdb
import pandas as pd

# Connexion à la base de données
con = duckdb.connect("real_estate_bi.duckdb")

# === LA CORRECTION EST ICI ===
# On active l'extension spatiale pour pouvoir lire la colonne 'geom'
con.execute("INSTALL spatial; LOAD spatial;")
# =============================

print("==================================================")
print("       INSPECTION DE LA BASE DE DONNÉES           ")
print("==================================================")

# 1. LECTURE DE LA TABLE DVF (TRANSACTIONS BRUTES)
print("\n--- 1. TABLE [dvf_raw] (Transactions Immobilières) ---")
print("Colonnes disponibles :")
print(con.execute("DESCRIBE dvf_raw;").df()[['column_name', 'column_type']].head(8).to_string(index=False) + "\n... (et autres)")

print("\nAperçu (5 premières lignes) :")
df_dvf = con.execute('SELECT "Date mutation", "Valeur fonciere", "Code departement", "Type local" FROM dvf_raw LIMIT 5;').df()
print(df_dvf)


# 2. LECTURE DE LA TABLE PEB (ZONES DE BRUIT)
print("\n" + "="*50)
print("\n--- 2. TABLE [peb_raw] (Zones de Bruit DGAC) ---")
print("Colonnes disponibles :")
print(con.execute("DESCRIBE peb_raw;").df()[['column_name', 'column_type']].to_string(index=False))

print("\nAperçu (5 premières lignes) :")
df_peb = con.execute('SELECT peb_zone, ST_GeometryType(geom) as type_geometrie FROM peb_raw LIMIT 5;').df()
print(df_peb)


# 3. LECTURE DE LA NOUVELLE TABLE GÉOLOCALISÉE
print("\n" + "="*50)
print("\n--- 3. TABLE [dvf_echantillon_gps] (Adresses Géolocalisées via l'API BAN) ---")

tables_existantes = con.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'").df()['table_name'].tolist()

if 'dvf_echantillon_gps' in tables_existantes:
    print("Colonnes disponibles :")
    print(con.execute("DESCRIBE dvf_echantillon_gps;").df()[['column_name', 'column_type']].to_string(index=False))
    
    print("\nAperçu (5 premières lignes) :")
    df_gps = con.execute('SELECT "Valeur fonciere", "Type local", longitude, latitude FROM dvf_echantillon_gps LIMIT 5;').df()
    print(df_gps)
else:
    print("La table 'dvf_echantillon_gps' n'existe pas encore.")
    print("Vous devez d'abord exécuter le script DVF.py pour créer la jointure avec l'API BAN.")

con.close()
print("\n==================================================")