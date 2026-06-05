import { useState, useEffect } from "react"
import { getStatsGlobal } from "../api/client"

const BRAND       = "#2D6A4F"
const BRAND_LIGHT = "#52B788"
const ACCENT      = "#D4764A"
const MUTED       = "#78716C"
const BORDER      = "#E8E3DC"
const BG          = "#F7F5F2"
const DPE_COLORS  = { A:"#009966", B:"#33cc66", C:"#99cc00", D:"#ffcc00", E:"#ff9900", F:"#ff6600", G:"#cc0000" }

function fmt(n) { return n?.toLocaleString("fr-FR") ?? "—" }

// ── Barre horizontale simple ────────────────────────────────────────────────
function BarH({ label, value, max, color, n }) {
  const pct = max > 0 ? Math.round((value / max) * 100) : 0
  return (
    <div style={{ marginBottom: 10 }}>
      <div style={{ display:"flex", justifyContent:"space-between", fontSize:12, marginBottom:4 }}>
        <span style={{ color:"#1C1917", fontWeight:500 }}>{label}</span>
        <span style={{ color:MUTED }}>{fmt(value)} €/m² {n != null ? <span style={{color:BORDER}}>({fmt(n)})</span> : ""}</span>
      </div>
      <div style={{ background:BORDER, borderRadius:99, height:10, overflow:"hidden" }}>
        <div style={{
          width:`${pct}%`, height:"100%",
          background: color ?? BRAND,
          borderRadius:99,
          transition:"width .4s ease",
        }} />
      </div>
    </div>
  )
}

// ── Courbe SVG légère ───────────────────────────────────────────────────────
function LineChartSVG({ data, lines, width=700, height=200 }) {
  if (!data.length) return null
  const pad = { top:16, right:16, bottom:28, left:48 }
  const W = width - pad.left - pad.right
  const H = height - pad.top - pad.bottom

  const allVals = lines.flatMap(l => data.map(d => d[l.key]).filter(Boolean))
  const minV = Math.min(...allVals) * 0.95
  const maxV = Math.max(...allVals) * 1.05
  const xKeys = data.map(d => d.annee)

  const x = i => (i / (data.length - 1)) * W
  const y = v => H - ((v - minV) / (maxV - minV)) * H

  const yTicks = 4
  const yStep  = (maxV - minV) / yTicks

  return (
    <div style={{ overflowX:"auto" }}>
      <svg width={width} height={height} style={{ display:"block" }}>
        <g transform={`translate(${pad.left},${pad.top})`}>
          {/* Grille */}
          {Array.from({length: yTicks+1}, (_,i) => {
            const val = minV + i * yStep
            const yy  = y(val)
            return (
              <g key={i}>
                <line x1={0} y1={yy} x2={W} y2={yy} stroke={BORDER} strokeWidth={1} />
                <text x={-6} y={yy+4} textAnchor="end" fontSize={10} fill={MUTED}>
                  {Math.round(val/1000)}k
                </text>
              </g>
            )
          })}
          {/* Labels X */}
          {data.map((d, i) => (
            <text key={i} x={x(i)} y={H+18} textAnchor="middle" fontSize={11} fill={MUTED}>
              {d.annee}
            </text>
          ))}
          {/* Lignes */}
          {lines.map(l => {
            const pts = data.map((d,i) => d[l.key] ? `${x(i)},${y(d[l.key])}` : null).filter(Boolean)
            if (!pts.length) return null
            return (
              <g key={l.key}>
                <polyline
                  points={pts.join(" ")}
                  fill="none" stroke={l.color} strokeWidth={2.5}
                  strokeLinejoin="round" strokeLinecap="round"
                />
                {data.map((d,i) => d[l.key] ? (
                  <circle key={i} cx={x(i)} cy={y(d[l.key])} r={4}
                    fill={l.color} stroke="#fff" strokeWidth={1.5} />
                ) : null)}
              </g>
            )
          })}
        </g>
      </svg>
      {/* Légende */}
      <div style={{ display:"flex", gap:16, marginTop:8, paddingLeft:pad.left }}>
        {lines.map(l => (
          <div key={l.key} style={{ display:"flex", alignItems:"center", gap:6, fontSize:12, color:MUTED }}>
            <div style={{ width:20, height:3, background:l.color, borderRadius:99 }} />
            {l.label}
          </div>
        ))}
      </div>
    </div>
  )
}

