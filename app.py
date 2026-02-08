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
    "🖥️ Web Server": "Deploy an EC2 instance t3.micro for a web server.",
    "🗄️ RDS Database": "Create a PostgreSQL RDS instance in a private subnet.",
    "🛡️ VPC Setup": "Architect a VPC with public and private subnets.",
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

if "thread_id" not in st.session_state:
    logger.debug("New session started")
    st.session_state.thread_id = str(uuid.uuid4())

if "memory" not in st.session_state:
    st.session_state.memory = MemorySaver()

if "messages" not in st.session_state:
    st.session_state.messages = []

if "initial_question" not in st.session_state:
    st.session_state.initial_question = None
if "selected_suggestion" not in st.session_state:
    st.session_state.selected_suggestion = None
if "pending_approval" not in st.session_state:
    st.session_state.pending_approval = False
if "applying" not in st.session_state:
    st.session_state.applying = False


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
        async for event in graph.astream(inp, config, stream_mode="updates"):
            for node_name in event:
                label = NODE_LABELS.get(node_name, node_name)
                step_placeholder.markdown(f"**Step:** {label}")
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


def _assistant_content_from_state(state):
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
            secops_parts.append("**Cambios requeridos:** " + "; ".join(secops_changes[:10]))
        parts.append("**SecOps:** " + " ".join(secops_parts))
    return "\n\n".join(parts) if parts else ""


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
for i, message in enumerate(messages):
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message.get("role") == "assistant":
            if message.get("plan_output"):
                with st.expander("Plan output (complete)", expanded=False):
                    st.code(message["plan_output"], language="text")
            if message.get("apply_summary") or message.get("apply_output"):
                st.markdown("Plan aplicado.")
                if message.get("apply_summary"):
                    st.markdown(f"**Apply summary:** {message['apply_summary']}")
                if message.get("apply_output"):
                    with st.expander("Apply output (complete)", expanded=False):
                        st.code(message["apply_output"], language="text")
            if message.get("rejected"):
                st.markdown("Plan rechazado.")
            if message.get("secops_risk_analysis") or message.get("secops_required_changes"):
                risk = message.get("secops_risk_analysis", "")
                changes = message.get("secops_required_changes") or []
                txt = ("**SecOps:** " + (risk[:300] + "…" if len(risk) > 300 else risk))
                if changes:
                    txt += " **Cambios requeridos:** " + "; ".join(changes[:5])
                st.markdown(txt)
            is_last = i == len(messages) - 1
            if st.session_state.pending_approval and is_last:
                type_map = {"Approve": "approve", "Reject": "reject", "Request changes": "revise"}
                if st.session_state.get("applying"):
                    resume = {
                        "type": st.session_state.get("hitl_decision", "reject"),
                        "feedback": st.session_state.get("hitl_feedback", ""),
                    }
                    with st.spinner("Applying plan..."):
                        final_state, interrupted = asyncio.run(run_graph(resume=resume))
                    st.session_state.applying = False
                    st.session_state.pending_approval = False
                    if interrupted:
                        content = _assistant_content_from_state(final_state)
                        if content:
                            msg = {"role": "assistant", "content": content}
                            if final_state.get("plan_output"):
                                msg["plan_summary"] = final_state.get("plan_summary", "")
                                msg["plan_output"] = final_state["plan_output"]
                            if final_state.get("secops_risk_analysis") or final_state.get("secops_required_changes"):
                                msg["secops_risk_analysis"] = final_state.get("secops_risk_analysis", "")
                                msg["secops_required_changes"] = final_state.get("secops_required_changes", [])
                            st.session_state.messages.append(msg)
                        st.session_state.pending_approval = True
                    else:
                        last = st.session_state.messages[-1]
                        if resume["type"] == "approve":
                            last["apply_summary"] = final_state.get("apply_summary", "")
                            last["apply_output"] = final_state.get("apply_output", "") or ""
                        else:
                            last["rejected"] = True
                    st.rerun()
                else:
                    with st.form("hitl"):
                        decision = st.radio("Decision", ["Approve", "Reject", "Request changes"])
                        feedback = st.text_area("Changes (optional)")
                        submitted = st.form_submit_button("Submit")
                    if submitted:
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
            config = {"configurable": {"thread_id": st.session_state.thread_id}}
            inputs = {"messages": [SystemMessage(content=ARCHITECT_SYSTEM_PROMPT), HumanMessage(content=user_message)]}

            try:
                final_state, interrupted = asyncio.run(run_graph(inputs=inputs, step_placeholder=step_placeholder))

                step_placeholder.empty()
                if interrupted:
                    content = _assistant_content_from_state(final_state)
                    if content:
                        msg = {"role": "assistant", "content": content}
                        if final_state.get("plan_output"):
                            msg["plan_summary"] = final_state.get("plan_summary", "")
                            msg["plan_output"] = final_state["plan_output"]
                        if final_state.get("secops_risk_analysis") or final_state.get("secops_required_changes"):
                            msg["secops_risk_analysis"] = final_state.get("secops_risk_analysis", "")
                            msg["secops_required_changes"] = final_state.get("secops_required_changes", [])
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

                    plan_summary = final_state.get("plan_summary", "")
                    plan_output = final_state.get("plan_output", "")
                    apply_summary = final_state.get("apply_summary", "")
                    apply_output = final_state.get("apply_output", "")
                    if plan_summary:
                        st.markdown(f"**Plan summary:** {plan_summary}")
                    if plan_output:
                        with st.expander("Plan output (completo)", expanded=False):
                            st.code(plan_output, language="text")
                    if apply_summary:
                        st.markdown(f"**Apply summary:** {apply_summary}")
                    if apply_output:
                        with st.expander("Apply output (completo)", expanded=False):
                            st.code(apply_output, language="text")

                    if content or plan_summary or apply_summary:
                        msg = {"role": "assistant", "content": content or f"**Plan summary:** {plan_summary}\n\n**Apply summary:** {apply_summary}"}
                        if plan_output:
                            msg["plan_summary"] = plan_summary
                            msg["plan_output"] = plan_output
                        if apply_output:
                            msg["apply_summary"] = apply_summary
                            msg["apply_output"] = apply_output
                        if final_state.get("secops_risk_analysis") or final_state.get("secops_required_changes"):
                            msg["secops_risk_analysis"] = final_state.get("secops_risk_analysis", "")
                            msg["secops_required_changes"] = final_state.get("secops_required_changes", [])
                        st.session_state.messages.append(msg)

            except Exception as e:
                st.error(f"An error occurred during architecting: {e}")
                logger.error(f"Error executing graph: {e}")