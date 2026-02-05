import logging

from src.states.graph_state import AgentState
from langchain_core.messages import ToolMessage

logger = logging.getLogger(__name__)

def finalize_architecture_node(state: AgentState):
    logger.info("--- FINALIZING ARCHITECTURE ---")
    messages = state.get("messages", [])
    
    if not messages:
        logger.error("No messages found in state")
        return {"messages": [], "errors": ["No messages found in state"]}
    
    last_message = messages[-1]
    
    if not hasattr(last_message, "tool_calls") or not last_message.tool_calls:
        logger.error("No tool_calls found in last message")
        return {"messages": [], "errors": ["No tool_calls found in last message"]}
    
    tool_call = last_message.tool_calls[0]
    tool_call_id = tool_call.get("id")
    
    if not tool_call_id:
        logger.error("No tool_call_id found in tool_call")
        return {"messages": [], "errors": ["No tool_call_id found in tool_call"]}
    
    design_args = tool_call.get("args", {})
    hcl_code = design_args.get("hcl_code", {})
    rationale = design_args.get("rationale", "")
    
    if not hcl_code:
        logger.warning("No hcl_code provided in TerraformDesign arguments")
    
    created_files = list(hcl_code.keys()) if hcl_code else []
    
    logger.info(f"Arguments extracted - Files: {created_files}")

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
        "next_step": "SecOps Guardian",
        "messages": [tool_message]
    }
