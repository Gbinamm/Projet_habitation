const inputStyle = {
  fontSize: 13, padding: "7px 10px",
  border: "1px solid #ddd", borderRadius: 8,
  background: "#fff", width: "100%",
}

const labelStyle = { fontSize: 11, color: "#888", marginBottom: 3, display: "block" }

function Field({ label, children }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", minWidth: 110 }}>
      <label style={labelStyle}>{label}</label>
      {children}
    </div>
  )
}

export default function FilterBar({
  communes, commune, setCommune,
  typeLocal, setTypeLocal,
  piecesMin, setPiecesMin,
  surfMin, setSurfMin,
  surfMax, setSurfMax,
  prixMin, setPrixMin,
  prixMax, setPrixMax,
  dpeMax, setDpeMax,
  distMax, setDistMax,
  onSearch, loading,
}) {
  return (
    <div style={{
      background: "#fff", borderBottom: "1px solid #e8e8e8",
      padding: "14px 24px",
    }}>
      <div style={{
        display: "flex", gap: 12, flexWrap: "wrap", alignItems: "flex-end",
      }}>

        <Field label="Commune">
          <select value={commune} onChange={e => setCommune(e.target.value)} style={inputStyle}>
            {communes.map(c => <option key={c} value={c}>{c}</option>)}
          </select>
        </Field>

        <Field label="Type de bien">
          <select value={typeLocal} onChange={e => setTypeLocal(e.target.value)} style={inputStyle}>
            <option value="Tous">Tous</option>
            <option value="Appartement">Appartement</option>
            <option value="Maison">Maison</option>
          </select>
        </Field>

        <Field label="Pièces min">
          <select value={piecesMin} onChange={e => setPiecesMin(e.target.value)} style={inputStyle}>
            <option value="">—</option>
            {[1,2,3,4,5].map(n => <option key={n} value={n}>{n}+</option>)}
          </select>
        </Field>

        <Field label="Surface min (m²)">
          <input
            type="number" value={surfMin} onChange={e => setSurfMin(e.target.value)}
            placeholder="0" style={inputStyle}
          />
        </Field>

        <Field label="Surface max (m²)">
          <input
            type="number" value={surfMax} onChange={e => setSurfMax(e.target.value)}
            placeholder="∞" style={inputStyle}
          />
        </Field>

        <Field label="Prix min (€)">
          <input
            type="number" value={prixMin} onChange={e => setPrixMin(e.target.value)}
            placeholder="0" style={inputStyle}
          />
        </Field>

        <Field label="Prix max (€)">
          <input
            type="number" value={prixMax} onChange={e => setPrixMax(e.target.value)}
            placeholder="∞" style={inputStyle}
          />
        </Field>

        <Field label="DPE max">
          <select value={dpeMax} onChange={e => setDpeMax(e.target.value)} style={inputStyle}>
            <option value="">Tous</option>
            {["A","B","C","D","E","F","G"].map(d => (
              <option key={d} value={d}>{d}</option>
            ))}
          </select>
        </Field>

        <Field label="Arrêt max (m)">
          <select value={distMax} onChange={e => setDistMax(e.target.value)} style={inputStyle}>
            <option value="">Tous</option>
            <option value="300">300 m</option>
            <option value="500">500 m</option>
            <option value="1000">1 km</option>
            <option value="2000">2 km</option>
          </select>
        </Field>

        <button
          onClick={onSearch}
          disabled={loading}
          style={{
            padding: "8px 22px", background: "#042C53", color: "#fff",
            border: "none", borderRadius: 8, fontSize: 14, fontWeight: 600,
            cursor: loading ? "not-allowed" : "pointer",
            opacity: loading ? 0.6 : 1, alignSelf: "flex-end",
          }}
        >
          {loading ? "..." : "Rechercher"}
        </button>
      </div>
    </div>
  )
}