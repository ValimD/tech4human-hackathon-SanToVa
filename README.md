# Agentes de Suporte N1

Projeto inicial para criação de agentes com [LangGraph](https://langchain-ai.github.io/langgraph/).

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
python -m n1_agents.main --loop "Leia os eventos disponíveis"
```

O loop processa no máximo 20 eventos por execução, para quando o MCP informar
que não há evento e envia decisões `incidente` ao agente `agente-incidente`.

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
