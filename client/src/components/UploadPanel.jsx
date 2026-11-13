import { useRef } from "react";
import { fileType, formatDay } from "../format.js";

// Right panel: every uploaded document and the Add button
export default function UploadPanel({ documents, open, uploading, error, onUpload, onClose }) {
  const input = useRef(null);

  function handleChange(e) {
    const file = e.target.files[0];
    if (file) onUpload(file);
    e.target.value = ""; // lets the same file be picked again
  }

  return (
    <aside id="library-panel" className={`library ${open ? "open" : ""}`}>
      <div className="library-head">
        <h2 className="label">Library</h2>
        <span className="library-tools">
          <span className="hint-inline">
            {documents.length} {documents.length === 1 ? "document" : "documents"}
          </span>
          <button type="button" className="icon-btn" aria-label="Hide library" onClick={onClose}>
            <svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M9 6l6 6-6 6" />
            </svg>
          </button>
        </span>
      </div>

      {documents.length === 0 && <p className="hint">No documents yet. Add one to start asking questions.</p>}
      <ul className="doc-list">
        {documents.map((d) => (
          <li key={d.docId} className="doc-row">
            <span className="doc-icon">
              <svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z" />
                <path d="M14 3v6h6" />
              </svg>
            </span>
            <span className="doc-text">
              <span className="doc-name" title={d.filename}>{d.filename}</span>
              <span className="doc-meta">
                {fileType(d.filename)} · {d.chunks} {d.chunks === 1 ? "chunk" : "chunks"} · Added {formatDay(d.uploadedAt)}
              </span>
            </span>
          </li>
        ))}
      </ul>

      <input ref={input} type="file" accept=".pdf,.md,.txt" hidden onChange={handleChange} />
      <button type="button" className="add-doc" disabled={uploading} onClick={() => input.current.click()}>
        {uploading ? (
          "Uploading…"
        ) : (
          <>
            <svg aria-hidden="true" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round">
              <path d="M12 5v14M5 12h14" />
            </svg>
            Add a document
            <span className="add-hint">.pdf, .md or .txt, up to 10 MB</span>
          </>
        )}
      </button>
      {error && <p className="upload-error" role="alert">{error}</p>}
    </aside>
  );
}
