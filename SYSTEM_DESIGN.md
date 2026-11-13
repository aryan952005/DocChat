# DocChat System Design

Nov 12, 2026 · @Aryan Patidar

## 1. How to use this document

This document is the source of truth for **what DocChat does and how data moves through it**. `CLAUDE.md` holds the working rules (concept revision, interview questions, one phase at a time). Where the two disagree on system behavior, this document wins.

Rules for Claude Code:

- Read this whole document before starting any phase.
- Build the flows exactly as written in sections 7–10. Do not reorder steps or merge nodes.
- Section 3 lists every decision that changes or clarifies the original `CLAUDE.md`. Apply all of them.
- Do not build anything listed under Future work (section 12) unless asked.
- Verify library APIs (LangChain, LangGraph, checkpointer, Gemini) against the installed versions before using them.
- Phases will be appended in section 13 after review.

## 2. Project summary and scope

DocChat is an internal documentation assistant for engineering teams. Users upload developer docs (PDF, Markdown, text) and ask questions. A LangGraph agent answers **only from the uploaded docs, with citations** (filename and page), or honestly says the answer was not found.

Interview pitch: *Engineers lose time searching scattered docs. DocChat is an adaptive RAG assistant: a LangGraph agent routes, retrieves, grades relevance, and retries before answering with citations, so it avoids hallucination.*

**In scope**

- Upload `.pdf`, `.md`, `.txt` files up to 10 MB. Multiple documents, shared by all chats.
- Multiple chat sessions. Each session has its own memory; a new session starts with empty memory.
- Adaptive RAG agent: router, query rewrite, retrieve, grade, retry, generate, not found.
- Citations (filename and page) on every docs answer.
- A small badge per answer showing route and retries.
- Evaluation of chunk size and retry ON/OFF.

**Out of scope**

- Login and users. DocChat is a single shared workspace: everyone sees the same docs and chats.
- Filtering a question to one document.
- Deleting documents.
- Mem0, Neo4j, Valkey, cloud deploy, UI libraries.
- Streaming agent trace (optional, only after Phase 10 and only if asked).

**Tech stack (fixed)**

| Layer | Tech |
| --- | --- |
| Frontend | React (Vite) |
| Gateway | Node.js, Express, Multer, Axios, Mongoose, form-data, cors, dotenv |
| AI service | Python 3.11+, FastAPI, Uvicorn, LangChain, LangGraph |
| Loading and chunking | `PyPDFLoader`, text loader, `RecursiveCharacterTextSplitter` |
| Embeddings | Ollama `nomic-embed-text` (768 dimensions) via `langchain-ollama` |
| Vector DB | Qdrant via `langchain-qdrant` + `qdrant-client` |
| LLM | Gemini via `langchain-google-genai`, model from `GEMINI_MODEL`, temperature 0 |
| Memory | LangGraph `MongoDBSaver` checkpointer (`langgraph-checkpoint-mongodb`); SQLite checkpointer only as a fallback |
| Database | MongoDB |
| Infra | Docker Compose for Qdrant and MongoDB; Ollama on the host |

## 3. Design decisions and changes from CLAUDE.md

These 14 decisions were made while reviewing the design. Rows marked **Change** override `CLAUDE.md`; rows marked **Clarify** fill a gap it left open.

| # | Type | Decision | Why | Phase |
| --- | --- | --- | --- | --- |
| D1 | Clarify | Keep the MongoDB checkpointer for chat memory. Do not use Mem0. | Stored history costs no tokens; prompts send only the last 6 messages. Mem0 stores user facts, not previous turns, and adds an LLM call per message. Mem0 may be added as an optional extra after Phase 10. | 6 |
| D2 | Change | Every rewrite is built from the **original question** + last 6 messages, never from the previous `search_query`. | Rewriting a rewrite chains small changes and the meaning drifts (query drift). | 5 |
| D3 | Change | Add state field `failed_queries: list[str]`. On a retry, the rewrite prompt lists them as "do not repeat these". | Temperature 0 gives the same query for the same prompt; listing failures forces new wording. | 5 |
| D4 | Change | The rewrite changes **wording only**: resolve references ("it" → "rate limit"), add keywords, use synonyms. It must keep the exact meaning. | Prevents answering a different question. | 5 |
| D5 | Change | `search_query` is used **only** by `retrieve`. `grade_documents` and `generate` use the original `question` plus the last 6 messages. | The rewrite may change what is searched, never what counts as relevant. History is included so follow-ups like "what if I exceed it?" are understood. | 5 |
| D6 | Clarify | Retry bookkeeping lives in a small `prepare_retry` node: append `search_query` to `failed_queries`, add 1 to `retry_count`. | One clear place for the loop counter; `rewrite_query` stays a pure rewrite. | 5 |
| D7 | Change | The router resets per-turn fields at the start of every turn (see section 9). | The checkpointer saves the whole state, so last turn's `retry_count`, documents and answer would otherwise leak into the next turn. | 4, 6 |
| D8 | Change | The new `HumanMessage` is passed in the graph **input** together with `question`. The router does **not** append it again. Every final node (`generate`, `direct_answer`, `not_found`) appends one `AIMessage`. | Avoids duplicate human messages; keeps history complete for every route. | 3, 4 |
| D9 | Clarify | Upload order: Express forwards the file to FastAPI first and saves the `Document` record only after FastAPI succeeds. | No fake entries in the file list when ingestion fails. | 8 |
| D10 | Clarify | Multer uses memory storage. Express sends the bytes to FastAPI as a new multipart request. FastAPI writes a temp file, ingests it, and deletes it. The original file is kept nowhere. | Express and FastAPI are separate programs; no shared disk. | 7, 8 |
| D11 | Clarify | Express generates `docId` (`crypto.randomUUID()`) before forwarding. | One ID links the MongoDB record and the Qdrant chunks. | 8 |
| D12 | Clarify | All documents live in one Qdrant collection shared by every session. No per-document filter. | Simple; `doc_id` metadata allows filtering later. | 2 |
| D13 | Clarify | `PyPDFLoader` page metadata is 0-based; store `page + 1`. Verify in the installed version. | Citations must match the page number people see. | 2 |
| D14 | Clarify | No authentication. One shared workspace. | Kept out of scope on purpose. | All |

