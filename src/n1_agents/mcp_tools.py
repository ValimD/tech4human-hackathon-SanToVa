"""Adaptação das ferramentas MCP para tool calling do LangChain."""

from typing import Any, Protocol

from langchain_core.tools import StructuredTool
from pydantic import create_model

from .event_processor import _decode_tool_result

ORCHESTRATOR_TOOL_NAMES = frozenset(
    {
        "proximo_evento",
        "listar_eventos",
        "ler_evento",
        "listar_bases",
        "consultar",
        "registrar_conversa",
    }
)
INCIDENT_TOOL_NAMES = frozenset(
    {
        "consultar",
        "listar_bases",
        "registrar",
        "atualizar",
        "enviar_mensagem",
        "registrar_conversa",
    }
)


class MCPToolProvider(Protocol):
    """Contrato necessário para criar ferramentas MCP."""

    def list_tools(self) -> list[dict[str, Any]]:
        """Lista as ferramentas publicadas."""

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Executa uma ferramenta."""


def _python_type(schema: dict[str, Any]) -> type:
    return {
        "string": str,
        "integer": int,
        "number": float,
        "boolean": bool,
        "array": list,
        "object": dict,
    }.get(schema.get("type"), Any)


def _args_schema(spec: dict[str, Any]):
    input_schema = spec.get("inputSchema", {})
    properties = input_schema.get("properties", {})
    required = set(input_schema.get("required", [])) - {"agente"}
    fields = {
        name: (
            _python_type(schema),
            ... if name in required else None,
        )
        for name, schema in properties.items()
        if name != "agente"
    }
    return create_model(f"{spec['name'].title()}Arguments", **fields)


def create_mcp_tools(
    client: MCPToolProvider,
    *,
    agent_name: str,
    allowed_names: frozenset[str] | None = None,
) -> list[StructuredTool]:
    """Converte as ferramentas MCP publicadas em tools chamáveis pelo modelo."""

    permitted_names = (
        ORCHESTRATOR_TOOL_NAMES if allowed_names is None else allowed_names
    )
    tools: list[StructuredTool] = []
    for spec in client.list_tools():
        name = spec["name"]
        if name not in permitted_names:
            continue
        description = spec.get("description", f"Ferramenta MCP {name}.")
        args_schema = _args_schema(spec)

        def call_tool(_name=name, **arguments: Any) -> dict[str, Any]:
            result = client.call_tool(
                _name,
                {"agente": agent_name, **arguments},
            )
            return _decode_tool_result(result)

        tools.append(
            StructuredTool.from_function(
                call_tool,
                name=name,
                description=description,
                args_schema=args_schema,
            )
        )
    return tools
