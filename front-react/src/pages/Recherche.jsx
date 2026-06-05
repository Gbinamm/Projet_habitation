import { useState, useEffect } from "react"
import { getCommunes, getAnnees, getBiens, getStats } from "../api/client"
import FilterBar from "../components/FilterBar"
import BienCard from "../components/BienCard"

export default function Recherche() {
  // ── Filtres ────────────────────────────────────────────────────
  const [communes, setCommunes]   = useState([])
  const [commune, setCommune]     = useState("")
  const [annees, setAnnees]       = useState([])
  const [annee, setAnnee]         = useState(0)    // 0 = auto (2 dernières de la commune)
  const [typeLocal, setTypeLocal] = useState("Tous")
  const [piecesMin, setPiecesMin] = useState("")
  const [surfMin, setSurfMin]     = useState("")
  const [surfMax, setSurfMax]     = useState("")
  const [prixMin, setPrixMin]     = useState("")
  const [prixMax, setPrixMax]     = useState("")
  const [dpeMax, setDpeMax]       = useState("")
  const [distMax, setDistMax]     = useState("")
  const [tri, setTri]             = useState("deal")

  // ── Résultats ──────────────────────────────────────────────────
  const [biens, setBiens]         = useState([])
  const [stats, setStats]         = useState(null)
  const [loading, setLoading]     = useState(false)
  const [searched, setSearched]   = useState(false)
  const [error, setError]         = useState(null)

  useEffect(() => {
    getCommunes().then(data => {
      setCommunes(data)
      if (data.length > 0) setCommune(data[0])
    })
    getAnnees().then(data => setAnnees(data))
  }, [])

  const handleSearch = async () => {
    if (!commune) return
    setLoading(true)
    setSearched(true)
    setError(null)
    try {
      const params = {
        commune,
        annee:      annee || 0,
        type_local: typeLocal,
        pieces_min: piecesMin ? Number(piecesMin) : 0,
        surf_min:   surfMin   ? Number(surfMin)   : 0,
        surf_max:   surfMax   ? Number(surfMax)   : 0,
        prix_min:   prixMin   ? Number(prixMin)   : 0,
        prix_max:   prixMax   ? Number(prixMax)   : 0,
        dpe_max:    dpeMax,
        dist_max:   distMax   ? Number(distMax)   : 0,
        tri,
        limit: 100,
      }
      const [bienData, statsData] = await Promise.all([
        getBiens(params),
        getStats(commune, annee || 0),
      ])
      setBiens(bienData)
      setStats(statsData)
    } catch (e) {
      setError(e?.response?.data?.detail ?? e.message ?? "Erreur réseau")
      setBiens([])
      setStats(null)
    } finally {
      setLoading(false)
    }
  }

  // Tri côté client (le backend trie déjà, mais on permet le retri sans requête)
  const biensTries = [...biens].sort((a, b) => {
    if (tri === "prix-asc")  return a.prix - b.prix
    if (tri === "prix-desc") return b.prix - a.prix
    if (tri === "surf-desc") return b.surface - a.surface
    if (tri === "transport") return (a.distance_arret_m ?? 9999) - (b.distance_arret_m ?? 9999)
    return (a.vs_marche ?? 999) - (b.vs_marche ?? 999)
  })

  const bonnes = biens.filter(b => (b.vs_marche ?? 0) < -5).length

  return (
    <div style={{ minHeight: "100vh", background: "#f8f9fa" }}>

      {/* FilterBar */}
      <FilterBar
        communes={communes}
        commune={commune}         setCommune={setCommune}
        annees={annees}           annee={annee}   setAnnee={setAnnee}
        typeLocal={typeLocal}     setTypeLocal={setTypeLocal}
        piecesMin={piecesMin}     setPiecesMin={setPiecesMin}
        surfMin={surfMin}         setSurfMin={setSurfMin}
        surfMax={surfMax}         setSurfMax={setSurfMax}
        prixMin={prixMin}         setPrixMin={setPrixMin}
        prixMax={prixMax}         setPrixMax={setPrixMax}
        dpeMax={dpeMax}           setDpeMax={setDpeMax}
        distMax={distMax}         setDistMax={setDistMax}
        onSearch={handleSearch}
        loading={loading}
      />

      <div style={{ maxWidth: 1100, margin: "0 auto", padding: "24px 16px" }}>

        {/* Erreur */}
        {error && (
          <div style={{
            background: "#ffebee", color: "#c62828", borderRadius: 10,
            padding: "12px 16px", marginBottom: 16, fontSize: 13,
          }}>
            ⚠️ {error}
          </div>
        )}

        {/* Métriques */}
        {searched && stats && !error && (
          <div style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))",
            gap: 12, marginBottom: 24,
          }}>
            {[
              { label: "Résultats",           value: biens.length },
              { label: "Prix médian",          value: stats.prix_median?.toLocaleString("fr-FR") + " €" },
              { label: "Médian / m²",          value: stats.prix_median_m2?.toLocaleString("fr-FR") + " €/m²" },
              { label: "Bonnes affaires",      value: `${bonnes} / ${biens.length}` },
              { label: "Arrêt médian",         value: stats.distance_arret_mediane != null ? stats.distance_arret_mediane + " m" : "—" },
              { label: "DPE dominant",         value: stats.dpe_dominant ?? "—" },
              { label: "% passoires",          value: stats.pct_passoires_moyen != null ? stats.pct_passoires_moyen + "%" : "—" },
              { label: "Réseau transport",     value: stats.reseau_principal ?? "—" },
            ].map(m => (
              <div key={m.label} style={{
                background: "#fff", border: "1px solid #e8e8e8",
                borderRadius: 12, padding: "14px 18px",
              }}>
                <div style={{ fontSize: 11, color: "#999", marginBottom: 4 }}>{m.label}</div>
                <div style={{ fontSize: 17, fontWeight: 700 }}>{m.value}</div>
              </div>
            ))}
          </div>
        )}

        {/* Tri + compteur */}
        {searched && biens.length > 0 && (
          <div style={{
            display: "flex", justifyContent: "space-between",
            alignItems: "center", marginBottom: 14,
          }}>
            <span style={{ fontSize: 13, color: "#666" }}>
              {biens.length} résultat{biens.length > 1 ? "s" : ""}
            </span>
            <select
              value={tri}
              onChange={e => setTri(e.target.value)}
              style={{ fontSize: 13, padding: "6px 10px", border: "1px solid #ddd", borderRadius: 8 }}
            >
              <option value="deal">Meilleures affaires d'abord</option>
              <option value="prix-asc">Prix croissant</option>
              <option value="prix-desc">Prix décroissant</option>
              <option value="surf-desc">Surface décroissante</option>
              <option value="transport">Plus proche transport</option>
            </select>
          </div>
        )}

        {loading && (
          <div style={{ textAlign: "center", padding: 60, color: "#999" }}>Chargement…</div>
        )}

        {searched && !loading && !error && biens.length === 0 && (
          <div style={{ textAlign: "center", padding: 60, color: "#aaa" }}>
            😶 Aucun résultat — essayez d'élargir les filtres.
          </div>
        )}

        {!loading && (
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {biensTries.map((bien, i) => (
              <BienCard key={bien.id_mutation ?? i} bien={bien} />
            ))}
          </div>
        )}

        {!searched && !loading && (
          <div style={{ textAlign: "center", padding: 80, color: "#aaa" }}>
            🔍 Choisissez une commune et lancez la recherche
          </div>
        )}
      </div>
    </div>
  )
}
