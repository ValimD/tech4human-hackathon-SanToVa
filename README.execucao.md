# Guia de execução

Este guia executa o orquestrador e o agente de incidentes P0/P1/P2 contra o
servidor MCP do desafio. Use dois terminais: um para o servidor Docker e outro
para os agentes Python.

## 1. Pré-requisitos

- Python 3.11 ou superior, com `pip` e `venv`.
- Docker com Docker Compose para executar o servidor MCP.
- Pasta do servidor MCP compartilhado pelo desafio (não incluída neste repositório).
- Chave válida para o endpoint LiteLLM do hackathon.

Os comandos abaixo usam Bash e devem ser executados na raiz deste repositório,
exceto os comandos do servidor, executados na pasta dele.

## 2. Preparar os agentes

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

Crie o arquivo de configuração se ele ainda não existir:

```bash
if [ ! -f .env ]; then cp .env.example .env; fi
```

Edite `.env`, mantendo a chave apenas no ambiente local:

```dotenv
MODEL_NAME=claude-sonnet-5
MODEL_BASE_URL=https://litellm.tech4humans.com.br/v1/chat/completions
OPENAI_API_KEY=preencha_com_sua_chave
MCP_ENDPOINT=http://localhost:8765/mcp
MCP_TIMEOUT_SECONDS=15
```

O programa carrega `.env` automaticamente. Não versione esse arquivo.
Se o servidor estiver em outra máquina ou porta, ajuste `MCP_ENDPOINT`.

## 3. Iniciar o servidor MCP — terminal 1

Na pasta do **servidor MCP compartilhado**, execute:

```bash
TEMA=triagem docker compose up --build mundo
```

O painel fica em <http://localhost:8765> e o endpoint dos agentes em
`http://localhost:8765/mcp`.

Para uma rodada sem as falhas simuladas do desafio:

```bash
TEMA=triagem ERROS=0 docker compose up --build mundo
```

Prepare o ambiente dos agentes antes de iniciar o servidor: o relógio do cenário
começa com ele. Segundo o contexto fornecido, o cenário padrão dura cerca de
20 minutos reais e distribui os eventos ao longo desse período.

## 4. Executar os dois agentes — terminal 2

Na raiz deste repositório:

```bash
source .venv/bin/activate
python -m n1_agents.main --loop
```

Esse comando inicia o orquestrador e chama automaticamente o executor de
incidentes quando necessário. **Não é preciso abrir outro processo para o
agente de incidentes.**

O fluxo é:

1. Coletar até **5 eventos** com chamadas sequenciais a `proximo_evento`.
2. Classificar o lote inteiro; se houver menos de 5, processar o lote parcial.
3. Encaminhar incidentes **P0, P1 e P2** ao `agente-incidente`, por prioridade.
4. Sinalizar `seguranca`, `ferias` e `chamado` para revisão humana, pois esses
   executores ainda não existem.
5. Buscar o próximo lote até o MCP informar `encerrado: true`.

Na resposta do modelo, `sinais` deve ser um objeto e `relacionados` uma lista.
Por compatibilidade, sinais em texto são preservados como `{"resumo": "texto"}`;
`sinais: null` vira `{}` e `relacionados: null` vira `[]`. Outros tipos inválidos
continuam sendo rejeitados, assim como destinos e criticidades desconhecidos.

A primeira leitura pode esperar até 10 segundos. As demais leituras do lote não
esperam novos eventos. Fila vazia não chama o modelo, e os resumos são gerados
localmente, sem consumir tokens de LLM.

Exemplo ilustrativo de saída:

```text
Lote: 5 eventos; total recebido: 5.
'PED-029': incidente P0: encaminhando
'PED-029': incidente P0: aberto
'PED-013': ferias: pendente de revisão humana (sem executor)
Fila vazia; aguardando eventos no MCP.
MCP encerrado; 60 eventos recebidos.
```

Os números e resultados variam conforme a rodada. O resumo não imprime corpos
de mensagens, remetentes ou justificativas livres do modelo.

