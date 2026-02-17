import logging
import os

from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode

from functools import partial

from src.agents.secops_guardian import secops_guardian_node, finalize_secops_review_node
from src.agents.solution_architect import solution_architect_node, finalize_architecture_node
from src.agents.iac_debugger import iac_debugger_node, finalize_debugger_node
from src.states.graph_state import AgentState
from src.tools.mcp_tools import get_secops_guardian_tools, get_solution_architect_tools, get_iac_debugger_tools

from src.nodes.nodes import (
    apply_to_workspace_node,
    terraform_init_node,
    terraform_plan_node,
    human_approval_node,
    terraform_apply_node,
)

logger = logging.getLogger(__name__)

MAX_REVIEW_ITERATIONS = int(os.getenv("MAX_REVIEW_ITERATIONS", "5"))
MAX_DEBUGGER_ATTEMPTS = int(os.getenv("MAX_DEBUGGER_ATTEMPTS", "5"))
MAX_DEBUGGER_TOOL_ROUNDS = int(os.getenv("MAX_DEBUGGER_TOOL_ROUNDS", "3"))


def _route_by_tool(state, mapping, default=END):
    """Router that branches by the first tool call name in the last message.
    mapping: dict tool_name -> node_name. If tool_name is in mapping, return that node; else return default.
    """
    messages = state.get("messages", [])
    if not messages:
        return END
    last_message = messages[-1]
    if not hasattr(last_message, "tool_calls") or not last_message.tool_calls:
        logger.debug("No tool calls - ending turn")
        return END
    tool_name = last_message.tool_calls[0]["name"]
    logger.debug(f"Tool call detected: {tool_name}")
    next_node = mapping.get(tool_name, default)
    logger.debug(f"Next node: {next_node}")
    return next_node


def __architect_router(state):
    """Router that decides the next node after solution_architect."""
    return _route_by_tool(
        state,
        mapping={"TerraformDesign": "finalize_architecture"},
        default="architect_tools",
    )


def __secops_router(state):
    """Router that decides the next node after secops_guardian."""
    return _route_by_tool(
        state,
        mapping={"SecurityReview": "finalize_secops_review"},
        default="secops_tools",
    )


def __after_init_router(state):
    """Router after terraform init: if OK → terraform_plan; if failed and under max debugger attempts → iac_debugger; else → solution_architect."""
    if state.get("init_success", True):
        logger.debug("Terraform init OK. Proceeding to terraform_plan.")
        return "terraform_plan"
    attempts = state.get("debugger_init_attempts", 0)
    if attempts >= MAX_DEBUGGER_ATTEMPTS:
        logger.warning("Terraform init failed; max debugger attempts reached. Returning to solution_architect.")
        return "solution_architect"
    logger.warning("Terraform init failed. Proceeding to iac_debugger.")
    return "iac_debugger"


def __after_security_review_router(state):
    """Router after processing SecurityReview. Shift-Left: only after SecOps approval we touch Terraform binary."""
    if state.get("is_approved"):
        logger.debug("Security approved. Proceeding to terraform init (first use of Terraform binary).")
        return "terraform_init"
    
    iterations = state.get("review_iterations", 0)
    if iterations >= MAX_REVIEW_ITERATIONS:
        logger.warning(f"Max review iterations ({iterations}) reached. Proceeding to terraform init.")
        return "terraform_init"
    
    logger.warning(f"Security rejected (iteration {iterations}/{MAX_REVIEW_ITERATIONS}). Returning to architect.")
    return "solution_architect"


def __after_plan_router(state):
    """Router after terraform plan: if OK → human_approval; if failed and under max debugger attempts → iac_debugger; else → solution_architect."""
    if state.get("plan_success", True):
        logger.debug("Terraform plan OK. Proceeding to human_approval.")
        return "human_approval"
    attempts = state.get("debugger_plan_attempts", 0)
    if attempts >= MAX_DEBUGGER_ATTEMPTS:
        logger.warning("Terraform plan failed; max debugger attempts reached. Returning to solution_architect.")
        return "solution_architect"
    logger.warning("Terraform plan failed. Proceeding to iac_debugger.")
    return "iac_debugger"


