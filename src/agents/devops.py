from typing import Dict, List, Optional, Literal
from langchain_core.messages import AIMessage, SystemMessage, HumanMessage
from src.states.graph_state import AgentState
from src.config import get_model
from src.mcp_client import get_devops_tools
from src.prompts.devops import DEVOPS_SYSTEM_PROMPT
from pydantic import BaseModel, Field

import logging
logger = logging.getLogger(__name__)

async def devops_node(state: AgentState):
    logger.info("--- DEVOPS NODE STARTED ---")
    
    llm = get_model()
    tools = await get_devops_tools()

    llm_with_output = llm.with_structured_output(DeploymentArtifact, method="function_calling")
    # llm_with_tools = llm.bind_tools(tools)
    
    system_message = SystemMessage(content=DEVOPS_SYSTEM_PROMPT)
    messages = [system_message] + state["messages"]

    # response = await llm_with_tools.ainvoke(messages)
    
    # if response.tool_calls:
    #     logger.info(f"--- MCP TOOL CALL DETECTED: {response.tool_calls[0]['name']} ---")
    #     return {
    #         "messages": [response],
    #         "next_step": "CONTINUE"
    #     }