const DPE_COLORS = {
  A: "#009966", B: "#33cc66", C: "#99cc00",
  D: "#ffcc00", E: "#ff9900", F: "#ff6600", G: "#cc0000",
}

function fmt(n) { return n?.toLocaleString("fr-FR") ?? "—" }

function DpeBadge({ dpe }) {
  if (!dpe) return null
  return (
    <span style={{
      background: DPE_COLORS[dpe] ?? "#ccc",
      color: ["A","B","C"].includes(dpe) ? "#fff" : "#222",
      borderRadius: 4, padding: "1px 7px",
      fontSize: 11, fontWeight: 700, letterSpacing: 1,
    }}>
      DPE {dpe}
    </span>
  )
}

function VsMarche({ vs }) {
  if (vs == null) return null
  const good = vs < -5
  const bad  = vs > 10
  return (
    <span style={{
      background: good ? "#e8f5e9" : bad ? "#ffebee" : "#f5f5f5",
      color:      good ? "#2e7d32" : bad ? "#c62828" : "#555",
      borderRadius: 6, padding: "2px 8px",
      fontSize: 12, fontWeight: 600,
    }}>
      {vs > 0 ? "+" : ""}{vs}% vs marché
    </span>
  )
}

export default function BienCard({ bien }) {
  return (
    <div style={{
      background: "#fff", border: "1px solid #e8e8e8",
      borderRadius: 12, padding: "16px 20px",
      display: "flex", flexDirection: "column", gap: 8,
    }}>

      {/* Ligne 1 : titre + badges */}
      <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
        <span style={{ fontWeight: 700, fontSize: 15 }}>
          {bien.type_local} · {fmt(bien.surface)} m²
          {bien.surface_terrain ? ` (terrain ${fmt(bien.surface_terrain)} m²)` : ""}
        </span>
        {bien.pieces && (
          <span style={{ fontSize: 13, color: "#888" }}>{bien.pieces} pièce{bien.pieces > 1 ? "s" : ""}</span>
        )}
        <DpeBadge dpe={bien.dpe} />
        {bien.peb_zone && (
          <span style={{
            background: "#fff3e0", color: "#e65100",
            borderRadius: 4, padding: "1px 7px",
            fontSize: 11, fontWeight: 600,
          }}>
            ✈️ PEB zone {bien.peb_zone}
            {bien.nom_aeroport ? ` — ${bien.nom_aeroport}` : ""}
          </span>
        )}
      </div>

      {/* Ligne 2 : prix */}
      <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        <span style={{ fontSize: 20, fontWeight: 800 }}>{fmt(bien.prix)} €</span>
        <span style={{ fontSize: 13, color: "#888" }}>{fmt(bien.prix_m2)} €/m²</span>
        <VsMarche vs={bien.vs_marche} />
      </div>

      {/* Ligne 3 : transport */}
      {bien.arret_plus_proche && (
        <div style={{ fontSize: 13, color: "#555", display: "flex", gap: 6, flexWrap: "wrap" }}>
          <span>🚌</span>
          <span>
            <strong>{bien.arret_plus_proche}</strong>
            {bien.mode_transport_proche ? ` (${bien.mode_transport_proche})` : ""}
            {bien.reseaux_transport ? ` · ${bien.reseaux_transport}` : ""}
            {bien.distance_arret_m != null ? ` · ${fmt(bien.distance_arret_m)} m` : ""}
          </span>
          {bien.nb_arrets_500m != null && (
            <span style={{ color: "#888" }}>
              · {bien.nb_arrets_500m} arrêt{bien.nb_arrets_500m > 1 ? "s" : ""} à 500m
            </span>
          )}
        </div>
      )}

      {/* Ligne 4 : DPE détail */}
      {(bien.pct_passoires != null || bien.conso_med_kwh_m2 != null) && (
        <div style={{ fontSize: 12, color: "#888", display: "flex", gap: 16, flexWrap: "wrap" }}>
          {bien.pct_passoires != null && (
            <span>🔥 {(bien.pct_passoires * 100).toFixed(0)}% passoires thermiques</span>
          )}
          {bien.pct_bons_dpe != null && (
            <span>✅ {(bien.pct_bons_dpe * 100).toFixed(0)}% bons DPE</span>
          )}
          {bien.conso_med_kwh_m2 != null && (
            <span>⚡ {bien.conso_med_kwh_m2} kWh/m²</span>
          )}
          {bien.n_dpe != null && (
            <span style={{ color: "#bbb" }}>({bien.n_dpe} DPE)</span>
          )}
        </div>
      )}

      {/* Ligne 5 : adresse + date */}
      <div style={{ fontSize: 12, color: "#aaa", display: "flex", justifyContent: "space-between" }}>
        <span>{bien.adresse ?? "—"}</span>
        <span>{bien.date ?? "—"}</span>
      </div>
    </div>
  )
}