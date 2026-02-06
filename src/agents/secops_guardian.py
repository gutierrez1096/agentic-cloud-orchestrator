import json
import logging
from typing import List, Any
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage

from src.config import get_model
from src.prompts.secops import SECOPS_SYSTEM_PROMPT
from src.schemas.secops_schemas import SecurityReview
from src.states.graph_state import AgentState

logger = logging.getLogger(__name__)

async def secops_guardian_node(state: AgentState, tools: List[Any]):
    logger.info("--- SECOPS GUARDIAN: AUDITING CODE ---")
    
    tf_code = state.get("terraform_code", {})
    
    if not tf_code:
        return {"messages": [], "security_errors": ["No terraform code found to audit"]}
        
    llm_with_tools = get_model().bind_tools(tools + [SecurityReview])
    
    
    user_request = next(
        (m.content for m in state["messages"] if isinstance(m, HumanMessage)),
        "No user request found"
    )
    
    tf_code_formatted = "\n\n".join(
        f"#### {filename}\n```hcl\n{content}\n```" for filename, content in tf_code.items()
    )
    
    messages = state["messages"]
    system_msg = SystemMessage(content=SECOPS_SYSTEM_PROMPT.format(
        user_request=user_request,
        terraform_code=tf_code_formatted
    ))
    if not isinstance(messages[0], SystemMessage):
        messages = [system_msg] + messages
    
    response = await llm_with_tools.ainvoke(messages)
    
    if response.tool_calls:
        logger.info(f"SecOps selected {len(response.tool_calls)} tool(s)")
        for tool in response.tool_calls:
            logger.info(f"Tool Request: {tool['name']} | Arguments: {json.dumps(tool['args'])}")
    else:
        logger.info("SecOps generated direct response")
    
    return {"messages": [response]}

def finalize_secops_review_node(state: AgentState):
    logger.info("--- FINALIZING SECOPS REVIEW ---")
    messages = state.get("messages", [])
    
    last_message = messages[-1]
    
    if not hasattr(last_message, "tool_calls") or not last_message.tool_calls:
        logger.error("No tool_calls found in last message")
        return {"messages": [], "security_errors": ["No tool_calls found in last message"]}
    
    tool_call = last_message.tool_calls[0]
    tool_call_id = tool_call.get("id")
    
    if not tool_call_id:
        logger.error("No tool_call_id found in tool_call")
        return {"messages": [], "security_errors": ["No tool_call_id found in tool_call"]}
    
    args = tool_call.get("args", {})
    
    verdict = args.get("verdict", "approved")
    risk_analysis = args.get("risk_analysis", "")
    required_changes = args.get("required_changes", [])
    
    logger.info(f"Security Review Verdict: {verdict}")
    
    if verdict == "approved" or verdict == "approved_with_warnings":
        output_message = f"Security Review {verdict}. {risk_analysis}"
    else:
        output_message = f"Security Review REJECTED. {risk_analysis}. Required changes: {required_changes}"
    
    tool_message = ToolMessage(
        content=output_message,
        tool_call_id=tool_call_id,
        name="SecurityReview"
    )
    
    current_iterations = state.get("review_iterations", 0)
    
    return {
        "verdict": verdict,
        "messages": [tool_message],
        "security_errors": required_changes if verdict == "rejected" else [],
        "review_iterations": current_iterations + 1
    }