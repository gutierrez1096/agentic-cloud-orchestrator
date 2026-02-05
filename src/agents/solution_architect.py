import json
import logging
from typing import List, Any
from langchain_core.messages import SystemMessage

from src.config import get_model
from src.prompts.architect import ARCHITECT_SYSTEM_PROMPT
from src.schemas.architect_schemas import TerraformDesign
from src.states.graph_state import AgentState

logger = logging.getLogger(__name__)

async def solution_architect_node(state: AgentState, tools: List[Any]):
    logger.info("--- SOLUTION ARCHITECT: THINKING ---")
    
    llm = get_model()
    llm_with_tools = llm.bind_tools(tools + [TerraformDesign])
    
    messages = state["messages"]

    if not isinstance(messages[0], SystemMessage):
        messages = [SystemMessage(content=ARCHITECT_SYSTEM_PROMPT)] + messages
    
    response = await llm_with_tools.ainvoke(messages)

    if response.tool_calls:
        logger.info(f"Model selected {len(response.tool_calls)} tool(s)")
        for tool in response.tool_calls:
            logger.info(f"Tool Request: {tool['name']} | Arguments: {json.dumps(tool['args'])}")
    else:
        logger.info("Model generated direct response")

    return {"messages": [response]}