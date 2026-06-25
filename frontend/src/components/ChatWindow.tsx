import { useEffect, useRef } from "react";
import { MessageBubble } from "./MessageBubble";
import { InputBar } from "./InputBar";
import { useChat } from "../hooks/useChat";

interface Props {
  sessionId: string;
}

export function ChatWindow({ sessionId }: Props) {
  const { messages, isLoading, isLoadingHistory, sendMessage, stopStreaming } = useChat(sessionId);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  return (
    <div style={{
      display: "flex",
      flexDirection: "column",
      height: "100vh",
      background: "#0f172a",
    }}>
      {/* Header */}
      <div style={{
        padding: "16px 20px",
        borderBottom: "1px solid #1e293b",
        display: "flex",
        alignItems: "center",
        gap: "10px",
        background: "#0f172a",
        flexShrink: 0,
      }}>
        <div style={{
          width: "8px", height: "8px",
          borderRadius: "50%",
          background: "#34d399",
          boxShadow: "0 0 6px #34d399",
        }} />
        <span style={{ color: "#94a3b8", fontSize: "13px", fontWeight: 500, letterSpacing: "0.05em" }}>
          SSI FINANCIAL ANALYST
        </span>
      </div>

      {/* Messages */}
      <div style={{
        flex: 1,
        overflowY: "auto",
        padding: "20px 16px",
        display: "flex",
        flexDirection: "column",
        gap: "12px",
      }}>
        {isLoadingHistory ? (
          <div style={{ textAlign: "center", marginTop: "60px", color: "#334155", fontSize: "14px" }}>
            Đang tải lịch sử...
          </div>
        ) : (
          <>
            {messages.length === 0 && (
              <div style={{ textAlign: "center", marginTop: "60px" }}>
                <p style={{ color: "#475569", fontSize: "16px", fontWeight: 300 }}>
                  Đặt câu hỏi về báo cáo tài chính SSI
                </p>
                <div style={{ marginTop: "20px", display: "flex", flexDirection: "column", gap: "8px", alignItems: "center" }}>
                  {[
                    "Doanh thu thuần Q1 2024 là bao nhiêu?",
                    "Lợi nhuận sau thuế năm 2023 thay đổi như thế nào?",
                    "Tổng tài sản của SSI hiện tại là bao nhiêu?",
                  ].map((q) => (
                    <button
                      key={q}
                      onClick={() => sendMessage(q)}
                      style={{
                        background: "#1e293b",
                        border: "1px solid #334155",
                        borderRadius: "8px",
                        padding: "8px 16px",
                        color: "#94a3b8",
                        fontSize: "13px",
                        cursor: "pointer",
                        maxWidth: "360px",
                        textAlign: "left",
                      }}
                    >
                      {q}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {messages.map((msg) => (
              <MessageBubble key={msg.id} message={msg} />
            ))}
          </>
        )}

        <div ref={bottomRef} />
      </div>

      <InputBar
        onSend={sendMessage}
        onStop={stopStreaming}
        isLoading={isLoading}
        disabled={isLoadingHistory}
      />
    </div>
  );
}
