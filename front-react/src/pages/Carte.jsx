import { useState, useEffect, useCallback, useRef } from "react"
import { MapContainer, TileLayer, GeoJSON, CircleMarker, Tooltip, useMap } from "react-leaflet"
import { getGeoJson, getCarteCommune, getAnnees } from "../api/client"
import "leaflet/dist/leaflet.css"

// ─── Constantes ─────────────────────────────────────────────────────────────
const DPE_COLORS = {
  A: "#009966", B: "#33cc66", C: "#99cc00",
  D: "#ffcc00", E: "#ff9900", F: "#ff6600", G: "#cc0000",
}
const inputStyle = {
  fontSize: 13, padding: "6px 10px",
  border: "1px solid #ddd", borderRadius: 8,
  background: "#fff", width: "100%",
}
const labelStyle = { fontSize: 11, color: "#888", marginBottom: 3, display: "block" }
function Field({ label, children }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", minWidth: 90 }}>
      <label style={labelStyle}>{label}</label>
      {children}
    </div>
  )
}
function fmt(n) { return n?.toLocaleString("fr-FR") ?? "—" }

// ─── Gradient prix → couleur ─────────────────────────────────────────────────
function getPrixColor(prix, min, max) {
  if (!prix) return "#cccccc"
  const t = Math.min(1, Math.max(0, (prix - min) / (max - min || 1)))
  if (t < 0.5) {
    return `rgb(${Math.round(76+(255-76)*(t*2))},${Math.round(175+(152-175)*(t*2))},${Math.round(80+(0-80)*(t*2))})`
  }
  return `rgb(${Math.round(255+(244-255)*((t-.5)*2))},${Math.round(152+(67-152)*((t-.5)*2))},${Math.round((54)*((t-.5)*2))})`
}

// ─── Zoom automatique sur un polygone ────────────────────────────────────────
function FlyToCommune({ bounds }) {
  const map = useMap()
  useEffect(() => {
    if (bounds) map.flyToBounds(bounds, { padding: [40, 40], maxZoom: 14 })
  }, [bounds, map])
  return null
}

