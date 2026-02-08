from typing import Annotated, List, Literal, TypedDict, Dict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from typing_extensions import NotRequired

class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    terraform_code: NotRequired[Dict[str, str]]
    plan_output: NotRequired[str]
    plan_summary: NotRequired[str]
    apply_summary: NotRequired[str]
    is_approved: NotRequired[bool]
    workspace_errors: NotRequired[List[str]]
    architect_rationale: NotRequired[str]
    created_files: NotRequired[List[str]]
    review_iterations: NotRequired[int]
    secops_required_changes: NotRequired[List[str]]
    secops_risk_analysis: NotRequired[str]
    init_success: NotRequired[bool]
    human_decision: NotRequired[Literal["approve", "revise", "reject"]]
    apply_output: NotRequired[str]
    plan_success: NotRequired[bool]
    apply_success: NotRequired[bool]
    debugger_phase: NotRequired[Literal["init", "plan", "apply"]]
    debugger_init_attempts: NotRequired[int]
    debugger_plan_attempts: NotRequired[int]
    debugger_apply_attempts: NotRequired[int]
    debugger_tool_rounds: NotRequired[int]
    from_debugger: NotRequired[bool]