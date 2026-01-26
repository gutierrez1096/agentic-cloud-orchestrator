from typing import Dict, List, Optional, Literal
from langchain_core.messages import AIMessage, SystemMessage, HumanMessage
from src.states.graph_state import AgentState
from src.config import get_model
from src.mcp_client import get_architect_tools
from src.prompts.architect import ARCHITECT_SYSTEM_PROMPT
from pydantic import BaseModel, Field

import logging
logger = logging.getLogger(__name__)

class SecurityConfig(BaseModel):
    access_level: Literal["public", "private", "internal_only"] = Field(
        description="Internet exposure level."
    )
    encryption_at_rest: bool = Field(
        default=True, 
        description="Whether the resource must have encryption enabled (KMS/SSE)."
    )

class OperationalConfig(BaseModel):
    availability: Literal["standard", "high_availability", "mission_critical"] = Field(
        description="Defines redundancy (e.g., Multi-AZ for 'high_availability')."
    )
    sizing_tier: Literal["development", "production_small", "production_large"] = Field(
        description="Capacity intent. The DevOps Agent will translate this to t3.micro or m5.large."
    )

class ResourceModel(BaseModel):
    logical_id: str = Field(description="Semantic ID (e.g., 'primary_database').")
    resource_type: str = Field(description="AWS resource type (e.g., 'aws_db_instance').")
    
    security: SecurityConfig
    operations: OperationalConfig
    
    essential_overrides: Dict[str, str] = Field(
        default_factory=dict, 
        description="Use ONLY if the user requested a specific name, port, or tag. DO NOT invent Terraform flags here."
    )
    
    dependencies: List[str] = Field(default_factory=list, description="Logical IDs of dependencies.")

class ArchitecturePlan(BaseModel):
    rationale: str = Field(description="Defense of the chosen architecture and trade-offs.")
    resources: List[ResourceModel]
    region: str = "eu-central-1"

async def cloud_architect_node(state: AgentState):
    logger.info("--- ARCHITECT NODE STARTED ---")
    
    llm = get_model()
    tools = await get_architect_tools()

    llm_with_output = llm.with_structured_output(ArchitecturePlan, method="function_calling")
    # llm_with_tools = llm.bind_tools(tools)
    
    system_message = SystemMessage(content=ARCHITECT_SYSTEM_PROMPT)
    messages = [system_message] + state["messages"]

    # response = await llm_with_tools.ainvoke(messages)
    
    # if response.tool_calls:
    #     logger.info(f"--- MCP TOOL CALL DETECTED: {response.tool_calls[0]['name']} ---")
    #     return {
    #         "messages": [response],
    #         "next_step": "CONTINUE"
    #     }
    
    logger.info("--- GENERATING FINAL OUTPUT ---")
    try:
        final_plan = await llm_with_output.ainvoke(messages)

        logger.info(f"Architecture Plan Generated: {len(final_plan.resources)} resources defined.")
        for resource in final_plan.resources:
            logger.info(f"Resource: {resource.logical_id} - {resource.resource_type}")
        logger.info(f"Architecture Plan Region: {final_plan.region}")
        logger.info(f"Architecture Plan Rationale: {final_plan.rationale}")

        return {
            "messages": [AIMessage(content=final_plan.rationale)],
            "plan_output": final_plan.model_dump_json(),
            "next_step": "DONE"
        }
    except Exception as e:
        logger.error(f"Architecture Validation Error: {e}")
        return {
            "messages": [HumanMessage(content=f"Error in architectural design: {str(e)}. Check your constraints.")],
            "next_step": "CONTINUE"
        }