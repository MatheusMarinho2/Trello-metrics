# SLA: medição, etapas e níveis

Este documento descreve como o sistema INTGEST mede SLA no fluxo Trello, quais limites se aplicam a cada coluna e como funcionam os níveis Fibonacci (desenvolvimento) e de análise.

Configuração em [`trello_metrics/resources/workflow.json`](../trello_metrics/resources/workflow.json) (`sla_rules`). Cálculo em [`trello_metrics/metrics/aggregators/sla.py`](../trello_metrics/metrics/aggregators/sla.py).

---

## Como o tempo é medido

### Horas úteis (padrão)

- **Fuso:** `America/Sao_Paulo`
- **Dias:** segunda a sexta
- **Entrada:** 08:00
- **Almoço (não conta):** 12:00–13:00
- **Saída:**
  - **Segunda a quarta:** 18:00 (9 h úteis/dia: 4 h manhã + 5 h tarde)
  - **Quinta e sexta:** 17:30 (8,5 h úteis/dia: 4 h manhã + 4,5 h tarde)
- **Contagem:** somente o tempo em que o card permanece na coluna ou etapa, dentro das janelas acima
- Fins de semana, noite e horário de almoço **não entram** no cálculo

Essas regras valem para **SLA**, **tempo por etapa**, **lead/cycle time**, **aging**, **DORA**, **prioridade**, **latência de atribuição** e demais métricas de permanência — exceto onde indicado abaixo.

### O que ainda usa tempo corrido (de propósito)

| Métrica | Motivo |
|---------|--------|
| SLA *Aguardando produção* | 7 dias corridos (configuração explícita) |
| CFR DORA (janela pós-deploy) | 7 dias corridos para achar card corretivo |
| `days_stuck` em gargalos | Dias desde última atividade no Trello (calendário) |
| CFD / throughput (Lei de Little) | Contagem por dia calendário e cards/dia |
| Janela de tendência 6 meses | Agrupamento por mês calendário |

### Dias corridos (exceção)

- **Aguardando produção:** 7 dias (168 h) corridos, incluindo fins de semana

### Início e fim do cronômetro

| Evento | O que acontece |
|--------|----------------|
| Card entra na coluna | Cronômetro **inicia** |
| Card sai da coluna | Cronômetro **para**; gera uma avaliação de SLA |
| Card ainda na coluna | Usa `now` como fim provisório (alertas em tempo real) |

Cada passagem pelo mesmo estágio gera **uma avaliação independente**.

### Status da avaliação

| Status | Condição |
|--------|----------|
| `ok` | Dentro do limite |
| `em_risco` | Card aberto e consumo ≥ **80%** do limite (configurável) |
| `estourado` | Tempo decorrido **superior** ao limite |

---

## Tabela completa de SLAs por coluna

| Grupo interno | Coluna no Trello | SLA | Modo | Base do limite |
|---------------|------------------|-----|------|----------------|
| `planning` | PLANEJAMENTO | 48 h úteis | business | Etapa fixa |
| `analysis_planning` | ANALISES PARA PLANEJAMENTO | 0,5 h / 1 h / 2 h | business | Nível de análise (1 / 2 / 3) |
| `approval` | AGUARDANDO APROVAÇÃO | 4 h úteis | business | Etapa fixa |
| `backlog` | BACKLOG | — | — | WIP (sem SLA rígido) |
| `backlog_analysis` | BACKLOG (ANÁLISES) | — | — | WIP (sem SLA rígido) |
| `development` | EM ANDAMENTO | 1 / 2 / 4 / 12 / 27 / 44 h | business | Nível Fibonacci (cards problema) |
| `return_developer` | RETORNO (DEV) | 2–8 h úteis | business | Prioridade do card |
| `return_support` | RETORNO (SUP) | 1–6 h úteis | business | Prioridade do card |
| `waiting_peer_review` | AGUARDANDO REVISÃO EM PAR | — | — | Fila neutra |
| `peer_review` | REVISÃO EM PAR | 1,5 h úteis | business | Etapa fixa |
| `review_control` | AGUARDANDO REVISÃO (Opcional) | — | — | Fila neutra |
| `waiting_review` | AGUARDANDO REVISÃO FORMAL | 4 h úteis | business | Etapa fixa |
| `review` | EM REVISÃO | 4 h úteis | business | Etapa fixa |
| `cicd_homologacao` | CI/CD HOMOLOGAÇÃO | 4 h úteis | business | Etapa fixa |
| `waiting_deploy` | AGUARDANDO DEPLOY | 1 h útil | business | Etapa fixa |
| `waiting_test` | AGUARDANDO TESTE (X) | 9 h úteis | business | Etapa fixa |
| `testing` | EM TESTE | 2 h úteis | business | Etapa fixa |
| `waiting_production` | AGUARDANDO PRODUÇÃO (X) | 7 dias | calendar | Etapa fixa |
| `paused` | PAUSADO | — | — | Excluído (pausa consciente) |
| `production` / `analysis_done` | finais | — | — | Etapa terminal |