## 4. Architecture

React shows, Express records, FastAPI thinks, Qdrant holds the docs, MongoDB holds everything else. Requests always travel React → Express → FastAPI; nothing skips a step.

&#91;embedded content: system architecture · 7 components\]

Express writes the app records in MongoDB; FastAPI writes only the checkpoints there.

| Component | Port | Responsible for | Never does |
| --- | --- | --- | --- |
| React (Vite) | 5173 | The screen: upload, file list, chat list, chat window, sources, badge. Remembers the open `sessionId` and the open chat's message list. | Talks to FastAPI; stores data permanently. |
| Express | 5000 | API gateway: validates input, receives uploads (Multer), forwards AI work to FastAPI, owns the `documents`, `sessions` and `messages` collections, central error handling. | Any AI logic; holds the Gemini key; reads checkpoints. |
| FastAPI (AI service) | 8000 | Ingestion (load, chunk, embed, store), the LangGraph agent, all calls to Ollama, Gemini and Qdrant, the checkpointer. | Writes `documents`, `sessions` or `messages`. |
| Ollama (host) | 11434 | Embeddings with `nomic-embed-text` (768 numbers per text). | Generates answers. |
| Gemini API | – | Route, rewrite, grade, generate, direct answer. | Embeddings. |
| Qdrant (Docker) | 6333 | Document chunks: vector + text + metadata. | – |
| MongoDB (Docker) | 27017 | App records and LangGraph checkpoints. | – |

**Communication rules**

- React calls only Express.
- Express calls only FastAPI (and MongoDB for its own collections). FastAPI is internal and is never exposed directly.
- Only FastAPI talks to Qdrant, Ollama, Gemini and the checkpoint collections.
- API keys live only in the AI service `.env`.
- Why the gateway: React needs one address; Express saves app records in the same request; the AI service and its API quota stay private; validation, errors and any future login live in one place. The cost is one extra local hop, which is negligible.

## 5. Data storage

Data lives in five places. Documents are global (shared by all chats); everything about a chat is keyed by its `sessionId`, which is also the LangGraph `thread_id`.

| # | Store | Location | Holds | Written by | Read by | Purpose |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | `docchat_docs` | Qdrant | Document chunks | FastAPI | FastAPI | Search the docs |
| 2 | `documents` | MongoDB | One record per uploaded file | Express | Express | Show the file list |
| 3 | `sessions` | MongoDB | One record per chat | Express | Express | Show the chat list; `_id` = `thread_id` |
| 4 | `messages` | MongoDB | Every question and answer | Express | Express | Show a chat's messages on screen |
| 5 | checkpoints | MongoDB (`MONGO_DB`) | Saved agent state per thread | LangGraph | LangGraph | Agent memory |

**1. Qdrant point** (collection `QDRANT_COLLECTION`, vector size 768, cosine distance, created if missing)

```json
{
  "id": "<generated>",
  "vector": [0.12, -0.45, "... 768 numbers"],
  "payload": {
    "page_content": "Rate limits. You can make 100 requests per minute...",
    "metadata": { "doc_id": "d1", "filename": "payments-api.pdf", "page": 3 }
  }
}
```

**2. `documents`**

```js
{ docId: String, filename: String, chunks: Number, uploadedAt: Date }
```

**3. `sessions`**

```js
{ _id: ObjectId /* = thread_id */, title: String /* default "New chat" */, createdAt: Date }
```

**4. `messages`** (index on `{ sessionId: 1, createdAt: 1 }`)

```js
{ sessionId: ObjectId, role: "user" | "assistant", content: String,
  sources: [{ filename: String, page: Number }], route: String, retries: Number, createdAt: Date }
```

**5. Checkpoints** are created and managed by `MongoDBSaver`. Collection names come from the library (verify in the installed version). One chat produces many checkpoint documents, each with its own `_id` and the same `thread_id` field; LangGraph loads the newest one for the given `thread_id`. Our code never reads or writes these directly.

**Stores 4 and 5 both hold the conversation, for different readers.** `messages` is for humans (the screen). Checkpoints are for the AI (memory). Express and React never read checkpoints; the agent never reads `messages`.

## 6. API contracts

React knows only the Express API. Express knows only the FastAPI API. `thread_id` sent to FastAPI is always the Express `sessionId`.

**React → Express (port 5000)**

| Method | Path | Body | Success response | Errors |
| --- | --- | --- | --- | --- |
| POST | `/api/upload` | multipart `file` | `{ docId, filename, chunks }` | 400 wrong type or over 10 MB · 503 AI service down |
| GET | `/api/documents` | – | `[{ docId, filename, chunks, uploadedAt }]` | – |
| POST | `/api/sessions` | `{ title? }` | `{ sessionId }` | – |
| GET | `/api/sessions` | – | `[{ sessionId, title, createdAt }]` newest first | – |
| GET | `/api/sessions/:id/messages` | – | `[{ role, content, sources, route, retries, createdAt }]` oldest first | 404 unknown session |
| POST | `/api/chat` | `{ sessionId, question }` | `{ answer, sources, route, retries }` | 400 missing or empty field · 404 unknown session · 503 AI service down |

**Express → FastAPI (port 8000, internal only)**

| Method | Path | Body | Success response | Errors |
| --- | --- | --- | --- | --- |
| GET | `/health` | – | `{ status: "ok" }` | – |
| POST | `/ingest` | multipart: `file`, `doc_id` | `{ doc_id, filename, chunks }` | 400 bad extension or empty file · 500 short message |
| POST | `/chat` | `{ thread_id, question }` | `{ answer, sources: [{ filename, page }], route, retries }` | 400 bad input · 500 short message |

