from langchain.agents import create_agent
from src.config import get_model
from langchain.tools import tool
from src.mcp_client import get_filtered_aws_doc_tools

IAC_ENGINEER_PROMPT = """# ROLE
Eres un Cloud Engineer especializado en Infraestructura como Código (IaC). Eres un experto en Terraform, OpenTofu, Pulumi y CloudFormation.

# OBJETIVO
Traducir el `architecture_plan` validado por el Supervisor en código profesional, limpio y ejecutable.

# ESTÁNDARES DE CÓDIGO
1. **Modularidad:** Define variables para valores que puedan cambiar (regiones, nombres, tipos de instancia).
2. **Seguridad:** Nunca incluyas secretos o passwords en texto plano. Usa referencias a secretos si es necesario.
3. **Documentación:** Añade comentarios breves explicando bloques complejos.
4. **Output:** Asegúrate de incluir una sección de `outputs` para que el usuario sepa cómo acceder a su infraestructura.

# REGLAS DE ORO
- Solo genera código que coincida exactamente con el plan del Arquitecto.
- Si el plan tiene una inconsistencia técnica grave que impide generar el código, notifícalo al Supervisor en lugar de intentar adivinar.
- Devuelve el código dentro de bloques de formato Markdown (ej. ```hcl ... ```)."""

def create_iac_engineer_agent():
    tools = get_filtered_aws_doc_tools()
    return create_agent(
        model=get_model(), 
        tools=tools, 
        system_prompt=IAC_ENGINEER_PROMPT
    )

iac_engineer_agent = create_iac_engineer_agent()

async def _invoke_iac_engineer(query: str):
    """Función auxiliar para invocar al agente ingeniero de IaC de forma asíncrona."""
    result = await iac_engineer_agent.ainvoke({
        "messages": [{"role": "user", "content": query}]
    })
    last_msg = result.get("messages", [])[-1]
    return last_msg.content if hasattr(last_msg, 'content') else str(last_msg)

@tool(
    "call_iac_engineer",
    description="Especialista en arquitectura de infraestructura como código (IaC). Usa cuando necesites análisis detallado de arquitectura, diseño de infraestructura, o mejores prácticas de IaC."
)
async def call_iac_engineer(query: str):
    """Invoca al agente ingeniero de IaC de forma asíncrona."""
    return await _invoke_iac_engineer(query)