# CLAUDE.md — DocChat Build Guide

This file tells Claude Code how to build DocChat with me, phase by phase.
Read it fully before doing anything. Follow the workflow rules strictly.

Section numbers are kept from the earlier version so references stay valid.
The sections that were removed (summary, tech stack, architecture, API contracts, phases)
now live in SYSTEM_DESIGN.md.

---

## Source of truth

The system design, all design decisions (D1 to D14), the exact flows, data schemas, API contracts
and all 10 phases are in SYSTEM_DESIGN.md, imported below. Read it fully before any phase.

- About **system behavior** (flows, state, nodes, schemas, APIs, phases): SYSTEM_DESIGN.md wins.
- About **how we work together** (workflow rules, my background): this file wins.

@SYSTEM_DESIGN.md

---

## 0. About me and how to work with me

- I am a final-year B.Tech CSE student preparing for an R&D Engineer interview (GenAI-focused role).
- I know **Generative AI concepts in Python** (LangChain, LangGraph, RAG, Qdrant, Ollama) but need revision.
- I know **backend in Node.js / Express** (MongoDB, REST), but I am rusty.
- I am **new to FastAPI**. Keep FastAPI code minimal and explain it briefly.
- I must be able to **explain every line of this project in an interview**. Readable, simple code beats clever code.

### Workflow rules (very important)

1. **Work one phase at a time.** Never start the next phase until I say so.
2. **Before any code in a phase**, give me a **Phase Briefing**, then stop and ask "Ready to build?".
   Do not create or change any file until I say go. The briefing has these parts, in simple words:
   - **Goal:** what this phase adds and what I will be able to run and see at the end.
   - **Requirements:** what must be installed, running or configured (tools, containers, models, env vars, keys, sample files),
     what must already exist from earlier phases, and anything I must do first.
   - **Concept Revision:** a short block (5-10 lines) on the GenAI concepts for this phase and how they appear in its code.
   - **Flow, step by step:** what happens when this phase runs, in order, from input to output, and what data moves between steps.
   - **Files and functions:** every file to create or change, with one line on its job and the functions or classes inside it.
   - **Decisions and scope:** which decisions (D1 to D14) apply and why, what is deliberately not built in this phase,
     and how it connects to the previous and next phase.
   - **How to verify and what can go wrong:** the "Done when" checks as exact commands, plus the likely failures.
3. **While coding**, add short comments only where a GenAI concept is applied (e.g. `# Chunk overlap keeps sentences that cross a boundary`). No noisy comments.
4. **After coding a phase**:
   - Give me the exact commands to run and verify it (the "Done when" check).
   - Ask me **3 interview-style questions** about that phase's GenAI concepts. Wait for my answers and correct me.
   - Suggest a 3-line note I can add to `NOTES.md`.
5. **Do not add features that are not in SYSTEM_DESIGN.md** (no auth, no cloud deploy, no Mem0/Neo4j/Valkey, no fancy UI) unless I ask.
6. **Never hardcode secrets.** Read keys from `.env`. Make sure `.env` is in `.gitignore`. Never print the API key.
7. **Verify library APIs before using them.** LangChain / LangGraph / Gemini package APIs change often. If unsure about an import path or class name, check the installed package or official docs instead of guessing.
8. If something fails, explain the error in simple words before fixing it.
9. Prefer simple, synchronous Python where possible. Use async only where it clearly helps.
10. **Follow SYSTEM_DESIGN.md exactly** for flows, state fields, node order, schemas and API shapes.
    If something looks wrong, missing or outdated, tell me and ask. Do not change the design silently.

---

## 4. Folder structure

```
docchat/
├── CLAUDE.md
├── SYSTEM_DESIGN.md         # system design, decisions, flows, phases (source of truth)
├── NOTES.md                 # my learning notes, one section per phase
├── README.md
├── docker-compose.yml
├── .env.example
├── .gitignore
├── client/                  # React (Vite)
│   └── src/
│       ├── App.jsx
│       ├── api.js
│       └── components/ (UploadPanel.jsx, ChatWindow.jsx, MessageBubble.jsx, SourceList.jsx, SessionList.jsx)
├── server/                  # Express
│   ├── index.js
│   ├── routes/ (upload.js, chat.js, sessions.js, documents.js)
│   ├── models/ (Session.js, Message.js, Document.js)
│   ├── services/aiClient.js
│   └── middleware/errorHandler.js
├── ai-service/              # Python
│   ├── requirements.txt
│   ├── app/
│   │   ├── main.py          # FastAPI endpoints
│   │   ├── config.py        # env vars, clients (embeddings, LLM, Qdrant)
│   │   ├── ingest.py        # load → chunk → embed → store
│   │   ├── prompts.py       # all prompts in one place
│   │   └── graph/
│   │       ├── state.py
│   │       ├── nodes.py
│   │       └── build_graph.py
│   └── scripts/
│       ├── test_ingest.py
│       └── test_graph.py
└── eval/
    ├── questions.json
    └── run_eval.py
```

---

## 5. Environment variables (`.env.example`)

```
# AI service
GEMINI_API_KEY=
GEMINI_MODEL=
OLLAMA_URL=http://localhost:11434
EMBED_MODEL=nomic-embed-text
QDRANT_URL=http://localhost:6333
QDRANT_COLLECTION=docchat_docs
MONGO_URI=mongodb://localhost:27017
MONGO_DB=docchat
CHUNK_SIZE=800
CHUNK_OVERLAP=100
TOP_K=5
MAX_RETRIES=2

# Express
PORT=5000
AI_SERVICE_URL=http://localhost:8000
```

Note for Docker: if the AI service runs inside a container, Ollama on the host is reached at
`http://host.docker.internal:11434` (on Linux add `extra_hosts: ["host.docker.internal:host-gateway"]`).

---

## 8. Final GenAI coverage checklist (for my revision)

- [ ] LLMs, tokens, tokenization, context window
- [ ] Transformers, self-attention
- [ ] Embeddings, vector space, cosine similarity
- [ ] Chunking, overlap
- [ ] Vector databases, HNSW, metadata
- [ ] RAG, hallucination, grounding
- [ ] Prompt engineering, system prompt, temperature, top-k
- [ ] Structured output
- [ ] Agents vs chains; LangGraph state, nodes, edges, conditional edges, cycles
- [ ] Query rewriting, LLM-as-judge, Corrective / Adaptive RAG
- [ ] Query drift and why grading uses the original question
- [ ] Memory types, checkpointing, context management
- [ ] Latency, cost, streaming
- [ ] RAG evaluation

Not covered by the build — explain these to me briefly at the end: **tool calling**, **fine-tuning vs RAG**, **few-shot prompting**.

---

## 9. How to start

When I say **"Start Phase 1"**, give me the Phase Briefing for Phase 1 (see workflow rule 2), then stop and ask "Ready to build?".
Build only after I say go. The same applies to every later phase.