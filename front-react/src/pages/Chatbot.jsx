import { useState, useRef, useEffect } from "react"

const API_URL = "http://localhost:8000"

export default function Chatbot() {
  const [messages, setMessages] = useState([{
    role: "assistant",
    content: "Bonjour ! Je suis Nimbus, votre assistant immo breton. Posez-moi une question sur les prix, les communes ou le marché.",
  }])
  const [input, setInput]         = useState("")
  const [sessionId, setSessionId] = useState(null)
  const [loading, setLoading]     = useState(false)
  const bottomRef                 = useRef(null)

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior:"smooth" }) }, [messages])

  const sendMessage = async () => {
    if (!input.trim() || loading) return
    const userMsg = input.trim()
    setInput("")
    setMessages(prev => [...prev, { role:"user", content:userMsg }])
    setLoading(true)
    try {
      const res = await fetch(`${API_URL}/chat`, {
        method: "POST",
        headers: { "Content-Type":"application/json" },
        body: JSON.stringify({ message:userMsg, session_id:sessionId }),
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      setSessionId(data.session_id)
      setMessages(prev => [...prev, { role:"assistant", content:data.reply }])
    } catch (err) {
      setMessages(prev => [...prev, { role:"assistant", content:`Erreur : ${err.message}` }])
    } finally { setLoading(false) }
  }

  const reset = () => {
    setMessages([{ role:"assistant", content:"Nouvelle conversation. Comment puis-je vous aider ?" }])
    setSessionId(null)
  }

  return (
    <div style={{
      display:"flex", flexDirection:"column",
      height:"calc(100vh - var(--nav-h))",
      maxWidth:760, margin:"0 auto",
      padding:"28px 20px",
      fontFamily:"'DM Sans', sans-serif",
    }}>
      {/* Header */}
      <div style={{ display:"flex", justifyContent:"space-between", alignItems:"flex-start", marginBottom:20 }}>
        <div>
          <h1 style={{ fontSize:20, fontWeight:700, color:"var(--text)", margin:0,
            fontFamily:"'Syne', sans-serif", letterSpacing:"-0.02em" }}>
            🪺 Assistant Nimbus
          </h1>
          <p style={{ fontSize:13, color:"var(--muted)", margin:"4px 0 0" }}>
            Questions sur le marché immo breton
          </p>
        </div>
        <button onClick={reset} style={{
          padding:"7px 14px", fontSize:12, fontWeight:500,
          border:"1.5px solid var(--border)", borderRadius:10,
          background:"var(--surface)", cursor:"pointer", color:"var(--muted)",
        }}>
          Nouvelle conv.
        </button>
      </div>

      {/* Messages */}
      <div style={{
        flex:1, overflowY:"auto",
        background:"var(--surface)",
        border:"1.5px solid var(--border)",
        borderRadius:16, padding:"20px",
        display:"flex", flexDirection:"column", gap:14,
      }}>
        {messages.map((msg, i) => (
          <div key={i} style={{ display:"flex",
            justifyContent: msg.role === "user" ? "flex-end" : "flex-start" }}>
            {msg.role === "assistant" && (
              <div style={{
                width:32, height:32, borderRadius:10,
                background:"var(--brand)", color:"#fff",
                display:"flex", alignItems:"center", justifyContent:"center",
                fontSize:14, flexShrink:0, marginRight:10, marginTop:2,
              }}>🪺</div>
            )}
            <div style={{
              maxWidth:"74%", padding:"10px 14px",
              borderRadius: msg.role === "user" ? "14px 14px 3px 14px" : "14px 14px 14px 3px",
              background: msg.role === "user" ? "var(--brand)" : "var(--bg)",
              color: msg.role === "user" ? "#fff" : "var(--text)",
              fontSize:14, lineHeight:1.55, whiteSpace:"pre-wrap",
              border: msg.role === "user" ? "none" : "1.5px solid var(--border)",
            }}>
              {msg.content}
            </div>
            {msg.role === "user" && (
              <div style={{
                width:32, height:32, borderRadius:10,
                background:"var(--bg)", border:"1.5px solid var(--border)",
                display:"flex", alignItems:"center", justifyContent:"center",
                fontSize:14, flexShrink:0, marginLeft:10, marginTop:2,
              }}>👤</div>
            )}
          </div>
        ))}
        {loading && (
          <div style={{ display:"flex", alignItems:"center", gap:10 }}>
            <div style={{ width:32, height:32, borderRadius:10, background:"var(--brand)",
              color:"#fff", display:"flex", alignItems:"center", justifyContent:"center", fontSize:14 }}>🪺</div>
            <div style={{ padding:"10px 14px", borderRadius:"14px 14px 14px 3px",
              background:"var(--bg)", border:"1.5px solid var(--border)", fontSize:14, color:"var(--muted)" }}>
              <span style={{ letterSpacing:3 }}>···</span>
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div style={{ display:"flex", gap:10, marginTop:14 }}>
        <input
          type="text" value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === "Enter" && sendMessage()}
          placeholder="Ex: Quel est le prix moyen à Rennes ?"
          disabled={loading}
          style={{
            flex:1, padding:"11px 16px",
            border:"1.5px solid var(--border)", borderRadius:12,
            fontSize:14, outline:"none",
            background: loading ? "var(--bg)" : "var(--surface)",
            fontFamily:"'DM Sans', sans-serif",
            color:"var(--text)",
          }}
        />
        <button onClick={sendMessage} disabled={loading || !input.trim()} style={{
          padding:"11px 22px", background:"var(--brand)", color:"#fff",
          border:"none", borderRadius:12, fontSize:14, fontWeight:600,
          cursor: loading || !input.trim() ? "not-allowed" : "pointer",
          opacity: loading || !input.trim() ? 0.5 : 1,
          transition:"opacity .15s",
          boxShadow: "0 2px 8px rgba(45,106,79,.25)",
        }}>
          Envoyer
        </button>
      </div>
    </div>
  )
}
