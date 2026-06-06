from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from agent.nodes import AgentState, find_prospects, should_continue


def build_agent() -> StateGraph:
    workflow = StateGraph(AgentState)

    workflow.add_node("find_prospects", find_prospects)

    workflow.set_entry_point("find_prospects")
    workflow.add_edge("find_prospects", END)

    memory = MemorySaver()
    return workflow.compile(checkpointer=memory)


agent = build_agent()