---

## SLA por nível Fibonacci (Em andamento)

Aplica-se a cards de **problema** (`PM CLIENTE`, `PROBLEMA`) com campo **Nível** preenchido.

| Nível | Limite em Em andamento | Interpretação de esforço |
|-------|------------------------|---------------------------|
| 1 | 1 h útil | Ajuste pontual, escopo fechado |
| 2 | 2 h úteis | Correção simples com validação |
| 3 | 4 h úteis | Pequena feature ou regra isolada |
| 5 | 12 h úteis | Módulo com regras moderadas |
| 8 | 27 h úteis | Impacto considerável, integrações |
| 13 | 44 h úteis | Fluxo crítico, alto risco de regressão |

Sem nível informado → etapa **não entra** na métrica de SLA de desenvolvimento.

Cards de **análise** em Em andamento **não** usam Fibonacci de desenvolvimento.

---

## SLA por nível de análise (Análises para planejamento)

### Quando medir

1. O desenvolvedor **conclui** a análise técnica
2. Preenche o campo **Nível (Análise)** no card
3. Move o card para **ANALISES PARA PLANEJAMENTO**

O SLA mede quanto tempo a análise fica **aguardando ser absorvida pelo planejamento** — não o tempo de execução da análise em si.

| Nível (Análise) | Limite na coluna | Uso típico |
|-----------------|------------------|------------|
| 1 | 30 min úteis | Análise rápida, impacto local |
| 2 | 1 h útil | Escopo médio, dependências moderadas |
| 3 | 2 h úteis | Análise ampla, múltiplos sistemas ou riscos |

Sem **Nível (Análise)** → coluna **não gera** check de SLA.

---

## SLA de retornos por prioridade

Aplica-se quando o card passa por **RETORNO (DEV)** ou **RETORNO (SUP)**. O limite usa o campo **Prioridade** do card.

### RETORNO (DEV)

| Prioridade | Limite |
|------------|--------|
| Crítica | 2 h úteis |
| Urgente | 4 h úteis |
| Alta | 6 h úteis |
| Demais / não informada | 8 h úteis |

### RETORNO (SUP)

| Prioridade | Limite |
|------------|--------|
| Crítica | 1 h útil |
| Urgente | 2 h úteis |
| Alta | 4 h úteis |
| Demais / não informada | 6 h úteis |

---

## Colunas excluídas e filas neutras

| Motivo | Colunas |
|--------|---------|
| **WIP** — controle por limite de trabalho em progresso, não por tempo | Backlog, Backlog (análises) |
| **Fila neutra** — ponto de controle, não atribuído a um papel | Aguardando revisão em par, Aguardando revisão (opcional) |
| **Pausa consciente** | Pausado |
| **Terminal / entregue** | Em produção, Diretamente na produção, Análises finalizadas |

---

## Campos exportados na métrica

Cada check de SLA inclui:

- `sla_basis`: `stage` | `development_level` | `analysis_level` | `return_priority`
- `fibonacci_level`: nível numérico quando aplicável
- `prioridade`: prioridade do card (retornos)
- `usage_pct`, `status`, `breached`, `limit_human`, `elapsed_human`

---

## Referência rápida: fluxo problema

```
Planejamento (48h) → Aprovação (4h) → Backlog (WIP)
  → Em andamento (por Fibonacci) → Revisão em par (1,5h)
  → Aguardando revisão formal (4h) → Em revisão (4h)
  → CI/CD (4h) → Aguardando deploy (1h)
  → Aguardando teste (9h) → Em teste (2h)
  → Aguardando produção (7 dias)
```

Retornos para **RETORNO (DEV)** ou **RETORNO (SUP)** reiniciam contagem com limite por prioridade.

Para orientação de nivelamento de tarefas, veja [guia_nivelacao_tarefas.md](guia_nivelacao_tarefas.md).
