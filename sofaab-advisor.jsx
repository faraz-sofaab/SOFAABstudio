import { useState, useRef } from "react";

const SYSTEM_PROMPT = `You are SOFAAB's AI Interior Design Advisor. SOFAAB is a premium Indian furniture brand. Recommend specific SOFAAB sofas, beds, and chairs based on the customer's room and style preferences. Be warm, specific, and mention prices.

PRODUCT KNOWLEDGE:
- Seat Foam Construction: We use a high-quality dual-layer foam system. The top layer is 32D foam to provide a soft, plush sink-in feel, while the bottom layer is 38D high-density foam to ensure long-lasting durability and structural support. Always highlight this when discussing comfort or durability.`;

export default function App() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [apiKey, setApiKey] = useState("AIzaSyBQYkXq4nu2IAlQPQtyE4tQhK6lQ-WaS_8");
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState(null);
  const [debug, setDebug] = useState(null);
  const history = useRef([]);

  const send = async () => {
    const txt = input.trim();
    if (!txt) return;

    setErr(null);
    setDebug(null);
    setMessages(p => [...p, { role: "user", text: txt }]);
    history.current.push({ role: "user", content: txt });
    setInput("");
    setLoading(true);

    try {
      if (!apiKey.trim()) {
        throw new Error("Please enter your Google Gemini API key at the top first.");
      }

      // Format messages for Gemini API
      const geminiContents = history.current.map(m => ({
        role: m.role === "assistant" ? "model" : "user",
        parts: [{ text: m.content }]
      }));

      const res = await fetch(`https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key=${apiKey.trim()}`, {
        method: "POST",
        headers: { 
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          systemInstruction: { parts: [{ text: SYSTEM_PROMPT }] },
          contents: geminiContents,
          generationConfig: { maxOutputTokens: 1000 },
        }),
      });

      const raw = await res.text();
      setDebug(raw); // show raw response

      let json;
      try { json = JSON.parse(raw); } catch(e) { throw new Error("Response not valid JSON: " + raw.slice(0,200)); }

      if (!res.ok) throw new Error(json?.error?.message || `HTTP ${res.status}`);

      const reply = json?.candidates?.[0]?.content?.parts?.[0]?.text;
      if (!reply) throw new Error("No text in candidates[0]. Full response: " + raw.slice(0,300));

      history.current.push({ role: "assistant", content: reply });
      setMessages(p => [...p, { role: "assistant", text: reply }]);
    } catch (e) {
      setErr(e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ padding: 20, fontFamily: "sans-serif", maxWidth: 600, margin: "0 auto" }}>
      <h2>SOFAAB Advisor — Debug Mode</h2>

      <div style={{ marginBottom: 20 }}>
        <input 
          type="password"
          value={apiKey} 
          onChange={e => setApiKey(e.target.value)}
          placeholder="Enter Google Gemini API Key (AIzaSy...)"
          style={{ width: "100%", padding: "10px 14px", borderRadius: 8, border: "1px solid #ccc", fontSize: 14, boxSizing: "border-box" }} 
        />
        <small style={{ color: "#666", marginTop: 4, display: "block" }}>
          Your key remains in your browser and is not stored.
        </small>
      </div>

      {messages.map((m, i) => (
        <div key={i} style={{ margin: "10px 0", textAlign: m.role === "user" ? "right" : "left" }}>
          <span style={{ background: m.role === "user" ? "#c8843a" : "#eee", color: m.role === "user" ? "#fff" : "#000", padding: "8px 14px", borderRadius: 12, display: "inline-block", maxWidth: "80%", textAlign: "left" }}>
            {m.text}
          </span>
        </div>
      ))}

      {loading && <p style={{ color: "#888" }}>Thinking…</p>}
      {err && <div style={{ background: "#fff0ee", border: "1px solid red", padding: 10, borderRadius: 8, margin: "10px 0", fontSize: 13 }}><strong>Error:</strong> {err}</div>}
      {debug && <details style={{ margin: "10px 0", fontSize: 12 }}><summary style={{ cursor: "pointer", color: "#666" }}>Raw API response</summary><pre style={{ background: "#f5f5f5", padding: 10, borderRadius: 6, overflow: "auto", maxHeight: 300 }}>{debug}</pre></details>}

      <div style={{ display: "flex", gap: 8, marginTop: 16 }}>
        <input value={input} onChange={e => setInput(e.target.value)} onKeyDown={e => e.key === "Enter" && send()}
          placeholder="Type a message…"
          style={{ flex: 1, padding: "10px 14px", borderRadius: 8, border: "1px solid #ccc", fontSize: 14 }} />
        <button onClick={send} disabled={loading || !input.trim()}
          style={{ background: "#c8843a", color: "#fff", border: "none", borderRadius: 8, padding: "10px 20px", fontSize: 14, cursor: "pointer" }}>Send</button>
      </div>
    </div>
  );
}
