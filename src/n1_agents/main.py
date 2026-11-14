"""Ponto de entrada para uma execução local do grafo."""

import sys

from .config import get_settings
from .graph import build_graph
from .incident_agent import IncidentResult
from .mcp_client import MCPClient
from .mcp_tools import create_mcp_tools
from .model import create_chat_model
from .orchestrator_loop import run_orchestrator_loop


def main() -> None:
    loop_mode = "--loop" in sys.argv[1:]
    arguments = [argument for argument in sys.argv[1:] if argument != "--loop"]
    user_input = " ".join(arguments).strip()
    if not user_input:
        user_input = (
            "Processe os eventos disponíveis"
            if loop_mode
            else input("Prompt: ").strip()
        )

    settings = get_settings()
    with MCPClient(
        settings.mcp_endpoint,
        timeout=settings.mcp_timeout_seconds,
    ) as client:
        if loop_mode:

            def print_result(result) -> None:
                if isinstance(result, IncidentResult):
                    detail = f"incidente {result.criticidade}: {result.acao}"
                    if result.acao == "falhou":
                        detail += "; revisão humana prioritária"
                elif result.destino == "incidente":
                    detail = f"incidente {result.criticidade}: encaminhando"
                else:
                    detail = (
                        f"{result.destino}: pendente de revisão humana (sem executor)"
                    )
                # Não imprime corpo, remetente, sinais ou texto livre do modelo.
                print(f"{result.evento_id!r}: {detail}", flush=True)

            run_orchestrator_loop(
                user_input,
                client=client,
                model=create_chat_model(),
                on_result=print_result,
                on_summary=lambda message: print(message, flush=True),
            )
            return

        tools = create_mcp_tools(client, agent_name=settings.agent_name)
        graph = build_graph(model=create_chat_model(), tools=tools)
        result = graph.invoke(
            {
                "messages": [],
                "user_input": user_input,
            }
        )
    print(result["response"])


if __name__ == "__main__":
    main()
