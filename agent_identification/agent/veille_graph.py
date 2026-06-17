from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from agent.veille_nodes import (
    VeilleState,
    generate_queries,
    search_tavily,
    search_duckduckgo,
    extract_and_store,
    decide_next_veille,
)


def build_veille_agent(max_iterations: int = 5) -> StateGraph:
    workflow = StateGraph(VeilleState)

    workflow.add_node("generate_queries", generate_queries)
    workflow.add_node("search_tavily", search_tavily)
    workflow.add_node("search_duckduckgo", search_duckduckgo)
    workflow.add_node("extract_and_store", extract_and_store)

    workflow.set_entry_point("generate_queries")

    # Sequential: Tavily then DuckDuckGo (avoids LangGraph parallel state conflict)
    workflow.add_edge("generate_queries", "search_tavily")
    workflow.add_edge("search_tavily", "search_duckduckgo")
    workflow.add_edge("search_duckduckgo", "extract_and_store")

    workflow.add_conditional_edges(
        "extract_and_store",
        decide_next_veille,
        {
            "continue": "generate_queries",
            "end": END,
        },
    )

    memory = MemorySaver()
    return workflow.compile(checkpointer=memory)


agent = build_veille_agent()
