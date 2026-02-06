from src.states.graph_state import AgentState
from src.tools.terraform_tools import write_terraform_file, execute_terraform_command
from langchain_core.messages import ToolMessage
import logging

from src.config import INFRA_WORKSPACE

logger = logging.getLogger(__name__)


def apply_to_workspace_node(state: AgentState):
    """Escribe el código Terraform al workspace."""
    logger.info("--- WRITING FILES TO WORKSPACE ---")
    tf_code = state.get("terraform_code", {})
    
    if not tf_code:
        logger.error("No terraform_code found in state")
        return {"workspace_errors": ["No terraform_code found in state"]}
    
    results = []
    
    try:
        logger.info(f"Writing {len(tf_code)} Terraform files to workspace")
        for filename, content in tf_code.items():
            if not filename.endswith('.tf'):
                logger.warning(f"File {filename} does not have .tf extension, skipping")
                continue
            result = write_terraform_file.invoke({"content": content, "filename": filename})
            results.append(f"{filename}: {result}")
        logger.info(f"Files written: {', '.join(results)}")
    except Exception as e:
        logger.error(f"Error writing Terraform files: {e}")
    
    logger.info("Terraform files written successfully")


def terraform_init_node(state: AgentState):
    """Ejecuta terraform init en el workspace."""
    logger.info("--- TERRAFORM INIT ---")
    
    try:
        fmt_result = execute_terraform_command.invoke({
            "command": "fmt",
            "working_directory": INFRA_WORKSPACE
        })
        logger.info(f"Terraform fmt completed: {fmt_result[:200]}...")

        init_result = execute_terraform_command.invoke({
            "command": "init",
            "working_directory": INFRA_WORKSPACE
        })
        logger.info(f"Terraform init completed: {init_result[:200]}...")
        
        validate_result = execute_terraform_command.invoke({
            "command": "validate",
            "working_directory": INFRA_WORKSPACE
        })
        logger.info(f"Terraform validate completed: {validate_result[:200]}...")
    
    except Exception as e:
        logger.error(f"Error executing terraform init: {e}")


def terraform_plan_node(state: AgentState):
    """Ejecuta terraform plan y retorna el output."""
    logger.info("--- TERRAFORM PLAN ---")
    
    try:
        plan_result = execute_terraform_command.invoke({
            "command": "plan",
            "working_directory": INFRA_WORKSPACE
        })
        
        plan_output = plan_result
        if "Terraform command execution" in plan_result:
            plan_output = plan_result.split("Terraform command execution", 1)[-1]
            if ":\n" in plan_output:
                plan_output = plan_output.split(":\n", 1)[1]
        
        logger.info("Terraform plan completed")
        
        return {
            "plan_output": plan_output
        }
    except Exception as e:
        logger.error(f"Error executing terraform plan: {e}")
        plan_result = f"Error executing terraform plan: {str(e)}"
        
        return {
            "plan_output": plan_result
        }