Notes:

- `route` is `"docs"` or `"direct"`. A not-found answer has `route: "docs"`, empty `sources`, and `retries` equal to `MAX_RETRIES`.
- Express uses an Axios timeout of about 60 seconds for `/chat`, because one request can make up to 7 Gemini calls.
- Errors are logged; the Gemini API key is never logged or returned.

## 7. Part 1: User flows

There is no login: a user opens the app and uses it. Creating a conversation means clicking **New chat**, which creates one `sessions` record whose `_id` becomes that chat's `thread_id`.

### 7.1 React state

| State | Holds | Changes when |
| --- | --- | --- |
| `documents` | File list | App opens; upload succeeds |
| `sessions` | Chat list | App opens; New chat |
| `activeSessionId` | ID of the open chat, or `null` | New chat; user clicks a chat |
| `messages` | Messages of the open chat only | Open or switch chat (replaced); send question (appended) |
| `loading` | Waiting for an answer ("Thinking…") | Send starts / answer or error arrives |
| `error` | Last error message to show | Any failed request |

### 7.2 Open the app

1. React calls `GET /api/documents` and `GET /api/sessions`.
2. The left panel shows the file list and the chat list. `activeSessionId` is `null`, so the chat window is empty.

### 7.3 Upload a file

1. User picks a file. React sends it as `FormData` to `POST /api/upload` and shows "Uploading…".
2. Express (Multer, memory storage) checks type (`.pdf`, `.md`, `.txt`) and size (≤ 10 MB). Invalid → 400.
3. Express creates `docId` and forwards `file` + `doc_id` to FastAPI `POST /ingest`.
4. FastAPI runs the ingestion pipeline (section 8) and returns `{ doc_id, filename, chunks }`.
5. Only now Express saves the `documents` record (D9).
6. Express returns `{ docId, filename, chunks }`. React adds it to the file list.

Uploading a file is not tied to any chat. Every chat can search every uploaded file.

### 7.4 Start a new chat

1. User clicks **New chat**. React calls `POST /api/sessions`.
2. Express creates a `sessions` record; MongoDB generates a new `_id`. Express returns it as `sessionId`.
3. React adds the chat to the list, sets `activeSessionId = sessionId`, and sets `messages = []`.

No AI call happens here. The new thread has no checkpoint yet, so its memory is empty.

### 7.5 Send a question

1. React appends `{ role: "user", content: question }` to `messages` immediately and sets `loading = true` ("Thinking…").
2. React calls `POST /api/chat` with `{ sessionId: activeSessionId, question }`.
3. Express validates both fields and that the session exists, then saves the user `Message`.
4. Express calls FastAPI `POST /chat` with `{ thread_id: sessionId, question }`.
5. FastAPI runs the agent (section 9) with `config = {"configurable": {"thread_id": thread_id}}`. The checkpointer loads this thread's memory (section 10).
6. FastAPI returns `{ answer, sources, route, retries }`.
7. Express saves the assistant `Message` with `sources`, `route`, `retries`, then returns the response.
8. React appends the assistant message, sets `loading = false`, and shows the answer, a **Sources** list (`filename — page N`) and the badge.

On any error, React removes the loading state and shows an assistant-style error message ("Something went wrong. Try again."); a 503 shows "AI service is unavailable".

Badge text: `direct` → "Direct reply"; `docs` with sources → "Searched docs · N retries"; `docs` without sources → "Not found".

### 7.6 Open an old chat

1. User clicks a chat in the list. React sets `activeSessionId` to its ID.
2. React calls `GET /api/sessions/:id/messages` and replaces `messages` with the result, oldest first.
3. New questions follow 7.5 with this ID, so the agent loads this chat's memory and follow-ups work.

### 7.7 Refresh the page

React state is lost on refresh, but everything is saved in MongoDB. React runs 7.2 again; `activeSessionId` is `null` until the user picks a chat, and 7.6 restores its messages. The agent's memory is unaffected because it lives in checkpoints.

## 8. Part 2: Ingestion pipeline

A file travels twice (React → Express, Express → FastAPI), then FastAPI turns it into labelled, embedded chunks in Qdrant. Function: `ingest_file(file_path, doc_id, filename) -> int` in `ingest.py`, returning the chunk count.

### 8.1 Steps

1. **Receive (Express).** Multer memory storage parses the multipart request into `req.file` (`originalname`, `mimetype`, `size`, `buffer`). It enforces the 10 MB limit and the allowed extensions. Multer is a parser inside Express, not a storage location.
2. **Forward (Express).** Build a new `FormData` with `file` (from `req.file.buffer`, keeping `originalname`) and `doc_id`; `axios.post` it to `/ingest` with `form.getHeaders()`.
3. **Receive (FastAPI).** `POST /ingest` accepts `UploadFile` + `doc_id` form field, rejects other extensions with 400, and writes the bytes to a temp file (loaders need a path).
4. **Load.** PDF → `PyPDFLoader`, one `Document` per page with page metadata. `.md` / `.txt` → text loader, one `Document`, page 1.
5. **Chunk.** `RecursiveCharacterTextSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)` (defaults 800 / 100 characters). It splits at paragraphs first, then lines, then sentences and words, so chunks stay readable.
6. **Label.** Set metadata on every chunk: `doc_id`, `filename`, `page` (1-based, D13).
7. **Ensure collection.** If `QDRANT_COLLECTION` does not exist, create it with vector size 768 and cosine distance.
8. **Embed and store.** `QdrantVectorStore` with the Ollama `nomic-embed-text` embeddings object embeds each chunk (768 numbers) and stores vector + text + metadata. Qdrant indexes vectors with HNSW for fast approximate nearest-neighbour search.
9. **Clean up and reply.** Delete the temp file in a `finally` block. Return `{ doc_id, filename, chunks }`.
10. **Record (Express).** Save the `documents` record, return `{ docId, filename, chunks }` to React.

