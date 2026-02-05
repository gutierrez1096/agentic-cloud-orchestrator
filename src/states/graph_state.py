from typing import Annotated, List, TypedDict, Dict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    terraform_code: Dict[str, str]
    tfvars_data: dict
    plan_output: str
    next_step: str
    is_approved: bool
    errors: List[str]
    architect_rationale: str
    created_files: List[str]