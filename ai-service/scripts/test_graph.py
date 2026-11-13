import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))  # so "app" is importable

from langchain_core.messages import HumanMessage
from app.graph.build_graph import build_graph

graph = build_graph()

# Same thread id = same conversation memory (loaded from MongoDB)
thread_id = input("Thread id: ").strip()

while True:
    q = input("\nYou: ").strip()
    if q.lower() in ("exit", "quit", ""):
        break

    # Only the new turn goes in; earlier messages come from the checkpointer via thread_id
    result = graph.invoke(
        {"question": q, "messages": [HumanMessage(content=q)]},
        config={"configurable": {"thread_id": thread_id}},
    )
    print("Bot:", result["answer"])