### 8.2 Why chunk with overlap

A whole page mixes several topics, which makes search noisy and wastes context. Small chunks give precise matches. Overlap repeats the end of one chunk at the start of the next, so a sentence cut at a boundary still appears whole in one chunk:

```text
Chunk 7: "...Rate limits. You can make 100 requests per minute. If you exceed"
Chunk 8:                    "per minute. If you exceed this, the API returns 429 and..."
```

### 8.3 Rules

- **The same embedding model is used for ingestion and search.** Vectors from different models are not comparable.
- The original file is not stored anywhere after ingestion. Only its chunks remain in Qdrant.
- Re-uploading the same file adds a second copy of its chunks (no de-duplication; see section 12).

### 8.4 Verification (`scripts/test_ingest.py`)

Ingest one sample PDF, print the chunk count, print one chunk's text and metadata, then run a similarity search for a sample question and print the top 3 results with scores. Chunks must be visible in the Qdrant dashboard at `http://localhost:6333/dashboard`.

## 9. Part 3: LangGraph agent

The agent decides, sharpens the question, searches, checks the results, retries if needed, and answers only from what passed the check, or honestly says not found. It is a graph of 8 nodes sharing one state.

### 9.1 Graph input and output

FastAPI invokes the compiled graph once per question:

```python
result = graph.invoke(
    {"question": question, "messages": [HumanMessage(content=question)]},
    config={"configurable": {"thread_id": thread_id}},
)
# returns {answer, sources, route, retries = result["retry_count"]}
```

### 9.2 State (`state.py`)

| Field | Type | Meaning | Written by | Reset each turn |
| --- | --- | --- | --- | --- |
| `messages` | `Annotated[list, add_messages]` | Chat history (appended, never replaced) | input, final nodes | No (memory) |
| `question` | `str` | The user's original words | input | Set by input |
| `route` | `str` | `"docs"` or `"direct"` | `router` | Yes |
| `search_query` | `str` | Current search text, used only by `retrieve` | `rewrite_query` | Yes → `""` |
| `failed_queries` | `list[str]` | Queries whose results all failed grading (D3) | `prepare_retry` | Yes → `[]` |
| `documents` | `list` | Chunks returned by Qdrant | `retrieve` | Yes → `[]` |
| `relevant_docs` | `list` | Chunks that passed grading | `grade_documents` | Yes → `[]` |
| `retry_count` | `int` | Retries done this turn | `prepare_retry` | Yes → `0` |
| `answer` | `str` | Final reply | final nodes | Yes → `""` |
| `sources` | `list` | `[{filename, page}]`, de-duplicated | `generate` (others set `[]`) | Yes → `[]` |

`failed_queries` and every reset field use plain overwrite, so the router's reset fully clears last turn's values (D7).

### 9.3 Nodes (`nodes.py`)

| Node | Reads | Writes | Gemini call |
| --- | --- | --- | --- |
| `router` | `question` | `route` + all per-turn resets | Yes, structured `RouteDecision(route: Literal["docs","direct"])` |
| `direct_answer` | `question`, last 6 `messages` | `answer`, `sources=[]`, +1 `AIMessage` | Yes |
| `rewrite_query` | `question`, last 6 `messages`, `failed_queries` | `search_query` | Yes |
| `retrieve` | `search_query` | `documents` (top `TOP_K`) | No (Ollama + Qdrant) |
| `grade_documents` | `question`, last 6 `messages`, `documents` | `relevant_docs` | Yes, one batched call, structured `Grade(relevant_ids: list[int])` |
| `prepare_retry` | `search_query`, `failed_queries`, `retry_count` | `failed_queries + [search_query]`, `retry_count + 1` | No |
| `generate` | `question`, last 6 `messages`, `relevant_docs` | `answer`, `sources`, +1 `AIMessage` | Yes |
| `not_found` | – | fixed `answer`, `sources=[]`, +1 `AIMessage` | No |

### 9.4 Edges (`build_graph.py`)

```text
START → router
router ── route == "direct" ──► direct_answer → END
router ── route == "docs"   ──► rewrite_query → retrieve → grade_documents
grade_documents ── relevant_docs not empty                      ──► generate → END
grade_documents ── empty and retry_count <  MAX_RETRIES          ──► prepare_retry → rewrite_query (loop)
grade_documents ── empty and retry_count >= MAX_RETRIES          ──► not_found → END
```

&#91;embedded content: agent graph · 8 nodes, 1 retry loop\]

Shaded nodes end the turn. The loop through `prepare_retry` runs at most `MAX_RETRIES` times, and grading always judges against the original question.

With `MAX_RETRIES = 2`, a question is searched at most 3 times. The counter is what stops the cycle.

### 9.5 Prompt rules (`prompts.py`)

- **ROUTER\_PROMPT:** "docs" if the message needs the documentation; "direct" for greetings, small talk, general questions not about the docs, or questions about the previous messages in this chat (e.g. "what did I ask before?"); questions about any product or system, even DocChat itself, are "docs". When unsure, choose "docs".
- **REWRITE\_PROMPT:** Input = chat history (last 6) + original question; on a retry also the failed queries. Write ONE standalone, keyword-rich search query: keep the user's key terms, add concrete words the answer text is likely to contain, and never add generic filler ("documentation", "guide", "overview", "process"). Replace references ("it", "that") with what they refer to. Keep the exact meaning (D4). On a retry, use different words or synonyms and do not repeat any failed query. Return only the query.
- **GRADE\_PROMPT:** Input = chat history (last 6) + original question + chunks numbered 1..k. Return the IDs of chunks that contain information answering the question; a chunk that partly answers counts, but a chunk that only mentions the topic, points to another section, or is a general overview does not. Return an empty list if none do. Judge against the user's question, never against the search query (D5). Ignore any returned ID outside 1..k.
- **GENERATE\_PROMPT:** Role = documentation assistant. Context = relevant chunks numbered with filename and page. Answer only from the context; if it does not fully answer, explain the part the docs cover, then say what is missing. Explain clearly in simple words: short answers for factual questions, step-by-step explanations for "explain" or "how" questions. Do not invent APIs, parameters or values. Start directly with the answer (never "Based on the documentation..."). Plain text only, no markdown symbols.
- **Direct reply:** short and friendly; if the message asks about the conversation, answer from the last 6 messages; otherwise mention that DocChat answers questions about the uploaded docs.
- **Not found text:** "I couldn't find this in the uploaded documentation. Try rephrasing or upload the relevant doc."

