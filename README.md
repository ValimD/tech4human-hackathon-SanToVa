# Agentes de Suporte N1

Projeto inicial para criação de agentes com [LangGraph](https://langchain-ai.github.io/langgraph/).

## Arquitetura inicial

```text
src/n1_agents/
├── config.py          # Configuração não sensível por ambiente
├── graph.py           # Orquestração e compilação do grafo
├── main.py            # Execução local
├── state.py           # Contrato de estado compartilhado
└── nodes/
    └── triage.py      # Triagem inicial, isolada e testável
```

O fluxo atual é intencionalmente pequeno:

```text
START → triage → END
```

Novos agentes, ferramentas e integrações devem ser adicionados como módulos
isolados e conectados ao grafo somente quando houver um caso de uso definido.

## Preparação

Requer Python 3.11 ou superior.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
cp .env.example .env
```

## Executar

```bash
python -m n1_agents.main
```

## Testar e verificar

```bash
pytest
ruff check .
```

As credenciais e chaves de provedores devem permanecer em variáveis de ambiente;
nenhuma chave é necessária para executar o fluxo inicial de triagem.
