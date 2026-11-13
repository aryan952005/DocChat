import { useEffect, useRef, useState } from "react";
import MessageBubble from "./MessageBubble.jsx";

export default function ChatWindow({
  title, active, messages, loading, error, libraryOpen,
  onSend, onNew, onToggleLibrary, onOpenSidebar,
}) {
  const [text, setText] = useState("");
  const end = useRef(null);

  // Keep the newest message in view
  useEffect(() => {
    end.current?.scrollIntoView({ block: "end" });
  }, [messages, loading]);

  function submit(e) {
    e.preventDefault();
    const question = text.trim();
    if (!question || !active || loading) return;
    setText("");
    onSend(question);
  }

  return (
    <main className="chat">
      <header className="chat-head">
        <button type="button" className="icon-btn menu-btn" aria-label="Open chats" onClick={onOpenSidebar}>
          <svg aria-hidden="true" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
            <path d="M4 6h16M4 12h16M4 18h16" />
          </svg>
        </button>
        <h1 className={active ? "chat-name" : "chat-name muted"}>{active ? title : "No chat selected"}</h1>
        <button
          type="button"
          className="library-arrow"
          aria-expanded={libraryOpen}
          aria-controls="library-panel"
          aria-label={libraryOpen ? "Hide library" : "Show library"}
          title={libraryOpen ? "Hide library" : "Show library"}
          onClick={onToggleLibrary}
        >
          <svg aria-hidden="true" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
            <path d={libraryOpen ? "M7 6l6 6-6 6M13 6l6 6-6 6" : "M11 6l-6 6 6 6M19 6l-6 6 6 6"} />
          </svg>
        </button>
      </header>

      {error && <p className="banner" role="alert">{error}</p>}

      {!active ? (
        <div className="empty">
          <h2>Ask anything about your docs</h2>
          <p>Pick a chat from the list, or start a new one. Answers come only from your uploaded documents, with the file and page shown under each reply.</p>
          <button type="button" className="btn-primary" onClick={onNew}>+ New chat</button>
        </div>
      ) : (
        <div className="messages">
          <div className="messages-inner">
            {messages.map((m, i) => (
              <MessageBubble key={i} message={m} />
            ))}
            {loading && (
              <div className="thinking" aria-live="polite">
                <span className="dots"><i /><i /><i /></span>
                Thinking…
              </div>
            )}
            <div ref={end} />
          </div>
        </div>
      )}

      <form className="composer" onSubmit={submit}>
        <input
          type="text"
          aria-label="Ask a question about your documents"
          placeholder={active ? "Ask about your docs…" : "Start a new chat to ask a question"}
          value={text}
          disabled={!active || loading}
          onChange={(e) => setText(e.target.value)}
        />
        <button type="submit" className="send" disabled={!active || loading || !text.trim()}>Send</button>
      </form>
    </main>
  );
}
