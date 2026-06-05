import { useState, useEffect } from "react"
import { getStatsGlobal } from "../api/client"
import {
  LineChart, Line, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip,
  Legend, Cell,
} from "recharts"

// ── Design tokens ─────────────────────────────────────────────────────────
const BRAND       = "#2D6A4F"
const BRAND_LIGHT = "#52B788"
const ACCENT      = "#D4764A"
const MUTED       = "#78716C"
const BORDER      = "#E8E3DC"
const BG          = "#F7F5F2"

const DPE_COLORS = {
  A:"#009966", B:"#33cc66", C:"#99cc00",
  D:"#ffcc00", E:"#ff9900", F:"#ff6600", G:"#cc0000",
}

function fmt(n) { return n?.toLocaleString("fr-FR") ?? "—" }

// ── Composants UI ─────────────────────────────────────────────────────────
function Section({ title, subtitle, children }) {
  return (
    <div style={{
      background:"#fff", border:`1.5px solid ${BORDER}`,
      borderRadius:16, padding:"24px 28px", marginBottom:20,
    }}>
      <div style={{ marginBottom:16 }}>
        <h2 style={{
          fontFamily:"'Syne', sans-serif", fontSize:17,
          fontWeight:700, color:"#1C1917", margin:0, letterSpacing:"-0.02em",
        }}>{title}</h2>
        {subtitle && (
          <p style={{ fontSize:13, color:MUTED, margin:"4px 0 0" }}>{subtitle}</p>
        )}
      </div>
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
      color:"#1C1917", lineHeight:1.5,
    }}>
      <span style={{ fontSize:16, flexShrink:0 }}>{emoji}</span>
      <span dangerouslySetInnerHTML={{ __html: text }} />
    </div>
  )
}

function KpiCard({ label, value, sub, color }) {
  return (
    <div style={{
      background:"#fff", border:`1.5px solid ${BORDER}`,
      borderRadius:14, padding:"18px 20px", flex:1, minWidth:140,
    }}>
      <div style={{ fontSize:11, color:MUTED, fontWeight:500,
        textTransform:"uppercase", letterSpacing:"0.04em", marginBottom:6 }}>
        {label}
      </div>
      <div style={{ fontSize:24, fontWeight:800, color: color ?? BRAND,
        letterSpacing:"-0.02em", fontFamily:"'Syne', sans-serif" }}>
        {value}
      </div>
      {sub && <div style={{ fontSize:12, color:MUTED, marginTop:4 }}>{sub}</div>}
    </div>
  )
}

const customTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  return (
    <div style={{ background:"#fff", border:`1.5px solid ${BORDER}`,
      borderRadius:10, padding:"10px 14px", fontSize:12 }}>
      <div style={{ fontWeight:600, marginBottom:4 }}>{label}</div>
      {payload.map((p, i) => (
        <div key={i} style={{ color:p.color }}>
          {p.name} : <strong>{fmt(p.value)} €/m²</strong>
        </div>
      ))}
    </div>
  )
}

