from typing import Annotated, List, TypedDict, Dict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from typing_extensions import NotRequired

class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    terraform_code: NotRequired[Dict[str, str]]
    plan_output: NotRequired[str]
    verdict: NotRequired[str]
    architect_errors: NotRequired[List[str]]
    workspace_errors: NotRequired[List[str]]
    security_errors: NotRequired[List[str]]
    architect_rationale: NotRequired[str]
    created_files: NotRequired[List[str]]
    review_iterations: NotRequired[int]