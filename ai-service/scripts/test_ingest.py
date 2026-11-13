import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))  # so "app" is importable

from app.ingest import ingest_file, get_vector_store

PDF = os.path.join(os.path.dirname(__file__), "..", "payments-api-sample-v2.pdf")
QUESTION = "What is the rate limit for test keys?"

count = ingest_file(PDF, doc_id="d1", filename="payments-api-sample-v2.pdf")
print("Chunks stored:", count)

store = get_vector_store()
results = store.similarity_search_with_score(QUESTION, k=3)
print(f"-------------*100-------------")
print("Printing result[0] for debugging purposes")
print(results[0])
print(f"-------------*100-------------")
print("\n--- Sample chunk ---")

doc, _ = results[0]
print(doc.page_content)
print(doc.metadata)

print(f"-------------*100-------------")

print(f"\n--- Top 3 for: {QUESTION} ---")
for doc, score in results:
    print(f"score={score:.3f} page={doc.metadata['page']} | {doc.page_content[:90]!r}")

print(f"-------------*100-------------")

# Page-number check (D13): the last page of the PDF is page 6
last = store.similarity_search("webhook signature events", k=1)[0]
print("\nWebhooks chunk page (expect 6):", last.metadata["page"])
