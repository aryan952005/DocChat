import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))  # so "app" is importable

from app.config import embeddings, llm, qdrant_client

vector = embeddings.embed_query("hello world")
print("Embedding length:", len(vector))  # expect 768

print("Qdrant collections:", [c.name for c in qdrant_client.get_collections().collections])

reply = llm.invoke("Reply with one short sentence saying hello.")
print("Gemini reply:", reply.text)
