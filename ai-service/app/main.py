import logging
import os
import tempfile

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from langchain_core.messages import HumanMessage
from pydantic import BaseModel

from app.graph.build_graph import build_graph
from app.ingest import ingest_file

logger = logging.getLogger("docchat")
app = FastAPI(title="DocChat AI service")

# Build the graph once at startup (it also connects the MongoDB checkpointer)
graph = build_graph()

ALLOWED_EXTENSIONS = {".pdf", ".md", ".txt"}


class ChatRequest(BaseModel):
    # Pydantic checks the JSON body against these fields automatically
    thread_id: str
    question: str


@app.exception_handler(RequestValidationError)
async def bad_input(request: Request, exc: RequestValidationError):
    # FastAPI answers 422 by default; the API contract says 400 for bad input
    return JSONResponse(status_code=400, content={"detail": "Bad request: missing or invalid field"})


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/ingest")
def ingest(file: UploadFile = File(...), doc_id: str = Form(...)):
    filename = os.path.basename(file.filename or "")
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Only .pdf, .md and .txt files are allowed")
    data = file.file.read()
    if not data or not doc_id.strip():
        raise HTTPException(status_code=400, detail="Empty file or doc_id")

    # Loaders need a file path, so write the bytes to a temp file
    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
        tmp.write(data)
        temp_path = tmp.name
    try:
        chunks = ingest_file(temp_path, doc_id, filename)
    except Exception:
        logger.exception("Ingestion failed")
        raise HTTPException(status_code=500, detail="Ingestion failed")
    finally:
        os.remove(temp_path)  # the original file is kept nowhere (D10)
    return {"doc_id": doc_id, "filename": filename, "chunks": chunks}


@app.post("/chat")
def chat(req: ChatRequest):
    if not req.thread_id.strip() or not req.question.strip():
        raise HTTPException(status_code=400, detail="thread_id and question are required")
    try:
        result = graph.invoke(
            {"question": req.question, "messages": [HumanMessage(content=req.question)]},
            config={"configurable": {"thread_id": req.thread_id}},
        )
    except Exception:
        logger.exception("Chat failed")
        raise HTTPException(status_code=500, detail="Chat failed")
    return {
        "answer": result["answer"],
        "sources": result["sources"],
        "route": result["route"],
        "retries": result["retry_count"],
    }