def __after_apply_router(state):
    """Router after terraform apply: if OK → END; if failed and under max debugger attempts → iac_debugger; else → solution_architect."""
    if state.get("apply_success", True):
        logger.debug("Terraform apply OK. Ending flow.")
        return END
    attempts = state.get("debugger_apply_attempts", 0)
    if attempts >= MAX_DEBUGGER_ATTEMPTS:
        logger.warning("Terraform apply failed; max debugger attempts reached. Returning to solution_architect.")
        return "solution_architect"
    logger.warning("Terraform apply failed. Proceeding to iac_debugger.")
    return "iac_debugger"


def __debugger_router(state):
    """Router after iac_debugger: TerraformFix → finalize_debugger; other tool → debugger_tools (max rounds)."""
    tool_name = None
    messages = state.get("messages", [])
    if messages and hasattr(messages[-1], "tool_calls") and messages[-1].tool_calls:
        tool_name = messages[-1].tool_calls[0]["name"]
    if tool_name == "TerraformFix":
        return "finalize_debugger"
    rounds = state.get("debugger_tool_rounds", 0)
    if rounds >= MAX_DEBUGGER_TOOL_ROUNDS:
        logger.warning("Max debugger tool rounds (%s) reached. Returning to solution_architect.", MAX_DEBUGGER_TOOL_ROUNDS)
        return "solution_architect"
    return "debugger_tools"


def __after_apply_to_workspace_router(state):
    """Router after apply_to_workspace: if from_debugger → terraform_init (re-run pipeline); else → secops_guardian."""
    if state.get("from_debugger"):
        logger.debug("Coming from debugger fix. Re-running terraform init → plan → apply.")
        return "terraform_init"
    logger.debug("New design written. Proceeding to SecOps guardian.")
    return "secops_guardian"


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
    debugger_tools = await get_iac_debugger_tools()
    architect_tool_node = ToolNode(architect_tools)
    secops_tool_node = ToolNode(secops_tools)
    debugger_tool_node = ToolNode(debugger_tools)
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
    builder.add_node("iac_debugger", partial(iac_debugger_node, tools=debugger_tools))

    async def debugger_tools_with_rounds(state):
        result = await debugger_tool_node.ainvoke(state)
        return {**result, "debugger_tool_rounds": state.get("debugger_tool_rounds", 0) + 1}

    builder.add_node("debugger_tools", debugger_tools_with_rounds)
    builder.add_node("finalize_debugger", finalize_debugger_node)

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
    # After writing: from debugger fix → re-run init/plan/apply; from new design → SecOps
    builder.add_conditional_edges(
        "apply_to_workspace",
        __after_apply_to_workspace_router,
        {
            "terraform_init": "terraform_init",
            "secops_guardian": "secops_guardian",
        }
    )

    builder.add_conditional_edges(
        "terraform_init",
        __after_init_router,
        {
            "terraform_plan": "terraform_plan",
            "solution_architect": "solution_architect",
            "iac_debugger": "iac_debugger",
        }
    )

    builder.add_conditional_edges(
        "secops_guardian",
        __secops_router,
        {
            "secops_tools": "secops_tools",
            "finalize_secops_review": "finalize_secops_review",
            END: END
        }
    )
    
    builder.add_edge("secops_tools", "secops_guardian")
    
    builder.add_conditional_edges(
        "finalize_secops_review",
        __after_security_review_router,
        {
            "terraform_init": "terraform_init",
            "solution_architect": "solution_architect",
        }
    )
    builder.add_conditional_edges(
        "terraform_plan",
        __after_plan_router,
        {
            "human_approval": "human_approval",
            "iac_debugger": "iac_debugger",
            "solution_architect": "solution_architect",
        }
    )
    builder.add_conditional_edges(
        "human_approval",
        __after_human_approval_router,
        {
            "terraform_apply": "terraform_apply",
            "solution_architect": "solution_architect",
            END: END,
        }
    )
    builder.add_conditional_edges(
        "terraform_apply",
        __after_apply_router,
        {
            END: END,
            "iac_debugger": "iac_debugger",
            "solution_architect": "solution_architect",
        }
    )
    builder.add_conditional_edges(
        "iac_debugger",
        __debugger_router,
        {
            "finalize_debugger": "finalize_debugger",
            "debugger_tools": "debugger_tools",
            "solution_architect": "solution_architect",
            END: END,
        }
    )
    builder.add_edge("debugger_tools", "iac_debugger")
    builder.add_edge("finalize_debugger", "apply_to_workspace")

    return builder.compile(checkpointer=checkpointer)