from typing import TypedDict, Annotated, Sequence
from langgraph.graph import add_messages, StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from models import Prospect
from agent.veille_models import Hackathon, Evenement
from agent.subventions_models import Subvention
from agent.nodes import (
    find_prospects_csv,
    find_prospects_api,
    find_prospects_web,
    classify_prospects,
    clean_prospects,
    qualify_prospects,
)
from agent.veille_nodes import (
    generate_queries,
    search_tavily,
    search_duckduckgo,
    extract_and_store,
    decide_next_veille,
)
from agent.subventions_nodes import (
    generate_queries_subventions,
    search_tavily_subventions,
    search_duckduckgo_subventions,
    extract_subventions,
    decide_next_subventions,
)


class UnifiedState(TypedDict):
    task: str
    messages: Annotated[Sequence[dict], add_messages]
    store: dict

    # Prospection
    prospects: list[Prospect]
    current_index: int
    total_count: int
    pays: str
    statut: str
    limit: int
    mode: str

    # Veille
    hackathons: list[Hackathon]
    evenements: list[Evenement]
    queries_executees: list[str]
    iteration: int
    max_iterations: int

    # Subventions
    subventions: list[Subvention]
    subventions_iteration: int
    subventions_max_iterations: int


def router_node(state: UnifiedState) -> dict:
    task = state.get("task", "prospection")
    print(f"\n{'=' * 60}")
    print(f"  AGENT UNIFIE - Mode: {task.upper()}")
    print(f"{'=' * 60}")
    return {}


def route_decision(state: UnifiedState) -> str:
    return state.get("task", "prospection")


def build_unified_agent() -> StateGraph:
    workflow = StateGraph(UnifiedState)

    workflow.add_node("router", router_node)

    workflow.add_node("find_prospects_csv", find_prospects_csv)
    workflow.add_node("find_prospects_api", find_prospects_api)
    workflow.add_node("find_prospects_web", find_prospects_web)
    workflow.add_node("classify_prospects", classify_prospects)
    workflow.add_node("clean_prospects", clean_prospects)
    workflow.add_node("qualify_prospects", qualify_prospects)

    workflow.add_node("generate_queries", generate_queries)
    workflow.add_node("search_tavily", search_tavily)
    workflow.add_node("search_duckduckgo", search_duckduckgo)
    workflow.add_node("extract_and_store", extract_and_store)

    workflow.add_node("generate_queries_subventions", generate_queries_subventions)
    workflow.add_node("search_tavily_subventions", search_tavily_subventions)
    workflow.add_node("search_duckduckgo_subventions", search_duckduckgo_subventions)
    workflow.add_node("extract_subventions", extract_subventions)
    workflow.add_node("decide_next_subventions", decide_next_subventions)

    workflow.set_entry_point("router")

    workflow.add_conditional_edges(
        "router",
        route_decision,
        {
            "prospection": "find_prospects_csv",
            "veille": "generate_queries",
            "subventions": "generate_queries_subventions",
        },
    )

    workflow.add_edge("find_prospects_csv", "find_prospects_api")
    workflow.add_edge("find_prospects_api", "find_prospects_web")
    workflow.add_edge("find_prospects_web", "classify_prospects")
    workflow.add_edge("classify_prospects", "clean_prospects")
    workflow.add_edge("clean_prospects", "qualify_prospects")
    workflow.add_edge("qualify_prospects", END)

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

    workflow.add_edge("generate_queries_subventions", "search_tavily_subventions")
    workflow.add_edge("search_tavily_subventions", "search_duckduckgo_subventions")
    workflow.add_edge("search_duckduckgo_subventions", "extract_subventions")
    workflow.add_conditional_edges(
        "extract_subventions",
        decide_next_subventions,
        {
            "continue": "generate_queries_subventions",
            "end": END,
        },
    )

    memory = MemorySaver()
    return workflow.compile(checkpointer=memory)


agent = build_unified_agent()
