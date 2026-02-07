from src.states.graph_state import AgentState
from src.tools.custom_tools import write_terraform_file, execute_terraform_command
from langchain_core.messages import ToolMessage, HumanMessage
from langgraph.types import interrupt
import logging

from src.config import INFRA_WORKSPACE

logger = logging.getLogger(__name__)


def apply_to_workspace_node(state: AgentState):
    """Writes Terraform code to the workspace."""
    logger.debug("--- WRITING FILES TO WORKSPACE ---")
    tf_code = state.get("terraform_code", {})
    
    if not tf_code:
        logger.error("No terraform_code found in state")
        return {"workspace_errors": ["No terraform_code found in state"]}
    
    results = []
    
    try:
        logger.debug(f"Writing {len(tf_code)} Terraform files to workspace")
        for filename, content in tf_code.items():
            if not filename.endswith('.tf'):
                logger.warning(f"File {filename} does not have .tf extension, skipping")
                continue
            result = write_terraform_file.invoke({"content": content, "filename": filename})
            results.append(f"{filename}: {result}")
        logger.debug(f"Files written: {', '.join(results)}")
    except Exception as e:
        logger.error(f"Error writing Terraform files: {e}")
    
    logger.debug("Terraform files written successfully")


def terraform_init_node(state: AgentState):
    """Runs terraform init in the workspace."""
    logger.debug("--- TERRAFORM INIT ---")
    errors = []

    def _is_success(result: str) -> bool:
        return "Success" in result and "Exit code:" not in result

    try:
        fmt_result = execute_terraform_command.invoke({
            "command": "fmt",
            "working_directory": INFRA_WORKSPACE
        })
        logger.debug(f"Terraform fmt completed: {fmt_result[:200]}...")

        init_result = execute_terraform_command.invoke({
            "command": "init",
            "working_directory": INFRA_WORKSPACE
        })
        logger.debug(f"Terraform init completed: {init_result[:200]}...")
        if not _is_success(init_result):
            errors.append(f"terraform init failed: {init_result}")

        validate_result = execute_terraform_command.invoke({
            "command": "validate",
            "working_directory": INFRA_WORKSPACE
        })
        logger.debug(f"Terraform validate completed: {validate_result[:200]}...")
        if not _is_success(validate_result):
            errors.append(f"terraform validate failed: {validate_result}")

        init_success = len(errors) == 0
        if not init_success:
            logger.error(f"Terraform init/validate failed: {errors}")
            return {
                "init_success": False,
                "workspace_errors": errors,
            }
        return {"init_success": True}
    except Exception as e:
        logger.error(f"Error executing terraform init: {e}")
        return {
            "init_success": False,
            "workspace_errors": state.get("workspace_errors", []) + [str(e)],
        }


def terraform_plan_node(state: AgentState):
    """Runs terraform plan and returns the output."""
    logger.debug("--- TERRAFORM PLAN ---")
    
    try:
        plan_result = execute_terraform_command.invoke({
            "command": "plan -no-color -input=false",
            "working_directory": INFRA_WORKSPACE
        })
        
        plan_output = plan_result
        if "Terraform command execution" in plan_result:
            plan_output = plan_result.split("Terraform command execution", 1)[-1]
            if ":\n" in plan_output:
                plan_output = plan_output.split(":\n", 1)[1]
        
        logger.debug("Terraform plan completed")
        
        return {
            "plan_output": plan_output
        }
    except Exception as e:
        logger.error(f"Error executing terraform plan: {e}")
        plan_result = f"Error executing terraform plan: {str(e)}"
        
        return {
            "plan_output": plan_result
        }


def human_approval_node(state: AgentState):
    """Pauses the graph for human review of the terraform plan."""
    decision = interrupt({})

    decision_type = decision.get("type", "reject")
    updates = {"human_decision": decision_type}

    if decision_type == "revise":
        feedback = decision.get("feedback", "")
        updates["messages"] = [HumanMessage(
            content=f"[HUMAN REVIEW] The user rejected the plan and requested changes:\n\n{feedback}\n\nReview the architecture and generate a new TerraformDesign."
        )]

    return updates


def terraform_apply_node(state: AgentState):
    """Runs terraform apply and returns the output."""
    logger.debug("--- TERRAFORM APPLY ---")

    try:
        apply_result = execute_terraform_command.invoke({
            "command": "apply -auto-approve -no-color -input=false",
            "working_directory": INFRA_WORKSPACE
        })

        apply_output = apply_result
        if "Terraform command execution" in apply_result:
            apply_output = apply_result.split("Terraform command execution", 1)[-1]
            if ":\n" in apply_output:
                apply_output = apply_output.split(":\n", 1)[1]

        logger.debug("Terraform apply completed")
        return {"apply_output": apply_output}
    except Exception as e:
        logger.error(f"Error executing terraform apply: {e}")
        return {"apply_output": f"Error executing terraform apply: {str(e)}"}