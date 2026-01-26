# agentic-cloud-orchestrator
Multi-agent orchestrator for autonomous cloud infrastructure deployment using LangGraph, Terraform, and Model Context Protocol (MCP).

---

## 1. Objetivo del Sistema

El objetivo principal es desarrollar un **Orquestador Multi-Agente Inteligente** capaz de transformar requerimientos de infraestructura en lenguaje natural en despliegues reales, seguros y validados en **AWS**.

A diferencia de un script de automatización tradicional, este sistema busca:

* **Abstracción Semántica:** Que el usuario no necesite conocer la sintaxis de Terraform, solo el objetivo de negocio.
* **Resiliencia Autónoma (Self-healing):** Capacidad de detectar fallos en la fase de `plan` o `validate` y corregirlos mediante razonamiento antes de la intervención humana.
* **Gobernanza mediante MCP:** Utilizar el **Model Context Protocol** como estándar de desacoplamiento entre la lógica del modelo y la ejecución técnica en la nube.

---

## 2. Los Agentes (Especialistas Funcionales)

Para cumplir con el requisito multi-agente, dividiremos las responsabilidades en roles especializados que interactúan sobre un estado compartido.

| Agente | Entrada | Acción Principal | Salida |
| :--- | :--- | :--- | :--- |
| **Supervisor** | Petición Usuario | Orquestación y Gestión de Estado | Delegación a Agentes |
| **Architect** | Petición Natural | Seleccionar Módulo y Región | HCL Template |
| **DevOps** | HCL Template | Generar .tfvars y escribir archivos | Workspace listo |
| **Executor** | Filesystem | terraform plan vía MCP | Plan o Error |
| **SRE** | HCL + Error | Diagnosticar y corregir | HCL Corregido |
| **Applier** | Aprobación | terraform apply final | Infra Real |

---

## 3. El Sistema Agéntico (Arquitectura del Grafo)

El sistema se define como un **Grafo de Estados Cíclico Dirigido** implementado en **LangGraph**. Los pilares de este sistema son:

### A. El Estado Compartido (`State`)

Es la "fuente única de verdad". Contiene:

* El historial de la conversación.
* El código HCL y variables generadas.
* El **Plan de Ejecución** devuelto por Terraform.
* Un marcador de aprobación humana.

### B. El Ciclo de Control (Feedback Loop)

Basado en patrones de diseño de sistemas autónomos, el sistema no avanza linealmente. Si el nodo de **Ejecución (MCP)** detecta un error de sintaxis o de políticas de AWS, el flujo retrocede al **Diagnosticador**, creando un bucle de corrección hasta que el estado sea válido.

### C. Human-in-the-Loop (HITL)

El sistema integra una **interrupción física** (breakpoint). El grafo se pausa tras generar el `terraform plan`.

* **Justificación Académica:** En un entorno de infraestructura, la autonomía total sin supervisión es un riesgo crítico. El TFG demuestra cómo la IA puede asistir al humano sin reemplazar el juicio final de seguridad.

### D. Integración MCP (La Capa de Abstracción)

El orquestador no "lanza" procesos de shell directamente. Utiliza el **AWS Terraform MCP Server** para:

* Consultar esquemas de recursos.
* Ejecutar validaciones estáticas (Checkov).
* Realizar el despliegue final.

---

## Posibles MCP Servers

MCP Server para Terraform
MCP Server para AWS
MCP Server para Gobernanza
MCP Server para Git