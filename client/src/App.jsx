import { useEffect, useRef, useState } from "react";
import * as api from "./api.js";
import SessionList from "./components/SessionList.jsx";
import ChatWindow from "./components/ChatWindow.jsx";
import UploadPanel from "./components/UploadPanel.jsx";

// React state from SYSTEM_DESIGN section 7.1 (plus two small UI flags)
export default function App() {
  const [documents, setDocuments] = useState([]);
  const [sessions, setSessions] = useState([]);
  const [activeSessionId, setActiveSessionId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState("");
  const [libraryOpen, setLibraryOpen] = useState(window.innerWidth >= 1000);
  const [sidebarOpen, setSidebarOpen] = useState(false); // phone only

  // Always holds the open chat, so a slow answer for chat A never lands in chat B
  const activeRef = useRef(null);
  activeRef.current = activeSessionId;

  // 7.2 Open the app
  useEffect(() => {
    api.getDocuments().then(setDocuments).catch(() => setError("Could not load documents."));
    api.getSessions().then(setSessions).catch(() => setError("Could not load chats."));
  }, []);

  // 7.3 Upload a file
  async function handleUpload(file) {
    setUploading(true);
    setUploadError("");
    try {
      const doc = await api.uploadFile(file);
      setDocuments((docs) => [...docs, { ...doc, uploadedAt: new Date().toISOString() }]);
    } catch (err) {
      setUploadError(err.status === 503 ? "AI service is unavailable." : err.message);
    } finally {
      setUploading(false);
    }
  }

  // 7.4 Start a new chat
  async function handleNewChat() {
    try {
      const { sessionId } = await api.createSession();
      setSessions((list) => [{ sessionId, title: "New chat", createdAt: new Date().toISOString() }, ...list]);
      setActiveSessionId(sessionId);
      setMessages([]);
      setLoading(false);
      setError("");
      setSidebarOpen(false);
    } catch {
      setError("Could not start a chat.");
    }
  }

  // 7.6 Open an old chat
  async function handleSelect(sessionId) {
    setActiveSessionId(sessionId);
    setMessages([]);
    setLoading(false);
    setError("");
    setSidebarOpen(false);
    try {
      const saved = await api.getMessages(sessionId);
      if (activeRef.current === sessionId) setMessages(saved);
    } catch {
      setError("Could not load this chat.");
    }
  }

  // 7.5 Send a question
  async function handleSend(question) {
    const sessionId = activeSessionId;
    setMessages((m) => [...m, { role: "user", content: question }]);
    setLoading(true);
    let reply;
    try {
      const { answer, sources, route, retries, title } = await api.sendChat(sessionId, question);
      reply = { role: "assistant", content: answer, sources, route, retries };
      // The server titles a new chat from its first question
      if (title) setSessions((list) => list.map((c) => (c.sessionId === sessionId ? { ...c, title } : c)));
    } catch (err) {
      const text = err.status === 503 ? "AI service is unavailable." : "Something went wrong. Try again.";
      reply = { role: "assistant", content: text, isError: true };
    }
    if (activeRef.current !== sessionId) return; // the user switched chats meanwhile
    setMessages((m) => [...m, reply]);
    setLoading(false);
  }

  const activeChat = sessions.find((s) => s.sessionId === activeSessionId);
  const anyDrawerOpen = sidebarOpen || (libraryOpen && window.innerWidth < 1000);

  return (
    <div className="app">
      <SessionList
        sessions={sessions}
        activeSessionId={activeSessionId}
        open={sidebarOpen}
        onSelect={handleSelect}
        onNew={handleNewChat}
      />
      <ChatWindow
        title={activeChat ? activeChat.title : ""}
        active={activeSessionId !== null}
        messages={messages}
        loading={loading}
        error={error}
        libraryOpen={libraryOpen}
        onSend={handleSend}
        onNew={handleNewChat}
        onToggleLibrary={() => setLibraryOpen((v) => !v)}
        onOpenSidebar={() => setSidebarOpen(true)}
      />
      <UploadPanel
        documents={documents}
        open={libraryOpen}
        uploading={uploading}
        error={uploadError}
        onUpload={handleUpload}
        onClose={() => setLibraryOpen(false)}
      />
      {anyDrawerOpen && (
        <div
          className="scrim"
          onClick={() => {
            setSidebarOpen(false);
            setLibraryOpen(false);
          }}
        />
      )}
    </div>
  );
}
