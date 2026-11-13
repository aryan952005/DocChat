// Citations: file name and page for every chunk the answer used (responsible AI: users can verify)
export default function SourceList({ sources }) {
  if (!sources || sources.length === 0) return null;
  return (
    <div className="sources">
      <span className="label-small">Sources</span>
      {sources.map((s) => (
        <span key={`${s.filename}-${s.page}`} className="source">
          {s.filename}, p. {s.page}
        </span>
      ))}
    </div>
  );
}
