from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from agent.nodes import (
    AgentState,
    find_prospects_csv,
    find_prospects_api,
    find_prospects_web,
    classify_prospects,
    clean_prospects,
    qualify_prospects,
    decide_next,
)


def build_agent() -> StateGraph:
    workflow = StateGraph(AgentState)

    workflow.add_node("find_prospects_csv", find_prospects_csv)
    workflow.add_node("find_prospects_api", find_prospects_api)
    workflow.add_node("find_prospects_web", find_prospects_web)
    workflow.add_node("classify_prospects", classify_prospects)
    workflow.add_node("clean_prospects", clean_prospects)
    workflow.add_node("qualify_prospects", qualify_prospects)

    workflow.set_entry_point("find_prospects_csv")

    workflow.add_edge("find_prospects_csv", "find_prospects_api")
    workflow.add_edge("find_prospects_api", "find_prospects_web")
    workflow.add_edge("find_prospects_web", "classify_prospects")
    workflow.add_edge("classify_prospects", "clean_prospects")
    workflow.add_edge("clean_prospects", "qualify_prospects")
    workflow.add_edge("qualify_prospects", END)

    memory = MemorySaver()
    return workflow.compile(checkpointer=memory)


agent = build_agent()