### 9.6 Query drift rules (must follow)

Query drift = retries slowly changing the question until the search answers something the user never asked.

1. The rewrite changes words, never meaning.
2. Every rewrite starts from the original question; failed queries are passed only as "do not repeat".
3. `search_query` is used only for retrieval. Grading and generation judge against the original question (with history to resolve references).

In short: the rewrite may hunt widely, but the original question decides what is accepted.

### 9.7 Why grading is needed

Qdrant ranks chunks by vector closeness and always returns `TOP_K`, even when none answer the question. Each chunk was embedded alone, so closeness measures topic, not whether the chunk contains the answer (for example, the Payments API rate limit is "close" to a question about the Refunds API rate limit). The grader reads the question and chunks together, like a reranker, and drops chunks that do not answer. A similarity-score cutoff cannot do this, because a wrong chunk can score higher than a right one.

### 9.8 Example journeys

| Question | Path | Gemini calls | Output |
| --- | --- | --- | --- |
| "hi" | router → direct\_answer | 2 | Direct reply, `route=direct` |
| "What is the rate limit?" | router → rewrite → retrieve → grade → generate | 4 | Answer + sources, `retries=0` |
| "What if I exceed it?" (same chat) | Same; rewrite uses history → "payments API rate limit exceeded response" | 4 | Answer + sources, `retries=0` |
| "How do I stop getting blocked?" | … grade finds 0 → prepare\_retry → rewrite ("rate limit throttling too many requests") → retrieve → grade finds 2 → generate | 6 | Answer + sources, `retries=1` |
| "How do I deploy to Kubernetes?" (not in docs) | 3 searches, all graded empty → not\_found | 7 | Not found, `retries=2` |

### 9.9 Verification (`scripts/test_graph.py`)

Print the path of nodes visited using `graph.stream(..., stream_mode="updates")`. Show: a doc question with `retries=0`; an out-of-scope question reaching `not_found` after `MAX_RETRIES`; "hi" skipping retrieval. Optionally save `graph.get_graph().draw_mermaid()` for the README.

## 10. Memory

LangGraph finds a chat's memory by `thread_id`, automatically, before any node runs. Our code only compiles the graph with the checkpointer and passes the right `thread_id`.

### 10.1 How memory is found and saved

1. Express sends `thread_id = sessionId` with the question.
2. FastAPI calls `graph.invoke(input, config={"configurable": {"thread_id": thread_id}})`.
3. The checkpointer loads the newest checkpoint for that `thread_id` from MongoDB. None found → the state starts empty (a new chat).
4. The input's `HumanMessage` is appended to `messages` by the `add_messages` reducer; `question` is overwritten.
5. Nodes run, reading history from `state["messages"]`. The final node appends one `AIMessage`.
6. The checkpointer saves the new state under the same `thread_id`. Restarting the service keeps it, because it is in MongoDB.

```python
checkpointer = MongoDBSaver(client, db_name=MONGO_DB)   # verify constructor for the installed version
graph = builder.compile(checkpointer=checkpointer)      # build once at startup
```

`messages + add_messages + checkpointer + thread_id = persistent conversation history.`

### 10.2 Context window control

- The checkpointer keeps the full history; storage costs no tokens.
- Every prompt that uses history (`direct_answer`, `rewrite_query`, `grade_documents`, `generate`) takes only the **last 6 messages**. Tokens per call therefore stay roughly constant however long the chat grows.
- Retrieved chunks are never added to `messages`; only questions and final answers are, so history stays small.
- Per-turn fields are reset by the router (D7); only `messages` carries over between turns.

### 10.3 Separation between chats

- Same `thread_id` → same memory. A follow-up like "What happens if I exceed it?" is rewritten into a standalone query.
- Different `thread_id` → no memory of other chats, but the same documents (they are global).

### 10.4 Verification

In `test_graph.py` with the same `thread_id`: Q1 "What is the rate limit of API X?", then Q2 "What happens if I exceed it?" → the rewrite makes Q2 standalone and the answer is correct. A different `thread_id` has no memory of Q1. After restarting the script, the first thread still remembers Q1.

## 11. Multiple documents

DocChat supports many documents. The agent never picks a document first: every question searches all chunks from all files, similarity picks the chunks, and each chunk's metadata says which file and page it came from.

- All chunks share one collection, each labelled `{doc_id, filename, page}`.
- One answer can cite several files when the question spans them.
- **Risk:** two docs on the same topic (e.g. two APIs that both have rate limits) can return mixed chunks. Mitigations: grading against the original question, the rewrite adding names from history, citations so the user can check, and users asking specific questions.
- Per-document filtering is not built. It would be a Qdrant filter on `metadata.doc_id` (future work).

## 12. Known limitations and future work

**Limitations (accepted for this project)**

| Limitation | Effect |
| --- | --- |
| No login | Everyone shares all docs and chats |
| No document filter or delete | Every chat searches every file; a wrong upload stays |
| Re-uploading a file duplicates its chunks | Duplicate sources in answers |
| Up to 7 Gemini calls per question | Slower and costlier on hard or out-of-scope questions |
| Grader can misjudge | Rarely drops a good chunk or keeps a partial one |
| History trimmed to 6 messages | References older than 3 turns may not resolve |
| A new chat has empty memory | Follow-ups only work inside the same chat |

