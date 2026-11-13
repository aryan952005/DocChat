import { formatDay } from "../format.js";

// Left sidebar: logo, past chats one per row, New chat pinned at the bottom
export default function SessionList({ sessions, activeSessionId, open, onSelect, onNew }) {
  return (
    <aside className={`sidebar ${open ? "open" : ""}`}>
      <div className="brand">
        <img src="/logo.svg" alt="" width="26" height="36" />
        <span className="brand-name">DocChat</span>
      </div>

      <h2 className="label">Conversations</h2>
      {sessions.length === 0 && <p className="hint">No chats yet. Start one below.</p>}
      <ul className="chat-list">
        {sessions.map((s) => (
          <li key={s.sessionId}>
            <button
              type="button"
              className={`chat-row ${s.sessionId === activeSessionId ? "active" : ""}`}
              onClick={() => onSelect(s.sessionId)}
            >
              <span className="chat-title">{s.title}</span>
              <span className="chat-date">{formatDay(s.createdAt)}</span>
            </button>
          </li>
        ))}
      </ul>

      <div className="sidebar-foot">
        <button type="button" className="btn-primary new-chat" onClick={onNew}>
          <svg aria-hidden="true" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round">
            <path d="M12 5v14M5 12h14" />
          </svg>
          New chat
        </button>
      </div>
    </aside>
  );
}
