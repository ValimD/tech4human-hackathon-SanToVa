"""Ponto de entrada para uma execução local do grafo."""

from .graph import build_graph


def main() -> None:
    graph = build_graph()
    result = graph.invoke(
        {
            "messages": [],
            "user_input": "Não consigo acessar minha conta",
        }
    )
    print(result["response"])


if __name__ == "__main__":
    main()
