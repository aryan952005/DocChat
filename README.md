# DocChat

An adaptive RAG assistant for engineering documentation. Upload developer docs (PDF, Markdown, text) and ask questions.
A LangGraph agent answers **only from your documents, with citations** (file name and page), or honestly says it could not find the answer.

## The problem

Engineers lose time searching scattered docs, and a plain chatbot invents answers. DocChat routes each question,
rewrites it into a good search query, retrieves chunks, **grades** them against the user's original question, retries with
new wording if nothing relevant came back, and only then answers. Every answer shows where it came from.

## Architecture

```mermaid
flowchart LR
  U[React app<br/>Vite, port 5174] --> X[Express gateway<br/>port 5001]
  X --> F[FastAPI AI service<br/>port 8000, internal]
  X --> M[(MongoDB Atlas<br/>documents, sessions, messages)]
  F --> Q[(Qdrant Cloud<br/>document chunks)]
  F --> G[Gemini API<br/>LLM and embeddings]
  F --> M2[(MongoDB Atlas<br/>agent checkpoints)]
```

React talks only to Express. Express talks only to FastAPI (and to MongoDB for its own records). Only FastAPI talks to Qdrant,
Gemini and the checkpoints, so API keys never leave the AI service.

## The LangGraph agent

```mermaid
flowchart TD
  S([start]) --> R[router]
  R -- direct --> D[direct_answer] --> E([end])
  R -- docs --> W[rewrite_query] --> T[retrieve] --> G[grade_documents]
  G -- relevant chunks --> A[generate] --> E
  G -- none, retries left --> P[prepare_retry] --> W
  G -- none, retries used up --> N[not_found] --> E
```

- **router**: Gemini with structured output picks `docs` or `direct`; when unsure it picks `docs`. It also resets per-turn state.
- **rewrite_query**: builds one standalone search query from the original question and the last 6 messages. Wording only, never meaning.
- **retrieve**: top-k similarity search in Qdrant (cosine, HNSW).
- **grade_documents**: one batched LLM call keeps only chunks that really answer the user's original question.
- **prepare_retry**: records the failed query and adds 1 to the retry counter; the next rewrite must not repeat it.
- **generate** / **not_found** / **direct_answer**: final nodes; each appends one message to the history.
- **Query drift rules**: every rewrite starts from the original question, the rewrite changes words only, and grading and answering
  always use the original question, never the rewritten query.
