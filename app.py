import streamlit as st
from langchain_core.messages import HumanMessage
from src.agents.supervisor import create_supervisor_graph
from langgraph.checkpoint.memory import MemorySaver
import uuid
import asyncio
from dotenv import load_dotenv
from src.logger import setup_logger
from htbuilder import div, styles
from htbuilder.units import rem
import datetime
import textwrap
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
    logger.info("Nueva sesión iniciada")
    st.session_state.thread_id = str(uuid.uuid4())

if "memory" not in st.session_state:
    st.session_state.memory = MemorySaver()

if "messages" not in st.session_state:
    st.session_state.messages = []

if "initial_question" not in st.session_state:
    st.session_state.initial_question = None
if "selected_suggestion" not in st.session_state:
    st.session_state.selected_suggestion = None

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

if user_message:
    st.session_state.messages.append({"role": "user", "content": user_message})
    with st.chat_message("user"):
        st.markdown(user_message)
    
    st.session_state.initial_question = None
    st.session_state.selected_suggestion = None

    with st.chat_message("assistant"):
        with st.spinner("Architecting..."):
            config = {
                "configurable": {"thread_id": st.session_state.thread_id},
                "recursion_limit": 15
                }
                
            inputs = {"messages": [HumanMessage(content=user_message)]}
            
            final_state = None
            
            async def run():
                supervisor_graph = await create_supervisor_graph(checkpointer=st.session_state.memory)
                
                result = None
                async for event in supervisor_graph.astream(inputs, config, stream_mode="values"):
                    result = event
                return result

            try:
                final_state = asyncio.run(run())
                
                if final_state:
                    messages = final_state.get("messages", [])
                    content = ""
                    if messages:
                        last_msg = messages[-1]
                        content = last_msg.content
                        if content:
                            st.markdown(content)
                    
                    rationale = final_state.get("architect_rationale", "")
                    if rationale:
                        with st.expander("📋 Rationale del Architect", expanded=False):
                            st.markdown(rationale)
                    
                    created_files = final_state.get("created_files", [])
                    if created_files:
                        with st.expander("📁 Archivos Creados", expanded=False):
                            for filename in created_files:
                                st.text(f"• {filename}")
                    
                    tf_code = final_state.get("terraform_code", "")
                    if tf_code:
                        with st.expander("🛠️ Código Terraform", expanded=False):
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
                        if content:
                            content = f"{content}\n\n{plan_block}"
                        else:
                            content = plan_block

                    if content:
                        st.session_state.messages.append({"role": "assistant", "content": content})
            
            except Exception as e:
                st.error(f"An error occurred during architecting: {e}")
                logger.error(f"Error executing graph: {e}")