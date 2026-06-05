import { BrowserRouter, Routes, Route, NavLink } from "react-router-dom"
import Recherche from "./pages/Recherche"
import Carte     from "./pages/Carte"
import Chatbot   from "./pages/Chatbot"

const navLink = ({ isActive }) => ({
  padding: "5px 14px",
  borderRadius: 99,
  textDecoration: "none",
  fontSize: 13,
  fontWeight: 500,
  fontFamily: "'DM Sans', sans-serif",
  letterSpacing: "0.01em",
  color:      isActive ? "#fff" : "rgba(255,255,255,0.6)",
  background: isActive ? "rgba(255,255,255,0.15)" : "transparent",
  border:     isActive ? "1px solid rgba(255,255,255,0.25)" : "1px solid transparent",
  transition: "all .18s ease",
})

export default function App() {
  return (
    <BrowserRouter>
      {/* ── Nav ── */}
      <header style={{
        position: "sticky", top: 0, zIndex: 200,
        height: "var(--nav-h)",
        background: "var(--brand)",
        padding: "0 28px",
        display: "flex", alignItems: "center", gap: 6,
        boxShadow: "0 1px 0 rgba(0,0,0,.08), 0 4px 16px rgba(45,106,79,.18)",
      }}>
        {/* Logo */}
        <div style={{ display: "flex", alignItems: "center", gap: 9, marginRight: 28 }}>
          <div style={{
            width: 30, height: 30, borderRadius: 10,
            background: "var(--accent)",
            display: "flex", alignItems: "center", justifyContent: "center",
            fontSize: 16, flexShrink: 0,
            boxShadow: "0 2px 8px rgba(212,118,74,.4)",
          }}>🪺</div>
          <span style={{
            fontFamily: "'Syne', sans-serif",
            fontWeight: 700, fontSize: 19,
            color: "#fff", letterSpacing: "-0.02em",
          }}>
            nimbus
          </span>
        </div>

        <nav style={{ display: "flex", gap: 4 }}>
          <NavLink to="/"        style={navLink}>Recherche</NavLink>
          <NavLink to="/carte"   style={navLink}>Carte des prix</NavLink>
          <NavLink to="/chatbot" style={navLink}>Assistant</NavLink>
        </nav>

        {/* Tagline discrète à droite */}
        <span style={{
          marginLeft: "auto",
          fontSize: 11, color: "rgba(255,255,255,0.35)",
          fontStyle: "italic", letterSpacing: "0.02em",
          fontFamily: "'DM Sans', sans-serif",
        }}>
          l'immo breton sous la loupe
        </span>
      </header>

      <Routes>
        <Route path="/"        element={<Recherche />} />
        <Route path="/carte"   element={<Carte />} />
        <Route path="/chatbot" element={<Chatbot />} />
      </Routes>
    </BrowserRouter>
  )
}
