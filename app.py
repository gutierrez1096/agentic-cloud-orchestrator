import streamlit as st
from langchain_core.messages import HumanMessage
from src.agents.supervisor import supervisor_graph
from langfuse.langchain import CallbackHandler

import asyncio

st.set_page_config(page_title="Sistema de Agentes IaC", page_icon="🏗️")

st.title("🏗️ Sistema de Agentes IaC")

langfuse_handler = CallbackHandler()

if "thread_id" not in st.session_state:
    import uuid
    st.session_state.thread_id = str(uuid.uuid4())

if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Input del chat
if prompt := st.chat_input("Escribe tu consulta sobre IaC aquí..."):
    # Agregar mensaje del usuario
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    
    # Procesar con el agente supervisor
    with st.chat_message("assistant"):
        with st.spinner("Procesando con el agente supervisor..."):
            try:
                result = asyncio.run(supervisor_graph.ainvoke(
                    {"messages": [HumanMessage(content=prompt)]},
                    config={"configurable": {"thread_id": st.session_state.thread_id}, "callbacks": [langfuse_handler]}
                ))
                
                # Extraer el último mensaje de la respuesta
                if result.get("messages"):
                    last_message = result["messages"][-1]
                    response_content = last_message.content if hasattr(last_message, 'content') else str(last_message)
                else:
                    response_content = str(result)
                
                st.markdown(response_content)
                st.session_state.messages.append({"role": "assistant", "content": response_content})
                
            except Exception as e:
                error_msg = f"Error al procesar la consulta: {str(e)}"
                st.error(error_msg)
                st.session_state.messages.append({"role": "assistant", "content": error_msg})
