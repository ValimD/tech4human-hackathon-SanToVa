"""Execução do agente de incidentes via terminal."""

import sys

from .config import get_settings
from .incident_agent import IncidentHandoff, run_incident_agent
from .mcp_client import MCPClient
from .model import create_chat_model


def main() -> None:
    payload = " ".join(sys.argv[1:]).strip()
    if not payload:
        payload = input("Handoff JSON: ").strip()

    handoff = IncidentHandoff.model_validate_json(payload)
    settings = get_settings()
    with MCPClient(
        settings.mcp_endpoint,
        timeout=settings.mcp_timeout_seconds,
    ) as client:
        result = run_incident_agent(
            handoff,
            model=create_chat_model(),
            client=client,
        )
    print(result.model_dump_json())


if __name__ == "__main__":
    main()
