import streamlit as st
from langchain_core.messages import HumanMessage, SystemMessage
from src.prompts.architect import ARCHITECT_SYSTEM_PROMPT
from langgraph.types import Command
from src.graphs.supervisor import create_supervisor_graph
from langgraph.checkpoint.memory import MemorySaver
from langfuse.langchain import CallbackHandler
import uuid
import asyncio
from dotenv import load_dotenv
from src.logger import setup_logger
from htbuilder import div, styles
from htbuilder.units import rem
import json

load_dotenv()
logger = setup_logger()

st.set_page_config(page_title="AWS IaC Agent", page_icon="🏗️", layout="centered")

SUGGESTIONS = {
    "☁️ Log Bucket": "I need an S3 bucket for storing application logs.",
    "📩 Async Messaging": "Setup an SNS topic for order notifications and an SQS queue subscribed to it to handle background processing.",
    "🗄️ NoSQL Table": "Create a DynamoDB table for user profiles using 'UserId' as the partition key and a Global Secondary Index (GSI) to allow efficient queries by 'Email'."
    }

NODE_LABELS = {
    "solution_architect": "Designing architecture",
    "finalize_architecture": "Finalizing design",
    "apply_to_workspace": "Writing Terraform files",
    "terraform_init": "Initializing Terraform",
    "secops_guardian": "Security review",
    "finalize_secops_review": "Security review",
    "terraform_plan": "Generating plan",
    "human_approval": "Waiting for your approval",
    "terraform_apply": "Applying plan",
    "iac_debugger": "Correcting Terraform errors",
    "finalize_debugger": "Applying Terraform fixes",
    "debugger_tools": "Correcting Terraform errors",
}

# Reset de estado al iniciar una nueva instrucción del usuario (no se toca el grafo).
RUN_STATE_RESET = {
    "terraform_code": None,
    "plan_output": None,
    "plan_summary": None,
    "apply_summary": None,
    "apply_output": None,
    "is_approved": None,
    "workspace_errors": None,
    "architect_rationale": None,
    "created_files": None,
    "review_iterations": 0,
    "secops_required_changes": None,
    "secops_risk_analysis": None,
    "init_success": None,
    "human_decision": None,
    "plan_success": None,
    "apply_success": None,
    "debugger_init_attempts": 0,
    "debugger_plan_attempts": 0,
    "debugger_apply_attempts": 0,
    "debugger_tool_rounds": 0,
    "from_debugger": None,
}