**Future work (do not build unless asked)**

- Agent trace UI with streaming (SSE): "Routing → Rewriting → Retrieved 5 → 2 relevant → Answering".
- Per-document filter using `doc_id`; document delete.
- Summarise older history instead of only trimming.
- Skip the first rewrite when a chat has no history, to save one call.
- Mem0 for long-term user preferences, alongside the checkpointer.
- Neo4j graph memory, Valkey caching, authentication, cloud deploy.

## 13. Phases

The build has 10 phases in 4 stages. Build them in order, one at a time. Every phase ends with something you can run and see.

| Stage | Phases | Milestone |
| --- | --- | --- |
| 1. Foundation | 1 | Script prints 768 and a Gemini reply |
| 2. AI brain in Python | 2–6 | The agent works in test scripts, with memory |
| 3. Web app | 7–9 | Chat with your docs in the browser |
| 4. Prove it | 10 | Results table in the README, repo on GitHub |

**Rules for every phase** (from `CLAUDE.md`, restated here)

1. Work on one phase only. Do not start the next until the user says so.
2. Before any code, give a Phase Briefing (described below) and wait for the user to say go. The briefing starts with a Concept Revision block (5–10 lines) explaining the phase's GenAI concepts in simple words and where they appear in the code.
3. While coding, comment only where a GenAI concept is applied. Keep FastAPI code minimal and explain it briefly. Prefer simple synchronous Python.
4. After coding, give the exact commands to verify the "Done when" checks, ask the user 3 interview-style questions and wait for answers, and suggest a 3-line note for `NOTES.md`.
5. Verify library APIs (imports, class names, constructors) in the installed package or official docs. Never guess.
6. Never hardcode secrets or print the API key. `.env` stays in `.gitignore`.
7. Do not add anything outside this document (no auth, no cloud, no Mem0, no extra UI).
8. If something fails, explain the error in simple words before fixing it.

**Phase Briefing (before any code)**

The user wants to understand and check each phase before it is built. Give the whole picture first, in simple words, then stop and ask "Ready to build?". Do not create or change any file until the user says go. The briefing has these parts:

1. **Goal:** what this phase adds, and what the user will be able to run and see at the end, in one or two sentences.
2. **Requirements:** what must be installed, running or configured (tools, Docker containers, models, env vars, API keys, a sample file), what must already exist from earlier phases, and anything the user has to do first.
3. **Concept Revision:** the 5–10 line block for this phase's GenAI concepts.
4. **Flow, step by step:** what happens when this phase runs, in order, from input to output. Use a short text flow or small diagram. Name the data that moves between steps.
5. **Files and functions:** every file to create or change, with one line on its job and the functions or classes inside it.
6. **Decisions and scope:** which decisions (D1 to D14) apply and why, what is deliberately not built in this phase, and how it connects to the previous and next phase.
7. **How to verify and what can go wrong:** the "Done when" checks as exact commands, plus the two or three most likely failures and what they mean.
8. **Stop:** ask "Ready to build?" and wait.

Folder structure and environment variables are as in `CLAUDE.md` sections 4 and 5.

### Phase 1: Setup

**Concepts to revise:** what an LLM is (next-token prediction); embedding model vs generative model; local (Ollama) vs hosted (Gemini) models: cost, privacy, speed.

**Implements:** sections 2 and 4.

**Build**

1. Folder structure, `.gitignore` (`.env`, `node_modules`, `__pycache__`, `.venv`, `uploads/`), `.env.example`, empty `NOTES.md`.
2. `docker-compose.yml` with Qdrant (port 6333, named volume) and MongoDB (port 27017, named volume). Ollama runs on the host; from a container it is reached at `host.docker.internal:11434`.
3. `ai-service/requirements.txt`: fastapi, uvicorn, python-multipart, python-dotenv, langchain, langchain-community, langchain-text-splitters, langchain-ollama, langchain-qdrant, qdrant-client, langchain-google-genai, langgraph, langgraph-checkpoint-mongodb, pymongo, pypdf, pydantic.
4. `config.py`: load env vars; create the Ollama embeddings object, the Gemini chat model (temperature 0, model from `GEMINI_MODEL`), and the Qdrant client.
5. A sanity script that embeds "hello world" and prints the vector length, then sends one short prompt to Gemini.

**Done when**

- `docker compose up -d` starts Qdrant and MongoDB.
- `ollama pull nomic-embed-text` is done.
- The sanity script prints `768` and a Gemini reply, and never prints the API key.

### Phase 2: Ingestion pipeline

**Concepts to revise:** tokens vs characters; context window; chunking and why; chunk overlap; embeddings and vector space; cosine similarity; vector DB and approximate nearest-neighbour search (HNSW); metadata for citations.

**Implements:** section 8; decisions D12, D13.

**Build**

1. `ingest_file(file_path, doc_id, filename) -> int` in `ingest.py`, returning the number of chunks.
2. Load: PDF with `PyPDFLoader`; `.md` / `.txt` with a text loader (page 1).
3. Chunk with `RecursiveCharacterTextSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)`.
4. Add metadata to every chunk: `doc_id`, `filename`, `page` (1-based; check what `PyPDFLoader` returns and convert, D13).
5. Create the Qdrant collection if missing (size 768, cosine), then store chunks with `QdrantVectorStore`.
6. `scripts/test_ingest.py`: ingest one sample PDF, print the chunk count, print one chunk's text and metadata, then run a similarity search and print the top 3 results with scores.

**Done when**

- Chunks are visible at `http://localhost:6333/dashboard`.
- The similarity search returns sensible chunks.
- A chunk from the last page of the PDF shows the correct page number.

### Phase 3: Basic RAG graph

**Concepts to revise:** RAG (retrieve, augment, generate); hallucination and grounding; prompt engineering and the system prompt; temperature; top-k; transformers and self-attention (how the LLM links the question to the context).

**Implements:** sections 9.1 to 9.3 and 9.5; decision D8.

