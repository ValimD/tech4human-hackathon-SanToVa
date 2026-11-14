# Instruções para agentes do GitHub Copilot

Este é um projeto Python de agentes de suporte N1 baseado em LangGraph.
Consulte [`AGENTS.md`](../AGENTS.md) antes de qualquer alteração: ele contém a
stack, a arquitetura, os comandos de validação e as regras de segurança.

Resumo obrigatório:

- Use Python 3.11+, layout `src/`, pytest e Ruff.
- Mantenha o estado dos grafos em `src/n1_agents/state.py`.
- Mantenha nós pequenos e testáveis em `src/n1_agents/nodes/`.
- Monte e compile grafos somente em `src/n1_agents/graph.py`.
- Mantenha o executor de incidentes em `src/n1_agents/incident_agent.py`,
  usando o contrato estruturado `IncidentHandoff`/`IncidentResult`.
- O agente de incidentes deve chamar o MCP como `agente-incidente`; o
  orquestrador usa `orquestrador`.
- Escreva testes antes da implementação de novos comportamentos.
- Execute `pytest -q --cov=n1_agents --cov-report=term-missing` e `ruff check .`.
- Nunca exponha credenciais ou dados sensíveis; não leia nem versiona `.env`.
