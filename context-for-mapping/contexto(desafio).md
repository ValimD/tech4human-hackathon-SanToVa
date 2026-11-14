# Hackathon — Servidor MCP e Tema 1: Triagem N1

Resumo consolidado dos nove prints fornecidos, sem repetições. As regras abaixo descrevem o desafio apresentado no material.

## 1. Visão geral e responsabilidades

O servidor MCP representa a empresa simulada: entrega eventos, mantém as bases de dados, valida regras e reage às ações dos agentes. MCP (Model Context Protocol) é um padrão aberto pelo qual o servidor publica ferramentas com nome, descrição e parâmetros para os agentes chamarem.

**O agente sempre inicia a comunicação.** O servidor nunca chama o agente; o time consulta continuamente a caixa de entrada. Linguagem, framework e modelo são de livre escolha do time.

| O time constrói | O servidor entrega pronto |
| --- | --- |
| Agentes com papéis diferentes, comunicação e revisão entre eles | Caixa de entrada com eventos do cenário e do painel |
| Laço de trabalho e tratamento de falhas | Bases do tema e validação das regras |
| Memória de curto prazo (caso aberto) e longo prazo (aprendizados) | Pessoas e times simulados; só responde quem o tema prevê |
| Escalação: quando chamar uma pessoa e como transferir o caso | Relógio simulado e falhas intencionais |
| Solicitação de aprovação humana e registro da decisão | Painel ao vivo e logs |
| Operação de sistemas sem API por navegador/computer use | Sistemas legados acessíveis apenas pela tela |

Memória, escalação e aprovação **não são implementadas pelo servidor**: ficam a cargo do time.

## 2. Eventos e relógio simulado

- Eventos chegam automaticamente nos horários do cenário de treino ou são criados manualmente pelo botão **+ Novo evento** no painel. Com `--sem-cenario`, chegam apenas os eventos do painel.
- Ao enviar uma mensagem ou responder esperando retorno, a resposta pode chegar minutos depois no relógio simulado, como um novo evento na caixa de entrada.
- O agente deve chamar `proximo_evento` em laço até receber `encerrado: true`.
- Sem evento novo, a resposta informa quando chega o próximo. O parâmetro `esperar_segundos` (até 30) permite ao servidor segurar a resposta até chegar um evento.
- O expediente simulado ocorre das **08:00 às 18:00, somente em dias úteis**.
- Cada cenário completo dura cerca de **20 minutos reais**: 5 dias no Tema 1, 10 no Tema 2 e 22 no Tema 3. A velocidade pode ser ajustada com `SEGUNDOS_POR_DIA` ou `--segundos-por-dia`.
- O relógio começa na primeira chamada de qualquer agente, via MCP ou tela. Antes disso, o mundo fica parado.
- Toda resposta inclui a hora simulada no campo `agora`.
- Ao fim do cenário, consultas continuam funcionando, mas ações retornam erro **410**. Reiniciar o servidor zera o cenário e exige reconexão do agente.

## 3. Ferramentas MCP

As ferramentas são iguais em todos os temas; as bases mudam e são descobertas com `listar_bases`.

| Ferramenta | Função |
| --- | --- |
| `proximo_evento`, `listar_eventos`, `ler_evento` | Obter e consultar eventos da caixa de entrada. |
| `responder_evento` | Responder ao remetente; com `aguardar_resposta`, ele pode responder de volta. |
| `enviar_mensagem` | Enviar e-mail para pessoas ou times do mundo simulado. |
| `listar_bases` | Descobrir bases, campos e o que pode ser alterado. |
| `consultar` | Buscar em uma base com filtros por campo ou palavras. |
| `registrar`, `atualizar` | Criar e alterar registros; o servidor rejeita operações contrárias às regras do tema. |
| `registrar_conversa` | Exibir no painel uma conversa entre dois agentes do time. |

### Regras das chamadas

- Toda chamada leva `agente`, com o nome do agente responsável, para identificação no painel.
- `motivo` é opcional e aparece ao lado da chamada no painel.
- A resposta é um JSON com `status` (`ok` ou `erro`) e `agora`.
- `registrar`, `atualizar` e `enviar_mensagem` aceitam `evento_id`. **Vincular a ação ao evento é o que conta como atendimento no painel.**
- `consultar` e `listar_eventos` retornam `total` e `tem_mais`; use `limite` e `offset` para paginar.
- Algumas falhas demoram até 9 segundos; o material orienta timeout do cliente MCP de **15 segundos ou mais**.

| Código | Significado |
| --- | --- |
| 400 | Campo obrigatório ausente. |
| 404 | Item não existe. |
| 405 | A base não aceita a operação. |
| 409 | O item mudou ou já está com alguém. |
| 410 | O cenário terminou. |
| 422 | Valor inválido ou violação de regra do tema. |

## 4. Sistemas legados: somente pela tela

Acesso em `http://localhost:8765/legado`. É necessário computer use ou automação de navegador. As ações realizadas na tela também aparecem no painel, identificadas por quem as executou.

| Tema | Sistema | Operação exclusiva da tela |
| --- | --- | --- |
| 1 | Sistema de férias | Lançar férias. |
| 2 | Portal da contabilidade | Enviar os dados do contratado para registro. |
| 3 | Portal do fornecedor | Comprar equipamentos. |

## 5. Como executar

Execute os comandos na pasta `Servidor MCP (Compartilhado)`.

### Docker

É a opção mais simples e dispensa a instalação de Python.

```bash
TEMA=triagem docker compose up --build mundo
```

No Windows, defina a variável antes de iniciar.

**PowerShell:**

