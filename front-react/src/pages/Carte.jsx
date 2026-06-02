import { useState, useEffect, useRef } from "react"
import { MapContainer, TileLayer, CircleMarker, Tooltip } from "react-leaflet"
import { getCarte, getAnnees } from "../api/client"
import "leaflet/dist/leaflet.css"

// ── Couleur selon prix/m² ──────────────────────────────────────────────────
function getPrixColor(prix, min, max) {
  const t = Math.min(1, Math.max(0, (prix - min) / (max - min || 1)))
  // Vert (#4caf50) → Orange (#ff9800) → Rouge (#f44336)
  if (t < 0.5) {
    const r = Math.round(76  + (255 - 76)  * (t * 2))
    const g = Math.round(175 + (152 - 175) * (t * 2))
    const b = Math.round(80  + (0   - 80)  * (t * 2))
    return `rgb(${r},${g},${b})`
  } else {
    const r = Math.round(255 + (244 - 255) * ((t - 0.5) * 2))
    const g = Math.round(152 + (67  - 152) * ((t - 0.5) * 2))
    const b = Math.round(0   + (54  - 0)   * ((t - 0.5) * 2))
    return `rgb(${r},${g},${b})`
  }
}

function fmt(n) { return n?.toLocaleString("fr-FR") ?? "—" }

export default function Carte() {
  const [data, setData]           = useState([])
  const [annees, setAnnees]       = useState([])
  const [annee, setAnnee]         = useState(2024)
  const [typeLocal, setTypeLocal] = useState("Tous")
  const [loading, setLoading]     = useState(false)
  const [selected, setSelected]   = useState(null)

  // Chargement des années dispo
  useEffect(() => {
    getAnnees().then(a => {
      setAnnees(a)
      if (a.length > 0) setAnnee(a[0])
    })
  }, [])

  // Chargement des données carte
  const load = async () => {
    setLoading(true)
    try {
      const rows = await getCarte({ type_local: typeLocal, annee })
      setData(rows)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [annee, typeLocal])

  const prixValues = data.map(d => d.prix_median_m2).filter(Boolean)
  const minPrix = Math.min(...prixValues)
  const maxPrix = Math.max(...prixValues)

  // Centre sur la France métropolitaine par défaut
  const center = data.length > 0
    ? [data.reduce((s,d) => s + d.lat, 0) / data.length,
       data.reduce((s,d) => s + d.lng, 0) / data.length]
    : [46.8, 2.3]

  const input = {
    fontSize: 13, padding: "7px 12px",
    border: "1px solid #ddd", borderRadius: 8,
    background: "#fff", cursor: "pointer",
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "calc(100vh - 56px)" }}>

      {/* ── Barre de contrôle ── */}
      <div style={{
        background: "#fff", borderBottom: "1px solid #e8e8e8",
        padding: "12px 24px", display: "flex", gap: 16,
        alignItems: "center", flexWrap: "wrap",
      }}>
        <span style={{ fontWeight: 600, fontSize: 15 }}>
          🗺️ Prix au m² par commune
        </span>

        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <label style={{ fontSize: 12, color: "#888" }}>Année</label>
          <select value={annee} onChange={e => setAnnee(Number(e.target.value))} style={input}>
            {annees.map(a => <option key={a} value={a}>{a}</option>)}
          </select>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <label style={{ fontSize: 12, color: "#888" }}>Type</label>
          <select value={typeLocal} onChange={e => setTypeLocal(e.target.value)} style={input}>
            <option value="Tous">Tous</option>
            <option value="Appartement">Appartement</option>
            <option value="Maison">Maison</option>
          </select>
        </div>

        {loading && (
          <span style={{ fontSize: 12, color: "#999" }}>Chargement...</span>
        )}

        {!loading && data.length > 0 && (
          <span style={{ fontSize: 12, color: "#999", marginLeft: "auto" }}>
            {data.length} communes · {fmt(minPrix)} – {fmt(maxPrix)} €/m²
          </span>
        )}
      </div>

      {/* ── Carte + légende ── */}
      <div style={{ flex: 1, position: "relative" }}>

        <MapContainer
          center={center}
          zoom={data.length > 0 ? 8 : 6}
          style={{ width: "100%", height: "100%" }}
          scrollWheelZoom={true}
        >
          <TileLayer
            attribution='© <a href="https://www.openstreetmap.org/">OpenStreetMap</a>'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />

          {data.map((d, i) => {
            const color  = getPrixColor(d.prix_median_m2, minPrix, maxPrix)
            const radius = Math.max(6, Math.min(20,
              6 + (d.nb_transactions / 50)
            ))
            return (
              <CircleMarker
                key={i}
                center={[d.lat, d.lng]}
                radius={radius}
                pathOptions={{
                  fillColor:   color,
                  fillOpacity: 0.8,
                  color:       "#fff",
                  weight:      1.5,
                }}
                eventHandlers={{
                  click: () => setSelected(d),
                }}
              >
                <Tooltip direction="top" offset={[0, -8]}>
                  <div style={{ fontFamily: "sans-serif", fontSize: 12 }}>
                    <strong>{d.commune}</strong><br />
                    {fmt(d.prix_median_m2)} €/m²<br />
                    {fmt(d.nb_transactions)} transactions
                  </div>
                </Tooltip>
              </CircleMarker>
            )
          })}
        </MapContainer>

        {/* ── Légende ── */}
        <div style={{
          position: "absolute", bottom: 24, left: 16, zIndex: 1000,
          background: "rgba(255,255,255,0.95)", borderRadius: 10,
          padding: "12px 16px", boxShadow: "0 2px 8px rgba(0,0,0,.12)",
          minWidth: 160,
        }}>
          <div style={{ fontSize: 11, fontWeight: 600, marginBottom: 8, color: "#555" }}>
            PRIX MÉDIAN / m²
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4 }}>
            <div style={{ width: 120, height: 10, borderRadius: 999,
              background: "linear-gradient(to right, #4caf50, #ff9800, #f44336)" }} />
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, color: "#888" }}>
            <span>{fmt(minPrix)} €</span>
            <span>{fmt(maxPrix)} €</span>
          </div>
          <div style={{ marginTop: 10, fontSize: 11, color: "#888" }}>
            <span style={{ fontSize: 13 }}>⬤ </span> taille = nb transactions
          </div>
        </div>

        {/* ── Fiche commune sélectionnée ── */}
        {selected && (
          <div style={{
            position: "absolute", top: 16, right: 16, zIndex: 1000,
            background: "#fff", borderRadius: 12, padding: "16px 20px",
            boxShadow: "0 4px 16px rgba(0,0,0,.12)", minWidth: 200,
          }}>
            <div style={{
              display: "flex", justifyContent: "space-between",
              alignItems: "flex-start", marginBottom: 12,
            }}>
              <strong style={{ fontSize: 15 }}>{selected.commune}</strong>
              <button onClick={() => setSelected(null)} style={{
                background: "none", border: "none", cursor: "pointer",
                fontSize: 16, color: "#aaa", lineHeight: 1,
              }}>✕</button>
            </div>
            {[
              { label: "Prix médian/m²",   value: fmt(selected.prix_median_m2) + " €" },
              { label: "Prix moyen/m²",    value: fmt(selected.prix_moyen_m2)  + " €" },
              { label: "Transactions",     value: fmt(selected.nb_transactions) },
            ].map(row => (
              <div key={row.label} style={{
                display: "flex", justifyContent: "space-between",
                fontSize: 13, marginBottom: 6,
              }}>
                <span style={{ color: "#888" }}>{row.label}</span>
                <span style={{ fontWeight: 600 }}>{row.value}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
