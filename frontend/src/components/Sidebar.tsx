import { useState, useEffect, useCallback, useRef, KeyboardEvent } from "react";

const API_BASE = "http://localhost:8000/api";
const USER_ID = "default-user";

interface SessionItem {
  session_id: string;
  title: string;
  updated_at: string;
}

interface Props {
  currentSessionId: string | null;
  onSelectSession: (id: string) => void;
}

function PencilIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
      <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
    </svg>
  );
}

function TrashIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="3 6 5 6 21 6" />
      <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" />
      <path d="M10 11v6M14 11v6" />
      <path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2" />
    </svg>
  );
}

export function Sidebar({ currentSessionId, onSelectSession }: Props) {
  const [sessions, setSessions] = useState<SessionItem[]>([]);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editingTitle, setEditingTitle] = useState("");
  const [hoveringId, setHoveringId] = useState<string | null>(null);
  const initializedRef = useRef(false);

  const fetchSessions = useCallback(async () => {
    const res = await fetch(`${API_BASE}/sessions?user_id=${USER_ID}`);
    const data = await res.json();
    setSessions(data.sessions ?? []);
    return data.sessions as SessionItem[];
  }, []);

  const createSession = useCallback(async (): Promise<string> => {
    const res = await fetch(`${API_BASE}/sessions`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: USER_ID }),
    });
    const data = await res.json();
    return data.session_id as string;
  }, []);

  useEffect(() => {
    if (initializedRef.current) return;
    initializedRef.current = true;

    (async () => {
      const list = await fetchSessions();
      if (list.length > 0) {
        onSelectSession(list[0].session_id);
      } else {
        const newId = await createSession();
        await fetchSessions();
        onSelectSession(newId);
      }
    })();
  }, [fetchSessions, createSession, onSelectSession]);

  const handleNewSession = async () => {
    const newId = await createSession();
    await fetchSessions();
    onSelectSession(newId);
  };

  const handleDelete = async (e: React.MouseEvent, sessionId: string) => {
    e.stopPropagation();
    const isActive = currentSessionId === sessionId;
    const remaining = sessions.filter((s) => s.session_id !== sessionId);

    await fetch(`${API_BASE}/sessions/${sessionId}`, { method: "DELETE" });

    if (isActive) {
      if (remaining.length > 0) {
        onSelectSession(remaining[0].session_id);
      } else {
        const newId = await createSession();
        onSelectSession(newId);
      }
    }

    await fetchSessions();
  };

  const handleStartEdit = (e: React.MouseEvent, session: SessionItem) => {
    e.stopPropagation();
    setEditingId(session.session_id);
    setEditingTitle(session.title);
  };

  const handleSaveEdit = async (sessionId: string) => {
    const trimmed = editingTitle.trim();
    if (trimmed) {
      await fetch(`${API_BASE}/sessions/${sessionId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: trimmed }),
      });
      await fetchSessions();
    }
    setEditingId(null);
  };

  const handleEditKeyDown = (e: KeyboardEvent<HTMLInputElement>, sessionId: string) => {
    if (e.key === "Enter") handleSaveEdit(sessionId);
    else if (e.key === "Escape") setEditingId(null);
  };

  return (
    <div style={{
      width: "260px",
      flexShrink: 0,
      height: "100vh",
      background: "#070d18",
      borderRight: "1px solid #1e293b",
      display: "flex",
      flexDirection: "column",
      overflow: "hidden",
    }}>
      {/* Logo / Brand */}
      <div style={{
        padding: "18px 16px 14px",
        borderBottom: "1px solid #1e293b",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "14px" }}>
          <div style={{
            width: "7px", height: "7px",
            borderRadius: "50%",
            background: "#34d399",
            boxShadow: "0 0 6px #34d399",
            flexShrink: 0,
          }} />
          <span style={{
            color: "#64748b",
            fontSize: "11px",
            fontWeight: 600,
            letterSpacing: "0.1em",
            textTransform: "uppercase",
          }}>
            SSI RAG Chatbot
          </span>
        </div>

        <button
          onClick={handleNewSession}
          style={{
            width: "100%",
            padding: "8px 12px",
            background: "#1e293b",
            border: "1px solid #334155",
            borderRadius: "8px",
            color: "#cbd5e1",
            fontSize: "13px",
            cursor: "pointer",
            display: "flex",
            alignItems: "center",
            gap: "8px",
            transition: "background 0.15s",
          }}
          onMouseEnter={(e) => (e.currentTarget.style.background = "#263548")}
          onMouseLeave={(e) => (e.currentTarget.style.background = "#1e293b")}
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
            <line x1="12" y1="5" x2="12" y2="19" />
            <line x1="5" y1="12" x2="19" y2="12" />
          </svg>
          Chat mới
        </button>
      </div>

      {/* Sessions list */}
      <div style={{
        flex: 1,
        overflowY: "auto",
        padding: "8px 6px",
      }}>
        {sessions.length === 0 && (
          <p style={{
            color: "#334155",
            fontSize: "12px",
            textAlign: "center",
            padding: "20px 12px",
          }}>
            Chưa có cuộc trò chuyện nào
          </p>
        )}

        {sessions.map((session) => {
          const isActive = currentSessionId === session.session_id;
          const isEditing = editingId === session.session_id;
          const isHovering = hoveringId === session.session_id;

          return (
            <div
              key={session.session_id}
              onClick={() => {
                if (!isEditing) onSelectSession(session.session_id);
              }}
              onMouseEnter={() => setHoveringId(session.session_id)}
              onMouseLeave={() => setHoveringId(null)}
              style={{
                padding: "7px 10px",
                marginBottom: "1px",
                borderRadius: "7px",
                cursor: "pointer",
                background: isActive ? "#1e293b" : isHovering ? "#111827" : "transparent",
                borderLeft: isActive ? "2px solid #3b82f6" : "2px solid transparent",
                display: "flex",
                alignItems: "center",
                gap: "6px",
                minHeight: "34px",
                transition: "background 0.1s",
              }}
            >
              {isEditing ? (
                <input
                  autoFocus
                  value={editingTitle}
                  onChange={(e) => setEditingTitle(e.target.value)}
                  onBlur={() => handleSaveEdit(session.session_id)}
                  onKeyDown={(e) => handleEditKeyDown(e, session.session_id)}
                  onClick={(e) => e.stopPropagation()}
                  style={{
                    flex: 1,
                    background: "#0f172a",
                    border: "1px solid #3b82f6",
                    borderRadius: "4px",
                    color: "#e2e8f0",
                    fontSize: "13px",
                    padding: "3px 7px",
                    outline: "none",
                    minWidth: 0,
                  }}
                />
              ) : (
                <>
                  <span style={{
                    flex: 1,
                    color: isActive ? "#e2e8f0" : "#94a3b8",
                    fontSize: "13px",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                    lineHeight: "1.4",
                  }}>
                    {session.title}
                  </span>

                  {(isHovering || isActive) && (
                    <div
                      style={{ display: "flex", gap: "2px", flexShrink: 0 }}
                      onClick={(e) => e.stopPropagation()}
                    >
                      <button
                        onClick={(e) => handleStartEdit(e, session)}
                        title="Đổi tên"
                        style={{
                          background: "none",
                          border: "none",
                          cursor: "pointer",
                          color: "#64748b",
                          padding: "3px 5px",
                          borderRadius: "4px",
                          display: "flex",
                          alignItems: "center",
                          transition: "color 0.1s, background 0.1s",
                        }}
                        onMouseEnter={(e) => {
                          e.currentTarget.style.color = "#94a3b8";
                          e.currentTarget.style.background = "#334155";
                        }}
                        onMouseLeave={(e) => {
                          e.currentTarget.style.color = "#64748b";
                          e.currentTarget.style.background = "none";
                        }}
                      >
                        <PencilIcon />
                      </button>
                      <button
                        onClick={(e) => handleDelete(e, session.session_id)}
                        title="Xoá"
                        style={{
                          background: "none",
                          border: "none",
                          cursor: "pointer",
                          color: "#64748b",
                          padding: "3px 5px",
                          borderRadius: "4px",
                          display: "flex",
                          alignItems: "center",
                          transition: "color 0.1s, background 0.1s",
                        }}
                        onMouseEnter={(e) => {
                          e.currentTarget.style.color = "#f87171";
                          e.currentTarget.style.background = "#2d1515";
                        }}
                        onMouseLeave={(e) => {
                          e.currentTarget.style.color = "#64748b";
                          e.currentTarget.style.background = "none";
                        }}
                      >
                        <TrashIcon />
                      </button>
                    </div>
                  )}
                </>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
