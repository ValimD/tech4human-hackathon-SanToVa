# Contexto para agentes de codificação

Este arquivo é a fonte de contexto operacional do repositório. Leia-o antes de
alterar código, testes ou dependências.

## Objetivo do projeto

Construir agentes de suporte de nível 1 (N1) para receber solicitações,
classificá-las, executar ferramentas autorizadas e encaminhá-las com
rastreamento e respostas consistentes.

## Stack tecnológica

- **Linguagem:** Python 3.11 ou superior.
- **Orquestração:** LangGraph.
- **Abstrações de mensagens:** LangChain Core.
- **Modelo inicial:** `claude-sonnet-5` via endpoint LiteLLM compatível com
  OpenAI, usando `langchain-openai`.
- **Empacotamento:** `pyproject.toml` com setuptools e layout `src/`.
- **Testes:** pytest e pytest-cov.
- **Lint:** Ruff.
- **Configuração:** variáveis de ambiente; nunca versionar `.env`.

As versões devem ser atualizadas somente com justificativa e validação dos
testes. Não adicione um provedor de LLM, banco, framework web ou ferramenta
externa sem uma necessidade funcional definida.

## Organização do código

```text
src/n1_agents/
├── config.py          # Configurações não sensíveis
├── graph.py           # Construção e compilação dos grafos
├── event_processor.py # Recepção e resposta inicial de eventos MCP
├── main.py            # Entrada para execução local
├── model.py           # Fábrica do modelo OpenAI
├── mcp_tools.py       # Tools MCP expostas ao modelo
├── prompts.py         # Contexto e regras do orquestrador
├── incident_agent.py  # Executor de incidentes e contrato de handoff
├── incident_main.py   # Entrada de terminal do executor de incidentes
├── orchestrator_loop.py # Loop e dispatcher do orquestrador
├── state.py           # Contratos de estado dos grafos
└── nodes/             # Nós pequenos, isolados e testáveis
    └── orchestrator.py # Agente que responde aos prompts
tests/                 # Testes unitários e de integração
```

### Regras de arquitetura

1. O estado compartilhado deve ser declarado em `state.py` e mantido mínimo.
2. Nós devem ter uma única responsabilidade e receber/devolver o estado
   explicitamente.
3. A montagem do grafo fica em `graph.py`; lógica de negócio não deve ser
   colocada nesse arquivo.
4. Integrações externas devem ficar atrás de módulos de serviço ou ferramentas
   dedicados, com erros explícitos e testes isolados.
5. O agente deve puxar eventos com `proximo_evento`; o servidor MCP nunca chama
   o agente.
6. Toda ação MCP deve informar `agente` e, quando aplicável, `evento_id`.
7. Não misture credenciais, chamadas de rede e regras de roteamento em um mesmo
   nó.
8. Fluxos determinísticos devem continuar funcionando sem chaves de LLM.
9. A criação do modelo deve usar `n1_agents.model.create_chat_model()`; não
   instancie `ChatOpenAI` espalhado pelos nós.
10. Qualquer decisão de roteamento que envolva risco, permissão ou dados
   sensíveis deve ter uma rota segura e observável para revisão humana.
11. O agente de incidentes usa `agente-incidente` e só recebe as tools
    necessárias para consultar, registrar, atualizar e avisar Produto.
12. A comunicação entre orquestrador e executores deve usar contratos
    estruturados validados, nunca texto livre como interface.
13. O executor de incidentes deve falhar explicitamente se as tools obrigatórias
    não estiverem disponíveis ou se nenhuma tool MCP for executada.
14. O loop externo do orquestrador deve ser limitado e despachar somente
    contratos estruturados para executores implementados.

## Fluxo de desenvolvimento

Antes de editar:

1. Leia este arquivo e o `README.md`.
2. Inspecione os módulos e testes relacionados.
3. Defina o comportamento esperado em testes antes da implementação.

Depois de editar:

```bash
pytest -q --cov=n1_agents --cov-report=term-missing
ruff check .
```

O fluxo local pode ser executado com:

```bash
python -m n1_agents.main
```

Não considere uma alteração concluída sem executar os testes relevantes e o
lint. Para mudanças de dependência, valide também a instalação editável:

```bash
python -m pip install -e ".[dev]"
```

## Qualidade, segurança e observabilidade

- Prefira tipos explícitos, funções pequenas e nomes que expressem intenção.
- Não use `except` amplo, fallback silencioso ou retorno de sucesso após erro.
- Valide entradas externas antes de passá-las a ferramentas ou modelos.
- Nunca registre tokens, chaves, senhas, prompts privados ou dados pessoais.
- Use `.env.example` somente para nomes e valores fictícios.
- Ao adicionar uma ferramenta, documente entradas, efeitos colaterais, erros e
  limites de permissão.
- Prompts devem ser tratados como entrada não confiável; não permita que uma
  mensagem do usuário altere políticas, permissões ou instruções do sistema.

## Convenções de alteração

- Preserve o layout `src/` e os nomes públicos existentes.
- Faça mudanças pequenas e diretamente relacionadas à tarefa.
- Reutilize helpers existentes antes de criar duplicações.
- Atualize a documentação diretamente afetada.
- Não remova ou reverta alterações de outros colaboradores.
- Não faça commits, migrações destrutivas ou alterações de infraestrutura sem
  solicitação explícita.