**Build**

1. `state.py`: the **full** `AgentState` from section 9.2, including `failed_queries`, so later phases only add nodes and never reshape the state.
2. `prompts.py`: `GENERATE_PROMPT` as in 9.5. Context chunks are numbered with filename and page.
3. `nodes.py`:
   - `retrieve(state)`: similarity search with `search_query`, or `question` if it is empty, `k=TOP_K`. Write `documents`.
   - `generate(state)`: for now use all `documents` as context. Call Gemini, set `answer` and de-duplicated `sources`, and append one `AIMessage` to `messages`.
4. `build_graph.py`: `START → retrieve → generate → END`, compiled without a checkpointer.
5. `scripts/test_graph.py`: invoke with `{"question": q, "messages": [HumanMessage(content=q)]}` (the final input format, D8). Ask 2 questions about the sample doc and print answer and sources.

**Done when**

- Answers to both questions are correct.
- Sources show the right filename and page.
- A question the doc does not answer produces a hedged or "not in the context" answer, not an invented one.

### Phase 4: Router and direct answer

**Concepts to revise:** LangGraph state, nodes, edges and conditional edges; chain vs graph; the LLM as a classifier; structured output (Pydantic) and why it is more reliable than parsing free text.

**Implements:** sections 9.3 to 9.5; decisions D7, D8.

**Build**

1. `ROUTER_PROMPT` as in 9.5 (unsure → "docs").
2. `router(state)`: `llm.with_structured_output(RouteDecision)` where `RouteDecision.route` is `Literal["docs", "direct"]`. It also **resets every per-turn field** listed in section 9.2 (`search_query`, `failed_queries`, `documents`, `relevant_docs`, `retry_count`, `answer`, `sources`). It does **not** append the human message; the input already carries it (D8).
3. `direct_answer(state)`: short friendly reply that mentions DocChat answers questions about the uploaded docs. Set `sources = []` and append one `AIMessage`.
4. Graph: `START → router`; conditional edge on `state["route"]`: `"docs" → retrieve → generate → END`, `"direct" → direct_answer → END`.

**Done when**

- "hi" goes to `direct_answer` and no retrieval happens (check with `stream_mode="updates"`).
- A doc question goes through `retrieve` and `generate`.
- An ambiguous message routes to "docs".

### Phase 5: Query rewrite, grading, retry loop

**Concepts to revise:** query transformation; using chat history to make follow-ups standalone; LLM-as-judge; Corrective RAG; cycles in a graph and stopping conditions; query drift; latency and cost of extra LLM calls.

**Implements:** all of section 9; decisions D2 to D6.

**Build**

1. `REWRITE_PROMPT` and `rewrite_query(state)`: built from the original `question`, the last 6 messages and `failed_queries` (never from the previous `search_query`). Wording changes only; the meaning must stay (9.5, 9.6). Writes `search_query`.
2. `GRADE_PROMPT` and `grade_documents(state)`: **one** Gemini call with the original `question`, the last 6 messages and all `documents` numbered 1..k. Structured output `Grade(relevant_ids: list[int])`. Ignore any ID outside 1..k. Writes `relevant_docs`. The prompt must use `question`, never `search_query` (D5).
3. `prepare_retry(state)`: append `search_query` to `failed_queries` and add 1 to `retry_count` (D6).
4. `not_found(state)`: the fixed text from 9.5, `sources = []`, append one `AIMessage`.
5. `generate` now uses only `relevant_docs`, with the original `question` and the last 6 messages.
6. Graph edges exactly as in section 9.4, including the loop `grade_documents → prepare_retry → rewrite_query`. The routing function reads `relevant_docs` and compares `retry_count` with `MAX_RETRIES`.
7. Return `retries` (= `retry_count`) in the final output.

Before memory exists (Phase 6), test follow-ups by putting earlier messages in the input `messages` list by hand.

**Done when**

- A doc question gives an answer with sources and `retries = 0`.
- A question unrelated to every document ends in `not_found` after `MAX_RETRIES` retries, with `retries = 2`.
- **Drift test:** a question that sounds related but is not in the docs (for example "How do I deploy to Kubernetes?" against API docs) ends in `not_found`, not a loosely related answer.
- A follow-up such as "What if I exceed it?" (with the earlier question in `messages`) is rewritten into a standalone query that names the topic.
- The printed node path (`stream_mode="updates"`) shows the loop running.
- Optional: save `graph.get_graph().draw_mermaid()` for the README.

### Phase 6: Memory with checkpointer

**Concepts to revise:** LLMs are stateless; short-term vs long-term memory; checkpointing and threads; context window management (trimming, summarizing); where Mem0 and graph memory (Neo4j) would fit (future work only).

**Implements:** section 10; decisions D1, D7.

**Build**

1. Compile the graph with `MongoDBSaver` (database `MONGO_DB`). Verify the import and constructor for the installed version. If it causes problems, fall back to the SQLite checkpointer and tell the user.
2. Invoke with `config={"configurable": {"thread_id": thread_id}}`.
3. Pass only the new `HumanMessage` and `question` per turn. History comes from the checkpointer through `messages`.
4. One small helper that returns the last 6 messages, used by every prompt that uses history (`direct_answer`, `rewrite_query`, `grade_documents`, `generate`).

**Done when**

- Same `thread_id`: Q1 "What is the rate limit of API X?" then Q2 "What happens if I exceed it?" gives a correct answer, with Q2 rewritten into a standalone query.
- A different `thread_id` has no memory of Q1.
- Restarting the script keeps the memory (it is in MongoDB).
- **Reset test:** in one thread, ask a question that needs a retry, then a simple one. The second shows `retries = 0`, with no leftover documents or answer.
- In MongoDB Compass, the checkpoint collections show several documents with different `_id`s and the same `thread_id`.

### Phase 7: FastAPI wrapper

**Concepts to revise:** latency of multi-step agents (count the LLM calls per request); token cost; streaming (for a future trace UI); keeping API keys server-side.

