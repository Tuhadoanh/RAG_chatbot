import { useState } from "react";
import type { Message } from "../hooks/useChat";

interface Props {
  message: Message;
}

export function MessageBubble({ message }: Props) {
  const [showSources, setShowSources] = useState(false);
  const isAI = message.role === "ai";

  return (
    <div style={{
      display: "flex",
      justifyContent: isAI ? "flex-start" : "flex-end",
      marginBottom: "4px",
    }}>
      <div style={{ maxWidth: "75%", minWidth: "60px" }}>
        <div style={{
          background: isAI ? "#1e293b" : "#2563eb",
          color: "#e2e8f0",
          borderRadius: isAI ? "4px 16px 16px 16px" : "16px 4px 16px 16px",
          padding: "10px 14px",
          fontSize: "14px",
          lineHeight: "1.6",
          wordBreak: "break-word",
          whiteSpace: "pre-wrap",
          border: isAI ? "1px solid #334155" : "none",
        }}>
          {message.content}
          {message.isStreaming && (
            <span style={{
              display: "inline-block",
              width: "3px",
              height: "16px",
              background: "#34d399",
              marginLeft: "4px",
              verticalAlign: "middle",
              animation: "blink 1s infinite",
            }} />
          )}
        </div>

        {isAI && message.sources && message.sources.length > 0 && !message.isStreaming && (
          <div style={{ marginTop: "6px" }}>
            <button
              onClick={() => setShowSources(!showSources)}
              style={{
                background: "none",
                border: "none",
                color: "#64748b",
                fontSize: "12px",
                cursor: "pointer",
                padding: "2px 0",
                display: "flex",
                alignItems: "center",
                gap: "4px",
              }}
            >
              📄 {message.sources.length} nguồn tham chiếu {showSources ? "▲" : "▼"}
            </button>

            {showSources && (
              <div style={{ marginTop: "6px", display: "flex", flexDirection: "column", gap: "6px" }}>
                {message.sources.map((src, i) => (
                  <div key={i} style={{
                    background: "#0f172a",
                    border: "1px solid #1e3a5f",
                    borderRadius: "8px",
                    padding: "10px 12px",
                    fontSize: "12px",
                  }}>
                    <div style={{ display: "flex", gap: "8px", marginBottom: "4px", flexWrap: "wrap" }}>
                      <span style={{ color: "#60a5fa", fontWeight: 500 }}>{src.source}</span>
                      <span style={{ color: "#6b7280" }}>tr.{src.page}</span>
                      {src.section && (
                        <span style={{ color: "#4b5563", fontStyle: "italic" }}>{src.section}</span>
                      )}
                    </div>
                    <p style={{ color: "#94a3b8", lineHeight: "1.5", margin: 0 }}>
                      {src.content_preview}
                    </p>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
