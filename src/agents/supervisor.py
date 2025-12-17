from langgraph.graph import StateGraph, START, END

from src.config import get_model, get_checkpointer
from langchain.agents import create_agent
from src.agents.solutions_architect import call_solutions_architect, _invoke_solutions_architect
from src.agents.iac_engineer import call_iac_engineer, _invoke_iac_engineer
from langfuse.langchain import CallbackHandler
from src.states.graph_state import SupervisorState

SUPERVISOR_PROMPT = """# ROLE
Eres un Lead Solutions Architect y Gerente de Proyectos Técnico. Tu objetivo es orquestar un flujo de trabajo entre un Arquitecto y un Ingeniero de IaC para cumplir con los requisitos del usuario.

# TAREAS ESENCIALES
1. **Análisis Inicial:** Evalúa si la petición del usuario tiene suficiente información. Si no, solicita aclaraciones.
2. **Delegación de Diseño:** Si no existe un `architecture_plan` o este es insuficiente, invoca al **Solutions Architect**.
3. **Validación Técnica:** Revisa el diseño del Arquitecto. Si le faltan componentes críticos (seguridad, red, escalabilidad), devuélvelo con feedback.
4. **Delegación de Implementación:** Una vez validado el plan, solicita al **IaC Engineer** que genere el código.
5. **Cierre:** Cuando el código y el plan coincidan y sean correctos, entrega el resultado final al usuario.

# LÓGICA DE ENRUTAMIENTO (CRÍTICO)
- Si el plan de arquitectura está ausente o rechazado -> `architect`.
- Si el plan es válido pero no hay código -> `iac_engineer`.
- Si el código tiene errores o no coincide con el plan -> `iac_engineer` (con correcciones).
- Si todo está completo -> `END`.

# NOTA
Mantén una actitud crítica. No permitas que el código se genere sobre una arquitectura mediocre."""

supervisor_agent = create_agent(
    model=get_model(),
    tools=[call_solutions_architect, call_iac_engineer],
    system_prompt=SUPERVISOR_PROMPT,
)

async def supervisor_node(state: SupervisorState):
    """Nodo supervisor: enruta y conserva el historial de mensajes."""
    langfuse_handler = CallbackHandler()
    
    config = {}
    if langfuse_handler:
        config["callbacks"] = [langfuse_handler]
    
    response = await supervisor_agent.ainvoke(
        {"messages": state["messages"]},
        config=config
    )
    
    dest = END
    last_msg = response["messages"][-1].content.lower() if response.get("messages") else ""
    
    if "arquitecto" in last_msg or not state.get("architecture_plan"):
        dest = "architect"
    elif "iac" in last_msg or (state.get("architecture_plan") and not state.get("iac_code")):
        dest = "iac"
    
    return {
        "messages": state["messages"] + [response["messages"][-1]],
        "next_node": dest
    }

async def architect_node(state: SupervisorState):
    query = ""
    if state.get("messages"):
        last_message = state["messages"][-1]
        query = getattr(last_message, "content", "") or str(last_message)

    # Usar la función auxiliar directamente (no la herramienta decorada)
    architecture_plan = await _invoke_solutions_architect(query)
    notes = state.get("coordination_notes", []) or []
    notes.append("Arquitectura generada")

    return {
        "architecture_plan": architecture_plan,
        "current_task": "architecture",
        "coordination_notes": notes,
    }


async def iac_node(state: SupervisorState):
    architecture_plan = state.get("architecture_plan", "")
    # Usar la función auxiliar directamente (no la herramienta decorada)
    iac_code = await _invoke_iac_engineer(architecture_plan)
    notes = state.get("coordination_notes", []) or []
    notes.append("IaC generado")

    return {
        "iac_code": iac_code,
        "current_task": "iac",
        "coordination_notes": notes,
    }


def supervisor_routing(state: SupervisorState) -> str:
    return state.get("next_node", END)

graph = StateGraph(SupervisorState)
graph.add_node("supervisor", supervisor_node)
graph.add_node("architect", architect_node)
graph.add_node("iac", iac_node)

graph.add_edge(START, "supervisor")
graph.add_conditional_edges(
    "supervisor",
    supervisor_routing,
    {
        "architect": "architect",
        "iac": "iac",
        END: END,
    },
)
graph.add_edge("architect", "supervisor")
graph.add_edge("iac", "supervisor")

supervisor_graph = graph.compile(checkpointer=get_checkpointer())