import logging

from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode

from functools import partial

from src.agents.secops_guardian import secops_guardian_node, finalize_secops_review_node
from src.agents.solution_architect import solution_architect_node, finalize_architecture_node
from src.states.graph_state import AgentState
from src.tools.mcp_tools import get_secops_guardian_tools, get_solution_architect_tools

from src.nodes.nodes import (
    apply_to_workspace_node,
    terraform_init_node,
    terraform_plan_node
)

logger = logging.getLogger(__name__)

MAX_REVIEW_ITERATIONS = 3


def __architect_router(state):
    """Router que decide el siguiente nodo después de solution_architect."""
    messages = state.get("messages", [])

    if not messages:
        return END
    
    last_message = messages[-1]
    
    if not hasattr(last_message, "tool_calls") or not last_message.tool_calls:
        logger.warning("No tool calls - respuesta directa del modelo")
        return END
        
    tool_name = last_message.tool_calls[0]["name"]
    logger.info(f"Llamada a herramienta detectada: {tool_name}")
    
    if tool_name == "TerraformDesign":
        logger.info("Siguiente nodo: finalize_architecture")
        return "finalize_architecture"
    else:
        logger.info("Siguiente nodo: architect_tools")
        return "architect_tools"


def __secops_router(state):
    """Router que decide el siguiente nodo después de secops_guardian."""
    messages = state.get("messages", [])

    if not messages:
        logger.error("No messages found in SecOps router")
        return END

    last_message = messages[-1]

    if not hasattr(last_message, "tool_calls") or not last_message.tool_calls:
        logger.warning("No tool calls en SecOps - volviendo a secops_guardian")
        return "secops_guardian"

    tool_name = last_message.tool_calls[0]["name"]
    logger.info(f"SecOps tool call detectado: {tool_name}")

    if tool_name == "SecurityReview":
        logger.info("Siguiente nodo: finalize_secops_review")
        return "finalize_secops_review"
    else:
        logger.info("Siguiente nodo: secops_tools")
        return "secops_tools"


def __after_init_router(state):
    """Router después de terraform init: si OK → secops, si falló → solution_architect para corregir."""
    if state.get("init_success", True):
        logger.info("Terraform init OK. Proceeding to secops_guardian.")
        return "secops_guardian"
    logger.warning("Terraform init failed. Returning to solution_architect to fix.")
    return "solution_architect"


def __after_security_review_router(state):
    """Router después de procesar SecurityReview."""
    if state.get("is_approved"):
        logger.info("Security approved. Proceeding to terraform plan.")
        return "terraform_plan"
    
    iterations = state.get("review_iterations", 0)
    if iterations >= MAX_REVIEW_ITERATIONS:
        logger.warning(f"Max review iterations ({iterations}) reached. Proceeding to terraform plan.")
        return "terraform_plan"
    
    logger.info(f"Security rejected (iteration {iterations}/{MAX_REVIEW_ITERATIONS}). Returning to architect.")
    return "solution_architect"


async def create_supervisor_graph(checkpointer=None):
    logger.info("Creando grafo del supervisor...")

    architect_tools = await get_solution_architect_tools()
    secops_tools = await get_secops_guardian_tools()
    architect_tool_node = ToolNode(architect_tools)
    secops_tool_node = ToolNode(secops_tools)
    builder = StateGraph(AgentState)

    builder.add_node("solution_architect", partial(solution_architect_node, tools=architect_tools))
    builder.add_node("architect_tools", architect_tool_node)
    builder.add_node("finalize_architecture", finalize_architecture_node)
    builder.add_node("secops_guardian", partial(secops_guardian_node, tools=secops_tools))
    builder.add_node("secops_tools", secops_tool_node)
    builder.add_node("finalize_secops_review", finalize_secops_review_node)
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
    builder.add_edge("finalize_architecture", "apply_to_workspace")
    builder.add_edge("apply_to_workspace", "terraform_init")

    builder.add_conditional_edges(
        "terraform_init",
        __after_init_router,
        {
            "secops_guardian": "secops_guardian",
            "solution_architect": "solution_architect",
        }
    )

    builder.add_conditional_edges(
        "secops_guardian",
        __secops_router,
        {
            "secops_tools": "secops_tools",
            "finalize_secops_review": "finalize_secops_review",
            "secops_guardian": "secops_guardian",
            END: END
        }
    )
    
    builder.add_edge("secops_tools", "secops_guardian")
    
    builder.add_conditional_edges(
        "finalize_secops_review",
        __after_security_review_router,
        {
            "terraform_plan": "terraform_plan",
            "solution_architect": "solution_architect",
        }
    )
    builder.add_edge("terraform_plan", END)

    return builder.compile(checkpointer=checkpointer)