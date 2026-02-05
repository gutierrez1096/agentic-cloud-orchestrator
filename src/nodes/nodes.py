from src.states.graph_state import AgentState
from src.tools.terraform_tools import write_terraform_file, execute_terraform_command, DEFAULT_WORKSPACE
from langchain_core.messages import ToolMessage
import logging

logger = logging.getLogger(__name__)


def apply_to_workspace_node(state: AgentState):
    """Escribe el código Terraform al workspace."""
    logger.info("--- WRITING FILES TO WORKSPACE ---")
    tf_code = state["terraform_code"]  # Ya es Dict[str, str]
    
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
    
    return {
        "next_step": "SecOps Guardian"
    }


def terraform_init_node(state: AgentState):
    """Ejecuta terraform init en el workspace."""
    logger.info("--- TERRAFORM INIT ---")
    
    try:
        init_result = execute_terraform_command.invoke({
            "command": "init",
            "working_directory": DEFAULT_WORKSPACE
        })
        logger.info(f"Terraform init completed: {init_result[:200]}...")
    except Exception as e:
        logger.error(f"Error executing terraform init: {e}")
    
    return {
        "next_step": "Terraform Plan"
    }


def terraform_plan_node(state: AgentState):
    """Ejecuta terraform plan y retorna el output."""
    logger.info("--- TERRAFORM PLAN ---")
    
    try:
        plan_result = execute_terraform_command.invoke({
            "command": "plan",
            "working_directory": DEFAULT_WORKSPACE
        })
        
        plan_output = plan_result
        if "Terraform command execution" in plan_result:
            plan_output = plan_result.split("Terraform command execution", 1)[-1]
            if ":\n" in plan_output:
                plan_output = plan_output.split(":\n", 1)[1]
        
        logger.info("Terraform plan completed")
        
        return {
            "plan_output": plan_output,
            "next_step": "Terraform Plan Complete"
        }
    except Exception as e:
        logger.error(f"Error executing terraform plan: {e}")
        plan_result = f"Error executing terraform plan: {str(e)}"
        
        return {
            "plan_output": plan_result,
            "next_step": "Terraform Plan Failed"
        }


def process_security_review_node(state: AgentState):
    """Procesa el veredicto de SecurityReview y actualiza el estado."""
    logger.info("--- PROCESSING SECURITY REVIEW ---")
    messages = state["messages"]
    last_message = messages[-1]
    
    tool_call = last_message.tool_calls[0]
    tool_call_id = tool_call["id"]
    args = tool_call["args"]
    
    is_approved = args.get("is_approved", False)
    risk_analysis = args.get("risk_analysis", "")
    required_changes = args.get("required_changes", [])
    
    logger.info(f"Security Review Verdict: {'APPROVED' if is_approved else 'REJECTED'}")
    
    if is_approved:
        output_message = f"Security Review APPROVED. {risk_analysis}"
    else:
        output_message = f"Security Review REJECTED. {risk_analysis}. Required changes: {required_changes}"
    
    tool_message = ToolMessage(
        content=output_message,
        tool_call_id=tool_call_id,
        name="SecurityReview"
    )
    
    return {
        "is_approved": is_approved,
        "messages": [tool_message],
        "errors": required_changes if not is_approved else [],
        "next_step": "Terraform Init" if is_approved else "Solution Architect"
    }