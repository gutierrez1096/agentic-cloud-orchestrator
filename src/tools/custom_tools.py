import os
import sys
import subprocess
import shutil
import logging
from langchain_core.tools import tool

from src.config import INFRA_WORKSPACE, PROTECTED_TERRAFORM_FILES

logger = logging.getLogger(__name__)

CHECKOV_PATH = shutil.which("checkov", path=os.path.dirname(sys.executable)) or shutil.which("checkov")

TERRAFORM_PATH = shutil.which("tflocal", path=os.path.dirname(sys.executable)) or shutil.which("tflocal")

@tool
def write_terraform_file(content: str, filename: str = "main.tf") -> str:
    """Writes Terraform HCL code to the infrastructure workspace."""
    if filename in PROTECTED_TERRAFORM_FILES:
        logger.warning(f"Attempted to write to protected file: {filename}")
        return f"Error: '{filename}' is a protected file and cannot be modified. This file contains critical infrastructure configuration."
    
    os.makedirs(INFRA_WORKSPACE, exist_ok=True)
    file_path = os.path.join(INFRA_WORKSPACE, filename)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
    logger.info(f"Wrote Terraform file: {file_path}")
    return f"Successfully wrote infrastructure code to {file_path}"


@tool
def execute_terraform_command(command: str, working_directory: str = INFRA_WORKSPACE) -> str:
    """Execute a Terraform command using tflocal."""

    if not os.path.exists(working_directory):
        return f"Error: Working directory does not exist: {working_directory}"

    logger.info(f"Terraform path: {TERRAFORM_PATH}")
    
    normalized_command = command.replace("terraform ", "").strip()
    full_command = [TERRAFORM_PATH] + normalized_command.split()

    logger.info(f"Executing Terraform command: {full_command}")
    
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


@tool(
    "RunCheckovScan"
)
def run_checkov_scan(working_directory: str = INFRA_WORKSPACE, framework: str = "terraform") -> str:
    """Run Checkov security scan on Terraform code to identify vulnerabilities and misconfigurations."""
    
    if not os.path.exists(working_directory):
        return f"Error: Working directory does not exist: {working_directory}"

    try:
        result = subprocess.run(
            [CHECKOV_PATH, "-d", working_directory, "--framework", framework,"--quiet", "--compact", "--skip-check", "LOW"],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
        output = result.stdout.strip() or result.stderr.strip()
        logger.info(f"Checkov output: {output}")
        if not output:
            return "Checkov executed but produced no output (exit code: {}).".format(result.returncode)
        return output
    except Exception as e:
        return f"Error running checkov: {e}"