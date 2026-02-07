import asyncio
import logging

from langchain_core.tools import StructuredTool
from langchain_mcp_adapters.client import MultiServerMCPClient

from src.tools.custom_tools import run_checkov_scan

logger = logging.getLogger(__name__)

SEARCH_AWS_DOCS_MAX_CHARS = 4000
TRUNCATION_SUFFIX = "\n\n[Documentation truncated to reduce context size.]"

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


def __wrap_search_aws_provider_docs(original_tool):
    """Wrap SearchAwsProviderDocs to truncate response and reduce context size."""

    async def _wrapped(**kwargs):
        result = await original_tool.ainvoke(kwargs)
        if not isinstance(result, str):
            result = str(result)
        if len(result) > SEARCH_AWS_DOCS_MAX_CHARS:
            return result[:SEARCH_AWS_DOCS_MAX_CHARS] + TRUNCATION_SUFFIX
        return result

    return StructuredTool.from_function(
        name=original_tool.name,
        description=original_tool.description,
        args_schema=getattr(original_tool, "args_schema", None),
        coroutine=_wrapped,
    )


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
    search_docs_tool = next((t for t in safe_terraform_tools if t.name == "SearchAwsProviderDocs"), None)
    other_terraform_tools = [t for t in safe_terraform_tools if t.name != "SearchAwsProviderDocs"]
    if search_docs_tool is None:
        return pricing_tools + safe_terraform_tools
    wrapped_search_docs = __wrap_search_aws_provider_docs(search_docs_tool)
    return pricing_tools + [wrapped_search_docs] + other_terraform_tools


async def get_secops_guardian_tools():
    return [run_checkov_scan]
