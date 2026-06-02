import { BrowserRouter, Routes, Route, NavLink } from "react-router-dom"
import Recherche from "./pages/Recherche"
import Carte     from "./pages/Carte"
import Chatbot from "./pages/Chatbot"

const navStyle = ({ isActive }) => ({
  padding: "6px 16px",
  borderRadius: 8,
  textDecoration: "none",
  fontSize: 14,
  fontWeight: 500,
  color:      isActive ? "#fff"    : "rgba(255,255,255,0.65)",
  background: isActive ? "rgba(255,255,255,0.15)" : "transparent",
  transition: "all .15s",
})

export default function App() {
  return (
    <BrowserRouter>
      {/* ── Header global ── */}
      <div style={{
        position: "sticky", top: 0, zIndex: 200,
        background: "#042C53",
        padding: "0 24px",
        display: "flex", alignItems: "center", gap: 8,
        height: 56,
        boxShadow: "0 1px 4px rgba(0,0,0,.2)",
      }}>
        <span style={{ fontSize: 22, marginRight: 8 }}>🏠</span>
        <span style={{
          color: "#fff", fontWeight: 700, fontSize: 18, marginRight: 24,
        }}>
          ImmoBI
        </span>

        <NavLink to="/"      style={navStyle}>Recherche</NavLink>
        <NavLink to="/carte" style={navStyle}>Carte des prix</NavLink>
        <NavLink to="/chatbot" style={navStyle}>Assistant</NavLink>
      </div>

      {/* ── Pages ── */}
      <Routes>
        <Route path="/"      element={<Recherche />} />
        <Route path="/carte" element={<Carte />} />
        <Route path="/chatbot" element={<Chatbot />} />
      </Routes>
    </BrowserRouter>
  )
}