// ─── Fiche offre ─────────────────────────────────────────────────────────────
function FicheOffre({ item, onClose }) {
  const dpeColor = DPE_COLORS[item.dpe] ?? "#ccc"
  const good = item.vs_marche != null && item.vs_marche < -5
  const bad  = item.vs_marche != null && item.vs_marche > 10
  return (
    <div style={{
      position: "absolute", top: 16, right: 16, zIndex: 1000,
      background: "#fff", borderRadius: 14, padding: "18px 20px",
      boxShadow: "0 4px 20px rgba(0,0,0,.15)", width: 280,
      maxHeight: "80vh", overflowY: "auto",
    }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 12 }}>
        <div>
          <div style={{ fontWeight: 700, fontSize: 15 }}>{item.type_local} · {fmt(item.surface)} m²</div>
          <div style={{ fontSize: 12, color: "#888", marginTop: 2 }}>{item.commune}</div>
        </div>
        <button onClick={onClose} style={{ background:"none", border:"none", cursor:"pointer", fontSize:18, color:"#bbb" }}>✕</button>
      </div>

      <div style={{ display:"flex", alignItems:"baseline", gap:8, marginBottom:10 }}>
        <span style={{ fontSize:22, fontWeight:800 }}>{fmt(item.prix)} €</span>
        <span style={{ fontSize:13, color:"#888" }}>{fmt(item.prix_m2)} €/m²</span>
      </div>

      {item.vs_marche != null && (
        <div style={{
          display:"inline-block", marginBottom:12,
          background: good?"#e8f5e9":bad?"#ffebee":"#f5f5f5",
          color: good?"#2e7d32":bad?"#c62828":"#555",
          borderRadius:6, padding:"3px 10px", fontSize:12, fontWeight:600,
        }}>
          {item.vs_marche > 0 ? "+" : ""}{item.vs_marche}% vs marché
        </div>
      )}

      <hr style={{ border:"none", borderTop:"1px solid #f0f0f0", margin:"10px 0" }} />

      {[
        { label:"Pièces",          value: item.pieces ? `${item.pieces} pièce${item.pieces>1?"s":""}` : null },
        { label:"Surface terrain", value: item.surface_terrain ? `${fmt(item.surface_terrain)} m²` : null },
        { label:"Date",            value: item.date },
        { label:"Adresse",        value: item.adresse },
      ].filter(r => r.value).map(row => (
        <div key={row.label} style={{ display:"flex", justifyContent:"space-between", fontSize:13, marginBottom:6 }}>
          <span style={{ color:"#888" }}>{row.label}</span>
          <span style={{ fontWeight:500, textAlign:"right", maxWidth:160 }}>{row.value}</span>
        </div>
      ))}

      {item.dpe && (
        <>
          <hr style={{ border:"none", borderTop:"1px solid #f0f0f0", margin:"10px 0" }} />
          <div style={{ display:"flex", alignItems:"center", gap:8, marginBottom:6 }}>
            <span style={{ background:dpeColor, color:["A","B","C"].includes(item.dpe)?"#fff":"#222", borderRadius:4, padding:"2px 8px", fontSize:12, fontWeight:700 }}>
              DPE {item.dpe}
            </span>
            {item.conso_med_kwh_m2 && <span style={{ fontSize:12, color:"#888" }}>⚡ {item.conso_med_kwh_m2} kWh/m²</span>}
          </div>
          {item.pct_passoires != null && (
            <div style={{ fontSize:12, color:"#888", marginBottom:4 }}>
              🔥 {(item.pct_passoires*100).toFixed(0)}% passoires · ✅ {(item.pct_bons_dpe*100).toFixed(0)}% bons DPE
            </div>
          )}
        </>
      )}

      {item.arret_plus_proche && (
        <>
          <hr style={{ border:"none", borderTop:"1px solid #f0f0f0", margin:"10px 0" }} />
          <div style={{ fontSize:13 }}>
            🚌 <strong>{item.arret_plus_proche}</strong>
            {item.mode_transport_proche && <span style={{ color:"#888" }}> ({item.mode_transport_proche})</span>}
          </div>
          <div style={{ fontSize:12, color:"#888", marginTop:3 }}>
            {item.reseaux_transport && <span>{item.reseaux_transport} · </span>}
            {fmt(item.distance_arret_m)} m
            {item.nb_arrets_500m != null && <span> · {item.nb_arrets_500m} arrêts à 500m</span>}
          </div>
        </>
      )}

      {item.peb_zone && (
        <>
          <hr style={{ border:"none", borderTop:"1px solid #f0f0f0", margin:"10px 0" }} />
          <div style={{ background:"#fff3e0", color:"#e65100", borderRadius:6, padding:"6px 10px", fontSize:12, fontWeight:600 }}>
            ✈️ Zone PEB {item.peb_zone}{item.nom_aeroport ? ` — ${item.nom_aeroport}` : ""}
          </div>
        </>
      )}
    </div>
  )
}

// ─── Fiche commune (mode polygone) ──────────────────────────────────────────
function FicheCommune({ props, onClose, onZoom }) {
  return (
    <div style={{
      position: "absolute", top: 16, right: 16, zIndex: 1000,
      background: "#fff", borderRadius: 14, padding: "18px 20px",
      boxShadow: "0 4px 20px rgba(0,0,0,.15)", width: 260,
    }}>
      <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center", marginBottom:12 }}>
        <strong style={{ fontSize:15 }}>{props.nom}</strong>
        <button onClick={onClose} style={{ background:"none", border:"none", cursor:"pointer", fontSize:18, color:"#bbb" }}>✕</button>
      </div>

      {[
        { label:"Prix médian/m²",  value: props.prix_median_m2 ? fmt(props.prix_median_m2)+" €" : "—" },
        { label:"Prix moyen/m²",   value: props.prix_moyen_m2  ? fmt(props.prix_moyen_m2)+" €"  : "—" },
        { label:"Ventes",          value: fmt(props.nb_ventes) },
        { label:"DPE dominant",    value: props.dpe_dominant ?? "—" },
        { label:"Arrêt médian",    value: props.dist_arret_med ? fmt(props.dist_arret_med)+" m" : "—" },
        { label:"% passoires",     value: props.pct_passoires != null ? props.pct_passoires+"%" : "—" },
      ].map(row => (
        <div key={row.label} style={{ display:"flex", justifyContent:"space-between", fontSize:13, marginBottom:6 }}>
          <span style={{ color:"#888" }}>{row.label}</span>
          <span style={{ fontWeight:600 }}>{row.value}</span>
        </div>
      ))}

      <button
        onClick={onZoom}
        style={{
          marginTop:12, width:"100%", padding:"9px 0",
          background:"#042C53", color:"#fff",
          border:"none", borderRadius:8, fontSize:13,
          fontWeight:600, cursor:"pointer",
        }}
      >
        🔍 Voir les offres
      </button>
    </div>
  )
}

