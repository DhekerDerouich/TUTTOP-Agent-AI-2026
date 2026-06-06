from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from agent.nodes import (
    AgentState,
    find_prospects_csv,
    find_prospects_api,
    find_prospects_web,
)


def build_agent() -> StateGraph:
    workflow = StateGraph(AgentState)

    workflow.add_node("find_prospects_csv", find_prospects_csv)
    workflow.add_node("find_prospects_api", find_prospects_api)
    workflow.add_node("find_prospects_web", find_prospects_web)

    workflow.set_entry_point("find_prospects_csv")

    workflow.add_edge("find_prospects_csv", "find_prospects_api")
    workflow.add_edge("find_prospects_api", "find_prospects_web")
    workflow.add_edge("find_prospects_web", END)

    memory = MemorySaver()
    return workflow.compile(checkpointer=memory)


agent = build_agent()
