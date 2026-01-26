from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver

from src.states.graph_state import AgentState
from src.agents.cloud_architect import cloud_architect_node
from src.agents.devops import devops_node
import asyncio

# 1. Definición de la lógica de enrutamiento (SOTA)
def should_continue(state: AgentState):
    messages = state["messages"]
    last_message = messages[-1]

    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "continue"
    return "exit"

async def create_supervisor_graph(checkpointer=None):
    """
    Factory function asíncrona para inicializar el grafo con sus herramientas MCP.
    """
    if checkpointer is None:
        checkpointer = MemorySaver()

    builder = StateGraph(AgentState)
    builder.add_node("cloud_architect", cloud_architect_node)
    builder.add_node("devops", devops_node)

    builder.set_entry_point("cloud_architect")

    builder.add_edge("cloud_architect")
    builder.add_edge("devops")

    return builder.compile(checkpointer=checkpointer)