```powershell
$env:TEMA="triagem"
docker compose up --build mundo
```

**Prompt de Comando:**

```cmd
set TEMA=triagem
docker compose up --build mundo
```

Para o Tema 3, use `equipamentos` no lugar de `triagem`. Para parar, pressione `Ctrl+C`.

### Python, sem Docker

Requer **Python 3.11 ou mais recente**. Confira com `python3 --version` e mantenha um ambiente virtual exclusivo para o servidor, separado do ambiente do agente.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python mundo.py --tema triagem
```

No Windows, o material indica ativar o ambiente com `.venv\Scripts\activate`. Se o agente estiver em outro container ou máquina, inicie o servidor com `--host 0.0.0.0` (já configurado no Docker).

### Endereços

| Recurso | Endereço |
| --- | --- |
| Painel ao vivo | `http://localhost:8765` |
| Servidor MCP | `http://localhost:8765/mcp` |
| Sistemas legados | `http://localhost:8765/legado` |

## 6. Falhas, painel e logs

Por padrão, **15% das chamadas falham ou demoram de propósito**. Tratar essas situações faz parte do desafio.

| Falha | Tratamento esperado |
| --- | --- |
| 503 | Tentar novamente após alguns segundos. |
| Resposta lenta | Esperar: a resposta chega correta, mas demora. |
| 504 em uma ação | Conferir o estado antes de repetir: a ação pode ter sido executada ou não. |
| 504 em uma consulta | Repetir a consulta, pois nada foi alterado. |
| 409 | Ocorre somente em ações; consultar novamente antes de agir. |

O painel mostra a caixa de entrada, chamadas, conversas dos agentes e reações do mundo ao vivo, além de permitir criar eventos manualmente.

Cada rodada grava um log em `logs/<tema>-<data>.jsonl`. Para ler o mais recente:

```bash
python ver_log.py
```

| Opção | Efeito |
| --- | --- |
| `--erros 0` | Desliga as falhas. |
| `--sem-cenario` | Mantém somente eventos criados no painel. |
| `--segundos-por-dia` | Ajusta a velocidade do relógio. |
| `--seed` | Repete os mesmos sorteios. |

No Docker, as opções são passadas como variáveis. Exemplo do material:

```bash
TEMA=triagem ERROS=0 docker compose up --build mundo
```

## 7. Tema 1 — Triagem N1 de chamados e incidentes

### Objetivo

Construir um time de agentes para o primeiro atendimento dos pedidos internos da T4H: entender e-mails, responder, encaminhar, abrir chamados ou incidentes e transferir para pessoas os casos que exigem intervenção humana.

Os pedidos incluem acesso a sistemas, equipamentos, férias e suporte a produtos. Podem estar classificados incorretamente, incompletos ou duplicados; entre eles, podem existir sistemas fora do ar que exigem atenção imediata.

### Recursos disponíveis

| Recurso | Conteúdo |
| --- | --- |
| Caixa de entrada | Cerca de 60 e-mails em 5 dias, incluindo dúvidas, pedidos, duplicados, falsas urgências, solicitações incompletas e incidentes reais. |
| FAQ | 15 respostas prontas. |
| Catálogo | 8 tipos de chamado, cada um com time responsável, campos obrigatórios, aprovação e prazo. |
| Times | Equipes da empresa, escopo de atendimento e e-mail de cada uma. |
| Chamados já abertos | Casos em andamento, úteis para identificar duplicados. |
| Sistema de férias | Sistema legado sem API, acessível apenas pela tela. |

O mundo reage: solicitantes respondem a pedidos de informação e cobram quando ficam sem resposta.

### Regras de atendimento

- Um chamado só pode ser aberto com um tipo válido do catálogo e todos os campos obrigatórios desse tipo.
- A palavra “urgente” no assunto não define criticidade: **a classificação depende do impacto**.

| Criticidade | Impacto | Ação |
| --- | --- | --- |
| P0 | Produto fora do ar para todos os clientes. | Abrir incidente e escalar imediatamente. |
| P1 | Função importante indisponível para muitos clientes. | Abrir incidente e escalar imediatamente. |
| P2 | Falha parcial, com contorno. | Abrir incidente. |
| P3 e P4 | Falha para uma pessoa, dúvida ou melhoria. | Abrir chamado de Suporte a produto ou responder. |

- Suspeita de golpe, vazamento ou acesso indevido, assim como pedidos com dados pessoais sensíveis, **sempre vão para uma pessoa**. O time define como encaminhar.
- **O agente nunca aprova nada**: a aprovação cabe a uma pessoa.
- Férias só podem ser lançadas pela tela do sistema de férias.

### Níveis de entrega

| Nível | Critérios |
| --- | --- |
| Mínimo | Pelo menos dois agentes com papéis diferentes processam todos os e-mails e decidem uma ação para cada um, com motivo. |
| Bom | Respondem com o FAQ, agrupam duplicados, pedem informações faltantes, classificam corretamente a criticidade e contam com um agente revisor antes de agir. |
| Excelente | Incluem uma tela de abertura de chamado integrada ao mesmo time de agentes **ou** um painel dos casos aguardando uma pessoa. |

### Erros graves

- Deixar passar um incidente P0/P1 ou classificá-lo abaixo da criticidade correta.
- Agir sem intervenção humana em casos de segurança ou dados pessoais.
- Responder com informação que não está no FAQ.

---

**Escopo da fonte:** os prints detalham a infraestrutura compartilhada e o Tema 1. Os Temas 2 e 3 aparecem apenas em referências ao relógio, sistemas legados e, no caso do Tema 3, à configuração `equipamentos`.