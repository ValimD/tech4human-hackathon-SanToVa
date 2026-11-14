from n1_agents.config import get_settings
from n1_agents.graph import build_graph
from n1_agents.main import main
from n1_agents.nodes.triage import classify_intent


def test_graph_routes_a_ticket_to_the_n1_queue() -> None:
    graph = build_graph()

    result = graph.invoke(
        {
            "messages": [],
            "user_input": "Não consigo acessar minha conta",
        }
    )

    assert result["intent"] == "access"
    assert result["queue"] == "n1"
    assert result["status"] == "triaged"


def test_graph_keeps_the_original_request_in_the_state() -> None:
    graph = build_graph()
    request = "O sistema está muito lento hoje"

    result = graph.invoke({"messages": [], "user_input": request})

    assert result["user_input"] == request
    assert result["response"]


def test_unknown_request_is_classified_as_general() -> None:
    assert classify_intent("Preciso de uma orientação") == "general"


def test_graph_rejects_an_empty_request() -> None:
    graph = build_graph()

    try:
        graph.invoke({"messages": [], "user_input": " "})
    except ValueError as error:
        assert str(error) == "user_input não pode ser vazio"
    else:
        raise AssertionError("A triagem deveria rejeitar uma solicitação vazia")


def test_settings_are_loaded_from_environment(monkeypatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "test")

    assert get_settings().environment == "test"


def test_main_prints_the_triage_response(capsys) -> None:
    main()

    assert "encaminhada para o suporte N1" in capsys.readouterr().out
