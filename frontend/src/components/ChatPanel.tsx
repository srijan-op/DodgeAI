import { useCallback, useId, useRef, useState } from "react";
import { streamChat, type SseEvent } from "../api";

export type ChatMessage = {
  role: "user" | "assistant";
  content: string;
  planSummary?: string;
};

type Props = {
  sessionId: string;
  onGraphHighlight: (ids: string[]) => void;
  disabled?: boolean;
  /** Panel width in pixels (resizable from parent). */
  widthPx?: number;
};

export function ChatPanel({ sessionId, onGraphHighlight, disabled, widthPx }: Props) {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      role: "assistant",
      content:
        "Hi! I can help you analyze the Order to Cash process. Ask about flows, entities, or specific document numbers.",
    },
  ]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const formId = useId();

  const scrollToBottom = () => {
    requestAnimationFrame(() => bottomRef.current?.scrollIntoView({ behavior: "smooth" }));
  };

  const send = useCallback(async () => {
    const text = input.trim();
    if (!text || busy || disabled) return;
    setInput("");
    setBusy(true);

    setMessages((m) => [
      ...m,
      { role: "user", content: text },
      { role: "assistant", content: "" },
    ]);
    scrollToBottom();

    let assistant = "";
    let planSummary = "";

    const patchAssistant = () => {
      setMessages((m) => {
        const n = [...m];
        const last = n[n.length - 1];
        if (last?.role === "assistant") {
          n[n.length - 1] = {
            role: "assistant",
            content: assistant,
            planSummary: planSummary || undefined,
          };
        }
        return n;
      });
      scrollToBottom();
    };

    try {
      await streamChat(text, sessionId, (ev: SseEvent) => {
        if (ev.type === "plan") {
          const p = ev.plan;
          const parts: string[] = [];
          if (p.run_analyze_flow) parts.push("analyze_flow");
          if (p.run_graph_query) parts.push("graph_query");
          planSummary = parts.length ? `Tools: ${parts.join(" + ")}` : "";
          patchAssistant();
        }
        if (ev.type === "graph_highlight") {
          onGraphHighlight(ev.node_ids);
        }
        if (ev.type === "token") {
          assistant += ev.delta;
          patchAssistant();
        }
        if (ev.type === "error") {
          assistant += `\n\n[Error] ${ev.detail}`;
          patchAssistant();
        }
      });
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      assistant = `[Error] ${msg}`;
      patchAssistant();
    } finally {
      setBusy(false);
      scrollToBottom();
    }
  }, [input, busy, disabled, sessionId, onGraphHighlight]);

  return (
    <aside
      className="chat-panel"
      style={widthPx != null ? { width: widthPx, minWidth: widthPx, maxWidth: widthPx } : undefined}
    >
      <div className="chat-panel-header">
        <h2>Chat with Graph</h2>
        <p className="chat-sub">Order to Cash</p>
      </div>

      <div className="chat-messages">
        {messages.map((msg, i) => (
          <div
            key={i}
            className={`chat-bubble ${msg.role === "user" ? "chat-bubble-user" : "chat-bubble-ai"}`}
          >
            {msg.role === "assistant" && (
              <div className="chat-avatar" aria-hidden>
                D
              </div>
            )}
            <div className="chat-bubble-body">
              {msg.role === "assistant" && (
                <div className="chat-meta">
                  <strong>Dodge AI</strong>
                  <span className="chat-badge">Graph Agent</span>
                </div>
              )}
              {msg.planSummary && (
                <div className="chat-plan-pill">{msg.planSummary}</div>
              )}
              <div className="chat-text">
                {msg.content || (busy && i === messages.length - 1 ? "…" : "")}
              </div>
            </div>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      <div className="chat-composer">
        <div className="chat-status">
          <span className={`chat-dot ${busy ? "chat-dot-busy" : "chat-dot-idle"}`} />
          {busy ? "Dodge AI is thinking…" : "Dodge AI is awaiting instructions"}
        </div>
        <form
          id={formId}
          className="chat-form"
          onSubmit={(e) => {
            e.preventDefault();
            void send();
          }}
        >
          <textarea
            className="chat-input"
            placeholder="Analyze anything."
            rows={3}
            value={input}
            disabled={busy || disabled}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                void send();
              }
            }}
          />
          <button type="submit" className="chat-send" disabled={busy || disabled || !input.trim()}>
            Send
          </button>
        </form>
      </div>
    </aside>
  );
}
