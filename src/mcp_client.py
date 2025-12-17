import asyncio
from typing import Dict, List

from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_core.tools import BaseTool


def _build_multi_server_client() -> MultiServerMCPClient:
    config: Dict[str, dict] = {
        "awslabs.aws-documentation-mcp-server": {
            "transport": "streamable_http",
            "url": "https://knowledge-mcp.global.api.aws",
        },
        "aws_documentation": {
            "transport": "stdio",
            "command": "uvx",
            "args": ["awslabs.aws-documentation-mcp-server@latest"],
            "env": {"AWS_REGION": "eu-central-1"},
        },
    }

    return MultiServerMCPClient(config)


async def get_all_tools(client: MultiServerMCPClient) -> List[BaseTool]:
    return await client.get_tools()


def _filter_aws_doc_tools(tools: List[BaseTool]) -> List[BaseTool]:
    allowed = {
        "aws___search_documentation",
        "aws___read_documentation",
        "aws___recommend",
    }
    return [t for t in tools if t.name in allowed]


def get_filtered_aws_doc_tools() -> List[BaseTool]:
    """
    Obtiene y filtra las herramientas de documentación AWS permitidas.
    Esta es la función principal que debería usarse para obtener las herramientas filtradas.
    """
    client = _build_multi_server_client()
    all_tools = asyncio.run(get_all_tools(client))
    return _filter_aws_doc_tools(all_tools)
