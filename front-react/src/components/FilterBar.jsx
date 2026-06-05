  import { useState, useRef, useEffect } from "react"

  const inputStyle = {
    fontSize: 13,
    padding: "7px 11px",
    border: "1.5px solid var(--border)",
    borderRadius: 10,
    background: "var(--surface)",
    color: "var(--text)",
    width: "100%",
    fontFamily: "'DM Sans', sans-serif",
    outline: "none",
    transition: "border-color .15s",
  }
  const labelStyle = {
    fontSize: 11, color: "var(--muted)",
    marginBottom: 4, display: "block",
    fontWeight: 500, letterSpacing: "0.03em",
    textTransform: "uppercase",
  }

  function Field({ label, children }) {
    return (
      <div style={{ display: "flex", flexDirection: "column", minWidth: 90 }}>
        <label style={labelStyle}>{label}</label>
        {children}
      </div>
    )
  }

  // ── Combobox commune ─────────────────────────────────────────────────────────
  function CommuneSearch({ communes = [], value = "", onChange }) {
    const [query, setQuery]     = useState(value)
    const [open, setOpen]       = useState(false)
    const [focused, setFocused] = useState(-1)
    const inputRef              = useRef(null)
    const listRef               = useRef(null)

    useEffect(() => { setQuery(value) }, [value])

    // LA CORRECTION EST ICI : Filtrage sécurisé à l'épreuve des balles
    const filtered = !query
      ? communes.slice(0, 60)
      : communes.filter(c => {
          if (!c || typeof c !== 'string') return false;
          return c.toLowerCase().includes(query.toLowerCase());
        }).slice(0, 60)

    const select = (c) => { onChange(c); setQuery(c); setOpen(false); setFocused(-1) }

    const handleKey = (e) => {
      if (!open) { setOpen(true); return }
      if (e.key === "ArrowDown") { e.preventDefault(); setFocused(f => Math.min(f+1, filtered.length-1)) }
      else if (e.key === "ArrowUp") { e.preventDefault(); setFocused(f => Math.max(f-1, 0)) }
      else if (e.key === "Enter" && focused >= 0) { e.preventDefault(); select(filtered[focused]) }
      else if (e.key === "Escape") setOpen(false)
    }

    useEffect(() => {
      if (focused >= 0 && listRef.current)
        listRef.current.children[focused]?.scrollIntoView({ block: "nearest" })
    }, [focused])

    return (
      <div style={{ position: "relative", minWidth: 170 }}>
        <label style={labelStyle}>Commune</label>
        <input
          ref={inputRef}
          type="text"
          value={query || ""}
          onChange={e => { setQuery(e.target.value); setOpen(true); setFocused(-1) }}
          onFocus={() => setOpen(true)}
          onBlur={() => setTimeout(() => setOpen(false), 150)}
          onKeyDown={handleKey}
          placeholder="Rechercher…"
          style={{ ...inputStyle, width: 170 }}
        />
        {open && filtered.length > 0 && (
          <ul ref={listRef} style={{
            position: "absolute", top: "calc(100% + 4px)", left: 0, zIndex: 999,
            background: "var(--surface)",
            border: "1.5px solid var(--border)",
            borderRadius: 12,
            boxShadow: "0 8px 24px rgba(0,0,0,.09)",
            maxHeight: 220, overflowY: "auto",
            padding: "4px 0", listStyle: "none", minWidth: 190,
          }}>
            {filtered.map((c, i) => (
              <li key={c} onMouseDown={() => select(c)} style={{
                padding: "8px 14px", fontSize: 13, cursor: "pointer",
                background: i === focused ? "#F0F7F4" : "transparent",
                color: c === value ? "var(--brand)" : "var(--text)",
                fontWeight: c === value ? 600 : 400,
                transition: "background .1s",
              }}>{c}</li>
            ))}
          </ul>
        )}
      </div>
    )
  }

  // ── FilterBar ────────────────────────────────────────────────────────────────
  export default function FilterBar({
    communes = [], commune, setCommune,
    annees = [], annee, setAnnee,
    typeLocal, setTypeLocal,
    piecesMin, setPiecesMin,
    surfMin, setSurfMin, surfMax, setSurfMax,
    prixMin, setPrixMin, prixMax, setPrixMax,
    dpeMax, setDpeMax,
    distMax, setDistMax,
    onSearch, loading,
  }) {
    return (
      <div style={{
        background: "var(--surface)",
        borderBottom: "1.5px solid var(--border)",
        padding: "14px 28px",
      }}>
        <div style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "flex-end" }}>

          <CommuneSearch communes={communes} value={commune} onChange={setCommune} />

          <Field label="Année">
            <select value={annee} onChange={e => setAnnee(Number(e.target.value))}
              style={{ ...inputStyle, width: 90 }}>
              <option value={0}>Toutes</option>
              {annees.map(a => <option key={a} value={a}>{a}</option>)}
            </select>
          </Field>

          <Field label="Type">
            <select value={typeLocal} onChange={e => setTypeLocal(e.target.value)}
              style={{ ...inputStyle, width: 120 }}>
              <option value="Tous">Tous</option>
              <option value="Appartement">Appartement</option>
              <option value="Maison">Maison</option>
            </select>
          </Field>

          <Field label="Pièces min">
            <select value={piecesMin} onChange={e => setPiecesMin(e.target.value)}
              style={{ ...inputStyle, width: 80 }}>
              <option value="">—</option>
              {[1,2,3,4,5].map(n => <option key={n} value={n}>{n}+</option>)}
            </select>
          </Field>

          <Field label="Surf. min">
            <input type="number" value={surfMin} onChange={e => setSurfMin(e.target.value)}
              placeholder="m²" style={{ ...inputStyle, width: 72 }} />
          </Field>

          <Field label="Surf. max">
            <input type="number" value={surfMax} onChange={e => setSurfMax(e.target.value)}
              placeholder="m²" style={{ ...inputStyle, width: 72 }} />
          </Field>

          <Field label="Prix min">
            <input type="number" value={prixMin} onChange={e => setPrixMin(e.target.value)}
              placeholder="€" style={{ ...inputStyle, width: 82 }} />
          </Field>

          <Field label="Prix max">
            <input type="number" value={prixMax} onChange={e => setPrixMax(e.target.value)}
              placeholder="€" style={{ ...inputStyle, width: 82 }} />
          </Field>

          <Field label="DPE max">
            <select value={dpeMax} onChange={e => setDpeMax(e.target.value)}
              style={{ ...inputStyle, width: 72 }}>
              <option value="">Tous</option>
              {["A","B","C","D","E","F","G"].map(d => <option key={d} value={d}>{d}</option>)}
            </select>
          </Field>

          <Field label="Arrêt max">
            <select value={distMax} onChange={e => setDistMax(e.target.value)}
              style={{ ...inputStyle, width: 80 }}>
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
              alignSelf: "flex-end",
              padding: "8px 22px",
              background: loading ? "var(--border)" : "var(--brand)",
              color: loading ? "var(--muted)" : "#fff",
              border: "none", borderRadius: 10,
              fontSize: 13, fontWeight: 600,
              fontFamily: "'DM Sans', sans-serif",
              cursor: loading ? "not-allowed" : "pointer",
              transition: "all .18s",
              boxShadow: loading ? "none" : "0 2px 8px rgba(45,106,79,.25)",
            }}
          >
            {loading ? "…" : "Rechercher"}
          </button>
        </div>
      </div>
    )
  }