**Implements:** the FastAPI side of sections 6 and 8.1, and section 9.1.

**Build** (keep it minimal; explain path operations, Pydantic request models, `UploadFile` and the `/docs` page briefly)

1. `GET /health` returns `{"status": "ok"}`.
2. `POST /ingest`: `UploadFile` + `doc_id` form field. Allow only `.pdf`, `.md`, `.txt` (else 400). Save to a temp file, call `ingest_file`, delete the temp file in `finally`, return `{doc_id, filename, chunks}`.
3. `POST /chat`: Pydantic request `{thread_id, question}`. Invoke the compiled graph, which is built **once at startup**. Return `{answer, sources, route, retries}`.
4. Clear errors: 400 for bad input, 500 with a short message for failures. Log errors; never log or return the API key.

**Done when**

- Both endpoints work from `http://localhost:8000/docs`.
- A doc question, "hi", an out-of-scope question and a same-thread follow-up all behave as in Phases 4 to 6.
- Count the Gemini calls for each of the five example journeys in section 9.8 and compare with the table.

### Phase 8: Express gateway

**Concepts to revise:** none new. Use this phase to revise Phases 2 to 6, and end with 3 revision questions from them.

**Implements:** sections 5, 6 and 7; decisions D9, D10, D11.

**Build**

1. Mongoose models: `Document { docId, filename, chunks, uploadedAt }`, `Session { title, createdAt }`, `Message { sessionId, role, content, sources, route, retries, createdAt }` with an index on `{ sessionId, createdAt }` (section 5).
2. `POST /api/upload`: Multer with memory storage, 10 MB limit, `.pdf` / `.md` / `.txt` only. Create `docId` with `crypto.randomUUID()` (D11), forward the bytes and `doc_id` to FastAPI `/ingest` with `form-data`, and **only after it succeeds** save the `Document` (D9).
3. `POST /api/chat`: validate `sessionId` and a non-empty `question`, check the session exists, save the user `Message`, call FastAPI `/chat` with `thread_id = sessionId`, save the assistant `Message` with `sources`, `route` and `retries`, and return the response. Axios timeout about 60 seconds.
4. `POST /api/sessions` (default title "New chat"), `GET /api/sessions` (newest first), `GET /api/sessions/:id/messages` (oldest first), `GET /api/documents`.
5. `cors`, `express.json()`, and a central `errorHandler`: if the AI service is down, return 503 with a clear message.
6. `services/aiClient.js` holds the Axios calls to FastAPI.

**Done when**

- In Postman: upload, create a session, chat, follow-up all work.
- A second session has no memory of the first, but still answers from the same documents.
- A wrong file type or a file over 10 MB gives 400.
- With FastAPI stopped, `/api/chat` and `/api/upload` give 503 with a clear message.
- After 3 revision questions on Phases 2 to 6, the user answers and is corrected.

### Phase 9: React UI

**Concepts to revise:** citations build trust and let users verify answers (responsible AI). Nothing else is new.

**Implements:** section 7, including the React state table in 7.1.

**Build** (simple and clean; no UI library required)

1. Left panel: upload control and uploaded-file list; chat list and a **New chat** button.
2. Right panel: the chat window. Each assistant message shows the answer, a **Sources** list (`filename — page N`) and a small badge: "Direct reply", "Searched docs · N retries" or "Not found" (rule in 7.5).
3. State and flows exactly as in sections 7.1 to 7.7: add the user message at once, show "Thinking…", append the answer on success, show an error message on failure.
4. Components: `UploadPanel`, `SessionList`, `ChatWindow`, `MessageBubble`, `SourceList`. `api.js` holds every call to Express.

**Done when**

- Upload a document and chat with it in the browser, including a follow-up question.
- New chat opens an empty window; clicking an old chat shows its saved messages.
- A page refresh brings back the lists, and an old chat's messages after you click it.
- The three badge states are each shown correctly, and loading and error states appear.

### Phase 10: Evaluation and README

**Concepts to revise:** RAG evaluation: retrieval quality (hit rate: did the right chunk appear in top-k?), faithfulness (is the answer supported by the context?), answer relevance; benchmarking. RAGAS and LangSmith are mentioned only.

**Implements:** section 9.6 (drift) and section 12 (limitations and future work).

**Build**

1. `eval/questions.json`: 10 questions about the sample docs, each with `expected_filename`, `expected_page` (approximate is fine) and a short `expected_answer`. Include 2 questions whose answers are **not** in the docs; they should end in not found.
2. `eval/run_eval.py`: for each config, run all questions and record retrieval hit (expected page among the retrieved sources), correct not-found handling, answer correctness (a simple LLM-as-judge: "does the answer match the expected answer? yes/no") and latency per question. Report the out-of-scope questions' accuracy as its own number, since it shows whether the drift rules work.
3. Configs to compare: chunk size 500 vs 1000 (re-ingest into separate collections), and retry loop ON (`MAX_RETRIES=2`) vs OFF (`MAX_RETRIES=0`).
4. Print a Markdown results table and write a 3 to 4 line recommendation: which config to use and why.
5. README: problem, architecture diagram, LangGraph flow (Mermaid), tech stack, setup steps, API list, evaluation table and recommendation, and future work (agent trace UI with streaming, Mem0 long-term memory, Neo4j graph memory, Valkey caching, cloud deploy).

**Done when**

- The results table and recommendation are in the README.
- The repo is pushed to GitHub without `.env`.
- At the end, explain briefly the topics the build does not cover: tool calling, fine-tuning vs RAG, few-shot prompting.

### Optional later: agent trace UI with streaming

Only if the user asks, after Phase 10. Use `graph.stream(..., stream_mode="updates")` in a FastAPI Server-Sent Events endpoint, relay it through Express, and show live steps in React: "Routing → Rewriting query → Retrieved 5 chunks → 2 relevant → Answering".
