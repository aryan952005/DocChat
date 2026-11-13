import os
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_qdrant import QdrantVectorStore
from qdrant_client.models import Distance, VectorParams

from app.config import (
    embeddings, qdrant_client, QDRANT_COLLECTION, CHUNK_SIZE, CHUNK_OVERLAP,
)

VECTOR_SIZE = 768  # must match output_dimensionality in config.py


def load_file(file_path: str):
    """Load a file into LangChain Documents: one per PDF page, or one for md/txt."""
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".pdf":
        return PyPDFLoader(file_path).load()
    if ext in (".md", ".txt"):
        return TextLoader(file_path, encoding="utf-8").load()
    raise ValueError(f"Unsupported file type: {ext}")


def ensure_collection():
    """Create the Qdrant collection (768 numbers per vector, cosine distance) if missing."""
    if not qdrant_client.collection_exists(QDRANT_COLLECTION):
        qdrant_client.create_collection(
            collection_name=QDRANT_COLLECTION,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
        )


def get_vector_store() -> QdrantVectorStore:
    """The store wraps Qdrant + the embedding model, so add/search embed text for us."""
    return QdrantVectorStore(
        client=qdrant_client,
        collection_name=QDRANT_COLLECTION,
        embedding=embeddings,
    )


def ingest_file(file_path: str, doc_id: str, filename: str) -> int:
    """load -> chunk -> label -> embed -> store. Returns the number of chunks."""
    is_pdf = file_path.lower().endswith(".pdf")
    pages = load_file(file_path)

    # Chunk overlap keeps sentences that cross a boundary whole in one chunk
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP
    )
    chunks = splitter.split_documents(pages)

    # Metadata travels with each chunk so answers can cite filename and page
    for chunk in chunks:
        # PyPDFLoader pages are 0-based (D13); md/txt files count as page 1
        page = chunk.metadata.get("page", 0) + 1 if is_pdf else 1
        chunk.metadata = {"doc_id": doc_id, "filename": filename, "page": page}

    ensure_collection()
    get_vector_store().add_documents(chunks)  # embeds each chunk, stores vector + text + metadata
    return len(chunks)