// ── Composants UI ────────────────────────────────────────────────────────────
function Section({ title, subtitle, children }) {
  return (
    <div style={{ background:"#fff", border:`1.5px solid ${BORDER}`,
      borderRadius:16, padding:"24px 28px", marginBottom:20 }}>
      <h2 style={{ fontFamily:"'Syne',sans-serif", fontSize:17, fontWeight:700,
        color:"#1C1917", margin:"0 0 4px", letterSpacing:"-0.02em" }}>{title}</h2>
      {subtitle && <p style={{ fontSize:13, color:MUTED, margin:"0 0 16px" }}>{subtitle}</p>}
      {children}
    </div>
  )
}

function Insight({ emoji, text, highlight }) {
  return (
    <div style={{
      display:"flex", alignItems:"flex-start", gap:10,
      background: highlight ? "#F0F7F4" : BG,
      border:`1.5px solid ${highlight ? "#B7DFC9" : BORDER}`,
      borderRadius:10, padding:"10px 14px", fontSize:13,
      color:"#1C1917", lineHeight:1.55, marginBottom:8,
    }}>
      <span style={{ fontSize:15, flexShrink:0 }}>{emoji}</span>
      <span dangerouslySetInnerHTML={{ __html: text }} />
    </div>
  )
}

function KpiCard({ label, value, sub, color }) {
  return (
    <div style={{ background:"#fff", border:`1.5px solid ${BORDER}`,
      borderRadius:14, padding:"18px 20px", flex:1, minWidth:140 }}>
      <div style={{ fontSize:11, color:MUTED, fontWeight:500,
        textTransform:"uppercase", letterSpacing:"0.04em", marginBottom:6 }}>{label}</div>
      <div style={{ fontSize:22, fontWeight:800, color: color ?? BRAND,
        letterSpacing:"-0.02em", fontFamily:"'Syne',sans-serif" }}>{value}</div>
      {sub && <div style={{ fontSize:12, color:MUTED, marginTop:4 }}>{sub}</div>}
    </div>
  )
}

function RankList({ items, colorFn, accent }) {
  if (!items.length) return <div style={{ color:MUTED, fontSize:13 }}>Pas de données</div>
  return (
    <div style={{ display:"flex", flexDirection:"column", gap:5 }}>
      {items.map((r, i) => (
        <div key={r.commune+i} style={{
          display:"flex", justifyContent:"space-between", alignItems:"center",
          padding:"8px 12px",
          background: i === 0 && !accent ? "#F0F7F4" : BG,
          borderRadius:8, fontSize:13,
        }}>
          <div style={{ display:"flex", alignItems:"center", gap:8 }}>
            <span style={{ width:18, color:MUTED, fontSize:11, fontWeight:600 }}>{i+1}</span>
            <span style={{ fontWeight: i < 3 ? 600 : 400 }}>{r.commune}</span>
          </div>
          <span style={{ fontWeight:700, color: colorFn ? colorFn(i) : BRAND }}>
            {fmt(r.prix_m2_med)} €/m²
          </span>
        </div>
      ))}
    </div>
  )
}

