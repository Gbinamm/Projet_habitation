import { useState, useRef, useEffect } from "react"

const API_URL = "http://localhost:8000"

export default function Chatbot() {
  const [messages, setMessages] = useState([{
    role: "assistant",
    content: "Bonjour ! Je suis votre assistant immobilier. Posez-moi une question sur les prix, la recherche de biens, ou la comparaison de communes.",
  }])
  const [input, setInput]       = useState("")
  const [sessionId, setSessionId] = useState(null)
  const [loading, setLoading]   = useState(false)
  const bottomRef               = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages])

  const sendMessage = async () => {
    if (!input.trim() || loading) return
    const userMsg = input.trim()
    setInput("")
    setMessages(prev => [...prev, { role: "user", content: userMsg }])
    setLoading(true)
    try {
      const res = await fetch(`${API_URL}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: userMsg, session_id: sessionId }),
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      setSessionId(data.session_id)
      setMessages(prev => [...prev, { role: "assistant", content: data.reply }])
    } catch (err) {
      setMessages(prev => [...prev, {
        role: "assistant",
        content: `Erreur : ${err.message}. Le backend est-il lancé ?`,
      }])
    } finally {
      setLoading(false)
    }
  }

  const reset = () => {
    setMessages([{
      role: "assistant",
      content: "Nouvelle conversation. Comment puis-je vous aider ?",
    }])
    setSessionId(null)
  }

  return (
    <div style={{
      display: "flex", flexDirection: "column",
      height: "calc(100vh - 56px)",
      maxWidth: 780, margin: "0 auto",
      padding: "24px 16px",
    }}>

      {/* Titre + reset */}
      <div style={{
        display: "flex", justifyContent: "space-between",
        alignItems: "center", marginBottom: 16,
      }}>
        <div>
          <h1 style={{ fontSize: 20, fontWeight: 700, margin: 0 }}>
            🤖 Assistant Immo
          </h1>
          <p style={{ fontSize: 13, color: "#888", margin: "4px 0 0" }}>
            Posez vos questions sur le marché immobilier
          </p>
        </div>
        <button onClick={reset} style={{
          padding: "7px 14px", fontSize: 13,
          border: "1px solid #ddd", borderRadius: 8,
          background: "#fff", cursor: "pointer", color: "#666",
        }}>
          🗑️ Nouvelle conv.
        </button>
      </div>

      {/* Zone messages */}
      <div style={{
        flex: 1, overflowY: "auto",
        background: "#fff", border: "1px solid #e8e8e8",
        borderRadius: 12, padding: "16px",
        display: "flex", flexDirection: "column", gap: 12,
      }}>
        {messages.map((msg, i) => (
          <div key={i} style={{
            display: "flex",
            justifyContent: msg.role === "user" ? "flex-end" : "flex-start",
          }}>
            {/* Avatar bot */}
            {msg.role === "assistant" && (
              <div style={{
                width: 32, height: 32, borderRadius: "50%",
                background: "#042C53", color: "#fff",
                display: "flex", alignItems: "center", justifyContent: "center",
                fontSize: 14, flexShrink: 0, marginRight: 8, marginTop: 2,
              }}>🤖</div>
            )}

            <div style={{
              maxWidth: "75%", padding: "10px 14px",
              borderRadius: msg.role === "user"
                ? "12px 12px 2px 12px"
                : "12px 12px 12px 2px",
              background: msg.role === "user" ? "#042C53" : "#f4f4f4",
              color:      msg.role === "user" ? "#fff"    : "#1a1a1a",
              fontSize: 14, lineHeight: 1.5,
              whiteSpace: "pre-wrap",
            }}>
              {msg.content}
            </div>

            {/* Avatar user */}
            {msg.role === "user" && (
              <div style={{
                width: 32, height: 32, borderRadius: "50%",
                background: "#e8e8e8", color: "#555",
                display: "flex", alignItems: "center", justifyContent: "center",
                fontSize: 14, flexShrink: 0, marginLeft: 8, marginTop: 2,
              }}>👤</div>
            )}
          </div>
        ))}

        {/* Indicateur de chargement */}
        {loading && (
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <div style={{
              width: 32, height: 32, borderRadius: "50%",
              background: "#042C53", color: "#fff",
              display: "flex", alignItems: "center", justifyContent: "center",
              fontSize: 14,
            }}>🤖</div>
            <div style={{
              padding: "10px 14px", borderRadius: "12px 12px 12px 2px",
              background: "#f4f4f4", fontSize: 14, color: "#888",
            }}>
              <span style={{ letterSpacing: 2 }}>···</span>
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div style={{
        display: "flex", gap: 10, marginTop: 12,
      }}>
        <input
          type="text"
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === "Enter" && sendMessage()}
          placeholder="Ex: Quel est le prix moyen à Nantes ?"
          disabled={loading}
          style={{
            flex: 1, padding: "10px 14px",
            border: "1px solid #ddd", borderRadius: 10,
            fontSize: 14, outline: "none",
            background: loading ? "#f9f9f9" : "#fff",
          }}
        />
        <button
          onClick={sendMessage}
          disabled={loading || !input.trim()}
          style={{
            padding: "10px 20px", background: "#042C53", color: "#fff",
            border: "none", borderRadius: 10, fontSize: 14,
            fontWeight: 500, cursor: loading ? "not-allowed" : "pointer",
            opacity: loading || !input.trim() ? 0.6 : 1,
            transition: "opacity .15s",
          }}
        >
          Envoyer
        </button>
      </div>
    </div>
  )
}
