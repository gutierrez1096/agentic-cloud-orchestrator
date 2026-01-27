from src.states.graph_state import AgentState
from src.tools.terraform_tools import write_terraform_file, execute_terraform_command, DEFAULT_WORKSPACE
from langchain_core.messages import ToolMessage
import logging
import json

logger = logging.getLogger(__name__)

def finalize_architecture_node(state: AgentState):
    logger.info("--- FINALIZING ARCHITECTURE ---")
    messages = state["messages"]
    last_message = messages[-1]
    
    tool_call = last_message.tool_calls[0]
    tool_call_id = tool_call["id"]
    design_args = tool_call["args"]
    
    hcl_code = design_args.get("hcl_code", "")
    rationale = design_args.get("rationale", "")
    
    created_files = []
    files_dict = None
    
    if isinstance(hcl_code, dict):
        files_dict = hcl_code
        created_files = list(files_dict.keys())
        hcl_code = json.dumps(hcl_code)
    else:
        try:
            files_dict = json.loads(hcl_code)
            if isinstance(files_dict, dict):
                created_files = list(files_dict.keys())
        except (json.JSONDecodeError, TypeError):
            created_files = ["main.tf"]
    
    logger.info(f"Arguments extracted - HCL Code length: {len(hcl_code)}, Files: {created_files}")

    output_message = f"Architecture design submitted successfully. Created files: {', '.join(created_files)}. Proceeding to SecOps review."
    
    tool_message = ToolMessage(
        content=output_message,
        tool_call_id=tool_call_id,
        name="TerraformDesign"
    )

    return {
        "terraform_code": hcl_code,
        "architect_rationale": rationale,
        "created_files": created_files,
        "next_step": "SecOps Guardian",
        "messages": [tool_message]
    }

def apply_to_workspace_node(state: AgentState):
    """Escribe el código Terraform al workspace."""
    logger.info("--- WRITING FILES TO WORKSPACE ---")
    tf_code = state["terraform_code"]
    
    messages = []
    results = []
    
    try:
        files_dict = json.loads(tf_code)
        
        if isinstance(files_dict, dict):
            logger.info(f"Writing {len(files_dict)} Terraform files to workspace")
            for filename, content in files_dict.items():
                if not filename.endswith('.tf'):
                    logger.warning(f"File {filename} does not have .tf extension, skipping")
                    continue
                result = write_terraform_file.invoke({"content": content, "filename": filename})
                results.append(f"{filename}: {result}")
            result_message = "\n".join(results)
        else:
            logger.info("Writing single Terraform file to workspace")
            result_message = write_terraform_file.invoke({"content": tf_code})
    except json.JSONDecodeError:
        logger.info("HCL code is not JSON, writing as single file (main.tf)")
        result_message = write_terraform_file.invoke({"content": tf_code})
    except Exception as e:
        logger.error(f"Error writing Terraform files: {e}")
        result_message = f"Error writing Terraform files: {str(e)}"
    
    messages.append(ToolMessage(content=result_message, tool_call_id="call_fs_injection"))
    logger.info("Terraform files written successfully")
    
    return {
        "messages": messages,
        "next_step": "Terraform Init"
    }


def terraform_init_node(state: AgentState):
    """Ejecuta terraform init en el workspace."""
    logger.info("--- TERRAFORM INIT ---")
    
    messages = state.get("messages", [])
    
    try:
        init_result = execute_terraform_command.invoke({
            "command": "init",
            "working_directory": DEFAULT_WORKSPACE
        })
        messages.append(ToolMessage(content=init_result, tool_call_id="call_terraform_init"))
        logger.info("Terraform init completed")
    except Exception as e:
        logger.error(f"Error executing terraform init: {e}")
        init_result = f"Error executing terraform init: {str(e)}"
        messages.append(ToolMessage(content=init_result, tool_call_id="call_terraform_init"))
    
    return {
        "messages": messages,
        "next_step": "Terraform Plan"
    }


def terraform_plan_node(state: AgentState):
    """Ejecuta terraform plan y retorna el output."""
    logger.info("--- TERRAFORM PLAN ---")
    
    messages = state.get("messages", [])
    
    try:
        plan_result = execute_terraform_command.invoke({
            "command": "plan",
            "working_directory": DEFAULT_WORKSPACE
        })
        messages.append(ToolMessage(content=plan_result, tool_call_id="call_terraform_plan"))
        
        plan_output = plan_result
        if "Terraform command execution" in plan_result:
            plan_output = plan_result.split("Terraform command execution", 1)[-1]
            if ":\n" in plan_output:
                plan_output = plan_output.split(":\n", 1)[1]
        
        logger.info("Terraform plan completed")
        
        return {
            "messages": messages,
            "plan_output": plan_output,
            "next_step": "Terraform Plan Complete"
        }
    except Exception as e:
        logger.error(f"Error executing terraform plan: {e}")
        plan_result = f"Error executing terraform plan: {str(e)}"
        messages.append(ToolMessage(content=plan_result, tool_call_id="call_terraform_plan"))
        
        return {
            "messages": messages,
            "plan_output": plan_result,
            "next_step": "Terraform Plan Failed"
        }