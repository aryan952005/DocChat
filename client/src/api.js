// Every call to the Express gateway lives here. React never talks to FastAPI (SYSTEM_DESIGN section 4).
const BASE = import.meta.env.VITE_API_URL || "http://localhost:5001/api";

async function request(path, options) {
  let res;
  try {
    res = await fetch(BASE + path, options);
  } catch {
    // Express itself is unreachable
    const err = new Error("Cannot reach the server");
    err.status = 0;
    throw err;
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const err = new Error(data.error || "Something went wrong");
    err.status = res.status;
    throw err;
  }
  return data;
}

const json = (body) => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export const getDocuments = () => request("/documents");

export function uploadFile(file) {
  const form = new FormData();
  form.append("file", file);
  return request("/upload", { method: "POST", body: form }); // browser sets the multipart header
}

export const getSessions = () => request("/sessions");
export const createSession = () => request("/sessions", json({}));
export const getMessages = (sessionId) => request(`/sessions/${sessionId}/messages`);
export const sendChat = (sessionId, question) => request("/chat", json({ sessionId, question }));
