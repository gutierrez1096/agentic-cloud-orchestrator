# agentic-cloud-orchestrator
Multi-agent orchestrator for autonomous cloud infrastructure deployment using LangGraph, Terraform, and Model Context Protocol (MCP).

---

## 1. Objetivo del Sistema

Desarrollar un **Orquestador Multi-Agente de grado empresarial** que actúe como una capa de abstracción inteligente entre los requerimientos de negocio y la infraestructura de AWS. El sistema no es un simple generador de código, sino un ecosistema autónomo basado en:

* **Abstracción Semántica:** Interfaz puramente en lenguaje natural para la definición de recursos.
* **Resiliencia Autónoma (Self-healing):** Ciclos de retroalimentación en tiempo real para corregir errores de plan y validación sin intervención manual.
* **Gobernanza mediante MCP:** Desacoplamiento total de las credenciales y la lógica de ejecución mediante el estándar **Model Context Protocol**, garantizando que el LLM solo interactúe con interfaces seguras y tipadas.

---

## 2. Arquitectura de Agentes y Nodos

En este sistema, diferenciamos entre agentes que **razonan** (LLM-based) y nodos que **ejecutan** (deterministic code/MCP).

### A. Capa de Razonamiento (Agentes)

| Agente | Responsabilidad | Entrada | Salida |
| --- | --- | --- | --- |
| **Supervisor** | Gestión del ciclo de vida y ruteo de estados. | Prompt Usuario / Estado | Delegación al siguiente nodo |
| **Cloud Architect** | Diseño de arquitectura HCL y selección de módulos. | Requerimientos | Código Terraform (HCL) |
| **SecOps Guardian** | Auditoría de seguridad y cumplimiento (Compliance). | Código HCL | Reporte de Riesgos |
| **IaC Debugger** | Análisis de errores y generación de parches. | Error Logs (MCP) | Instrucciones de corrección |

### B. Capa de Acción y Control (Nodos)

| Nodo | Función Técnica | Herramienta / Protocolo |
| --- | --- | --- |
| **MCP Provisioner** | Ejecución determinista de Terraform (`plan`/`apply`). | **Terraform MCP Server** |
| **HITL Gate** | Punto de interrupción para aprobación humana. | **LangGraph Breakpoint** |
| **State Sync** | Persistencia y sincronización del estado del grafo. |  |

---

## 3. El Sistema Agéntico (Diseño del Grafo)

El orquestador utiliza **LangGraph** para implementar un **Grafo de Estados Cíclico Dirigido (DAG con ciclos)**, permitiendo la iteración hasta alcanzar el estado deseado.

### A. El Estado Compartido (`State`)

La "fuente única de verdad" es un objeto `TypedDict` que persiste:

* **HCL_Code:** El código generado actualmente.
* **Plan_Output:** El resultado del último `terraform plan`.
* **Compliance_Report:** El output del agente de seguridad.
* **Is_Approved:** Flag booleano gestionado por el nodo HITL.

### B. Ciclo de Autocorrección (Feedback Loop)

Si el **MCP Provisioner** falla durante el `plan`, el **Orchestrator** redirige el flujo al **SRE Diagnostic**. Este agente analiza el error y actualiza el contexto para el **Architect**, quien regenera el HCL corregido, iniciando un nuevo ciclo de validación.

### C. Seguridad y Gobernanza (MCP)

El sistema utiliza servidores MCP para abstraer la complejidad del entorno:

* **Encapsulamiento:** El LLM nunca ve las variables de entorno de AWS.
* **Validación Estática:** El **SecOps Guardian** invoca herramientas como *Checkov* o *TFSec* a través de herramientas MCP antes de permitir el paso al provisionador.

---

## 4. Servidores MCP Utilizados

Para la implementación se requieren los siguientes conectores:

1. **Terraform MCP Server:** Gestión de binarios, inicialización de workspaces y ejecución de comandos.
2. **AWS SDK MCP Server:** Discovery de recursos existentes y validación de cuotas en tiempo real.
3. **Governance MCP Server:** Interfaz con motores de políticas (OPA/Rego) para auditoría de seguridad.
4. **Filesystem MCP Server:** Manejo seguro de archivos temporales y persistencia de estados locales.