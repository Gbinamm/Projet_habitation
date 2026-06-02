export default function BienCard({ bien }) {
  const {
    commune, type_local, surface, pieces,
    prix, prix_m2, dpe, date, vs_marche,
  } = bien

  const fmt = n => n?.toLocaleString("fr-FR") ?? "—"

  // Badge deal
  let dealClass, dealLabel
  if (vs_marche == null)    { dealClass = "ok";   dealLabel = "Prix non comparé" }
  else if (vs_marche < -5)  { dealClass = "good"; dealLabel = `↓ ${Math.abs(vs_marche).toFixed(0)}% sous le marché` }
  else if (vs_marche > 5)   { dealClass = "bad";  dealLabel = `↑ ${vs_marche.toFixed(0)}% au-dessus` }
  else                      { dealClass = "ok";   dealLabel = "≈ Prix dans la moyenne" }

  const dealColors = {
    good: { background: "#e8f5e9", color: "#2e7d32" },
    ok:   { background: "#fff8e1", color: "#e65100" },
    bad:  { background: "#fce4ec", color: "#880e4f" },
  }

  const dpeColors = {
    A: { background: "#e8f5e9", color: "#2e7d32" },
    B: { background: "#e0f2f1", color: "#00695c" },
    C: { background: "#fff8e1", color: "#e65100" },
    D: { background: "#fce4ec", color: "#880e4f" },
  }

  const icon = type_local === "Maison" ? "🏠" : "🏢"
  const titre = `${type_local} ${pieces}P · ${surface} m²`

  return (
    <div style={{
      display: "grid", gridTemplateColumns: "90px 1fr auto",
      gap: 16, alignItems: "start",
      background: "#fff", border: "1px solid #e8e8e8",
      borderRadius: 12, padding: "14px 16px",
      transition: "border-color .15s, box-shadow .15s",
      cursor: "default",
    }}
      onMouseEnter={e => {
        e.currentTarget.style.borderColor = "#bbb"
        e.currentTarget.style.boxShadow = "0 2px 8px rgba(0,0,0,.07)"
      }}
      onMouseLeave={e => {
        e.currentTarget.style.borderColor = "#e8e8e8"
        e.currentTarget.style.boxShadow = "none"
      }}
    >
      {/* Thumb */}
      <div style={{
        width: 90, height: 70, borderRadius: 8,
        background: "#f4f4f4", display: "flex",
        alignItems: "center", justifyContent: "center",
        fontSize: 28, flexShrink: 0,
      }}>
        {icon}
      </div>

      {/* Infos */}
      <div>
        <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 3 }}>
          {titre}
        </div>
        <div style={{ fontSize: 12, color: "#888", marginBottom: 8 }}>
          📍 {commune}{date ? ` · ${date.slice(0, 10)}` : ""}
        </div>
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
          {/* Tags */}
          {[
            `${surface} m²`,
            `${pieces} pièce${pieces > 1 ? "s" : ""}`,
          ].map(t => (
            <span key={t} style={{
              fontSize: 11, padding: "3px 9px", borderRadius: 999,
              background: "#f0f0f0", color: "#555",
            }}>{t}</span>
          ))}
          {/* DPE */}
          {dpe && dpe !== "?" && (
            <span style={{
              fontSize: 11, padding: "3px 9px", borderRadius: 999,
              ...(dpeColors[dpe] ?? { background: "#f0f0f0", color: "#555" }),
            }}>
              DPE {dpe}
            </span>
          )}
        </div>
      </div>

      {/* Prix + badge */}
      <div style={{ textAlign: "right", minWidth: 140 }}>
        <div style={{ fontSize: 18, fontWeight: 700, whiteSpace: "nowrap" }}>
          {fmt(prix)} €
        </div>
        <div style={{ fontSize: 12, color: "#999", marginTop: 3 }}>
          {fmt(prix_m2)} €/m²
        </div>
        <span style={{
          display: "inline-block", fontSize: 11, marginTop: 8,
          padding: "4px 10px", borderRadius: 999,
          whiteSpace: "nowrap", ...dealColors[dealClass],
        }}>
          {dealLabel}
        </span>
      </div>
    </div>
  )
}