- **Memory**: a `MongoDBSaver` checkpointer keyed by `thread_id` (the chat's id). Prompts see only the last 6 messages.

## Tech stack

| Layer | Technology |
|---|---|
| Frontend | React (Vite), plain CSS |
| Gateway | Node.js, Express 5, Multer, Axios, Mongoose |
| AI service | Python 3.12, FastAPI, LangChain, LangGraph |
| LLM | Gemini (model from `GEMINI_MODEL`) via `langchain-google-genai` |
| Embeddings | Gemini `gemini-embedding-001`, shortened to 768 dimensions |
| Vector DB | Qdrant (cloud or Docker), cosine distance |
| Database | MongoDB (Atlas or Docker): app records and LangGraph checkpoints |

## Setup

You need Node 20+, Python 3.12, a Gemini API key, a MongoDB (Atlas free tier, or `docker compose up -d`) and a Qdrant
(Qdrant Cloud free tier, or the same `docker compose`).

1. **AI service**
   ```bash
   cd ai-service
   python3.12 -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   ```
   Create `ai-service/.env` (see `.env.example` in the project root):
   `GEMINI_API_KEY`, `GEMINI_MODEL`, `EMBED_MODEL=gemini-embedding-001`, `MONGO_URI`, `MONGO_DB=docchat`,
   `QDRANT_URL`, `QDRANT_API_KEY` (empty for local Docker), `QDRANT_COLLECTION=docchat_docs`.
   ```bash
   uvicorn app.main:app --port 8000
   ```
2. **Express gateway**
   ```bash
   cd server && npm install
   ```
   Create `server/.env`: `PORT=5001`, `AI_SERVICE_URL=http://localhost:8000`, `MONGO_URI`, `MONGO_DB=docchat`, `CLIENT_URL=http://localhost:5174`.
   ```bash
   node index.js
   ```
3. **React app**
   ```bash
   cd client && npm install && npm run dev
   ```
   Open http://localhost:5174. Optional: `client/.env` with `VITE_API_URL=http://localhost:5001/api`.

Secrets live only in `.env` files, which are git-ignored.

## API

React to Express (port 5001):

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/upload` | Upload a `.pdf`, `.md` or `.txt` (up to 10 MB); returns `{docId, filename, chunks}` |
| GET | `/api/documents` | List uploaded documents |
| POST | `/api/sessions` | Create a chat; returns `{sessionId}` |
| GET | `/api/sessions` | List chats, newest first |
| GET | `/api/sessions/:id/messages` | Saved messages of a chat, oldest first |
| POST | `/api/chat` | `{sessionId, question}` returns `{answer, sources, route, retries, title}` |

Express to FastAPI (internal): `GET /health`, `POST /ingest` (multipart `file`, `doc_id`), `POST /chat` (`{thread_id, question}`).
Errors are short JSON messages: 400 bad input, 404 unknown chat, 503 when the AI service is down.

## Evaluation

`eval/run_eval.py` sends 10 questions from `eval/questions.json` through the real agent: 8 that the sample Payments API PDF answers
(each with its expected page and answer) and 2 that it does not. It compares chunk size 500 vs 1000 and the retry loop ON (`MAX_RETRIES=2`)
vs OFF (`MAX_RETRIES=0`). Each config runs in its own process with its own Qdrant collection, and every question gets a fresh `thread_id`.

- **Retrieval hit:** the expected page is among the cited sources.
- **Answer correct:** an LLM judge (Gemini, yes/no structured output) compares the answer with the expected answer.
- **Out-of-scope correct:** the question ends in "not found" instead of a made-up answer. This tests the query-drift rules.
- **Latency:** seconds per question, end to end.

| Config | Chunk size | Retries | Chunks stored | Retrieval hit | Answer correct | Out-of-scope correct | Avg latency | Avg retries (in-docs) |
|---|---|---|---|---|---|---|---|---|
| c500_retry_on | 500 | 2 | 12 | 8/8 (100%) | 8/8 (100%) | 2/2 (100%) | 15.3s | 0.00 |
| c1000_retry_on | 1000 | 2 | 6 | 8/8 (100%) | 8/8 (100%) | 2/2 (100%) | 14.1s | 0.00 |
| c500_retry_off | 500 | 0 | 12 | 8/8 (100%) | 8/8 (100%) | 2/2 (100%) | 11.1s | 0.00 |
| c1000_retry_off | 1000 | 0 | 6 | 8/8 (100%) | 8/8 (100%) | 2/2 (100%) | 12.8s | 0.00 |

The cost of the retry loop shows on the out-of-scope questions:

| Out-of-scope question | Gemini calls | Latency |
|---|---|---|
| Retries ON | 7 (router, 3 rewrites, 3 grades) | 14.5 to 38.4s |
| Retries OFF | 3 (router, 1 rewrite, 1 grade) | 5.0 to 6.4s (one outlier at 27.0s) |

**What the results say**

- All four configs answered every question correctly and refused both out-of-scope questions, so on this corpus neither setting changes accuracy.
- The retry loop never ran for answerable questions (0 retries on all 8). It ran only on out-of-scope questions, where it more than doubled the calls and the time.
- Answerable questions averaged about 12 to 14 seconds in every config. The differences between the averages come from network and free-tier variance (single questions took up to 43 seconds).

**Recommendation:** use chunk size 500 with retries ON. Accuracy was equal, but smaller chunks cite a narrower part of the page, and with
1000-character chunks the whole document was only 6 chunks, so a top-5 search returned almost all of it (which also makes that result weaker).
Retries cost nothing when the first search works and are the only way to recover from a vaguely worded question. Switch to `MAX_RETRIES=0`
only if latency or the free-tier quota matters more: it makes "not found" answers about 3 times faster. (The app currently uses chunk size 800,
the design default; changing it is one line in `.env` plus a re-ingest.)

**Caveats:** one 6-page document, 10 questions, one run per config, and the same model both answers and judges. The test set had no vaguely
worded questions, so it could not show the retry loop helping. A next version should add those, similar documents (two APIs that both have
rate limits) and many more questions.

Run it with `ai-service/.venv/bin/python eval/run_eval.py` (all four configs, about 200 Gemini calls). Raw results are in `eval/results_*.json`.

## Known limitations

- No login: everyone shares all documents and chats.
- No document delete or per-document filter; re-uploading a file duplicates its chunks.
- A question can take up to 7 Gemini calls (about 5 to 30 seconds).
- The grader can misjudge, and history is trimmed to the last 6 messages.
- The evaluation uses one small document, so its conclusions are tentative.

## Future work

Agent trace UI with streaming, Mem0 long-term memory, Neo4j graph memory, Valkey caching, authentication, cloud deployment,
per-document filtering, AI-written chat titles.
