from pymongo import MongoClient
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.mongodb import MongoDBSaver

from app.config import MAX_RETRIES, MONGO_URI, MONGO_DB
from app.graph.state import AgentState
from app.graph.nodes import (
    router, direct_answer, rewrite_query, retrieve,
    grade_documents, prepare_retry, generate, not_found,
)


def route_after_router(state):
    return "rewrite_query" if state["route"] == "docs" else "direct_answer"


def route_after_grading(state):
    if state["relevant_docs"]:
        return "generate"
    # The counter is what stops the cycle
    if state["retry_count"] < MAX_RETRIES:
        return "prepare_retry"
    return "not_found"


def build_graph():
    g = StateGraph(AgentState)
    for name, fn in [
        ("router", router), ("direct_answer", direct_answer),
        ("rewrite_query", rewrite_query), ("retrieve", retrieve),
        ("grade_documents", grade_documents), ("prepare_retry", prepare_retry),
        ("generate", generate), ("not_found", not_found),
    ]:
        g.add_node(name, fn)

    g.add_edge(START, "router")
    g.add_conditional_edges("router", route_after_router, ["rewrite_query", "direct_answer"])
    g.add_edge("rewrite_query", "retrieve")
    g.add_edge("retrieve", "grade_documents")
    g.add_conditional_edges(
        "grade_documents", route_after_grading, ["generate", "prepare_retry", "not_found"]
    )
    g.add_edge("prepare_retry", "rewrite_query")  # the retry loop
    g.add_edge("generate", END)
    g.add_edge("not_found", END)
    g.add_edge("direct_answer", END)
    # Checkpointer saves the whole state to MongoDB after every node, keyed by thread_id.
    # Same thread_id next turn -> the saved messages are loaded back (conversation memory).
    checkpointer = MongoDBSaver(MongoClient(MONGO_URI), db_name=MONGO_DB)
    return g.compile(checkpointer=checkpointer)
