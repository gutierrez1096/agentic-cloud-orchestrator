from typing import Annotated, TypedDict, List
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage

class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    terraform_code: str
    tfvars_data: dict
    plan_output: str
    next_step: str
    is_approved: bool
    errors: List[str]