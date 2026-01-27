from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver

from src.mcp_client import get_solution_architect_tools
from src.states.graph_state import AgentState
from src.agents.solution_architect import solution_architect_node
import logging

logger = logging.getLogger(__name__)

def finalize_architecture_node(state: AgentState):
    """
    Este nodo se activa cuando el Arquitecto decide que ha terminado.
    Extrae el HCL de la intención de llamada a herramienta y lo guarda en el estado.
    """
    logger.info("--- FINALIZING ARCHITECTURE ---")
    messages = state["messages"]
    last_message = messages[-1]
    
    tool_call = last_message.tool_calls[0]
    design_args = tool_call["args"]
    
    hcl_code = design_args.get("hcl_code", "")
    explanation = design_args.get("rationale", "")
    
    logger.info(f"Arguments extracted - HCL Code length: {len(hcl_code)}")
    
    return {
        "terraform_code": hcl_code,
        "next_step": "SecOps Guardian",
        "messages": [last_message]
    }

async def create_supervisor_graph(checkpointer=None):
    logger.info("Creando grafo del supervisor...")

    tools = await get_solution_architect_tools()
    tool_node = ToolNode(tools)

    builder = StateGraph(AgentState)
    
    builder.add_node("solution_architect", solution_architect_node)
    builder.add_node("mcp_tools", tool_node)
    builder.add_node("finalize_architecture", finalize_architecture_node)

    builder.set_entry_point("solution_architect")

    def router(state):
        messages = state["messages"]
        last_message = messages[-1]
        
        if not last_message.tool_calls:
            return END
            
        tool_name = last_message.tool_calls[0]["name"]
        logger.info(f"Llamada a herramienta detectada: {tool_name}")
        
        if tool_name == "TerraformDesign":
            logger.info("Siguiente nodo: finalize_architecture")
            return "finalize_architecture"
        else:
            logger.info("Siguiente nodo: mcp_tools")
            return "mcp_tools"

    builder.add_conditional_edges(
        "solution_architect",
        router,
        {
            "mcp_tools": "mcp_tools",
            "finalize_architecture": "finalize_architecture",
            END: END
        }
    )

    builder.add_edge("mcp_tools", "solution_architect")
    builder.add_edge("finalize_architecture", END)

    return builder.compile(checkpointer=checkpointer)