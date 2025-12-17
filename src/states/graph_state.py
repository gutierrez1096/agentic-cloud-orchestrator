from typing import TypedDict, Annotated
from langgraph.graph.message import add_messages

class SupervisorState(TypedDict):
    messages: Annotated[list, add_messages]
    is_valid: bool
    coordination_notes: list
    architecture_plan: str
    iac_code: str
    next_node: str