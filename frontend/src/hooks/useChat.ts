import { useState, useCallback, useRef, useEffect } from "react";

export type SourceDoc = {
  source: string;
  page: number;
  section: string;
  content_preview: string;
};

export type Message = {
  id: string;
  role: "human" | "ai";
  content: string;
  sources?: SourceDoc[];
  isStreaming?: boolean;
};

const API_BASE = "http://localhost:8000/api";

export function useChat(sessionId: string) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    abortRef.current?.abort();
    setIsLoading(false);
    setMessages([]);
    setIsLoadingHistory(true);

    let cancelled = false;
    fetch(`${API_BASE}/sessions/${sessionId}/history`)
      .then((r) => r.json())
      .then((data) => {
        if (cancelled) return;
        const msgs: Message[] = (data.messages ?? []).map(
          (m: { role: "human" | "ai"; content: string }, i: number) => ({
            id: `hist-${sessionId}-${i}`,
            role: m.role,
            content: m.content,
          })
        );
        setMessages(msgs);
      })
      .catch(() => {})
      .finally(() => {
        if (!cancelled) setIsLoadingHistory(false);
      });

    return () => {
      cancelled = true;
    };
  }, [sessionId]);

  const sendMessage = useCallback(
    async (question: string) => {
      if (!question.trim() || isLoading) return;

      const userMsg: Message = {
        id: Date.now().toString(),
        role: "human",
        content: question,
      };

      const aiMsgId = (Date.now() + 1).toString();
      const aiMsg: Message = {
        id: aiMsgId,
        role: "ai",
        content: "",
        isStreaming: true,
      };

      setMessages((prev) => [...prev, userMsg, aiMsg]);
      setIsLoading(true);
      abortRef.current = new AbortController();

      try {
        const response = await fetch(`${API_BASE}/chat/stream`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ session_id: sessionId, question }),
          signal: abortRef.current.signal,
        });

        if (!response.ok) throw new Error("Stream failed");

        const reader = response.body!.getReader();
        const decoder = new TextDecoder();

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          const text = decoder.decode(value);
          const lines = text.split("\n");

          for (const line of lines) {
            if (!line.startsWith("data: ")) continue;
            const data = line.slice(6);
            if (data === "[DONE]") break;

            try {
              const parsed = JSON.parse(data);
              if (parsed.type === "token") {
                setMessages((prev) =>
                  prev.map((m) =>
                    m.id === aiMsgId
                      ? { ...m, content: m.content + parsed.content }
                      : m
                  )
                );
              } else if (parsed.type === "metadata") {
                setMessages((prev) =>
                  prev.map((m) =>
                    m.id === aiMsgId
                      ? {
                          ...m,
                          sources: parsed.data.retrieved_docs,
                          isStreaming: false,
                        }
                      : m
                  )
                );
              }
            } catch (_) {}
          }
        }
      } catch (err: unknown) {
        if (err instanceof Error && err.name !== "AbortError") {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === aiMsgId
                ? {
                    ...m,
                    content: "Lỗi kết nối. Vui lòng thử lại.",
                    isStreaming: false,
                  }
                : m
            )
          );
        }
      } finally {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === aiMsgId ? { ...m, isStreaming: false } : m
          )
        );
        setIsLoading(false);
      }
    },
    [sessionId, isLoading]
  );

  const stopStreaming = useCallback(() => {
    abortRef.current?.abort();
    setIsLoading(false);
  }, []);

  return { messages, isLoading, isLoadingHistory, sendMessage, stopStreaming };
}
