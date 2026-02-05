from typing import Annotated, List, TypedDict, Dict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from typing_extensions import NotRequired

class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    terraform_code: NotRequired[Dict[str, str]]
    tfvars_data: NotRequired[dict]
    plan_output: NotRequired[str]
    next_step: NotRequired[str]
    is_approved: NotRequired[bool]
    errors: NotRequired[List[str]]
    architect_rationale: NotRequired[str]
    created_files: NotRequired[List[str]]