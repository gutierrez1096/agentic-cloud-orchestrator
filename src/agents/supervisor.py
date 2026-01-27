import logging

from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode

from src.agents.secops_guardian import secops_guardian_node
from src.agents.solution_architect import solution_architect_node
from src.states.graph_state import AgentState
from src.tools.mcp_tools import get_secops_guardian_tools, get_solution_architect_tools
from src.nodes.nodes import (
    finalize_architecture_node, 
    apply_to_workspace_node,
    terraform_init_node,
    terraform_plan_node
)

logger = logging.getLogger(__name__)


def __architect_router(state):
    """Router que decide el siguiente nodo después de solution_architect."""
    messages = state["messages"]
    last_message = messages[-1]
    
    if not last_message.tool_calls:
        return END
        
    tool_name = last_message.tool_calls[0]["name"]
    logger.info(f"Llamada a herramienta detectada: {tool_name}")
    
    if tool_name == "TerraformDesign":
        logger.info("Siguiente nodo: finalize_architecture")
        return "finalize_architecture"
    else:
        logger.info("Siguiente nodo: architect_tools")
        return "architect_tools"


def secops_router(state):
    """Router que decide el siguiente nodo después de secops_guardian."""
    if state.get("is_approved"):
        logger.info("SecOps APPROVED. Proceeding to Injection.")
        return "apply_to_workspace"
    else:
        logger.info("SecOps REJECTED. Returning to Architect.")
        return "solution_architect"


async def create_supervisor_graph(checkpointer=None):
    logger.info("Creando grafo del supervisor...")

    architect_tools = await get_solution_architect_tools()
    secops_tools = await get_secops_guardian_tools()
    architect_tool_node = ToolNode(architect_tools)
    secops_tool_node = ToolNode(secops_tools)
    builder = StateGraph(AgentState)
    
    builder.add_node("solution_architect", solution_architect_node)
    builder.add_node("architect_tools", architect_tool_node)
    builder.add_node("secops_tools", secops_tool_node)
    builder.add_node("finalize_architecture", finalize_architecture_node)
    builder.add_node("secops_guardian", secops_guardian_node)
    builder.add_node("apply_to_workspace", apply_to_workspace_node)
    builder.add_node("terraform_init", terraform_init_node)
    builder.add_node("terraform_plan", terraform_plan_node)

    builder.set_entry_point("solution_architect")

    builder.add_conditional_edges(
        "solution_architect",
        __architect_router,
        {
            "architect_tools": "architect_tools",
            "finalize_architecture": "finalize_architecture",
            END: END
        }
    )
    
    builder.add_edge("architect_tools", "solution_architect")
    builder.add_edge("finalize_architecture", "secops_guardian")

    builder.add_conditional_edges(
        "secops_guardian",
        secops_router,
        {
            "apply_to_workspace": "apply_to_workspace",
            "solution_architect": "solution_architect",
        }
    )

    builder.add_edge("apply_to_workspace", "terraform_init")
    builder.add_edge("terraform_init", "terraform_plan")
    builder.add_edge("terraform_plan", END)

    return builder.compile(checkpointer=checkpointer)