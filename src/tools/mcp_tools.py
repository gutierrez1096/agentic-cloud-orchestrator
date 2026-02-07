import asyncio
import logging

from langchain_mcp_adapters.client import MultiServerMCPClient

from src.tools.custom_tools import run_checkov_scan

logger = logging.getLogger(__name__)

MCP_CONFIG = {
    "aws-terraform": {
        "transport": "stdio",
        "command": "uvx",
        "args": ["awslabs.terraform-mcp-server@latest"],
        "env": {
            "AWS_REGION": "eu-central-1",
            "FASTMCP_LOG_LEVEL": "ERROR",
        }
    },
    "aws-pricing": {
        "transport": "stdio",
        "command": "uvx",
        "args": ["awslabs.aws-pricing-mcp-server@latest"],
        "env": {
            "AWS_REGION": "eu-central-1",
        }
    }
}

pricing_client = MultiServerMCPClient({"aws-pricing": MCP_CONFIG["aws-pricing"]})
terraform_client = MultiServerMCPClient({"aws-terraform": MCP_CONFIG["aws-terraform"]})

for tool in asyncio.run(pricing_client.get_tools()):
    logger.debug(f"Pricing Tool: {tool.name}")
for tool in asyncio.run(terraform_client.get_tools()):
    logger.debug(f"Terraform Tool: {tool.name}")


def __filter_terraform_tools(terraform_tools):
    BLOCKED = {"ExecuteTerraformCommand", "execute_terraform_command", "RunCheckovScan", "ExecuteTerragruntCommand"}
    return [t for t in terraform_tools if t.name not in BLOCKED]


def __filter_terraform_tools_for_debugger(terraform_tools):
    """Debugger gets Terraform MCP including ExecuteTerraformCommand; only block Terragrunt and Checkov."""
    BLOCKED = {"RunCheckovScan", "ExecuteTerragruntCommand"}
    return [t for t in terraform_tools if t.name not in BLOCKED]


async def get_iac_debugger_tools():
    """Terraform MCP tools for the IaC Debugger, including ExecuteTerraformCommand."""
    terraform_tools = await terraform_client.get_tools()
    return __filter_terraform_tools_for_debugger(terraform_tools)


async def get_solution_architect_tools():
    pricing_tools = await pricing_client.get_tools()
    terraform_tools = await terraform_client.get_tools()
    safe_terraform_tools = __filter_terraform_tools(terraform_tools)
    return pricing_tools + safe_terraform_tools


async def get_secops_guardian_tools():
    return [run_checkov_scan]
