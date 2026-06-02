import { useState, useEffect } from "react"
import { getCommunes, getBiens, getStats } from "../api/client"
import FilterBar from "../components/FilterBar"
import BienCard from "../components/BienCard"

export default function Recherche() {
  // ── State filtres ──────────────────────────────────────────────
  const [communes, setCommunes]       = useState([])
  const [commune, setCommune]         = useState("")
  const [mode, setMode]               = useState("Achat")
  const [typeLocal, setTypeLocal]     = useState("Tous")
  const [piecesMin, setPiecesMin]     = useState("")
  const [surfMin, setSurfMin]         = useState("")
  const [surfMax, setSurfMax]         = useState("")
  const [prixMin, setPrixMin]         = useState("")
  const [prixMax, setPrixMax]         = useState("")
  const [dpeMax, setDpeMax]           = useState("")
  const [tri, setTri]                 = useState("deal")

  // ── State résultats ────────────────────────────────────────────
  const [biens, setBiens]             = useState([])
  const [stats, setStats]             = useState(null)
  const [loading, setLoading]         = useState(false)
  const [searched, setSearched]       = useState(false)

  // ── Chargement communes ────────────────────────────────────────
  useEffect(() => {
    getCommunes().then(data => {
      setCommunes(data)
      setCommune(data[0] || "")
    })
  }, [])

  // ── Recherche ──────────────────────────────────────────────────
  const handleSearch = async () => {
    if (!commune) return
    setLoading(true)
    setSearched(true)
    try {
      const params = {
        commune,
        type_local: typeLocal,
        pieces_min: piecesMin || 0,
        surf_min:   surfMin   || 0,
        surf_max:   surfMax   || 0,
        prix_min:   prixMin   || 0,
        prix_max:   prixMax   || 0,
        dpe_max:    dpeMax,
        tri,
      }
      const [bienData, statsData] = await Promise.all([
        getBiens(params),
        getStats(commune),
      ])
      setBiens(bienData)
      setStats(statsData)
    } finally {
      setLoading(false)
    }
  }

  // ── Tri côté client ────────────────────────────────────────────
  const biensTries = [...biens].sort((a, b) => {
    if (tri === "prix-asc")  return a.prix - b.prix
    if (tri === "prix-desc") return b.prix - a.prix
    if (tri === "surf-desc") return b.surface - a.surface
    return (a.vs_marche ?? 999) - (b.vs_marche ?? 999)
  })

  const bonnes = biens.filter(b => b.vs_marche < -5).length

  return (
    <div style={{ minHeight: "100vh", background: "#f8f9fa" }}>

      {/* ── Header ── */}
      <div style={{
        background: "#042C53", padding: "14px 24px",
        display: "flex", alignItems: "center", gap: 12,
      }}>
        <span style={{ fontSize: 22 }}>🏠</span>
        <span style={{ color: "#fff", fontWeight: 700, fontSize: 18 }}>
          ImmoBI
        </span>
      </div>

      {/* ── FilterBar ── */}
      <FilterBar
        communes={communes}
        commune={commune}         setCommune={setCommune}
        mode={mode}               setMode={setMode}
        typeLocal={typeLocal}     setTypeLocal={setTypeLocal}
        piecesMin={piecesMin}     setPiecesMin={setPiecesMin}
        surfMin={surfMin}         setSurfMin={setSurfMin}
        surfMax={surfMax}         setSurfMax={setSurfMax}
        prixMin={prixMin}         setPrixMin={setPrixMin}
        prixMax={prixMax}         setPrixMax={setPrixMax}
        dpeMax={dpeMax}           setDpeMax={setDpeMax}
        onSearch={handleSearch}
        loading={loading}
      />

      {/* ── Contenu ── */}
      <div style={{ maxWidth: 1100, margin: "0 auto", padding: "24px 16px" }}>

        {/* Métriques */}
        {searched && stats && (
          <div style={{
            display: "grid", gridTemplateColumns: "repeat(4, 1fr)",
            gap: 12, marginBottom: 24,
          }}>
            {[
              { label: "Annonces",        value: biens.length },
              { label: "Prix médian",     value: stats.prix_median?.toLocaleString("fr-FR") + " €" },
              { label: "Médian / m²",     value: stats.prix_median_m2?.toLocaleString("fr-FR") + " €/m²" },
              { label: "Bonnes affaires", value: `${bonnes} / ${biens.length}` },
            ].map(m => (
              <div key={m.label} style={{
                background: "#fff", border: "1px solid #e8e8e8",
                borderRadius: 12, padding: "14px 18px",
              }}>
                <div style={{ fontSize: 11, color: "#999", marginBottom: 4 }}>{m.label}</div>
                <div style={{ fontSize: 22, fontWeight: 700 }}>{m.value}</div>
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
              style={{
                fontSize: 13, padding: "6px 10px",
                border: "1px solid #ddd", borderRadius: 8,
              }}
            >
              <option value="deal">Meilleures affaires d'abord</option>
              <option value="prix-asc">Prix croissant</option>
              <option value="prix-desc">Prix décroissant</option>
              <option value="surf-desc">Surface décroissante</option>
            </select>
          </div>
        )}

        {/* Loading */}
        {loading && (
          <div style={{ textAlign: "center", padding: 60, color: "#999" }}>
            Chargement...
          </div>
        )}

        {/* Aucun résultat */}
        {searched && !loading && biens.length === 0 && (
          <div style={{ textAlign: "center", padding: 60, color: "#aaa" }}>
            😶 Aucun résultat — essayez d'élargir les filtres.
          </div>
        )}

        {/* Cards */}
        {!loading && (
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {biensTries.map((bien, i) => (
              <BienCard key={i} bien={bien} />
            ))}
          </div>
        )}

        {/* État initial */}
        {!searched && !loading && (
          <div style={{ textAlign: "center", padding: 80, color: "#aaa" }}>
            🔍 Choisissez une commune et lancez la recherche
          </div>
        )}

      </div>
    </div>
  )
}