// ─── Composant principal ─────────────────────────────────────────────────────
export default function Carte() {
  // Filtres
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
  const [colorMode, setColorMode] = useState("prix")

  // Données
  const [geojson, setGeojson]         = useState(null)
  const [points, setPoints]           = useState([])     // offres d'une commune
  const [loadingGeo, setLoadingGeo]   = useState(true)
  const [loadingPts, setLoadingPts]   = useState(false)

  // UI carte
  const [mode, setMode]               = useState("choropleth") // "choropleth" | "points"
  const [selectedCommune, setSelectedCommune] = useState(null) // { props, bounds }
  const [selectedOffre, setSelectedOffre]     = useState(null)
  const [flyBounds, setFlyBounds]     = useState(null)
  const geojsonRef                    = useRef(null)

  // Init
  useEffect(() => {
    getAnnees().then(a => { setAnnees(a); if (a.length > 0) setAnnee(a[0]) })
    getGeoJson().then(g => { setGeojson(g); setLoadingGeo(false) })
      .catch(() => setLoadingGeo(false))
  }, [])

  // Stats prix pour l'échelle de couleur (choroplèthe)
  const allPrix = geojson
    ? geojson.features.map(f => f.properties?.prix_median_m2).filter(Boolean)
    : []
  const minPrix = allPrix.length ? Math.min(...allPrix) : 0
  const maxPrix = allPrix.length ? Math.max(...allPrix) : 1

  // Couleur d'un polygone
  function communeColor(feature) {
    const p = feature.properties
    if (colorMode === "dpe") return DPE_COLORS[p?.dpe_dominant] ?? "#cccccc"
    return getPrixColor(p?.prix_median_m2, minPrix, maxPrix)
  }

  // Style GeoJSON
  const styleFeature = useCallback((feature) => ({
    fillColor:   communeColor(feature),
    fillOpacity: 0.72,
    color:       "#fff",
    weight:      1,
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }), [geojson, colorMode, minPrix, maxPrix])

  // Clic sur un polygone → fiche commune
  const onEachFeature = useCallback((feature, layer) => {
    layer.on({
      click: (e) => {
        const bounds = layer.getBounds()
        setSelectedCommune({ props: feature.properties, bounds })
        setSelectedOffre(null)
      },
      mouseover: (e) => { e.target.setStyle({ fillOpacity: 0.92, weight: 2 }) },
      mouseout:  (e) => { geojsonRef.current?.resetStyle(e.target) },
    })
  }, [])

  // Charger les offres de la commune sélectionnée
  const zoomIntoCommune = useCallback(async () => {
    if (!selectedCommune) return
    setLoadingPts(true)
    setMode("points")
    setFlyBounds(selectedCommune.bounds)
    try {
      const data = await getCarteCommune({
        commune:    selectedCommune.props.nom,
        annee:      annee || 0,
        type_local: typeLocal,
        pieces_min: piecesMin || 0,
        surf_min:   surfMin   || 0,
        surf_max:   surfMax   || 0,
        prix_min:   prixMin   || 0,
        prix_max:   prixMax   || 0,
        dpe_max:    dpeMax,
        dist_max:   distMax   || 0,
      })
      setPoints(data)
    } finally {
      setLoadingPts(false)
    }
  }, [selectedCommune, annee, typeLocal, piecesMin, surfMin, surfMax, prixMin, prixMax, dpeMax, distMax])

  // Couleur d'un point offre
  const prixPts = points.map(p => p.prix_m2).filter(Boolean)
  const minPrixPts = prixPts.length ? Math.min(...prixPts) : 0
  const maxPrixPts = prixPts.length ? Math.max(...prixPts) : 1

  function pointColor(p) {
    if (colorMode === "dpe")       return DPE_COLORS[p.dpe] ?? "#aaa"
    if (colorMode === "transport") {
      const dists = points.map(x => x.distance_arret_m).filter(Boolean)
      const mn = Math.min(...dists), mx = Math.max(...dists)
      const t = Math.min(1, Math.max(0, (p.distance_arret_m - mn) / (mx - mn || 1)))
      return `rgb(${Math.round(76+(244-76)*t)},${Math.round(175+(67-175)*t)},${Math.round(80+(54-80)*t)})`
    }
    return getPrixColor(p.prix_m2, minPrixPts, maxPrixPts)
  }

  // Retour vue générale
  const backToChoropleth = () => {
    setMode("choropleth")
    setPoints([])
    setSelectedOffre(null)
    setSelectedCommune(null)
    setFlyBounds(null)
  }

  return (
    <div style={{ display:"flex", flexDirection:"column", height:"calc(100vh - 56px)" }}>

      {/* ── Filtres ── */}
      <div style={{ background:"#fff", borderBottom:"1px solid #e8e8e8", padding:"12px 20px" }}>
        <div style={{ display:"flex", gap:10, flexWrap:"wrap", alignItems:"flex-end" }}>

          <Field label="Année">
            <select value={annee} onChange={e => setAnnee(Number(e.target.value))} style={{ ...inputStyle, width:90 }}>
              <option value={0}>Toutes</option>
              {annees.map(a => <option key={a} value={a}>{a}</option>)}
            </select>
          </Field>

          <Field label="Type">
            <select value={typeLocal} onChange={e => setTypeLocal(e.target.value)} style={{ ...inputStyle, width:110 }}>
              <option value="Tous">Tous</option>
              <option value="Appartement">Appartement</option>
              <option value="Maison">Maison</option>
            </select>
          </Field>

          <Field label="Pièces min">
            <select value={piecesMin} onChange={e => setPiecesMin(e.target.value)} style={{ ...inputStyle, width:75 }}>
              <option value="">—</option>
              {[1,2,3,4,5].map(n => <option key={n} value={n}>{n}+</option>)}
            </select>
          </Field>

          <Field label="Surf. min">
            <input type="number" value={surfMin} onChange={e => setSurfMin(e.target.value)}
              placeholder="m²" style={{ ...inputStyle, width:65 }} />
          </Field>
          <Field label="Surf. max">
            <input type="number" value={surfMax} onChange={e => setSurfMax(e.target.value)}
              placeholder="m²" style={{ ...inputStyle, width:65 }} />
          </Field>

          <Field label="Prix min">
            <input type="number" value={prixMin} onChange={e => setPrixMin(e.target.value)}
              placeholder="€" style={{ ...inputStyle, width:75 }} />
          </Field>
          <Field label="Prix max">
            <input type="number" value={prixMax} onChange={e => setPrixMax(e.target.value)}
              placeholder="€" style={{ ...inputStyle, width:75 }} />
          </Field>

          <Field label="DPE max">
            <select value={dpeMax} onChange={e => setDpeMax(e.target.value)} style={{ ...inputStyle, width:65 }}>
              <option value="">Tous</option>
              {["A","B","C","D","E","F","G"].map(d => <option key={d} value={d}>{d}</option>)}
            </select>
          </Field>

          <Field label="Arrêt max">
            <select value={distMax} onChange={e => setDistMax(e.target.value)} style={{ ...inputStyle, width:75 }}>
              <option value="">Tous</option>
              <option value="300">300 m</option>
              <option value="500">500 m</option>
              <option value="1000">1 km</option>
              <option value="2000">2 km</option>
            </select>
          </Field>

          <Field label="Couleur">
            <select value={colorMode} onChange={e => setColorMode(e.target.value)} style={{ ...inputStyle, width:110 }}>
              <option value="prix">Prix / m²</option>
              <option value="transport">Transport</option>
              <option value="dpe">DPE</option>
            </select>
          </Field>

          {mode === "points" && (
            <button onClick={backToChoropleth} style={{
              padding:"7px 16px", background:"#f0f4ff", color:"#042C53",
              border:"1px solid #c5d2f0", borderRadius:8, fontSize:13,
              fontWeight:600, cursor:"pointer", alignSelf:"flex-end",
            }}>
              ← Vue générale
            </button>
          )}

          {/* Indicateurs mode */}
          <div style={{ alignSelf:"flex-end", marginLeft:"auto", fontSize:12, color:"#999" }}>
            {loadingGeo && "Chargement de la carte…"}
            {loadingPts && "Chargement des offres…"}
            {mode === "choropleth" && !loadingGeo && "Cliquez sur une commune"}
            {mode === "points" && !loadingPts && `${points.length} offres · ${selectedCommune?.props?.nom}`}
          </div>
        </div>
      </div>

      {/* ── Carte ── */}
      <div style={{ flex:1, position:"relative" }}>
        <MapContainer
          center={[47.8, -2.5]}
          zoom={8}
          style={{ width:"100%", height:"100%" }}
          scrollWheelZoom
        >
          <TileLayer
            attribution='© <a href="https://www.openstreetmap.org/">OpenStreetMap</a>'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />

          {flyBounds && <FlyToCommune bounds={flyBounds} />}

          {/* ── Mode choroplèthe ── */}
          {mode === "choropleth" && geojson && (
            <GeoJSON
              ref={geojsonRef}
              key={colorMode + annee}   // force recalcul couleurs si filtre change
              data={geojson}
              style={styleFeature}
              onEachFeature={onEachFeature}
            />
          )}

          {/* ── Mode points (offres d'une commune) ── */}
          {mode === "points" && points.map((p, i) => (
            <CircleMarker
              key={p.id_mutation ?? i}
              center={[p.lat, p.lng]}
              radius={7}
              pathOptions={{
                fillColor:   pointColor(p),
                fillOpacity: 0.85,
                color:       "#fff",
                weight:      1.5,
              }}
              eventHandlers={{ click: () => { setSelectedOffre(p); setSelectedCommune(null) } }}
            >
              <Tooltip direction="top" offset={[0,-8]}>
                <div style={{ fontFamily:"sans-serif", fontSize:12, lineHeight:1.4 }}>
                  <strong>{p.type_local}</strong> · {p.surface} m²<br />
                  {fmt(p.prix)} € · {fmt(p.prix_m2)} €/m²
                  {p.dpe && <><br />DPE {p.dpe}</>}
                </div>
              </Tooltip>
            </CircleMarker>
          ))}
        </MapContainer>

        {/* ── Légende ── */}
        <div style={{
          position:"absolute", bottom:24, left:16, zIndex:1000,
          background:"rgba(255,255,255,0.95)", borderRadius:10,
          padding:"10px 14px", boxShadow:"0 2px 8px rgba(0,0,0,.12)", minWidth:150,
        }}>
          {colorMode === "prix" && (
            <>
              <div style={{ fontSize:11, fontWeight:600, color:"#555", marginBottom:6 }}>PRIX / m²</div>
              <div style={{ width:120, height:8, borderRadius:999,
                background:"linear-gradient(to right, #4caf50, #ff9800, #f44336)", marginBottom:4 }} />
              <div style={{ display:"flex", justifyContent:"space-between", fontSize:10, color:"#888" }}>
                <span>{fmt(mode==="points"?minPrixPts:minPrix)} €</span>
                <span>{fmt(mode==="points"?maxPrixPts:maxPrix)} €</span>
              </div>
            </>
          )}
          {colorMode === "transport" && (
            <>
              <div style={{ fontSize:11, fontWeight:600, color:"#555", marginBottom:6 }}>TRANSPORT</div>
              <div style={{ width:120, height:8, borderRadius:999,
                background:"linear-gradient(to right, #4caf50, #f44336)", marginBottom:4 }} />
              <div style={{ display:"flex", justifyContent:"space-between", fontSize:10, color:"#888" }}>
                <span>Proche</span><span>Loin</span>
              </div>
            </>
          )}
          {colorMode === "dpe" && (
            <>
              <div style={{ fontSize:11, fontWeight:600, color:"#555", marginBottom:6 }}>DPE</div>
              {Object.entries(DPE_COLORS).map(([k,c]) => (
                <div key={k} style={{ display:"flex", alignItems:"center", gap:5, marginBottom:2 }}>
                  <div style={{ width:10, height:10, borderRadius:2, background:c }} />
                  <span style={{ fontSize:10, color:"#555" }}>Classe {k}</span>
                </div>
              ))}
            </>
          )}
          <div style={{ marginTop:8, borderTop:"1px solid #eee", paddingTop:6, fontSize:10, color:"#aaa" }}>
            {mode === "choropleth" ? "Polygone = commune" : "Point = offre"}
          </div>
        </div>

        {/* ── Fiche commune ── */}
        {selectedCommune && mode === "choropleth" && (
          <FicheCommune
            props={selectedCommune.props}
            onClose={() => setSelectedCommune(null)}
            onZoom={zoomIntoCommune}
          />
        )}

        {/* ── Fiche offre ── */}
        {selectedOffre && mode === "points" && (
          <FicheOffre item={selectedOffre} onClose={() => setSelectedOffre(null)} />
        )}
      </div>
    </div>
  )
}
