from n1_agents import main as main_module


class FakeGraph:
    def invoke(self, state):
        return {"response": f"Recebido: {state['user_input']}"}


class FakeMCPClient:
    def __init__(self, endpoint, timeout):
        self.endpoint = endpoint
        self.timeout = timeout

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None


def test_main_accepts_a_prompt_as_argument(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        main_module,
        "build_graph",
        lambda model, tools: FakeGraph(),
    )
    monkeypatch.setattr(main_module, "MCPClient", FakeMCPClient)
    monkeypatch.setattr(main_module, "create_mcp_tools", lambda client, agent_name: [])
    monkeypatch.setattr(main_module, "create_chat_model", lambda: object())
    monkeypatch.setattr(main_module.sys, "argv", ["n1_agents.main", "Olá", "agente"])

    main_module.main()

    assert capsys.readouterr().out == "Recebido: Olá agente\n"


def test_loop_prints_compact_summary_without_private_data(monkeypatch, capsys):
    from n1_agents.orchestrator_loop import OrchestratorDecision

    def loop(prompt, **kwargs):
        assert prompt
        kwargs["on_summary"]("Lote: 5 eventos.")
        kwargs["on_result"](
            OrchestratorDecision(
                evento_id="PED-1",
                destino="seguranca",
                remetente="privado@exemplo.com",
                motivo="conteudo privado",
            )
        )

    monkeypatch.setattr(main_module, "run_orchestrator_loop", loop)
    monkeypatch.setattr(main_module, "MCPClient", FakeMCPClient)
    monkeypatch.setattr(main_module, "create_chat_model", lambda: object())
    monkeypatch.setattr(main_module.sys, "argv", ["n1_agents.main", "--loop"])
    monkeypatch.setattr("builtins.input", lambda _: "Leia eventos")
    main_module.main()
    output = capsys.readouterr().out
    assert "Lote: 5" in output
    assert "revisão humana" in output
    assert "privado" not in output
