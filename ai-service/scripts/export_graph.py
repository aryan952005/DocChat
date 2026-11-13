# Prints the LangGraph as Mermaid text (paste into the README)
from app.graph.build_graph import build_graph

print(build_graph().get_graph().draw_mermaid())
