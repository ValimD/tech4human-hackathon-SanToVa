# Agentes de Suporte N1

Projeto inicial para criação de agentes com [LangGraph](https://langchain-ai.github.io/langgraph/).

Para preparar o ambiente e rodar os agentes com o MCP, siga o
[guia de execução](README.execucao.md).

## Contexto para agentes de codificação

As instruções de stack, arquitetura, segurança e validação ficam em
[`AGENTS.md`](AGENTS.md). O GitHub Copilot também recebe um resumo em
`.github/copilot-instructions.md`.

## Arquitetura inicial

```text
src/n1_agents/
├── config.py          # Configuração não sensível por ambiente
├── graph.py           # Orquestração e compilação do grafo
├── event_processor.py # Recepção e resposta inicial de eventos MCP
├── main.py            # Execução local
├── model.py           # Fábrica do modelo OpenAI
├── mcp_tools.py       # Tools MCP expostas ao modelo
├── prompts.py         # Contexto e regras do orquestrador
├── incident_agent.py  # Executor de incidentes e contrato de handoff
├── state.py           # Contrato de estado compartilhado
└── nodes/
    └── orchestrator.py # Agente que responde aos prompts
```

O fluxo atual é intencionalmente pequeno:

```text
START → orchestrator ⇄ tools → END
```

O agente orquestrador recebe `user_input`, envia o prompt ao `claude-sonnet-5` e
retorna a resposta em `response`. Quando necessário, o modelo solicita uma
tool MCP, o grafo executa a ferramenta e devolve o resultado ao modelo antes da
resposta final.

O módulo `event_processor.py` também permite buscar um evento com
`proximo_evento`, gerar uma resposta e registrá-la com `responder_evento`.
O agente usa `orquestrador` como identificador fixo nas chamadas MCP.
Por segurança, ele recebe apenas tools de leitura e `registrar_conversa`;
operações como responder, registrar ou atualizar ficam reservadas aos
executores.
O grafo limita o loop do agente a 2 iterações completas por execução,
equivalente ao `max_iterations=2` de um `AgentExecutor` do LangChain. Uma
iteração pode conter uma chamada de tool e o retorno ao modelo.

## Agente de incidentes

O executor está em `incident_agent.py` e recebe um `IncidentHandoff` estruturado
do orquestrador. Ele usa o identificador MCP `agente-incidente` e pode consultar
incidentes, registrar/atualizar incidentes e avisar o time de Produto.

Contrato de entrada:

```json
{
  "evento_id": "PED-029",
  "destino": "incidente",
  "criticidade": "P0",
  "produto": "Portal do Cliente",
  "motivo": "Produto fora do ar para todos."
}
```

Contrato de saída:

```json
{
  "evento_id": "PED-029",
  "acao": "aberto",
  "incidente_id": "INC-001",
  "criticidade": "P0",
  "motivo": "Incidente aberto e time Produto avisado."
}
```

O executor não recebe tools do orquestrador: suas permissões são definidas
separadamente em `INCIDENT_TOOL_NAMES`.

Para executar um handoff manualmente pelo terminal:

```bash
python -m n1_agents.incident_main \
  '{"evento_id":"PED-029","remetente":"ana@t4h.exemplo","destino":"incidente","criticidade":"P0","categoria":"incidente_produto","produto":"Portal do Cliente","motivo":"Produto fora do ar para todos."}'
```

O executor falha explicitamente se as quatro tools obrigatórias (`consultar`,
`registrar`, `atualizar` e `enviar_mensagem`) não forem publicadas pelo MCP ou
se o modelo terminar sem executar uma tool.

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

Também é possível enviar o prompt como argumento:

```bash
python -m n1_agents.main "Como redefino minha senha?"
```

Para processar eventos em loop e despachar incidentes:

```bash
python -m n1_agents.main --loop
```

O modo `--loop` permanece ouvindo o MCP. `evento: null` significa que não há
evento naquele momento e faz o orquestrador aguardar o próximo ciclo; o
encerramento só é terminal quando `encerrado: true` vier sem evento. Se o MCP
enviar `encerrado: true` junto com um evento, esse evento é processado e uma
última leitura confirma o encerramento. O loop também termina quando o processo
recebe interrupção (`Ctrl+C`). Cada decisão `incidente` é convertida em
`IncidentHandoff` e executada pelo agente `agente-incidente`, que consulta,
registra/atualiza e avisa o time de Produto.

O orquestrador coleta **até 5 eventos por lote** com chamadas sequenciais a
`proximo_evento` (a ferramenta entrega um evento por chamada). Espera até 10
segundos somente na primeira leitura; se a fila esvaziar, analisa o lote parcial
imediatamente para não atrasar incidentes. A classificação recebe o lote inteiro,
sem carregar o histórico de mensagens de lotes anteriores. Consultas MCP
continuam disponíveis para identificar duplicatas e follow-ups.

A fila vazia não chama o LLM. Cada lote exige exatamente uma decisão por evento,
com id e remetente preservados. Incidentes P0/P1/P2 são despachados por prioridade;
os destinos `seguranca`, `ferias` e `chamado` ficam sinalizados no terminal como
pendentes de revisão humana, sem simular executores inexistentes.

O terminal mostra resumos locais de coleta, encaminhamento e resultado, sem
imprimir corpos, remetentes ou justificativas livres. Não há chamada de LLM para
produzir esses resumos. Falhas explícitas do executor são registradas no retorno
como `falhou` e sinalizadas para revisão prioritária; o restante do lote continua.
Não se repetem automaticamente ações que possam já ter sido executadas.

O encerramento normal é o `encerrado: true` do cenário MCP, mesmo que o contêiner
Docker continue ativo. Erros de transporte/coleta e contratos inválidos continuam
sendo falhas explícitas, não são interpretados como encerramento bem-sucedido.

Para limitar ciclos durante uma execução controlada, use
`run_orchestrator_loop(..., max_events=N)`. O padrão é escutar continuamente. Cada ciclo coleta um lote de até 5 eventos
ou aguarda a fila; `max_events` mantém o nome público e limita ciclos, não eventos.

Para testar a conexão MCP e listar todos os eventos disponíveis:

```bash
python -m n1_agents.mcp_diagnostics
```

Esse comando apenas consulta `listar_eventos`; ele não marca eventos como lidos
nem responde mensagens. Eventos do cenário só aparecem depois que o servidor MCP
é iniciado e o relógio simulado começa.

## Testar e verificar

```bash
pytest
ruff check .
```

As credenciais e chaves de provedores devem permanecer em variáveis de ambiente;
nenhuma chave é necessária para executar os testes com o modelo simulado.

## Configurar o modelo OpenAI

O projeto está preparado para usar o `claude-sonnet-5` no endpoint LiteLLM do
hackathon por meio do pacote `langchain-openai`. Copie o arquivo de exemplo e
preencha a chave localmente:

```bash
cp .env.example .env
```

No arquivo `.env`:

```env
MODEL_NAME=claude-sonnet-5
MODEL_BASE_URL=https://litellm.tech4humans.com.br/v1/chat/completions
OPENAI_API_KEY=sua_chave_da_openai
```

A fábrica `create_chat_model()` em `src/n1_agents/model.py` valida a chave e
cria o modelo sem fazer chamadas durante a inicialização. O SDK recebe o base
URL sem `/chat/completions`, mas a requisição final é enviada para o endpoint
configurado acima. Nunca coloque a chave em código, commits ou mensagens.

Chamadas MCP com HTTP 503 são repetidas automaticamente até três tentativas.
Chamadas do modelo também possuem duas novas tentativas internas. Erros 504 não
são repetidos automaticamente, pois a ação pode ter sido executada.
