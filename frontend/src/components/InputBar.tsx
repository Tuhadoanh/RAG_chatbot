import { useState, KeyboardEvent } from "react";

interface Props {
  onSend: (message: string) => void;
  onStop: () => void;
  isLoading: boolean;
  disabled?: boolean;
}

export function InputBar({ onSend, onStop, isLoading, disabled = false }: Props) {
  const [input, setInput] = useState("");

  const handleSend = () => {
    if (input.trim() && !disabled) {
      onSend(input.trim());
      setInput("");
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div style={{ padding: "12px 16px", borderTop: "1px solid #2d2d2d", flexShrink: 0 }}>
      <div style={{
        display: "flex",
        alignItems: "flex-end",
        gap: "8px",
        background: "#1e1e1e",
        borderRadius: "12px",
        padding: "8px",
        border: "1px solid #3d3d3d",
        opacity: disabled ? 0.5 : 1,
      }}>
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Đặt câu hỏi về báo cáo tài chính SSI..."
          rows={1}
          disabled={isLoading || disabled}
          style={{
            flex: 1,
            background: "transparent",
            border: "none",
            outline: "none",
            color: "#e5e5e5",
            fontSize: "14px",
            resize: "none",
            minHeight: "36px",
            maxHeight: "120px",
            padding: "4px 8px",
            fontFamily: "inherit",
          }}
        />
        {isLoading && !disabled ? (
          <button
            onClick={onStop}
            style={{
              padding: "8px 12px",
              background: "#dc2626",
              border: "none",
              borderRadius: "8px",
              color: "white",
              cursor: "pointer",
              fontSize: "13px",
              whiteSpace: "nowrap",
            }}
          >
            ■ Dừng
          </button>
        ) : (
          <button
            onClick={handleSend}
            disabled={!input.trim() || disabled}
            style={{
              padding: "8px 14px",
              background: input.trim() && !disabled ? "#2563eb" : "#374151",
              border: "none",
              borderRadius: "8px",
              color: "white",
              cursor: input.trim() && !disabled ? "pointer" : "not-allowed",
              fontSize: "13px",
              whiteSpace: "nowrap",
            }}
          >
            Gửi ↑
          </button>
        )}
      </div>
      <p style={{ textAlign: "center", fontSize: "11px", color: "#6b7280", marginTop: "6px" }}>
        Enter để gửi · Shift+Enter để xuống dòng
      </p>
    </div>
  );
}
