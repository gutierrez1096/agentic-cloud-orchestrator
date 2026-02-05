from langchain_mcp_adapters.client import MultiServerMCPClient
import logging
import asyncio
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

async def get_solution_architect_tools():
    pricing_tools = await pricing_client.get_tools()
    terraform_tools = await terraform_client.get_tools()
    
    BLOCKED_TOOLS = {"ExecuteTerraformCommand", "execute_terraform_command"}
    safe_terraform_tools = [t for t in terraform_tools if t.name not in BLOCKED_TOOLS]
    
    return pricing_tools + safe_terraform_tools

async def get_secops_guardian_tools():
    terraform_tools = await terraform_client.get_tools()
    return terraform_tools