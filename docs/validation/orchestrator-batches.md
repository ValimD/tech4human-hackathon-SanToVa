# Validação: orquestrador em lotes

Comportamentos derivados da solicitação e de `context-for-mapping`: escutar
até o encerramento MCP, analisar até cinco eventos juntos, despachar incidentes
P0/P1/P2 e mostrar resumos sem dados pessoais.

## Evidências TDD

- `pytest -q tests/test_orchestrator_loop.py`: novos testes inicialmente falharam
  (4 falhas) pela ausência de coleta em lotes, callback de resumo e controle da
  fila sem LLM. Depois da implementação, os testes relevantes passaram.
- `pytest -q tests/test_main.py`: o teste de resumo falhou pela ausência de
  `on_summary`; passou após substituir a impressão de JSON por resumos locais.
- Teste de falha do executor: falhou com RuntimeError antes da implementação;
  passou ao registrar `falhou` e continuar com o restante do lote.

| Garantia | Testes |
| --- | --- |
| Sete eventos geram lotes de cinco e dois | `test_loop_batches_five_and_drains_partial_batch` |
| Fila vazia não invoca modelo | `test_empty_queue_never_calls_model` |
| Cada evento tem exatamente uma decisão, com remetente preservado | `test_missing_decision_rejected_before_dispatch`, `test_batch_rejects_incompatible_decisions` |
| P0/P1/P2 chegam ao executor; outros destinos não executam | `test_dispatch_sends_all_incident_priorities`, `test_unimplemented_destinations_do_not_execute` |
| Falha do executor não descarta os demais eventos | `test_executor_failure_does_not_drop_remaining_events` |
| Terminal omite remetente e motivo livre | `test_loop_prints_compact_summary_without_private_data` |
| Coleta rejeita resposta inválida e erro MCP | `test_batch_rejects_invalid_mcp_response`, `test_mcp_error_is_not_treated_as_idle` |
| Limite opcional de ciclos preservado | `test_max_events_bounds_empty_polling` |

## Verificação final

Comandos executados com os binários de `.venv/bin`:

- `pytest -q --cov=n1_agents --cov-report=term-missing`: PASS, 45 testes, 86%.
- `ruff check .`: PASS.
- `python -m compileall -q src`: PASS.
- `git diff --check`: PASS.
- Revisão de impressão e credenciais nos módulos alterados: sem segredos novos;
  saída do loop limitada a identificadores, destinos, criticidade e estados.
- Tipagem estática: não executada; pyright não disponível/configurado no projeto.
- Docker/MCP/LLM reais: não executados; testes usam serviços simulados.

Sem mudanças de dependências. Sem commits, conforme instrução do repositório.
Alterações locais anteriores preservadas. Avisos de depreciação do LangSmith
aparecem sob Python 3.14 e não falham os testes.

Erros de coleta e contratos inválidos interrompem explicitamente a execução;
ações do executor com falha exigem revisão antes de repetição. As pendências
são visíveis no terminal e no retorno da função, sem nova fila persistente.

## Correção de falhas na coleta MCP

O relato de erro revelou uma mensagem genérica que ocultava o código MCP.
Adicionados testes para 503 no JSON (recuperação e limite de três tentativas),
410 (fim de cenário), 504 sem repetição e processamento do lote parcial antes
da propagação do erro. RED: quatro falhas em `test_event_processor.py` e uma
no novo teste do loop. GREEN: 29 testes relevantes passaram.

Validação completa após a correção: 50 testes passaram, cobertura global 86%;
Ruff, compileall e diff check passaram. A mensagem de erro omite o texto livre
do servidor e preserva o código numérico. O código da falha real relatada não
foi confirmado; não houve execução contra o servidor real.

## Correção do contrato retornado pelo modelo

Reproduzido o erro relatado: `sinais` textual e `relacionados: null` provocavam
ValidationError após a coleta. Normalização anterior à validação preserva texto
em `sinais.resumo` e converte null em coleções vazias. O prompt especifica os
formatos canônicos. Não há inferência de impacto, prioridade ou destino.

RED: quatro testes de normalização/loop falharam; seis testes de rejeição de
tipos e roteamentos inválidos passaram. GREEN: suíte completa com 60 testes
aprovados e cobertura 87%; Ruff e diff check aprovados. O teste integrado
confirma que o handoff de incidente recebe objeto e lista normalizados.
Validação com modelo e MCP simulados; cenário real não executado.
