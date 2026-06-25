import { useState } from "react";
import { Sidebar } from "./components/Sidebar";
import { ChatWindow } from "./components/ChatWindow";

export default function App() {
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);

  return (
    <div style={{
      width: "100vw",
      height: "100vh",
      background: "#0f172a",
      display: "flex",
      overflow: "hidden",
    }}>
      <Sidebar
        currentSessionId={currentSessionId}
        onSelectSession={setCurrentSessionId}
      />

      <div style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column" }}>
        {currentSessionId ? (
          <ChatWindow sessionId={currentSessionId} />
        ) : (
          <div style={{
            flex: 1,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color: "#334155",
            fontSize: "14px",
          }}>
            Đang khởi động...
          </div>
        )}
      </div>
    </div>
  );
}
