import json
import logging
from typing import List, Any
from langchain_core.messages import SystemMessage

from src.config import get_model
from src.prompts.secops import SECOPS_SYSTEM_PROMPT
from src.schemas.secops_schemas import SecurityReview
from src.states.graph_state import AgentState
from src.tools.mcp_tools import get_secops_guardian_tools

logger = logging.getLogger(__name__)

async def secops_guardian_node(state: AgentState, tools: List[Any]):
    logger.info("--- SECOPS GUARDIAN: AUDITING CODE ---")
    
    tf_code = state.get("terraform_code", {})
    
    if not tf_code:
        return {"errors": ["No terraform code found to audit"]}
        
    llm = get_model()
    llm_with_tools = llm.bind_tools(tools + [SecurityReview])
    
    messages = state["messages"]
    
    if not any(isinstance(m, SystemMessage) for m in messages):
        messages = [SystemMessage(content=SECOPS_SYSTEM_PROMPT)] + messages
    
    response = await llm_with_tools.ainvoke(messages)
    
    if response.tool_calls:
        logger.info(f"SecOps selected {len(response.tool_calls)} tool(s)")
        for tool in response.tool_calls:
            logger.info(f"Tool Request: {tool['name']} | Arguments: {json.dumps(tool['args'])}")
    else:
        logger.info("SecOps generated direct response")
    
    return {"messages": [response]}
