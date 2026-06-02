import useScrollDirection from "../hooks/useScrollDirection"

export default function FilterBar({
  communes, commune, setCommune,
  mode, setMode,
  typeLocal, setTypeLocal,
  piecesMin, setPiecesMin,
  surfMin, setSurfMin, surfMax, setSurfMax,
  prixMin, setPrixMin, prixMax, setPrixMax,
  dpeMax, setDpeMax,
  onSearch, loading,
}) {
  const visible = useScrollDirection(80)

  const input = {
    fontSize: 13, padding: "7px 10px",
    border: "1px solid #ddd", borderRadius: 8,
    width: "100%", background: "#fff",
  }

  const label = {
    fontSize: 11, color: "#999", fontWeight: 600,
    textTransform: "uppercase", letterSpacing: ".4px",
    marginBottom: 5, display: "block",
  }

  const col = { display: "flex", flexDirection: "column" }

  return (
    <div style={{
      position:   "sticky",
      top:        0,
      zIndex:     100,
      background: "#fff",
      borderBottom: "1px solid #e8e8e8",
      padding:    "14px 24px",
      transform:  visible ? "translateY(0)" : "translateY(-110%)",
      transition: "transform 0.3s ease, box-shadow 0.3s ease",
      boxShadow:  visible ? "0 2px 12px rgba(0,0,0,0.08)" : "none",
    }}>

      {/* Ligne 1 : mode + commune + rechercher */}
      <div style={{
        display: "flex", gap: 12, alignItems: "center",
        marginBottom: 14, flexWrap: "wrap",
      }}>

        {/* Toggle Achat / Location */}
        <div style={{
          display: "flex", border: "1px solid #ddd",
          borderRadius: 8, overflow: "hidden", flexShrink: 0,
        }}>
          {["Achat", "Location"].map(m => (
            <button key={m} onClick={() => setMode(m)} style={{
              padding: "8px 20px", border: "none", cursor: "pointer",
              fontSize: 13, transition: "all .15s",
              background: mode === m ? "#042C53" : "#fff",
              color:      mode === m ? "#fff"    : "#666",
            }}>
              {m}
            </button>
          ))}
        </div>

        {/* Commune */}
        <div style={{ position: "relative", flex: 1, minWidth: 200 }}>
          <span style={{
            position: "absolute", left: 10, top: "50%",
            transform: "translateY(-50%)", fontSize: 14, pointerEvents: "none",
          }}>📍</span>
          <select
            value={commune}
            onChange={e => setCommune(e.target.value)}
            style={{ ...input, paddingLeft: 30 }}
          >
            {communes.map(c => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>

        {/* Bouton */}
        <button onClick={onSearch} disabled={loading} style={{
          padding: "8px 24px", background: "#042C53", color: "#fff",
          border: "none", borderRadius: 8, fontSize: 14, fontWeight: 500,
          cursor: loading ? "not-allowed" : "pointer",
          opacity: loading ? 0.7 : 1, flexShrink: 0,
          transition: "opacity .15s",
        }}>
          {loading ? "..." : "🔍 Rechercher"}
        </button>
      </div>

      {/* Ligne 2 : filtres */}
      <div style={{
        display: "grid",
        gridTemplateColumns: "1.2fr 0.8fr 0.7fr 0.7fr 0.9fr 0.9fr 0.7fr",
        gap: 12, alignItems: "end",
      }}>

        <div style={col}>
          <span style={label}>Type de bien</span>
          <select value={typeLocal} onChange={e => setTypeLocal(e.target.value)} style={input}>
            <option value="Tous">Tous</option>
            <option value="Appartement">Appartement</option>
            <option value="Maison">Maison</option>
          </select>
        </div>

        <div style={col}>
          <span style={label}>Pièces min</span>
          <select value={piecesMin} onChange={e => setPiecesMin(e.target.value)} style={input}>
            <option value="">Toutes</option>
            {[1,2,3,4,5].map(n => <option key={n} value={n}>{n}+</option>)}
          </select>
        </div>

        <div style={col}>
          <span style={label}>Surface min m²</span>
          <input type="number" placeholder="Min" value={surfMin}
            onChange={e => setSurfMin(e.target.value)} style={input} min={0} />
        </div>

        <div style={col}>
          <span style={label}>Surface max m²</span>
          <input type="number" placeholder="Max" value={surfMax}
            onChange={e => setSurfMax(e.target.value)} style={input} min={0} />
        </div>

        <div style={col}>
          <span style={label}>{mode === "Achat" ? "Budget min €" : "Loyer min €"}</span>
          <input type="number" placeholder="Min" value={prixMin}
            onChange={e => setPrixMin(e.target.value)} style={input} min={0} />
        </div>

        <div style={col}>
          <span style={label}>{mode === "Achat" ? "Budget max €" : "Loyer max €"}</span>
          <input type="number" placeholder="Max" value={prixMax}
            onChange={e => setPrixMax(e.target.value)} style={input} min={0} />
        </div>

        <div style={col}>
          <span style={label}>DPE max</span>
          <select value={dpeMax} onChange={e => setDpeMax(e.target.value)} style={input}>
            <option value="">Tous</option>
            {["A","B","C","D","E","F","G"].map(d => (
              <option key={d} value={d}>{d}</option>
            ))}
          </select>
        </div>

      </div>
    </div>
  )
}
