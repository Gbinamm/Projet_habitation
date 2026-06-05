import duckdb

# Connexion à la base Nimbus
conn = duckdb.connect('immo_et_bruit.duckdb')

# Affichage des colonnes de la table dvf_enrichi
print("--- Structure de la table dvf_enrichi ---")
columns = conn.execute("PRAGMA table_info('dvf_enrichi')").df()
print(columns[['name', 'type']])

# Aperçu des données de transport pour vérifier la casse (ex: 'Bus', 'Tramway')
print("\n--- Aperçu des modes de transport disponibles ---")
modes = conn.execute("SELECT DISTINCT mode_transport_proche FROM dvf_enrichi WHERE mode_transport_proche IS NOT NULL").fetchall()
print(modes)