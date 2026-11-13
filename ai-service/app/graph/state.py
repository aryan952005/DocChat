from typing import Annotated, TypedDict
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    # add_messages appends new messages instead of replacing the list (chat history)
    messages: Annotated[list, add_messages]
    question: str          # the user's original words
    route: str             # "docs" or "direct" (Phase 4)
    search_query: str      # used only by retrieve (Phase 5)
    failed_queries: list[str]  # queries whose results all failed grading (Phase 5)
    documents: list        # chunks returned by Qdrant
    relevant_docs: list    # chunks that passed grading (Phase 5)
    retry_count: int       # retries done this turn (Phase 5)
    answer: str            # final reply
    sources: list          # [{filename, page}], de-duplicated
