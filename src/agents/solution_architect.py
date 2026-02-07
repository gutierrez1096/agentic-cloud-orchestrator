import json
import logging
from typing import List, Any
from langchain_core.messages import AIMessage, SystemMessage, ToolMessage, HumanMessage

from src.config import get_model
from src.prompts.architect import ARCHITECT_SYSTEM_PROMPT
from src.schemas.architect_schemas import TerraformDesign
from src.states.graph_state import AgentState

logger = logging.getLogger(__name__)

async def solution_architect_node(state: AgentState, tools: List[Any]):
    logger.debug("--- SOLUTION ARCHITECT: THINKING ---")
    
    llm_with_tools = get_model().bind_tools(
        tools + [TerraformDesign],
        tool_choice="auto",
    )
    
    messages = list(state["messages"])

    if not isinstance(messages[0], SystemMessage):
        messages = [SystemMessage(content=ARCHITECT_SYSTEM_PROMPT)] + messages

    workspace_errors = state.get("workspace_errors") or []
    if workspace_errors:
        error_text = "\n".join(workspace_errors)
        messages.append(HumanMessage(
            content=f"Terraform init/validate failed with the following errors. Fix the Terraform design and call TerraformDesign again with the corrected HCL.\n\nErrors:\n{error_text}"
        ))
    
    response = await llm_with_tools.ainvoke(messages)

    if response.tool_calls:
        logger.debug(f"Model selected {len(response.tool_calls)} tool(s)")
        for tool in response.tool_calls:
            logger.debug(f"Tool Request: {tool['name']} | Arguments: {json.dumps(tool['args'])}")
    else:
        logger.debug("Model generated direct response")

    return {
        "messages": [response]
    }

def finalize_architecture_node(state: AgentState):
    logger.debug("--- FINALIZING ARCHITECTURE ---")
    messages = state.get("messages", [])

    last_message = messages[-1]
    
    if not hasattr(last_message, "tool_calls") or not last_message.tool_calls:
        logger.error("No tool_calls found in last message")
        return {"messages": [AIMessage(content="Error: No tool_calls found in last message.")]}

    tool_call = last_message.tool_calls[0]
    tool_call_id = tool_call.get("id")

    if not tool_call_id:
        logger.error("No tool_call_id found in tool_call")
        return {"messages": [AIMessage(content="Error: No tool_call_id found in tool_call.")]}
    
    design_args = tool_call.get("args", {})
    hcl_code = design_args.get("hcl_code", {})
    rationale = design_args.get("rationale", "")
    
    created_files = list(hcl_code.keys()) if hcl_code else []
    
    logger.debug(f"Arguments extracted - Files: {created_files}")

    output_message = f"Architecture design submitted successfully. Files to create: {', '.join(created_files)}. Writing to workspace before SecOps review."
    
    tool_message = ToolMessage(
        content=output_message,
        tool_call_id=tool_call_id,
        name="TerraformDesign"
    )

    return {
        "terraform_code": hcl_code,
        "architect_rationale": rationale,
        "created_files": created_files,
        "messages": [tool_message]
    }