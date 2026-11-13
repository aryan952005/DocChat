const axios = require("axios");
const FormData = require("form-data");

const ai = axios.create({ baseURL: process.env.AI_SERVICE_URL });

// Send the file bytes (from Multer memory) to FastAPI as a new multipart request
async function ingestFile(buffer, filename, docId) {
  const form = new FormData();
  form.append("file", buffer, { filename });
  form.append("doc_id", docId);
  const { data } = await ai.post("/ingest", form, { headers: form.getHeaders() });
  return data; // { doc_id, filename, chunks }
}

// One question can take up to 7 Gemini calls, so allow about 60 seconds
async function askAgent(threadId, question) {
  const { data } = await ai.post("/chat", { thread_id: threadId, question }, { timeout: 60000 });
  return data; // { answer, sources, route, retries }
}

module.exports = { ingestFile, askAgent };
