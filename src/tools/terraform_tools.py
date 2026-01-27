import os
import subprocess
import logging
from langchain_core.tools import tool

logger = logging.getLogger(__name__)

DEFAULT_WORKSPACE = "./infra_workspace"


@tool
def write_terraform_file(content: str, filename: str = "main.tf") -> str:
    """Writes Terraform HCL code to the infrastructure workspace."""
    os.makedirs(DEFAULT_WORKSPACE, exist_ok=True)
    file_path = os.path.join(DEFAULT_WORKSPACE, filename)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
    logger.info(f"Wrote Terraform file: {file_path}")
    return f"Successfully wrote infrastructure code to {file_path}"


@tool
def execute_terraform_command(command: str, working_directory: str = DEFAULT_WORKSPACE) -> str:
    """Execute a Terraform command using tflocal."""
    if not os.path.exists(working_directory):
        return f"Error: Working directory does not exist: {working_directory}"
    
    normalized_command = command.replace("terraform ", "").strip()
    full_command = ["tflocal"] + normalized_command.split()
    
    try:
        result = subprocess.run(
            full_command,
            cwd=working_directory,
            capture_output=True,
            text=True,
            timeout=300,
            check=False
        )
        output = "\n".join([result.stdout or "", result.stderr or ""]).strip()
        status = "Success" if result.returncode == 0 else f"Exit code: {result.returncode}"
        return f"Terraform command execution ({status}):\n{output}"
    except Exception as e:
        return f"Error: {str(e)}"
