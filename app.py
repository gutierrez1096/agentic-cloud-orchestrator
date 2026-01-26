import streamlit as st
from langchain_core.messages import HumanMessage
from src.agents.supervisor import create_supervisor_graph
from langgraph.checkpoint.memory import MemorySaver
import uuid
import asyncio
from dotenv import load_dotenv
from src.logger import setup_logger

load_dotenv()

# Setup logger
logger = setup_logger()
logger.info("Iniciando aplicación Streamlit")

st.set_page_config(page_title="Architect Agent Test", page_icon="🏗️")
st.title("🏗️ Architect Agent Test")

# Session ID
if "thread_id" not in st.session_state:
    logger.info("Nueva sesión iniciada")
    st.session_state.thread_id = str(uuid.uuid4())

# Memory (Checkpoint)
if "memory" not in st.session_state:
    st.session_state.memory = MemorySaver()

# Chat History
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display History
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Input
if prompt := st.chat_input("Describe infrastructure (e.g., 'S3 bucket for logs')..."):
    # Add User Message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    
    # Run Graph
    with st.chat_message("assistant"):
        with st.spinner("Architecting..."):
            config = {"configurable": {"thread_id": st.session_state.thread_id}}
            inputs = {"messages": [HumanMessage(content=prompt)]}
            
            # Simple run (we expect it to finish in one go)
            final_state = None
            async def run():
                # Initialize graph asynchronously with persistent memory
                supervisor_graph = await create_supervisor_graph(checkpointer=st.session_state.memory)
                
                # We use astream to get the final state more reliably in this context
                result = None
                async for event in supervisor_graph.astream(inputs, config, stream_mode="values"):
                    result = event
                return result

            final_state = asyncio.run(run())
            
            if final_state:
                # 1. Response Message
                messages = final_state.get("messages", [])
                if messages:
                    last_msg = messages[-1]
                    content = last_msg.content
                    st.markdown(content)
                    st.session_state.messages.append({"role": "assistant", "content": content})
                
                # 2. Terraform Code
                tf_code = final_state.get("terraform_code", "")
                if tf_code:
                    st.subheader("🛠️ Terraform Code")
                    st.code(tf_code, language="hcl")
                    # Add code block to history for context/visibility
                    code_msg = f"```hcl\n{tf_code}\n```"
                    st.session_state.messages.append({"role": "assistant", "content": code_msg})