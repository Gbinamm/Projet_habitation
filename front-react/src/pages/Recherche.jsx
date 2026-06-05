import { useState, useEffect } from "react"
import { getCommunes, getAnnees, getBiens, getStats } from "../api/client"
import FilterBar from "../components/FilterBar"
import BienCard  from "../components/BienCard"

function StatCard({ label, value, accent }) {
  return (
    <div style={{
      background: accent ? "var(--brand)" : "var(--surface)",
      border: `1.5px solid ${accent ? "var(--brand)" : "var(--border)"}`,
      borderRadius: 14, padding: "14px 18px",
    }}>
      <div style={{ fontSize:11, color: accent ? "rgba(255,255,255,.7)" : "var(--muted)",
        marginBottom:5, fontWeight:500, textTransform:"uppercase", letterSpacing:"0.04em" }}>
        {label}
      </div>
      <div style={{ fontSize:18, fontWeight:700, color: accent ? "#fff" : "var(--text)" }}>
        {value}
      </div>
    </div>
  )
}

export default function Recherche() {
  const [communes, setCommunes]   = useState([])
  const [commune, setCommune]     = useState("")
  const [annees, setAnnees]       = useState([])
  const [annee, setAnnee]         = useState(0)
  const [typeLocal, setTypeLocal] = useState("Tous")
  const [piecesMin, setPiecesMin] = useState("")
  const [surfMin, setSurfMin]     = useState("")
  const [surfMax, setSurfMax]     = useState("")
  const [prixMin, setPrixMin]     = useState("")
  const [prixMax, setPrixMax]     = useState("")
  const [dpeMax, setDpeMax]       = useState("")
  const [distMax, setDistMax]     = useState("")
  const [tri, setTri]             = useState("deal")
  const [biens, setBiens]         = useState([])
  const [stats, setStats]         = useState(null)
  const [loading, setLoading]     = useState(false)
  const [searched, setSearched]   = useState(false)
  const [error, setError]         = useState(null)

  useEffect(() => {
    getCommunes().then(d => { setCommunes(d); if (d.length) setCommune(d[0]) })
    getAnnees().then(setAnnees)
  }, [])

  const handleSearch = async () => {
    if (!commune) return
    setLoading(true); setSearched(true); setError(null)
    try {
      const params = {
        commune, annee: annee || 0, type_local: typeLocal,
        pieces_min: piecesMin ? Number(piecesMin) : 0,
        surf_min: surfMin ? Number(surfMin) : 0,
        surf_max: surfMax ? Number(surfMax) : 0,
        prix_min: prixMin ? Number(prixMin) : 0,
        prix_max: prixMax ? Number(prixMax) : 0,
        dpe_max: dpeMax, dist_max: distMax ? Number(distMax) : 0,
        tri, limit: 100,
      }
      const [bienData, statsData] = await Promise.all([
        getBiens(params),
        getStats(commune, annee || 0),
      ])
      setBiens(bienData); setStats(statsData)
    } catch (e) {
      setError(e?.response?.data?.detail ?? e.message ?? "Erreur réseau")
      setBiens([]); setStats(null)
    } finally { setLoading(false) }
  }

  const biensTries = [...biens].sort((a, b) => {
    if (tri === "prix-asc")  return a.prix - b.prix
    if (tri === "prix-desc") return b.prix - a.prix
    if (tri === "surf-desc") return b.surface - a.surface
    if (tri === "transport") return (a.distance_arret_m ?? 9999) - (b.distance_arret_m ?? 9999)
    return (a.vs_marche ?? 999) - (b.vs_marche ?? 999)
  })

  const bonnes = biens.filter(b => (b.vs_marche ?? 0) < -5).length

  return (
    <div style={{ minHeight:"100vh", background:"var(--bg)" }}>
      <FilterBar
        communes={communes} commune={commune} setCommune={setCommune}
        annees={annees} annee={annee} setAnnee={setAnnee}
        typeLocal={typeLocal} setTypeLocal={setTypeLocal}
        piecesMin={piecesMin} setPiecesMin={setPiecesMin}
        surfMin={surfMin} setSurfMin={setSurfMin}
        surfMax={surfMax} setSurfMax={setSurfMax}
        prixMin={prixMin} setPrixMin={setPrixMin}
        prixMax={prixMax} setPrixMax={setPrixMax}
        dpeMax={dpeMax} setDpeMax={setDpeMax}
        distMax={distMax} setDistMax={setDistMax}
        onSearch={handleSearch} loading={loading}
      />

      <div style={{ maxWidth:1100, margin:"0 auto", padding:"28px 20px" }}>

        {error && (
          <div style={{ background:"#FFF1F0", color:"#DC2626", border:"1px solid #FECACA",
            borderRadius:12, padding:"12px 16px", marginBottom:20, fontSize:13 }}>
            ⚠️ {error}
          </div>
        )}

        {searched && stats && !error && (
          <div style={{ display:"grid", gridTemplateColumns:"repeat(auto-fit, minmax(140px, 1fr))", gap:10, marginBottom:28 }}>
            <StatCard label="Résultats"       value={biens.length} accent />
            <StatCard label="Prix médian"      value={(stats.prix_median?.toLocaleString("fr-FR") ?? "—") + " €"} />
            <StatCard label="Médian / m²"      value={(stats.prix_median_m2?.toLocaleString("fr-FR") ?? "—") + " €/m²"} />
            <StatCard label="Bonnes affaires"  value={`${bonnes} / ${biens.length}`} />
            <StatCard label="Arrêt médian"     value={stats.distance_arret_mediane != null ? stats.distance_arret_mediane + " m" : "—"} />
            <StatCard label="DPE dominant"     value={stats.dpe_dominant ?? "—"} />
            <StatCard label="% passoires"      value={stats.pct_passoires_moyen != null ? stats.pct_passoires_moyen + "%" : "—"} />
            <StatCard label="Réseau transport" value={stats.reseau_principal ?? "—"} />
          </div>
        )}

        {searched && biens.length > 0 && (
          <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center", marginBottom:16 }}>
            <span style={{ fontSize:13, color:"var(--muted)" }}>
              {biens.length} résultat{biens.length > 1 ? "s" : ""}
            </span>
            <select value={tri} onChange={e => setTri(e.target.value)} style={{
              fontSize:13, padding:"6px 12px", border:"1.5px solid var(--border)",
              borderRadius:10, background:"var(--surface)", outline:"none",
            }}>
              <option value="deal">Meilleures affaires</option>
              <option value="prix-asc">Prix croissant</option>
              <option value="prix-desc">Prix décroissant</option>
              <option value="surf-desc">Surface décroissante</option>
              <option value="transport">Plus proche transport</option>
            </select>
          </div>
        )}

        {loading && (
          <div style={{ textAlign:"center", padding:80, color:"var(--muted)" }}>
            <div style={{ fontSize:28, marginBottom:12 }}>🪺</div>
            Chargement…
          </div>
        )}

        {searched && !loading && !error && biens.length === 0 && (
          <div style={{ textAlign:"center", padding:80, color:"var(--muted)" }}>
            <div style={{ fontSize:32, marginBottom:12 }}>🔍</div>
            Aucun résultat — essayez d'élargir les filtres.
          </div>
        )}

        {!loading && (
          <div style={{ display:"flex", flexDirection:"column", gap:10 }}>
            {biensTries.map((b, i) => <BienCard key={b.id_mutation ?? i} bien={b} />)}
          </div>
        )}

        {!searched && !loading && (
          <div style={{ textAlign:"center", padding:100, color:"var(--muted)" }}>
            <div style={{ fontSize:40, marginBottom:16 }}>🪺</div>
            <div style={{ fontSize:16, fontWeight:600, color:"var(--text)", marginBottom:8 }}>
              Trouvez votre nimbus
            </div>
            <div style={{ fontSize:13 }}>Choisissez une commune et lancez la recherche</div>
          </div>
        )}

      </div>
    </div>
  )
}