// ── Page principale ────────────────────────────────────────────────────────
export default function Stats() {
  const [data, setData]     = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [typeFilter, setTypeFilter] = useState("Appartement")

  useEffect(() => {
    getStatsGlobal()
      .then((res) => {
        setData(res)
        setLoading(false)
      })
      .catch((err) => {
        console.error("Erreur lors de la récupération des stats :", err)
        setError(err)
        setLoading(false)
      })
  }, [])

  if (loading) return (
    <div style={{ textAlign:"center", padding:100, color:MUTED,
      fontFamily:"'DM Sans', sans-serif" }}>
      <div style={{ fontSize:36, marginBottom:16 }}>📊</div>
      Chargement des analyses…
    </div>
  )

  if (error || !data) return (
    <div style={{ textAlign:"center", padding:100, color:MUTED }}>
      <div style={{ fontSize:36, marginBottom:16 }}>⚠️</div>
      Erreur de chargement des données. Vérifiez la console.
    </div>
  )

  const { 
    resume = {}, 
    evolution = [], 
    peb = [], 
    transport = [], 
    top_communes = [], 
    flop_communes = [], 
    dpe_prix = [] 
  } = data

  // ── Préparer données graphiques ──────────────────────────────────────────

  const evolutionByYear = {}
  for (const r of evolution) {
    if (!evolutionByYear[r.annee]) evolutionByYear[r.annee] = { annee: r.annee }
    evolutionByYear[r.annee][r.type_local] = r.prix_m2_med
  }
  const evolutionData = Object.values(evolutionByYear).sort((a,b) => a.annee - b.annee)

  const evoFiltered = evolution.filter(e => e.type_local === typeFilter)
  const evoFirst = evoFiltered[0]?.prix_m2_med
  const evoLast  = evoFiltered[evoFiltered.length - 1]?.prix_m2_med
  const evoEvol  = evoFirst && evoLast
    ? Math.round((evoLast - evoFirst) / evoFirst * 100) : null

  const transportData = transport
    .filter(r => r.type_local === typeFilter)
    .map(r => ({ ...r, name: r.bucket }))

  const tClose = transport.find(r => r.type_local===typeFilter && r.bucket==="< 300 m")
  const tFar   = transport.find(r => r.type_local===typeFilter && r.bucket==="> 2 km")
  const tDiff  = tClose && tFar && tFar.prix_m2_med > 0
    ? Math.round((tClose.prix_m2_med - tFar.prix_m2_med) / tFar.prix_m2_med * 100) : null

  const pebData = peb.filter(r => r.type_local === typeFilter)
  const pebZone = pebData.find(r => r.zone !== "Hors zone PEB")
  const pebHors = pebData.find(r => r.zone === "Hors zone PEB")
  const pebDiff = pebZone && pebHors && pebHors.prix_m2_med > 0
    ? Math.round((pebZone.prix_m2_med - pebHors.prix_m2_med) / pebHors.prix_m2_med * 100) : null

  const dpeData = dpe_prix
    .filter(r => r.type_local === typeFilter)
    .map(r => ({ ...r, name: `Classe ${r.dpe}` }))
  const dpeA = dpeData.find(r => r.dpe === "A")
  const dpeG = dpeData.find(r => r.dpe === "G")
  const dpeDiff = dpeA && dpeG && dpeG.prix_m2_med > 0
    ? Math.round((dpeA.prix_m2_med - dpeG.prix_m2_med) / dpeG.prix_m2_med * 100) : null

  const topData  = top_communes.filter(r => r.type_local === typeFilter).slice(0, 10)
  const flopData = flop_communes.filter(r => r.type_local === typeFilter).slice(0, 10)

  const pctVentesPeb = resume.n_total > 0 ? Math.round((resume.n_en_peb || 0) / resume.n_total * 100) : 0

  return (
    <div style={{ background:BG, minHeight:"100vh",
      fontFamily:"'DM Sans', sans-serif", padding:"28px 24px" }}>
      <div style={{ maxWidth:1100, margin:"0 auto" }}>

        <div style={{ marginBottom:28 }}>
          <h1 style={{
            fontFamily:"'Syne', sans-serif", fontSize:26, fontWeight:800,
            color:"#1C1917", margin:0, letterSpacing:"-0.03em",
          }}>
            Analyses du marché
          </h1>
          <p style={{ fontSize:14, color:MUTED, margin:"6px 0 0" }}>
            {fmt(resume.n_total)} transactions · {fmt(resume.n_communes)} communes ·{" "}
            {resume.annee_min ?? "—"}–{resume.annee_max ?? "—"}
          </p>
        </div>

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

        <div style={{ display:"flex", gap:12, flexWrap:"wrap", marginBottom:20 }}>
          <KpiCard
            label="Prix médian global"
            value={`${fmt(resume.prix_m2_global)} €/m²`}
            sub="tous types confondus"
          />
          <KpiCard
            label="En zone PEB"
            value={fmt(resume.n_en_peb)}
            sub={`${pctVentesPeb}% des ventes`}
            color={ACCENT}
          />
          <KpiCard
            label="% passoires therm."
            value={`${resume.pct_passoires_moy ?? "—"}%`}
            sub="moyenne des communes"
            color={resume.pct_passoires_moy > 30 ? "#DC2626" : BRAND}
          />
          <KpiCard
            label="Communes analysées"
            value={fmt(resume.n_communes)}
            sub={`${resume.annee_min ?? "—"}–${resume.annee_max ?? "—"}`}
          />
        </div>

        <Section
          title="📈 Évolution des prix au m²"
          subtitle="Prix médian annuel par type de bien"
        >
          <div style={{ display:"flex", gap:10, flexDirection:"column" }}>
            {evoEvol !== null && (
              <Insight
                emoji={evoEvol >= 0 ? "📈" : "📉"}
                highlight={Math.abs(evoEvol) > 10}
                text={`Les ${typeFilter.toLowerCase()}s ont <strong>${evoEvol >= 0 ? "augmenté" : "baissé"} de ${Math.abs(evoEvol)}%</strong> entre ${resume.annee_min ?? "—"} et ${resume.annee_max ?? "—"} (${fmt(evoFirst)} → ${fmt(evoLast)} €/m²).`}
              />
            )}
          </div>
          {evolutionData.length > 0 ? (
            <div style={{ marginTop:16, width: '100%', overflowX: 'auto' }}>
              <LineChart width={1000} height={280} data={evolutionData}>
                <CartesianGrid strokeDasharray="3 3" stroke={BORDER} />
                <XAxis dataKey="annee" tick={{ fontSize:12, fill:MUTED }} />
                <YAxis tick={{ fontSize:12, fill:MUTED }}
                  tickFormatter={v => `${(v/1000).toFixed(0)}k`} />
                <Tooltip content={customTooltip} />
                <Legend />
                <Line type="monotone" dataKey="Appartement"
                  stroke={BRAND} strokeWidth={2.5} dot={{ r:4 }} />
                <Line type="monotone" dataKey="Maison"
                  stroke={ACCENT} strokeWidth={2.5} dot={{ r:4 }} />
              </LineChart>
            </div>
          ) : (
            <div style={{ padding: 40, textAlign: "center", color: MUTED, fontSize: 13 }}>Aucune donnée d'évolution disponible.</div>
          )}
        </Section>

        <Section
          title="🚌 Impact de la proximité aux transports"
          subtitle="Prix médian selon la distance au premier arrêt"
        >
          <div style={{ display:"flex", flexDirection:"column", gap:8, marginBottom:16 }}>
            {tDiff !== null && (
              <Insight
                emoji="🚌"
                highlight={Math.abs(tDiff) > 5}
                text={`Les ${typeFilter.toLowerCase()}s à moins de 300m d'un arrêt sont en moyenne <strong>${tDiff > 0 ? "+" : ""}${tDiff}%</strong> ${tDiff > 0 ? "plus chers" : "moins chers"} que ceux à plus de 2km (${fmt(tClose?.prix_m2_med)} vs ${fmt(tFar?.prix_m2_med)} €/m²).`}
              />
            )}
            <Insight
              emoji="💡"
              text="La proximité aux transports en commun est un facteur de valorisation important, notamment pour les appartements en zone urbaine."
            />
          </div>
          {transportData.length > 0 ? (
             <div style={{ width: '100%', overflowX: 'auto' }}>
              <BarChart width={1000} height={240} data={transportData} barSize={40}>
                <CartesianGrid strokeDasharray="3 3" stroke={BORDER} vertical={false} />
                <XAxis dataKey="bucket" tick={{ fontSize:11, fill:MUTED }} />
                <YAxis tick={{ fontSize:12, fill:MUTED }}
                  tickFormatter={v => `${(v/1000).toFixed(0)}k`} />
                <Tooltip content={customTooltip} />
                <Bar dataKey="prix_m2_med" name="Prix médian/m²" radius={[6,6,0,0]}>
                  {transportData.map((_, i) => (
                    <Cell key={i}
                      fill={i === 0 ? BRAND : i === transportData.length-1 ? "#E8E3DC" : BRAND_LIGHT}
                    />
                  ))}
                </Bar>
              </BarChart>
            </div>
          ) : (
             <div style={{ padding: 40, textAlign: "center", color: MUTED, fontSize: 13 }}>Aucune donnée de transport disponible.</div>
          )}
        </Section>

        <Section
          title="✈️ Impact du bruit aéroport (zones PEB)"
          subtitle="Comparaison prix en zone de bruit vs hors zone"
        >
          <div style={{ display:"flex", flexDirection:"column", gap:8, marginBottom:16 }}>
            {pebDiff !== null && (
              <Insight
                emoji="✈️"
                highlight
                text={`Les ${typeFilter.toLowerCase()}s en zone PEB sont <strong>${Math.abs(pebDiff)}% ${pebDiff < 0 ? "moins chers" : "plus chers"}</strong> que hors zone (${fmt(pebZone?.prix_m2_med)} vs ${fmt(pebHors?.prix_m2_med)} €/m²). La décote liée au bruit aéroport est réelle et mesurable.`}
              />
            )}
            <Insight
              emoji="🗺️"
              text="Les zones PEB (Plan d'Exposition au Bruit) sont classées A, B, C, D selon l'intensité des nuisances sonores de l'aéroport Nantes-Atlantique."
            />
          </div>
          {pebData.length > 0 ? (
             <div style={{ width: '100%', overflowX: 'auto' }}>
              <BarChart width={1000} height={200} data={pebData} barSize={50} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" stroke={BORDER} horizontal={false} />
                <XAxis type="number" tick={{ fontSize:11, fill:MUTED }}
                  tickFormatter={v => `${(v/1000).toFixed(0)}k`} />
                <YAxis type="category" dataKey="zone" width={160}
                  tick={{ fontSize:11, fill:MUTED }} />
                <Tooltip content={customTooltip} />
                <Bar dataKey="prix_m2_med" name="Prix médian/m²" radius={[0,6,6,0]}>
                  {pebData.map((r, i) => (
                    <Cell key={i}
                      fill={r.zone === "Hors zone PEB" ? BRAND : ACCENT}
                    />
                  ))}
                </Bar>
              </BarChart>
            </div>
          ) : (
            <div style={{ padding: 40, textAlign: "center", color: MUTED, fontSize: 13 }}>Aucune donnée PEB disponible.</div>
          )}
        </Section>

        <Section
          title="⚡ Performance énergétique et prix"
          subtitle="Les passoires thermiques se vendent-elles moins cher ?"
        >
          <div style={{ display:"flex", flexDirection:"column", gap:8, marginBottom:16 }}>
            {dpeDiff !== null && (
              <Insight
                emoji="⚡"
                highlight={Math.abs(dpeDiff) > 15}
                text={`Un ${typeFilter.toLowerCase()} classé A se vend <strong>${dpeDiff > 0 ? "+" : ""}${dpeDiff}%</strong> ${dpeDiff > 0 ? "plus cher" : "moins cher"} qu'un G (${fmt(dpeA?.prix_m2_med)} vs ${fmt(dpeG?.prix_m2_med)} €/m²). La rénovation énergétique a un impact direct sur la valeur.`}
              />
            )}
            <Insight
              emoji="🔥"
              text={`${resume.pct_passoires_moy ?? 0}% des biens sont des passoires thermiques (DPE F ou G) en moyenne sur la zone. Depuis 2025, les logements G ne peuvent plus être loués.`}
            />
          </div>
          {dpeData.length > 0 ? (
             <div style={{ width: '100%', overflowX: 'auto' }}>
              <BarChart width={1000} height={240} data={dpeData} barSize={38}>
                <CartesianGrid strokeDasharray="3 3" stroke={BORDER} vertical={false} />
                <XAxis dataKey="name" tick={{ fontSize:12, fill:MUTED }} />
                <YAxis tick={{ fontSize:12, fill:MUTED }}
                  tickFormatter={v => `${(v/1000).toFixed(0)}k`} />
                <Tooltip content={customTooltip} />
                <Bar dataKey="prix_m2_med" name="Prix médian/m²" radius={[6,6,0,0]}>
                  {dpeData.map((r, i) => (
                    <Cell key={i} fill={DPE_COLORS[r.dpe] ?? "#ccc"} />
                  ))}
                </Bar>
              </BarChart>
            </div>
           ) : (
            <div style={{ padding: 40, textAlign: "center", color: MUTED, fontSize: 13 }}>Aucune donnée DPE disponible.</div>
          )}
        </Section>

        <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:16 }}>

          <Section title="🏆 Communes les plus chères" subtitle={`Top 10 ${typeFilter.toLowerCase()}s (≥ 20 ventes)`}>
            <div style={{ display:"flex", flexDirection:"column", gap:6 }}>
              {topData.length > 0 ? topData.map((r, i) => (
                <div key={r.commune} style={{
                  display:"flex", justifyContent:"space-between",
                  alignItems:"center", padding:"8px 12px",
                  background: i === 0 ? "#F0F7F4" : BG,
                  borderRadius:8, fontSize:13,
                }}>
                  <div style={{ display:"flex", alignItems:"center", gap:8 }}>
                    <span style={{ width:20, color:MUTED, fontSize:11, fontWeight:600 }}>
                      {i+1}
                    </span>
                    <span style={{ fontWeight: i < 3 ? 600 : 400 }}>{r.commune}</span>
                  </div>
                  <span style={{ fontWeight:700, color:BRAND }}>
                    {fmt(r.prix_m2_med)} €/m²
                  </span>
                </div>
              )) : <div style={{ color: MUTED, fontSize: 13 }}>Pas de données</div>}
            </div>
          </Section>

          <Section title="📉 Communes les moins chères" subtitle={`Top 10 ${typeFilter.toLowerCase()}s (≥ 20 ventes)`}>
            <div style={{ display:"flex", flexDirection:"column", gap:6 }}>
              {flopData.length > 0 ? flopData.map((r, i) => (
                <div key={r.commune} style={{
                  display:"flex", justifyContent:"space-between",
                  alignItems:"center", padding:"8px 12px",
                  background: BG, borderRadius:8, fontSize:13,
                }}>
                  <div style={{ display:"flex", alignItems:"center", gap:8 }}>
                    <span style={{ width:20, color:MUTED, fontSize:11, fontWeight:600 }}>
                      {i+1}
                    </span>
                    <span>{r.commune}</span>
                  </div>
                  <span style={{ fontWeight:700, color:ACCENT }}>
                    {fmt(r.prix_m2_med)} €/m²
                  </span>
                </div>
              )) : <div style={{ color: MUTED, fontSize: 13 }}>Pas de données</div>}
            </div>
          </Section>

        </div>

      </div>
    </div>
  )
}