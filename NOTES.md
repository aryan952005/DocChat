## Phase 1: Setup
- An LLM predicts the next token; an embedding model maps text to a fixed vector (768 numbers here) and generates nothing.
- Local Ollama = free, private, slower; hosted Gemini = stronger and faster, but costs quota and sends text out.
- config.py is the single place for env vars and clients (embeddings, llm, Qdrant); later phases import from it.


## Phase 2: Ingestion pipeline
- Load -> chunk (800 chars, 100 overlap) -> label {doc_id, filename, page+1} -> embed -> store in Qdrant (768, cosine).
- Overlap keeps boundary sentences whole; metadata on each chunk is what makes citations possible; PyPDFLoader pages are 0-based.
- Search embeds the question with the same model, and Qdrant ranks chunks by cosine similarity using an HNSW index.

## Phase 3: Basic RAG graph
- RAG = retrieve top-k chunks, put them in the prompt as numbered context, let the LLM generate from them; grounding prompt = "answer only from context".
- LangGraph: nodes read the shared AgentState and return partial updates; add_messages appends to chat history.
- Without grading, top-k always returns chunks even when irrelevant, so sources are noisy; Phase 5 adds the grader.

## Phase 4: Router and direct answer
- A graph branches on state: router (LLM as classifier) writes state["route"], a conditional edge picks the next node.
- with_structured_output(Pydantic + Literal) forces a valid label; unsure defaults to "docs" because a wasted search is cheaper than skipping the docs.
- The router resets per-turn fields (D7) so old values never leak across turns; the HumanMessage comes from the input only (D8).