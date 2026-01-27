import logging

from langchain_core.messages import SystemMessage

from src.config import get_model
from src.prompts.secops import SECOPS_SYSTEM_PROMPT
from src.schemas.secops_schemas import SecurityReview
from src.states.graph_state import AgentState
from src.tools.mcp_tools import get_secops_guardian_tools

logger = logging.getLogger(__name__)

async def secops_guardian_node(state: AgentState):
    logger.info("--- SECOPS GUARDIAN: AUDITING CODE ---")
    
    tf_code = state.get("terraform_code")
    
    if not tf_code:
        return {"errors": ["No terraform code found to audit"]}

    llm = get_model()
    mcp_tools = await get_secops_guardian_tools()
    llm_with_tool = llm.bind_tools(mcp_tools).with_structured_output(SecurityReview)
    
    messages = [
        SystemMessage(content=SECOPS_SYSTEM_PROMPT),
        {"role": "user", "content": f"Analyze this HCL for security violations:\n\n{tf_code}"}
    ]
    
    review: SecurityReview = await llm_with_tool.ainvoke(messages)
    
    logger.info(f"SecOps Verdict: {'APPROVED' if review.is_approved else 'REJECTED'}")
    
    if not review.is_approved:
        feedback_msg = f"Security Rejection: {review.risk_analysis}. Fix these: {review.required_changes}"
        return {
            "is_approved": False, 
            "messages": [{"role": "user", "content": feedback_msg}],
            "errors": review.required_changes
        }
    
    return {
        "is_approved": True, 
        "errors": []
    }