import { useState, useEffect } from "react"
import { MapContainer, TileLayer, CircleMarker, Tooltip } from "react-leaflet"
import { getCarte, getAnnees } from "../api/client"
import "leaflet/dist/leaflet.css"

const DPE_COLORS = {
  A: "#009966", B: "#33cc66", C: "#99cc00",
  D: "#ffcc00", E: "#ff9900", F: "#ff6600", G: "#cc0000",
}

function getPrixColor(prix, min, max) {
  const t = Math.min(1, Math.max(0, (prix - min) / (max - min || 1)))
  if (t < 0.5) {
    const r = Math.round(76  + (255 - 76)  * (t * 2))
    const g = Math.round(175 + (152 - 175) * (t * 2))
    const b = Math.round(80  + (0   - 80)  * (t * 2))
    return `rgb(${r},${g},${b})`
  }
  const r = Math.round(255 + (244 - 255) * ((t - 0.5) * 2))
  const g = Math.round(152 + (67  - 152) * ((t - 0.5) * 2))
  const b = Math.round(0   + (54  - 0)   * ((t - 0.5) * 2))
  return `rgb(${r},${g},${b})`
}

function fmt(n) { return n?.toLocaleString("fr-FR") ?? "—" }

export default function Carte() {
  const [data, setData]           = useState([])
  const [annees, setAnnees]       = useState([])
  const [annee, setAnnee]         = useState(2024)
  const [typeLocal, setTypeLocal] = useState("Tous")
  const [colorMode, setColorMode] = useState("prix")   // "prix" | "transport" | "dpe"
  const [loading, setLoading]     = useState(false)
  const [selected, setSelected]   = useState(null)

  useEffect(() => {
    getAnnees().then(a => {
      setAnnees(a)
      if (a.length > 0) setAnnee(a[0])
    })
  }, [])

  useEffect(() => {
    setLoading(true)
    getCarte({ type_local: typeLocal, annee })
      .then(rows => setData(rows))
      .finally(() => setLoading(false))
  }, [annee, typeLocal])

  const prixValues = data.map(d => d.prix_median_m2).filter(Boolean)
  const minPrix = Math.min(...prixValues)
  const maxPrix = Math.max(...prixValues)

  const distValues = data.map(d => d.distance_arret_mediane).filter(Boolean)
  const minDist = Math.min(...distValues)
  const maxDist = Math.max(...distValues)

  function getColor(d) {
    if (colorMode === "transport") {
      // Vert = proche, Rouge = loin
      const t = Math.min(1, Math.max(0,
        (d.distance_arret_mediane - minDist) / (maxDist - minDist || 1)
      ))
      const r = Math.round(76  + (244 - 76)  * t)
      const g = Math.round(175 + (67  - 175) * t)
      const b = Math.round(80  + (54  - 80)  * t)
      return `rgb(${r},${g},${b})`
    }
    if (colorMode === "dpe") {
      return DPE_COLORS[d.dpe_dominant] ?? "#aaa"
    }
    return getPrixColor(d.prix_median_m2, minPrix, maxPrix)
  }

  const center = data.length > 0
    ? [
        data.reduce((s, d) => s + d.lat, 0) / data.length,
        data.reduce((s, d) => s + d.lng, 0) / data.length,
      ]
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
        <span style={{ fontWeight: 600, fontSize: 15 }}>🗺️ Carte immobilière</span>

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

        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <label style={{ fontSize: 12, color: "#888" }}>Couleur</label>
          <select value={colorMode} onChange={e => setColorMode(e.target.value)} style={input}>
            <option value="prix">Prix / m²</option>
            <option value="transport">Proximité transport</option>
            <option value="dpe">DPE dominant</option>
          </select>
        </div>

        {loading && <span style={{ fontSize: 12, color: "#999" }}>Chargement...</span>}

        {!loading && data.length > 0 && (
          <span style={{ fontSize: 12, color: "#999", marginLeft: "auto" }}>
            {data.length} communes · {fmt(minPrix)} – {fmt(maxPrix)} €/m²
          </span>
        )}
      </div>

      {/* ── Carte ── */}
      <div style={{ flex: 1, position: "relative" }}>
        <MapContainer
          center={center}
          zoom={data.length > 0 ? 8 : 6}
          style={{ width: "100%", height: "100%" }}
          scrollWheelZoom
        >
          <TileLayer
            attribution='© <a href="https://www.openstreetmap.org/">OpenStreetMap</a>'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />

          {data.map((d, i) => (
            <CircleMarker
              key={i}
              center={[d.lat, d.lng]}
              radius={Math.max(6, Math.min(20, 6 + d.nb_transactions / 50))}
              pathOptions={{
                fillColor:   getColor(d),
                fillOpacity: 0.82,
                color:       "#fff",
                weight:      1.5,
              }}
              eventHandlers={{ click: () => setSelected(d) }}
            >
              <Tooltip direction="top" offset={[0, -8]}>
                <div style={{ fontFamily: "sans-serif", fontSize: 12 }}>
                  <strong>{d.commune}</strong><br />
                  {fmt(d.prix_median_m2)} €/m²<br />
                  🚌 {fmt(d.distance_arret_mediane)} m · {d.dpe_dominant ?? "—"}<br />
                  {fmt(d.nb_transactions)} transactions
                </div>
              </Tooltip>
            </CircleMarker>
          ))}
        </MapContainer>

        {/* ── Légende ── */}
        <div style={{
          position: "absolute", bottom: 24, left: 16, zIndex: 1000,
          background: "rgba(255,255,255,0.95)", borderRadius: 10,
          padding: "12px 16px", boxShadow: "0 2px 8px rgba(0,0,0,.12)",
          minWidth: 160,
        }}>
          {colorMode === "prix" && (
            <>
              <div style={{ fontSize: 11, fontWeight: 600, marginBottom: 8, color: "#555" }}>
                PRIX MÉDIAN / m²
              </div>
              <div style={{
                width: 120, height: 10, borderRadius: 999,
                background: "linear-gradient(to right, #4caf50, #ff9800, #f44336)",
                marginBottom: 4,
              }} />
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, color: "#888" }}>
                <span>{fmt(minPrix)} €</span>
                <span>{fmt(maxPrix)} €</span>
              </div>
            </>
          )}
          {colorMode === "transport" && (
            <>
              <div style={{ fontSize: 11, fontWeight: 600, marginBottom: 8, color: "#555" }}>
                PROXIMITÉ TRANSPORT
              </div>
              <div style={{
                width: 120, height: 10, borderRadius: 999,
                background: "linear-gradient(to right, #4caf50, #f44336)",
                marginBottom: 4,
              }} />
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, color: "#888" }}>
                <span>Proche</span>
                <span>Loin</span>
              </div>
            </>
          )}
          {colorMode === "dpe" && (
            <>
              <div style={{ fontSize: 11, fontWeight: 600, marginBottom: 8, color: "#555" }}>
                DPE DOMINANT
              </div>
              {Object.entries(DPE_COLORS).map(([k, c]) => (
                <div key={k} style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 2 }}>
                  <div style={{ width: 12, height: 12, borderRadius: 2, background: c }} />
                  <span style={{ fontSize: 11, color: "#555" }}>Classe {k}</span>
                </div>
              ))}
            </>
          )}
          <div style={{ marginTop: 10, fontSize: 11, color: "#888" }}>
            ⬤ taille = nb transactions
          </div>
        </div>

        {/* ── Fiche commune sélectionnée ── */}
        {selected && (
          <div style={{
            position: "absolute", top: 16, right: 16, zIndex: 1000,
            background: "#fff", borderRadius: 12, padding: "16px 20px",
            boxShadow: "0 4px 16px rgba(0,0,0,.12)", minWidth: 220,
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
              { label: "Prix médian/m²",       value: fmt(selected.prix_median_m2) + " €" },
              { label: "Prix moyen/m²",         value: fmt(selected.prix_moyen_m2)  + " €" },
              { label: "Transactions",          value: fmt(selected.nb_transactions) },
              { label: "Arrêt médian",          value: fmt(selected.distance_arret_mediane) + " m" },
              { label: "Arrêts dans 1 km",      value: fmt(selected.moy_arrets_1km) },
              { label: "DPE dominant",          value: selected.dpe_dominant ?? "—" },
              { label: "% passoires",           value: selected.pct_passoires != null ? selected.pct_passoires + "%" : "—" },
              { label: "En zone PEB",           value: selected.nb_en_peb > 0 ? `Oui (${selected.nb_en_peb})` : "Non" },
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
