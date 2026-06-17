from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from agent.veille_nodes import (
    VeilleState,
    generate_queries,
    search_tavily,
    llm_generate,
    extract_and_store,
    decide_next,
)


def build_veille_agent(max_iterations: int = 5) -> StateGraph:
    workflow = StateGraph(VeilleState)

    workflow.add_node("generate_queries", generate_queries)
    workflow.add_node("search_tavily", search_tavily)
    workflow.add_node("llm_generate", llm_generate)
    workflow.add_node("extract_and_store", extract_and_store)

    workflow.set_entry_point("generate_queries")

    workflow.add_edge("generate_queries", "search_tavily")
    workflow.add_edge("search_tavily", "llm_generate")
    workflow.add_edge("llm_generate", "extract_and_store")

    workflow.add_conditional_edges(
        "extract_and_store",
        decide_next,
        {
            "continue": "generate_queries",
            "end": END,
        },
    )

    memory = MemorySaver()
    return workflow.compile(checkpointer=memory)


agent = build_veille_agent()
