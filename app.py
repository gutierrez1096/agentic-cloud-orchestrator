import streamlit as st
from langchain_core.messages import HumanMessage, SystemMessage
from src.prompts.architect import ARCHITECT_SYSTEM_PROMPT
from langgraph.types import Command
from src.graphs.supervisor import create_supervisor_graph
from langgraph.checkpoint.memory import MemorySaver
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


async def run_graph(inputs=None, resume=None):
    """Runs the graph (inputs) or resumes after interrupt (resume). Returns (state, interrupted)."""
    graph = await create_supervisor_graph(checkpointer=st.session_state.memory)
    config = {"configurable": {"thread_id": st.session_state.thread_id}}
    inp = Command(resume=resume) if resume else inputs
    result = None
    async for event in graph.astream(inp, config, stream_mode="values"):
        result = event
    snapshot = await graph.aget_state(config)
    interrupted = bool(snapshot.interrupts)
    return result, interrupted


def _assistant_content_from_state(state):
    """Builds the assistant message markdown content (rationale + plan) from state."""
    rationale = state.get("architect_rationale", "")
    plan_output = state.get("plan_output", "")
    parts = []
    if rationale:
        parts.append(f"### Architect Rationale\n\n{rationale}")
    if plan_output:
        parts.append(f"### Terraform Plan Output\n\n```\n{plan_output}\n```")
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

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if st.session_state.pending_approval:
    with st.chat_message("assistant"):
        with st.form("hitl"):
            decision = st.radio("Decision", ["Approve", "Reject", "Request changes"])
            feedback = st.text_area("Changes (optional)")
            submitted = st.form_submit_button("Submit")
    if submitted:
        type_map = {"Approve": "approve", "Reject": "reject", "Request changes": "revise"}
        resume = {"type": type_map[decision], "feedback": feedback or ""}
        final_state, interrupted = asyncio.run(run_graph(resume=resume))
        st.session_state.pending_approval = False
        if interrupted:
            content = _assistant_content_from_state(final_state)
            if content:
                st.session_state.messages.append({"role": "assistant", "content": content})
            st.session_state.pending_approval = True
        else:
            if resume["type"] == "approve":
                apply_out = final_state.get("apply_output", "")
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": f"Plan approved.\n\n### Terraform Apply\n\n```\n{apply_out}\n```"
                })
            else:
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": "Plan rejected by user."
                })
        st.rerun()
    st.stop()

if user_message:
    st.session_state.messages.append({"role": "user", "content": user_message})
    with st.chat_message("user"):
        st.markdown(user_message)

    st.session_state.initial_question = None
    st.session_state.selected_suggestion = None

    with st.chat_message("assistant"):
        with st.spinner("Architecting..."):
            config = {"configurable": {"thread_id": st.session_state.thread_id}}
            inputs = {"messages": [SystemMessage(content=ARCHITECT_SYSTEM_PROMPT), HumanMessage(content=user_message)]}

            try:
                final_state, interrupted = asyncio.run(run_graph(inputs=inputs))

                if interrupted:
                    content = _assistant_content_from_state(final_state)
                    if content:
                        st.session_state.messages.append({"role": "assistant", "content": content})
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

                    architect_errors = final_state.get("architect_errors", [])
                    if architect_errors:
                        with st.expander("⚠️ Architect Errors", expanded=True):
                            for err in architect_errors:
                                st.text(f"• {err}")

                    security_errors = final_state.get("security_errors", [])
                    if security_errors:
                        with st.expander("⚠️ Security Errors", expanded=True):
                            for err in security_errors:
                                st.text(f"• {err}")

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

                    plan_output = final_state.get("plan_output", "")
                    if plan_output:
                        st.subheader("📊 Terraform Plan Output")
                        st.code(plan_output, language="text")
                        plan_block = f"### 📊 Terraform Plan Output\n```\n{plan_output}\n```"
                        content = f"{content}\n\n{plan_block}" if content else plan_block

                    if content:
                        st.session_state.messages.append({"role": "assistant", "content": content})

            except Exception as e:
                st.error(f"An error occurred during architecting: {e}")
                logger.error(f"Error executing graph: {e}")