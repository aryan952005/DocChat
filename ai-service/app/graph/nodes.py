from typing import Literal
from pydantic import BaseModel
from langchain_core.messages import AIMessage

from app.config import llm, TOP_K
from app.ingest import get_vector_store
from app.prompts import (
    GENERATE_PROMPT, ROUTER_PROMPT, DIRECT_PROMPT,
    REWRITE_PROMPT, RETRY_RULE, GRADE_PROMPT, NOT_FOUND_TEXT,
)


class RouteDecision(BaseModel):
    route: Literal["docs", "direct"]


class Grade(BaseModel):
    relevant_ids: list[int]  # numbers (1..k) of the chunks that help answer


def format_history(state):
    # Last 6 messages before the current question (the question is passed separately).
    # Keeping only 6 keeps tokens per call roughly constant however long the chat is.
    prior = state["messages"][:-1][-6:]
    if not prior:
        return "(none)"
    return "\n".join(f"{'User' if m.type == 'human' else 'Assistant'}: {m.content}" for m in prior)


def router(state):
    # Structured output: Gemini must return a RouteDecision, never free text
    decision = llm.with_structured_output(RouteDecision).invoke(
        ROUTER_PROMPT.format(question=state["question"])
    )
    # Reset per-turn fields so last turn's values cannot leak in (D7).
    # The HumanMessage is already in the input, so it is not appended here (D8).
    return {
        "route": decision.route,
        "search_query": "",
        "failed_queries": [],
        "documents": [],
        "relevant_docs": [],
        "retry_count": 0,
        "answer": "",
        "sources": [],
    }


def direct_answer(state):
    prompt = DIRECT_PROMPT.format(history=format_history(state), question=state["question"])
    answer = llm.invoke(prompt).text
    return {"answer": answer, "sources": [], "messages": [AIMessage(content=answer)]}


def rewrite_query(state):
    # Always built from the ORIGINAL question, never the previous search_query (D2)
    failed = state.get("failed_queries", [])
    retry_rule = RETRY_RULE.format(failed=failed) if failed else ""
    prompt = REWRITE_PROMPT.format(
        retry_rule=retry_rule, history=format_history(state), question=state["question"]
    )
    return {"search_query": llm.invoke(prompt).text.strip()}


def retrieve(state):
    # Top-k similarity search: the k chunks whose vectors are closest to the query vector
    query = state.get("search_query") or state["question"]
    docs = get_vector_store().similarity_search(query, k=TOP_K)
    return {"documents": docs}


def format_context(docs):
    # Number each chunk and label it with file and page so the answer can cite it
    return "\n\n".join(
        f"[{i}] ({d.metadata['filename']}, page {d.metadata['page']})\n{d.page_content}"
        for i, d in enumerate(docs, 1)
    )


def grade_documents(state):
    # LLM-as-judge: one batched call reads the question + all chunks together
    docs = state["documents"]
    prompt = GRADE_PROMPT.format(
        history=format_history(state), question=state["question"], chunks=format_context(docs)
    )
    grade = llm.with_structured_output(Grade).invoke(prompt)
    ids = {i for i in grade.relevant_ids if 1 <= i <= len(docs)}  # ignore invalid IDs
    return {"relevant_docs": [d for i, d in enumerate(docs, 1) if i in ids]}


def prepare_retry(state):
    # One clear place for the loop bookkeeping (D6)
    return {
        "failed_queries": state["failed_queries"] + [state["search_query"]],
        "retry_count": state["retry_count"] + 1,
    }


def not_found(state):
    return {"answer": NOT_FOUND_TEXT, "sources": [], "messages": [AIMessage(content=NOT_FOUND_TEXT)]}


def generate(state):
    docs = state["relevant_docs"]  # only chunks that passed grading
    prompt = GENERATE_PROMPT.format(
        context=format_context(docs), history=format_history(state), question=state["question"]
    )
    answer = llm.invoke(prompt).text

    # De-duplicate sources, keeping order
    sources = []
    for d in docs:
        s = {"filename": d.metadata["filename"], "page": d.metadata["page"]}
        if s not in sources:
            sources.append(s)

    return {"answer": answer, "sources": sources, "messages": [AIMessage(content=answer)]}
