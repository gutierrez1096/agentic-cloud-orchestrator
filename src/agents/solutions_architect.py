from langchain.agents import create_agent
from src.config import get_model
from langchain.tools import tool
from src.mcp_client import get_filtered_aws_doc_tools

SOLUTIONS_ARCHITECT_PROMPT = """# ROLE
Eres un Senior Solutions Architect experto en nubes públicas (AWS, Azure, GCP) y entornos On-Premise.

# OBJETIVO
Transformar los requisitos del usuario en un documento técnico detallado que servirá de base para la automatización.

# ESTRUCTURA DEL ENTREGABLE (Architecture Plan)
Tu respuesta debe seguir estrictamente este orden:
1. **Resumen de la Solución:** Breve descripción de la topología.
2. **Diagrama Lógico (Texto):** Descripción de flujos de red y comunicación.
3. **Listado de Componentes:** Detalle de servicios (ej. S3 Buckets, VPC Peering, RDS Clusters).
4. **Estrategia de Seguridad:** Roles IAM, Grupos de Seguridad y Cifrado de datos.
5. **Justificación:** Por qué esta solución es la mejor en términos de costo/rendimiento.

# RESTRICCIONES
- NO generes código (Terraform/Ansible).
- NO seas ambiguo. Especifica tipos de instancia, regiones y nombres de servicios.
- Si recibes feedback del Supervisor, prioriza esos cambios sobre el diseño original."""

def create_solutions_architect_agent():
    tools = get_filtered_aws_doc_tools()
    return create_agent(
        model=get_model(), 
        tools=tools, 
        system_prompt=SOLUTIONS_ARCHITECT_PROMPT
    )

solutions_architect_agent = create_solutions_architect_agent()

async def _invoke_solutions_architect(query: str):
    """Función auxiliar para invocar al agente arquitecto de forma asíncrona."""
    result = await solutions_architect_agent.ainvoke({
        "messages": [{"role": "user", "content": query}]
    })
    last_msg = result.get("messages", [])[-1]
    return last_msg.content if hasattr(last_msg, 'content') else str(last_msg)

@tool(
    "call_solutions_architect",
    description="Especialista en arquitectura de infraestructura como código (IaC). Usa cuando necesites análisis detallado de arquitectura, diseño de infraestructura, o mejores prácticas de IaC."
)
async def call_solutions_architect(query: str):
    """Invoca al agente arquitecto de forma asíncrona."""
    return await _invoke_solutions_architect(query)