## 5. Acompanhar e encerrar

Acompanhe os resumos no terminal dos agentes e as ações no painel do MCP.

- `evento: null`: a fila está temporariamente vazia; o agente continua esperando.
- `encerrado: true` sem evento (`evento: null`): o cenário terminou; o loop
  encerra normalmente. Se `encerrado: true` vier junto com um evento, esse
  evento é processado e o agente faz uma última leitura para confirmar o
  encerramento. O contêiner
  pode continuar ativo para consulta ao painel.
- `Ctrl+C` no terminal dos agentes: interrompe o processamento local.
- `Ctrl+C` no terminal do Docker Compose: interrompe o servidor iniciado em
  primeiro plano.

Uma falha explícita no executor aparece como `falhou`, com revisão humana
prioritária, e os demais eventos do lote continuam. Erros de coleta, transporte
ou contratos inválidos podem interromper a execução e precisam ser investigados.
Antes de repetir uma ação com falha, confira no MCP se ela já foi executada.

Na coleta, erros 503 no JSON da ferramenta recebem até três tentativas, com
pausa de 0,5 segundo. O código 410 indica fim do cenário. Outras falhas mostram
o código retornado pelo MCP; os eventos já coletados são processados antes
de propagar esse erro. Um 504 não é repetido automaticamente, porque a leitura
pode já ter marcado um evento como lido. Consulte o painel/log do servidor.


As pendências aparecem no terminal e no retorno da função; não há fila
persistente local. Reiniciar os agentes não garante reprocessar eventos já
marcados como lidos pelo servidor.

## Diagnóstico da conexão

Com o MCP ativo:

```bash
python -m n1_agents.mcp_diagnostics
```

O comando consulta `listar_eventos`, sem marcar eventos como lidos ou responder
mensagens. Não precisa da chave do LLM. Uma lista vazia pode significar que o
cenário ainda não liberou eventos.

| Sintoma | Verificação |
| --- | --- |
| `python: command not found` | Use `python3` para criar o ambiente e ative `.venv`. |
| `No module named n1_agents` | Ative `.venv` e execute a instalação editável da etapa 2. |
| Chave ausente ou erro de autenticação do modelo | Confira `OPENAI_API_KEY` e o acesso ao endpoint configurado. |
| Conexão MCP recusada | Confira o terminal do Docker, a porta publicada e `MCP_ENDPOINT`. |
| Timeout MCP | Mantenha `MCP_TIMEOUT_SECONDS` em pelo menos 15 e confira o servidor. |
| Tools obrigatórias de incidente ausentes | Confira se o MCP publica `consultar`, `registrar`, `atualizar` e `enviar_mensagem`. |
| Fila vazia após encerrar o cenário | Inicie uma nova rodada conforme as instruções do servidor. |

## Execuções opcionais

### Uma interação com o orquestrador

```bash
python -m n1_agents.main "Como redefino minha senha?"
```

Sem `--loop`, o programa faz uma execução do grafo; não fica ouvindo eventos
continuamente. Sem argumentos, pede um prompt no terminal.

### Um incidente manual

Use um evento real da rodada e adapte os campos abaixo. Este comando pode
registrar/atualizar incidentes e enviar mensagens ao time de Produto:

```bash
python -m n1_agents.incident_main \
  '{"evento_id":"PED-029","remetente":"ana@t4h.exemplo","destino":"incidente","criticidade":"P0","categoria":"incidente_produto","produto":"Portal do Cliente","motivo":"Produto fora do ar para todos."}'
```

## Testes locais

Os testes usam serviços simulados; não exigem Docker nem chave do LLM:

```bash
source .venv/bin/activate
pytest -q --cov=n1_agents --cov-report=term-missing
ruff check .
```

## Contexto de referência

- [Servidor MCP](context-for-mapping/contexto%28server_mcp%29.md)
- [Orquestrador](context-for-mapping/contexto-orquestrador.md)
- [Agente de incidentes](context-for-mapping/contexto-incidente.md)
- [Arquitetura e configuração do projeto](README.md)
