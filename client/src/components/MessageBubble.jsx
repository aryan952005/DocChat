import SourceList from "./SourceList.jsx";

// Badge rule from SYSTEM_DESIGN 7.5
function badgeFor(m) {
  if (m.route === "direct") return { text: "Direct reply", kind: "neutral" };
  if (m.sources && m.sources.length > 0) {
    return { text: `Searched docs · ${m.retries} ${m.retries === 1 ? "retry" : "retries"}`, kind: "docs" };
  }
  return { text: "Not found", kind: "warn" };
}

export default function MessageBubble({ message }) {
  if (message.role === "user") {
    return <div className="msg user">{message.content}</div>;
  }
  if (message.isError) {
    return <div className="msg error" role="alert">{message.content}</div>;
  }

  const badge = badgeFor(message);
  const [lead, ...rest] = message.content.split("\n");
  return (
    <div className="msg assistant">
      <div className="answer">
        <p className="lead">{lead}</p>
        {rest.length > 0 && <div className="body">{rest.join("\n").trim()}</div>}
      </div>
      <div className="msg-foot">
        <SourceList sources={message.sources} />
        <span className={`badge ${badge.kind}`}>{badge.text}</span>
      </div>
    </div>
  );
}