// ── Page principale ──────────────────────────────────────────────────────────
export default function Stats() {
  const [data, setData]         = useState(null)
  const [loading, setLoading]   = useState(true)
  const [error, setError]       = useState(null)
  const [typeFilter, setTypeFilter] = useState("Appartement")

  useEffect(() => {
    getStatsGlobal()
      .then(setData)
      .catch(err => { console.error(err); setError(true) })
      .finally(() => setLoading(false))
  }, [])

  if (loading) return (
    <div style={{ textAlign:"center", padding:100, color:MUTED, fontFamily:"'DM Sans',sans-serif" }}>
      <div style={{ fontSize:36, marginBottom:16 }}>📊</div>Chargement des analyses…
    </div>
  )
  if (error || !data) return (
    <div style={{ textAlign:"center", padding:100, color:MUTED, fontFamily:"'DM Sans',sans-serif" }}>
      <div style={{ fontSize:36, marginBottom:16 }}>⚠️</div>
      Erreur de chargement. Vérifiez que le backend est lancé.
    </div>
  )

  const { resume={}, evolution=[], peb=[], transport=[], top_communes=[], flop_communes=[], dpe_prix=[] } = data

  // ── Pivot évolution ──────────────────────────────────────────────────────
  const evoByYear = {}
  for (const r of evolution) {
    if (!evoByYear[r.annee]) evoByYear[r.annee] = { annee: r.annee }
    evoByYear[r.annee][r.type_local] = r.prix_m2_med
  }
  const evolutionData = Object.values(evoByYear).sort((a,b) => a.annee - b.annee)

  const evoFiltered = evolution.filter(e => e.type_local === typeFilter)
  const evoFirst = evoFiltered[0]?.prix_m2_med
  const evoLast  = evoFiltered[evoFiltered.length-1]?.prix_m2_med
  const evoEvol  = evoFirst && evoLast ? Math.round((evoLast-evoFirst)/evoFirst*100) : null

  // ── Transport ────────────────────────────────────────────────────────────
  const transportData = transport.filter(r => r.type_local === typeFilter)
  const tMax   = Math.max(...transportData.map(r => r.prix_m2_med))
  const tClose = transportData.find(r => r.bucket === "< 300 m")
  const tFar   = transportData.find(r => r.bucket === "> 2 km")
  const tDiff  = tClose && tFar && tFar.prix_m2_med > 0
    ? Math.round((tClose.prix_m2_med - tFar.prix_m2_med) / tFar.prix_m2_med * 100) : null

  // ── PEB ──────────────────────────────────────────────────────────────────
  const pebData = peb.filter(r => r.type_local === typeFilter)
  const pebMax  = Math.max(...pebData.map(r => r.prix_m2_med))
  const pebZone = pebData.find(r => r.zone !== "Hors zone PEB")
  const pebHors = pebData.find(r => r.zone === "Hors zone PEB")
  const pebDiff = pebZone && pebHors && pebHors.prix_m2_med > 0
    ? Math.round((pebZone.prix_m2_med - pebHors.prix_m2_med) / pebHors.prix_m2_med * 100) : null

  // ── DPE ──────────────────────────────────────────────────────────────────
  const dpeData = dpe_prix.filter(r => r.type_local === typeFilter)
  const dpeMax  = Math.max(...dpeData.map(r => r.prix_m2_med))
  const dpeA    = dpeData.find(r => r.dpe === "A")
  const dpeG    = dpeData.find(r => r.dpe === "G")
  const dpeDiff = dpeA && dpeG && dpeG.prix_m2_med > 0
    ? Math.round((dpeA.prix_m2_med - dpeG.prix_m2_med) / dpeG.prix_m2_med * 100) : null

  // ── Top/Flop ─────────────────────────────────────────────────────────────
  const topData  = top_communes.filter(r => r.type_local === typeFilter).slice(0,10)
  const flopData = flop_communes.filter(r => r.type_local === typeFilter).slice(0,10)
  const pctPeb   = resume.n_total > 0 ? Math.round((resume.n_en_peb||0)/resume.n_total*100) : 0

  return (
    <div style={{ background:BG, minHeight:"100vh", fontFamily:"'DM Sans',sans-serif", padding:"28px 24px" }}>
      <div style={{ maxWidth:1100, margin:"0 auto" }}>

        {/* Header */}
        <div style={{ marginBottom:28 }}>
          <h1 style={{ fontFamily:"'Syne',sans-serif", fontSize:26, fontWeight:800,
            color:"#1C1917", margin:0, letterSpacing:"-0.03em" }}>
            Analyses du marché
          </h1>
          <p style={{ fontSize:14, color:MUTED, margin:"6px 0 0" }}>
            {fmt(resume.n_total)} transactions · {fmt(resume.n_communes)} communes · {resume.annee_min}–{resume.annee_max}
          </p>
        </div>

        {/* Toggle type */}
        <div style={{ display:"flex", gap:8, marginBottom:24 }}>
          {["Appartement","Maison"].map(t => (
            <button key={t} onClick={() => setTypeFilter(t)} style={{
              padding:"7px 18px", borderRadius:99, fontSize:13, fontWeight:600,
              border:`1.5px solid ${typeFilter===t ? BRAND : BORDER}`,
              background: typeFilter===t ? BRAND : "#fff",
              color: typeFilter===t ? "#fff" : MUTED,
              cursor:"pointer", transition:"all .15s",
            }}>{t}</button>
          ))}
        </div>

        {/* KPIs */}
        <div style={{ display:"flex", gap:12, flexWrap:"wrap", marginBottom:20 }}>
          <KpiCard label="Prix médian global"   value={`${fmt(resume.prix_m2_global)} €/m²`} sub="tous types" />
          <KpiCard label="En zone PEB"           value={fmt(resume.n_en_peb)} sub={`${pctPeb}% des ventes`} color={ACCENT} />

          <KpiCard label="Communes analysées"    value={fmt(resume.n_communes)} sub={`${resume.annee_min}–${resume.annee_max}`} />
        </div>

        {/* Évolution */}
        <Section title="📈 Évolution des prix au m²" subtitle="Prix médian annuel par type de bien">
          {evoEvol !== null && (
            <Insight
              emoji={evoEvol >= 0 ? "📈" : "📉"}
              highlight={Math.abs(evoEvol) > 10}
              text={`Les ${typeFilter.toLowerCase()}s ont <strong>${evoEvol >= 0 ? "augmenté" : "baissé"} de ${Math.abs(evoEvol)}%</strong> entre ${resume.annee_min} et ${resume.annee_max} (${fmt(evoFirst)} → ${fmt(evoLast)} €/m²).`}
            />
          )}
          <LineChartSVG
            data={evolutionData}
            lines={[
              { key:"Appartement", label:"Appartement", color:BRAND },
              { key:"Maison",      label:"Maison",      color:ACCENT },
            ]}
            width={900} height={220}
          />
        </Section>

        {/* Transport */}
        <Section title="🚌 Impact de la proximité aux transports" subtitle="Prix médian selon la distance au premier arrêt">
          {tDiff !== null && (
            <Insight
              emoji="🚌" highlight={Math.abs(tDiff) > 5}
              text={`Les ${typeFilter.toLowerCase()}s à moins de 300m d'un arrêt sont <strong>${tDiff > 0 ? "+" : ""}${tDiff}%</strong> ${tDiff > 0 ? "plus chers" : "moins chers"} que ceux à plus de 2km (${fmt(tClose?.prix_m2_med)} vs ${fmt(tFar?.prix_m2_med)} €/m²).`}
            />
          )}
          <Insight emoji="💡" text="La proximité aux transports est un facteur de valorisation clé, notamment pour les appartements en zone urbaine." />
          {transportData.map(r => (
            <BarH key={r.bucket} label={r.bucket} value={r.prix_m2_med} max={tMax}
              n={r.n}
              color={r.bucket === "< 300 m" ? BRAND : r.bucket === "> 2 km" ? BORDER : BRAND_LIGHT} />
          ))}
        </Section>

        {/* PEB */}
        <Section title="✈️ Impact du bruit aéroport (zones PEB)" subtitle="Comparaison prix en zone de bruit vs hors zone">
          {pebDiff !== null && (
            <Insight emoji="✈️" highlight
              text={`Les ${typeFilter.toLowerCase()}s en zone PEB sont <strong>${Math.abs(pebDiff)}% ${pebDiff < 0 ? "moins chers" : "plus chers"}</strong> que hors zone (${fmt(pebZone?.prix_m2_med)} vs ${fmt(pebHors?.prix_m2_med)} €/m²).`}
            />
          )}
          <Insight emoji="🗺️" text="Les zones PEB (Plan d'Exposition au Bruit) sont classées A→D selon l'intensité des nuisances sonores de l'aéroport Nantes-Atlantique." />
          {pebData.map(r => (
            <BarH key={r.zone} label={r.zone} value={r.prix_m2_med} max={pebMax}
              n={r.n} color={r.zone === "Hors zone PEB" ? BRAND : ACCENT} />
          ))}
        </Section>

        {/* DPE */}
        <Section title="⚡ Performance énergétique et prix" subtitle="Impact de la performance énergétique sur les prix">
          {dpeDiff !== null && (
            <Insight emoji="⚡" highlight={dpeDiff > 15}
              text={`Un ${typeFilter.toLowerCase()} classé A se vend <strong>${dpeDiff > 0 ? "+" : ""}${dpeDiff}%</strong> ${dpeDiff > 0 ? "plus cher" : "moins cher"} qu'un G (${fmt(dpeA?.prix_m2_med)} vs ${fmt(dpeG?.prix_m2_med)} €/m²). La performance énergétique a un impact direct sur la valeur du bien.`}
            />
          )}

          {dpeData.map(r => (
            <BarH key={r.dpe} label={`Classe ${r.dpe}`} value={r.prix_m2_med}
              max={dpeMax} n={r.n} color={DPE_COLORS[r.dpe] ?? "#ccc"} />
          ))}
        </Section>

        {/* Top / Flop */}
        <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:16 }}>
          <Section title="🏆 Communes les plus chères" subtitle={`Top 10 ${typeFilter.toLowerCase()}s (≥ 20 ventes)`}>
            <RankList items={topData} colorFn={() => BRAND} />
          </Section>
          <Section title="📉 Communes les moins chères" subtitle={`Top 10 ${typeFilter.toLowerCase()}s (≥ 20 ventes)`}>
            <RankList items={flopData} colorFn={() => ACCENT} accent />
          </Section>
        </div>

      </div>
    </div>
  )
}
