import json
import logging
import os

from langchain_core.messages import ToolMessage, HumanMessage
from langgraph.types import interrupt

from src.config import INFRA_WORKSPACE
from src.states.graph_state import AgentState
from src.tools.custom_tools import write_terraform_file, execute_terraform_command

logger = logging.getLogger(__name__)


def _is_terraform_success(result: str) -> bool:
    """True if Terraform command output indicates success (no Exit code)."""
    return "Success" in result and "Exit code:" not in result


def _plan_summary_from_json(workspace: str) -> str:
    """Resumen Add/Change/Delete desde terraform show -json tfplan."""
    plan_path = os.path.join(workspace, "tfplan")
    if not os.path.exists(plan_path):
        return ""
    try:
        raw = execute_terraform_command.invoke({"command": "show -json tfplan", "working_directory": workspace})
        if ":\n" in raw:
            raw = raw.split(":\n", 1)[1]
        data = json.loads(raw)
        cambios = data.get("resource_changes", [])
        detalles = [str(c.get("change", {}).get("actions", [])) for c in cambios]
        add = sum(1 for x in detalles if "create" in x)
        change = sum(1 for x in detalles if "update" in x)
        delete = sum(1 for x in detalles if "delete" in x)
        return f"Add: {add}, Change: {change}, Delete: {delete}"
    except Exception as e:
        logger.debug(f"Could not build plan summary: {e}")
        return ""


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
        if not _is_terraform_success(init_result):
            errors.append(f"terraform init failed: {init_result}")

        validate_result = execute_terraform_command.invoke({
            "command": "validate",
            "working_directory": INFRA_WORKSPACE
        })
        logger.debug(f"Terraform validate completed: {validate_result[:200]}...")
        if not _is_terraform_success(validate_result):
            errors.append(f"terraform validate failed: {validate_result}")

        init_success = len(errors) == 0
        if not init_success:
            logger.error(f"Terraform init/validate failed: {errors}")
            return {
                "init_success": False,
                "workspace_errors": errors,
            }
        return {"init_success": True, "debugger_init_attempts": 0}
    except Exception as e:
        logger.error(f"Error executing terraform init: {e}")
        return {
            "init_success": False,
            "workspace_errors": state.get("workspace_errors", []) + [str(e)],
        }


def terraform_plan_node(state: AgentState):
    """Runs terraform plan -out=tfplan and returns output + summary."""
    logger.debug("--- TERRAFORM PLAN ---")
    try:
        plan_result = execute_terraform_command.invoke({
            "command": "plan -no-color -input=false -out=tfplan",
            "working_directory": INFRA_WORKSPACE
        })
        plan_output = plan_result
        if "Terraform command execution" in plan_result:
            plan_output = plan_result.split("Terraform command execution", 1)[-1]
            if ":\n" in plan_output:
                plan_output = plan_output.split(":\n", 1)[1]
        plan_success = _is_terraform_success(plan_result)
        plan_summary = _plan_summary_from_json(INFRA_WORKSPACE) if plan_success else ""
        updates = {"plan_output": plan_output, "plan_summary": plan_summary or "", "plan_success": plan_success}
        if plan_success:
            updates["debugger_plan_attempts"] = 0
        updates["review_iterations"] = 0
        return updates
    except Exception as e:
        logger.error(f"Error executing terraform plan: {e}")
        return {"plan_output": f"Error executing terraform plan: {str(e)}", "plan_summary": "", "plan_success": False}


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
    """Runs terraform apply tfplan and returns output + summary (from plan)."""
    logger.debug("--- TERRAFORM APPLY ---")
    try:
        apply_result = execute_terraform_command.invoke({
            "command": "apply -auto-approve -no-color tfplan",
            "working_directory": INFRA_WORKSPACE
        })
        apply_output = apply_result
        if "Terraform command execution" in apply_result:
            apply_output = apply_result.split("Terraform command execution", 1)[-1]
            if ":\n" in apply_output:
                apply_output = apply_output.split(":\n", 1)[1]
        apply_success = _is_terraform_success(apply_result)
        apply_summary = state.get("plan_summary", "") or "Applied."
        updates = {"apply_output": apply_output, "apply_summary": apply_summary, "apply_success": apply_success}
        if apply_success:
            updates["debugger_apply_attempts"] = 0
        return updates
    except Exception as e:
        logger.error(f"Error executing terraform apply: {e}")
        return {"apply_output": f"Error executing terraform apply: {str(e)}", "apply_summary": "", "apply_success": False}