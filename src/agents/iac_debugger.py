import json
import logging
from typing import List, Any
from langchain_core.messages import AIMessage, SystemMessage, ToolMessage, HumanMessage

from src.config import get_model
from src.tools.custom_tools import load_terraform_code_from_workspace
from src.prompts.debugger import IAC_DEBUGGER_SYSTEM_PROMPT
from src.schemas.debugger_schemas import TerraformFix
from src.states.graph_state import AgentState

logger = logging.getLogger(__name__)


def _debugger_phase_and_counter_updates(state: AgentState):
    """Determine which phase failed and return the counter key + increment value for state update."""
    if state.get("init_success") is False:
        key = "debugger_init_attempts"
    elif state.get("plan_success") is False:
        key = "debugger_plan_attempts"
    else:
        key = "debugger_apply_attempts"
    current = state.get(key, 0)
    return key, current + 1


def _build_error_context(state: AgentState) -> str:
    """Build the error message to show the debugger based on which step failed."""
    if state.get("init_success") is False:
        errors = state.get("workspace_errors") or []
        return "terraform init/validate failed:\n\n" + "\n".join(errors)
    if state.get("plan_success") is False:
        return "terraform plan failed:\n\n" + (state.get("plan_output") or "")
    if state.get("apply_success") is False:
        return "terraform apply failed:\n\n" + (state.get("apply_output") or "")
    return "Terraform error (unknown phase)."


async def iac_debugger_node(state: AgentState, tools: List[Any]):
    logger.debug("--- IAC DEBUGGER: FIXING TERRAFORM ---")
    tf_code = state.get("terraform_code") or {}
    error_context = _build_error_context(state)
    counter_key, counter_value = _debugger_phase_and_counter_updates(state)

    code_block = "\n\n---\n\n".join(
        f"### {fn}\n```hcl\n{content}\n```" for fn, content in tf_code.items()
    ) or "(no terraform_code in state)"
    user_content = (
        f"Current Terraform code (from state):\n\n{code_block}\n\n"
        f"Error to fix:\n\n{error_context}\n\n"
        "Correct the code and call TerraformFix with the fixed hcl_code."
    )

    messages = [
        SystemMessage(content=IAC_DEBUGGER_SYSTEM_PROMPT),
        HumanMessage(content=user_content),
    ]
    llm_with_tools = get_model().bind_tools(
        tools + [TerraformFix],
        tool_choice="auto",
    )
    response = await llm_with_tools.ainvoke(messages)

    if response.tool_calls:
        logger.debug(f"Debugger selected {len(response.tool_calls)} tool(s)")
        for tool in response.tool_calls:
            logger.debug(f"Tool Request: {tool['name']} | Args: {json.dumps(tool.get('args', {}))}")
    else:
        logger.debug("Debugger generated direct response")

    return {"messages": [response], **{counter_key: counter_value}}


def finalize_debugger_node(state: AgentState):
    logger.debug("--- FINALIZING DEBUGGER FIX ---")
    messages = state.get("messages", [])
    if not messages:
        logger.error("No messages in state")
        return {"messages": [AIMessage(content="Error: No messages in state.")]}
    last_message = messages[-1]
    if not hasattr(last_message, "tool_calls") or not last_message.tool_calls:
        logger.error("No tool_calls found in last message")
        return {"messages": [AIMessage(content="Error: No tool_calls found in last message.")]}
    tool_call = last_message.tool_calls[0]
    tool_call_id = tool_call.get("id")
    if not tool_call_id:
        logger.error("No tool_call_id in tool_call")
        return {"messages": [AIMessage(content="Error: No tool_call_id in tool_call.")]}
    args = tool_call.get("args", {})
    hcl_code = args.get("hcl_code", {})
    if not hcl_code:
        hcl_code = load_terraform_code_from_workspace()
    changes_summary = args.get("changes_summary", "")
    created = list(hcl_code.keys()) if hcl_code else []
    logger.info(f"Debugger fix - Files: {created}")
    content = f"Terraform fix applied. Files: {', '.join(created)}." + (
        f" Summary: {changes_summary}" if changes_summary else ""
    )
    tool_message = ToolMessage(
        content=content,
        tool_call_id=tool_call_id,
        name="TerraformFix",
    )
    return {
        "terraform_code": hcl_code,
        "workspace_errors": [],
        "messages": [tool_message],
        "from_debugger": True,
    }
