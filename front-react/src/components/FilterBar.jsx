import { useState, useRef, useEffect } from "react"

const inputStyle = {
  fontSize: 13, padding: "7px 10px",
  border: "1px solid #ddd", borderRadius: 8,
  background: "#fff", width: "100%",
}
const labelStyle = { fontSize: 11, color: "#888", marginBottom: 3, display: "block" }

function Field({ label, children }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", minWidth: 100 }}>
      <label style={labelStyle}>{label}</label>
      {children}
    </div>
  )
}

// ── Combobox communes avec recherche ────────────────────────────────────────
function CommuneSearch({ communes, value, onChange }) {
  const [query, setQuery]       = useState(value)
  const [open, setOpen]         = useState(false)
  const [focused, setFocused]   = useState(-1)
  const inputRef                = useRef(null)
  const listRef                 = useRef(null)

  // Sync si la valeur change de l'extérieur
  useEffect(() => { setQuery(value) }, [value])

  const filtered = query.length === 0
    ? communes.slice(0, 50)   // max 50 dans la liste déroulante par défaut
    : communes
        .filter(c => c.toLowerCase().includes(query.toLowerCase()))
        .slice(0, 50)

  const select = (c) => {
    onChange(c)
    setQuery(c)
    setOpen(false)
    setFocused(-1)
  }

  const handleKey = (e) => {
    if (!open) { setOpen(true); return }
    if (e.key === "ArrowDown") {
      e.preventDefault()
      setFocused(f => Math.min(f + 1, filtered.length - 1))
    } else if (e.key === "ArrowUp") {
      e.preventDefault()
      setFocused(f => Math.max(f - 1, 0))
    } else if (e.key === "Enter" && focused >= 0) {
      e.preventDefault()
      select(filtered[focused])
    } else if (e.key === "Escape") {
      setOpen(false)
    }
  }

  // Scroll l'item actif dans la liste
  useEffect(() => {
    if (focused >= 0 && listRef.current) {
      const item = listRef.current.children[focused]
      item?.scrollIntoView({ block: "nearest" })
    }
  }, [focused])

  return (
    <div style={{ position: "relative", minWidth: 160 }}>
      <label style={labelStyle}>Commune</label>
      <input
        ref={inputRef}
        type="text"
        value={query}
        onChange={e => { setQuery(e.target.value); setOpen(true); setFocused(-1) }}
        onFocus={() => setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
        onKeyDown={handleKey}
        placeholder="Rechercher..."
        style={{ ...inputStyle, width: 160 }}
      />
      {open && filtered.length > 0 && (
        <ul
          ref={listRef}
          style={{
            position: "absolute", top: "100%", left: 0, zIndex: 999,
            background: "#fff", border: "1px solid #ddd", borderRadius: 8,
            boxShadow: "0 4px 12px rgba(0,0,0,.1)",
            maxHeight: 220, overflowY: "auto",
            margin: "2px 0", padding: 0, listStyle: "none",
            minWidth: 180,
          }}
        >
          {filtered.map((c, i) => (
            <li
              key={c}
              onMouseDown={() => select(c)}
              style={{
                padding: "8px 12px", fontSize: 13, cursor: "pointer",
                background: i === focused ? "#f0f4ff" : "transparent",
                fontWeight: c === value ? 600 : 400,
              }}
            >
              {c}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

// ── FilterBar principal ──────────────────────────────────────────────────────
export default function FilterBar({
  communes, commune, setCommune,
  annees, annee, setAnnee,
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
      <div style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "flex-end" }}>

        <CommuneSearch communes={communes} value={commune} onChange={setCommune} />

        <Field label="Année">
          <select value={annee} onChange={e => setAnnee(Number(e.target.value))} style={{ ...inputStyle, width: 90 }}>
            <option value={0}>Toutes</option>
            {annees.map(a => <option key={a} value={a}>{a}</option>)}
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
          <input type="number" value={surfMin} onChange={e => setSurfMin(e.target.value)}
            placeholder="0" style={inputStyle} />
        </Field>

        <Field label="Surface max (m²)">
          <input type="number" value={surfMax} onChange={e => setSurfMax(e.target.value)}
            placeholder="∞" style={inputStyle} />
        </Field>

        <Field label="Prix min (€)">
          <input type="number" value={prixMin} onChange={e => setPrixMin(e.target.value)}
            placeholder="0" style={inputStyle} />
        </Field>

        <Field label="Prix max (€)">
          <input type="number" value={prixMax} onChange={e => setPrixMax(e.target.value)}
            placeholder="∞" style={inputStyle} />
        </Field>

        <Field label="DPE max">
          <select value={dpeMax} onChange={e => setDpeMax(e.target.value)} style={inputStyle}>
            <option value="">Tous</option>
            {["A","B","C","D","E","F","G"].map(d => (
              <option key={d} value={d}>{d}</option>
            ))}
          </select>
        </Field>

        <Field label="Arrêt max">
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
          {loading ? "…" : "Rechercher"}
        </button>
      </div>
    </div>
  )
}
