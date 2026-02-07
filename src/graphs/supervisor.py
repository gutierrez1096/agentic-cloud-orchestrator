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
    terraform_plan_node,
    human_approval_node,
    terraform_apply_node,
)

logger = logging.getLogger(__name__)

MAX_REVIEW_ITERATIONS = 3


def __architect_router(state):
    """Router that decides the next node after solution_architect."""
    messages = state.get("messages", [])

    if not messages:
        return END
    
    last_message = messages[-1]
    
    if not hasattr(last_message, "tool_calls") or not last_message.tool_calls:
        logger.warning("No tool calls - returning to finalize_architecture")
        return "finalize_architecture"
        
    tool_name = last_message.tool_calls[0]["name"]
    logger.debug(f"Tool call detected: {tool_name}")
    
    if tool_name == "TerraformDesign":
        logger.debug("Next node: finalize_architecture")
        return "finalize_architecture"
    else:
        logger.debug("Next node: architect_tools")
        return "architect_tools"


def __secops_router(state):
    """Router that decides the next node after secops_guardian."""
    messages = state.get("messages", [])

    if not messages:
        logger.error("No messages found in SecOps router")
        return END

    last_message = messages[-1]

    if not hasattr(last_message, "tool_calls") or not last_message.tool_calls:
        logger.warning("No tool calls in SecOps - returning to finalize_secops_review")
        return "finalize_secops_review"

    tool_name = last_message.tool_calls[0]["name"]
    logger.debug(f"SecOps tool call detected: {tool_name}")

    if tool_name == "SecurityReview":
        logger.debug("Next node: finalize_secops_review")
        return "finalize_secops_review"
    else:
        logger.debug("Next node: secops_tools")
        return "secops_tools"


def __after_init_router(state):
    """Router after terraform init: if OK → secops, if failed → solution_architect to fix."""
    if state.get("init_success", True):
        logger.debug("Terraform init OK. Proceeding to secops_guardian.")
        return "secops_guardian"
    logger.warning("Terraform init failed. Returning to solution_architect to fix.")
    return "solution_architect"


def __after_security_review_router(state):
    """Router after processing SecurityReview."""
    if state.get("is_approved"):
        logger.debug("Security approved. Proceeding to terraform plan.")
        return "terraform_plan"
    
    iterations = state.get("review_iterations", 0)
    if iterations >= MAX_REVIEW_ITERATIONS:
        logger.warning(f"Max review iterations ({iterations}) reached. Proceeding to terraform plan.")
        return "terraform_plan"
    
    logger.warning(f"Security rejected (iteration {iterations}/{MAX_REVIEW_ITERATIONS}). Returning to architect.")
    return "solution_architect"


def __after_human_approval_router(state):
    """Router after human_approval: approve → terraform_apply, revise → architect, reject → END."""
    decision = state.get("human_decision", "reject")
    if decision == "approve":
        logger.debug("Human approved. Proceeding to terraform apply.")
        return "terraform_apply"
    if decision == "revise":
        logger.debug("Human requested changes. Returning to solution_architect.")
        return "solution_architect"
    logger.warning("Human rejected. Ending flow.")
    return END


async def create_supervisor_graph(checkpointer=None):
    logger.debug("Creating supervisor graph...")

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
    builder.add_node("human_approval", human_approval_node)
    builder.add_node("terraform_apply", terraform_apply_node)

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
    builder.add_edge("terraform_plan", "human_approval")
    builder.add_conditional_edges(
        "human_approval",
        __after_human_approval_router,
        {
            "terraform_apply": "terraform_apply",
            "solution_architect": "solution_architect",
            END: END,
        }
    )
    builder.add_edge("terraform_apply", END)

    return builder.compile(checkpointer=checkpointer)