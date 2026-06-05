const DPE_COLORS = {
  A: "#009966", B: "#33cc66", C: "#99cc00",
  D: "#ffcc00", E: "#ff9900", F: "#ff6600", G: "#cc0000",
}

function fmt(n) { return n?.toLocaleString("fr-FR") ?? "—" }

function DpeBadge({ dpe }) {
  if (!dpe) return null
  const bg = DPE_COLORS[dpe] ?? "#ccc"
  return (
    <span style={{
      background: bg,
      color: ["A","B","C"].includes(dpe) ? "#fff" : "#222",
      borderRadius: 6, padding: "2px 8px",
      fontSize: 11, fontWeight: 700, letterSpacing: "0.05em",
    }}>DPE {dpe}</span>
  )
}

function VsMarche({ vs }) {
  if (vs == null) return null
  const good = vs < -5, bad = vs > 10
  return (
    <span style={{
      background: good ? "#ECFDF5" : bad ? "#FFF1F0" : "#F5F5F4",
      color:      good ? "#15803D" : bad ? "#DC2626" : "var(--muted)",
      border:     `1px solid ${good ? "#BBF7D0" : bad ? "#FECACA" : "var(--border)"}`,
      borderRadius: 99, padding: "2px 10px",
      fontSize: 12, fontWeight: 600,
    }}>
      {vs > 0 ? "+" : ""}{vs}% vs marché
    </span>
  )
}

export default function BienCard({ bien }) {
  return (
    <div style={{
      background: "var(--surface)",
      border: "1.5px solid var(--border)",
      borderRadius: 14,
      padding: "16px 20px",
      display: "flex", flexDirection: "column", gap: 8,
      transition: "box-shadow .18s, border-color .18s",
      fontFamily: "'DM Sans', sans-serif",
    }}
    onMouseEnter={e => {
      e.currentTarget.style.boxShadow = "0 4px 16px rgba(45,106,79,.10)"
      e.currentTarget.style.borderColor = "var(--brand-light)"
    }}
    onMouseLeave={e => {
      e.currentTarget.style.boxShadow = "none"
      e.currentTarget.style.borderColor = "var(--border)"
    }}
    >
      {/* Ligne 1 : titre + badges */}
      <div style={{ display:"flex", alignItems:"center", gap:8, flexWrap:"wrap" }}>
        <span style={{ fontWeight:700, fontSize:15, color:"var(--text)" }}>
          {bien.type_local} · {fmt(bien.surface)} m²
          {bien.surface_terrain ? <span style={{ fontWeight:400, color:"var(--muted)", fontSize:13 }}> (terrain {fmt(bien.surface_terrain)} m²)</span> : ""}
        </span>
        {bien.pieces && (
          <span style={{ fontSize:12, color:"var(--muted)", background:"var(--bg)", borderRadius:6, padding:"1px 7px" }}>
            {bien.pieces} p.
          </span>
        )}
        <DpeBadge dpe={bien.dpe} />
        {bien.peb_zone && (
          <span style={{
            background:"#FFF7ED", color:"#C2410C",
            border:"1px solid #FED7AA",
            borderRadius:6, padding:"1px 7px", fontSize:11, fontWeight:600,
          }}>
            ✈️ PEB {bien.peb_zone}{bien.nom_aeroport ? ` — ${bien.nom_aeroport}` : ""}
          </span>
        )}
      </div>

      {/* Ligne 2 : prix */}
      <div style={{ display:"flex", alignItems:"baseline", gap:10, flexWrap:"wrap" }}>
        <span style={{ fontSize:21, fontWeight:800, color:"var(--brand)", letterSpacing:"-0.02em" }}>
          {fmt(bien.prix)} €
        </span>
        <span style={{ fontSize:13, color:"var(--muted)" }}>{fmt(bien.prix_m2)} €/m²</span>
        <VsMarche vs={bien.vs_marche} />
      </div>

      {/* Ligne 3 : transport */}
      {bien.arret_plus_proche && (
        <div style={{ fontSize:13, color:"var(--muted)", display:"flex", gap:6, alignItems:"flex-start" }}>
          <span style={{ fontSize:14 }}>🚌</span>
          <span>
            <span style={{ color:"var(--text)", fontWeight:500 }}>{bien.arret_plus_proche}</span>
            {bien.mode_transport_proche && <span> ({bien.mode_transport_proche})</span>}
            {bien.reseaux_transport && <span> · {bien.reseaux_transport}</span>}
            {bien.distance_arret_m != null && <span> · <strong style={{ color:"var(--text)" }}>{fmt(bien.distance_arret_m)} m</strong></span>}
            {bien.nb_arrets_500m != null && <span style={{ color:"var(--muted)", fontSize:12 }}> · {bien.nb_arrets_500m} arrêts à 500m</span>}
          </span>
        </div>
      )}

      {/* Ligne 4 : DPE détail */}
      {(bien.pct_passoires != null || bien.conso_med_kwh_m2 != null) && (
        <div style={{ fontSize:12, color:"var(--muted)", display:"flex", gap:14, flexWrap:"wrap" }}>
          {bien.pct_passoires != null && <span>🔥 {(bien.pct_passoires*100).toFixed(0)}% passoires</span>}
          {bien.pct_bons_dpe != null  && <span>✅ {(bien.pct_bons_dpe*100).toFixed(0)}% bons DPE</span>}
          {bien.conso_med_kwh_m2 != null && <span>⚡ {bien.conso_med_kwh_m2} kWh/m²</span>}
          {bien.n_dpe != null && <span style={{ color:"var(--border)" }}>({bien.n_dpe} DPE)</span>}
        </div>
      )}

      {/* Ligne 5 : adresse + date */}
      <div style={{ fontSize:12, color:"var(--muted)", display:"flex", justifyContent:"space-between" }}>
        <span>{bien.adresse ?? "—"}</span>
        <span style={{ flexShrink:0, marginLeft:12 }}>{bien.date ?? "—"}</span>
      </div>
    </div>
  )
}