def _init_session_state():
    """Initialize all session_state keys in one place (recommended by Streamlit)."""
    defaults = {
        "thread_id": str(uuid.uuid4()),
        "memory": MemorySaver(),
        "messages": [],
        "initial_question": None,
        "selected_suggestion": None,
        "pending_approval": False,
        "applying": False,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value
            if key == "thread_id":
                logger.debug("New session started")


_init_session_state()


async def run_graph(inputs=None, resume=None, step_placeholder=None):
    """Runs the graph (inputs) or resumes after interrupt (resume). Returns (state, interrupted)."""
    graph = await create_supervisor_graph(checkpointer=st.session_state.memory)
    langfuse_handler = CallbackHandler()
    config = {
        "configurable": {"thread_id": st.session_state.thread_id},
        "callbacks": [langfuse_handler],
        "run_name": "AWS IaC Agent",
        "metadata": {"langfuse_session_id": st.session_state.thread_id},
    }
    inp = Command(resume=resume) if resume else inputs
    if step_placeholder is not None:
        steps_trail = []
        async for event in graph.astream(inp, config, stream_mode="updates"):
            for node_name in event:
                label = NODE_LABELS.get(node_name, node_name)
                if not steps_trail or steps_trail[-1] != label:
                    steps_trail.append(label)
                steps_trail = steps_trail[-5:]
                lines = [f"- {s}" for s in steps_trail[:-1]] + [f"- *{steps_trail[-1]}*"]
                step_placeholder.markdown("**Steps:**\n" + "\n".join(lines))
        snapshot = await graph.aget_state(config)
        result = snapshot.values if snapshot else None
        interrupted = bool(snapshot.interrupts) if snapshot else False
        return result, interrupted
    result = None
    async for event in graph.astream(inp, config, stream_mode="values"):
        result = event
    snapshot = await graph.aget_state(config)
    interrupted = bool(snapshot.interrupts)
    return result, interrupted


def _flow_summary_bullets(state):
    """Short list of flow steps and decisions (transparency without overwhelming)."""
    bullets = []
    if state.get("created_files"):
        bullets.append("Design and Terraform files generated")
    if state.get("is_approved") is True:
        bullets.append("SecOps approved")
    elif state.get("secops_required_changes"):
        bullets.append("SecOps requested changes")
    if state.get("init_success") is False:
        bullets.append("Terraform init failed (fixed by debugger)")
    if state.get("plan_success") is True:
        bullets.append("Plan generated")
    elif state.get("plan_success") is False:
        bullets.append("Plan failed")
    decision = state.get("human_decision")
    if decision == "approve":
        bullets.append("Plan applied successfully" if state.get("apply_success") else "Apply failed")
    elif decision == "reject":
        bullets.append("Plan rejected")
    if state.get("plan_success") and not decision and not state.get("apply_output"):
        bullets.append("Waiting for your approval")
    return bullets


def _assistant_content_from_state(state):
    """Summary text for the assistant message from state."""
    rationale = state.get("architect_rationale", "")
    plan_summary = state.get("plan_summary", "")
    secops_risk = state.get("secops_risk_analysis", "")
    secops_changes = state.get("secops_required_changes") or []
    parts = []
    if rationale:
        parts.append(f"### Architect Rationale\n\n{rationale}")
    if plan_summary:
        parts.append(f"**Plan summary:** {plan_summary}")
    if secops_risk or secops_changes:
        secops_parts = []
        if secops_risk:
            secops_parts.append(secops_risk[:500] + ("..." if len(secops_risk) > 500 else ""))
        if secops_changes:
            secops_parts.append("**Required changes:** " + "; ".join(secops_changes[:10]))
        parts.append("**SecOps:** " + " ".join(secops_parts))
    return "\n\n".join(parts) if parts else ""


def _assistant_message_from_state(state, content_override=None):
    """Build the assistant message dict for st.session_state.messages (avoids duplicating in 3 places)."""
    content = content_override if content_override is not None else _assistant_content_from_state(state)
    if not content and not state.get("plan_output") and not state.get("apply_summary"):
        return None
    msg = {"role": "assistant", "content": content or ""}
    if state.get("plan_output"):
        msg["plan_summary"] = state.get("plan_summary", "")
        msg["plan_output"] = state["plan_output"]
    if state.get("secops_risk_analysis") or state.get("secops_required_changes"):
        msg["secops_risk_analysis"] = state.get("secops_risk_analysis", "")
        msg["secops_required_changes"] = state.get("secops_required_changes", [])
    if state.get("apply_summary") is not None or state.get("apply_output") is not None:
        msg["apply_summary"] = state.get("apply_summary", "")
        msg["apply_output"] = state.get("apply_output", "") or ""
        msg["apply_success"] = state.get("apply_success", True)
    if state.get("human_decision") and state.get("human_decision") != "approve":
        msg["rejected"] = True
    return msg


def _render_tf_code(tf_code):
    """Render the Terraform code block (dict or str/JSON) within the current context."""
    if isinstance(tf_code, dict):
        for filename, file_content in tf_code.items():
            st.subheader(f"`{filename}`")
            st.code(file_content, language="hcl")
    elif isinstance(tf_code, str):
        try:
            files_dict = json.loads(tf_code)
            if isinstance(files_dict, dict):
                for filename, file_content in files_dict.items():
                    st.subheader(f"`{filename}`")
                    st.code(file_content, language="hcl")
            else:
                st.code(tf_code, language="hcl")
        except json.JSONDecodeError:
            st.code(tf_code, language="hcl")


st.html(div(style=styles(font_size=rem(5), line_height=1))["✈"])

title_row = st.container(
    horizontal=True,
    vertical_alignment="bottom",
)

with title_row:
    st.title(
        "AWS Autonomous Architect",
        anchor=False,
        width="stretch",
    )

with title_row:
    def clear_conversation():
        st.session_state.messages = []
        st.session_state.initial_question = None
        st.session_state.selected_suggestion = None
        st.session_state.pending_approval = False
        st.session_state.applying = False
        st.session_state.thread_id = str(uuid.uuid4())
        st.session_state.memory = MemorySaver()

    st.button(
        "Restart",
        icon=":material/refresh:",
        on_click=clear_conversation,
    )

user_just_asked_initial_question = (
    "initial_question" in st.session_state and st.session_state.initial_question
)

user_just_clicked_suggestion = (
    "selected_suggestion" in st.session_state and st.session_state.selected_suggestion
)

user_first_interaction = (
    user_just_asked_initial_question or user_just_clicked_suggestion
)

has_message_history = len(st.session_state.messages) > 0

if not user_first_interaction and not has_message_history:
    st.session_state.messages = []

    with st.container():
        st.chat_input("Describe infrastructure (e.g., 'S3 bucket for logs')...", key="initial_question")

        selected_suggestion = st.pills(
            label="Examples",
            label_visibility="collapsed",
            options=SUGGESTIONS.keys(),
            key="selected_suggestion",
        )
    
    st.stop()

user_message = st.chat_input("Describe additional infrastructure...")

if not user_message:
    if user_just_asked_initial_question:
        user_message = st.session_state.initial_question
    if user_just_clicked_suggestion:
        user_message = SUGGESTIONS[st.session_state.selected_suggestion]

messages = st.session_state.messages
last_assistant_idx = next((i for i in range(len(messages) - 1, -1, -1) if messages[i].get("role") == "assistant"), -1)
for i, message in enumerate(messages):
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message.get("role") == "assistant":
            if message.get("flow_bullets"):
                st.markdown("**Flow summary**")
                for b in message["flow_bullets"]:
                    st.markdown(f"- {b}")
            if message.get("plan_output"):
                with st.expander("Plan output (complete)", expanded=False):
                    st.code(message["plan_output"], language="text")
            if message.get("apply_success") or message.get("apply_summary") or message.get("apply_output"):
                st.success("Plan applied successfully. Flow complete.")
                if message.get("apply_summary"):
                    st.markdown(f"**Apply summary:** {message['apply_summary']}")
                if message.get("apply_output"):
                    with st.expander("Apply output (complete)", expanded=False):
                        st.code(message["apply_output"], language="text")
            if message.get("rejected"):
                st.warning("Plan rejected.")
            if message.get("secops_risk_analysis") or message.get("secops_required_changes"):
                risk = message.get("secops_risk_analysis", "")
                changes = message.get("secops_required_changes") or []
                txt = ("**SecOps:** " + (risk[:300] + "…" if len(risk) > 300 else risk))
                if changes:
                    txt += " **Required changes:** " + "; ".join(changes[:5])
                st.markdown(txt)
            show_hitl = st.session_state.pending_approval and i == last_assistant_idx
            if show_hitl:
                type_map = {"Approve": "approve", "Reject": "reject", "Request changes": "revise"}
                if st.session_state.get("applying"):
                    decision = st.session_state.get("hitl_decision", "reject")
                    resume = {
                        "type": decision,
                        "feedback": st.session_state.get("hitl_feedback", ""),
                    }
                    spinner_msg = (
                        "Applying plan..."
                        if decision == "approve"
                        else ("Processing requested changes..." if decision == "revise" else "Rejecting plan...")
                    )
                    with st.spinner(spinner_msg):
                        final_state, interrupted = asyncio.run(run_graph(resume=resume))
                    st.session_state.applying = False
                    st.session_state.pending_approval = False
                    if interrupted:
                        msg = _assistant_message_from_state(final_state)
                        if msg:
                            st.session_state.messages.append(msg)
                        st.session_state.pending_approval = True
                    else:
                        last = st.session_state.messages[last_assistant_idx]
                        if resume["type"] == "approve":
                            last["apply_summary"] = final_state.get("apply_summary", "")
                            last["apply_output"] = final_state.get("apply_output", "") or ""
                            last["apply_success"] = final_state.get("apply_success", True)
                        else:
                            last["rejected"] = True
                        last["flow_bullets"] = _flow_summary_bullets(final_state)
                    st.rerun()
                else:
                    with st.form("hitl"):
                        decision = st.radio("Decision", ["Approve", "Reject", "Request changes"])
                        feedback = st.text_area("Changes (optional)")
                        submitted = st.form_submit_button("Submit")
                    if submitted:
                        if decision == "Request changes" and not (feedback or "").strip():
                            st.error("Please describe the changes you want when requesting modifications.")
                        else:
                            st.session_state.applying = True
                            st.session_state.hitl_decision = type_map[decision]
                            st.session_state.hitl_feedback = feedback or ""
                            st.rerun()

if st.session_state.pending_approval:
    st.stop()

if user_message:
    st.session_state.messages.append({"role": "user", "content": user_message})
    with st.chat_message("user"):
        st.markdown(user_message)

    st.session_state.initial_question = None
    st.session_state.selected_suggestion = None

    with st.chat_message("assistant"):
        step_placeholder = st.empty()
        with st.spinner("Architecting..."):
            inputs = {
                "messages": [SystemMessage(content=ARCHITECT_SYSTEM_PROMPT), HumanMessage(content=user_message)],
                **RUN_STATE_RESET,
            }

            try:
                final_state, interrupted = asyncio.run(run_graph(inputs=inputs, step_placeholder=step_placeholder))

                step_placeholder.empty()
                if interrupted:
                    msg = _assistant_message_from_state(final_state)
                    if msg:
                        msg["flow_bullets"] = _flow_summary_bullets(final_state)
                        st.session_state.messages.append(msg)
                    st.session_state.pending_approval = True
                    st.rerun()
                elif final_state:
                    messages = final_state.get("messages", [])
                    content = ""
                    if messages:
                        last_msg = messages[-1]
                        content = last_msg.content or ""
                    if content:
                        st.markdown(content)

                    flow_bullets = _flow_summary_bullets(final_state)
                    if flow_bullets:
                        st.markdown("**Flow summary**")
                        for b in flow_bullets:
                            st.markdown(f"- {b}")

                    rationale = final_state.get("architect_rationale", "")
                    if rationale:
                        with st.expander("📋 Architect Rationale", expanded=False):
                            st.markdown(rationale)

                    created_files = final_state.get("created_files", [])
                    if created_files:
                        with st.expander("📁 Created Files", expanded=False):
                            for filename in created_files:
                                st.text(f"• {filename}")

                    tf_code = final_state.get("terraform_code", {})
                    if tf_code:
                        with st.expander("🛠️ Terraform Code", expanded=False):
                            _render_tf_code(tf_code)

                    plan_summary = final_state.get("plan_summary", "")
                    plan_output = final_state.get("plan_output", "")
                    apply_summary = final_state.get("apply_summary", "")
                    apply_output = final_state.get("apply_output", "")
                    if plan_summary:
                        st.markdown(f"**Plan summary:** {plan_summary}")
                    if plan_output:
                        with st.expander("Plan output (complete)", expanded=False):
                            st.code(plan_output, language="text")
                    if apply_summary:
                        st.markdown(f"**Apply summary:** {apply_summary}")
                    if apply_output:
                        with st.expander("Apply output (complete)", expanded=False):
                            st.code(apply_output, language="text")

                    content_display = content or f"**Plan summary:** {plan_summary}\n\n**Apply summary:** {apply_summary}"
                    msg = _assistant_message_from_state(final_state, content_override=content_display)
                    if msg:
                        msg["flow_bullets"] = flow_bullets
                        st.session_state.messages.append(msg)

            except Exception as e:
                st.error(f"An error occurred during architecting: {e}")
                logger.error(f"Error executing graph: {e}")