# Relatório de mudanças não commitadas — Métricas Trello (INTGEST)

**Data:** 15/07/2026  
**Escopo:** working tree local (ainda **não** enviado ao repositório)  
**Volume aproximado:** ~51 arquivos alterados + 11 novos · **+3.658 / −556** linhas (diff vs HEAD)  
**Base:** commit `0845c9c` (*docs: análise crítica completa do projeto e auditoria de métricas*)

---

## 1. Resumo executivo (para gestão)

Esta leva de mudanças deixa o motor de métricas mais justo, mais alinhado ao fluxo real do board e mais útil para gestão:

1. **Calendário operacional** — feriados, meio período, exclusões e hora extra passam a entrar no cálculo de horas úteis (SLA, lead/cycle time).
2. **Qualidade mais justa** — retorno indevido de teste prejudica só o tester; revisão em par deixa de ser tratada como “falha”; revisor formal ganha relatório próprio.
3. **Novas leituras de fluxo** — FTR, aging baseline, net flow, rework ratio, previsibilidade (due), atribuição de membros, board moves.
4. **DORA parcial** — só frequência de deploy + lead time de deploy (sem CFR/TTR, por serem proxies fracos).
5. **Correções de mapeamento** — “Aguardando revisão” volta a contar; CI/CD Homologação deixa de aparecer como gargalo fantasma.
6. **Colaborador excluído (Jucelio)** — não gera métrica pessoal, mas o card e os demais colaboradores (dev, peer, solicitante, etc.) continuam contabilizados.

**Comunicação (comentários / silent blocked)** foi implementada e **removida de propósito** — não entrará no modelo de uso.

---

## 2. O que muda para o negócio

| Tema | Antes | Depois | Impacto |
|------|--------|--------|---------|
| Horas úteis | Só expediente fixo | + feriados / HE / exclusões | Tempos e SLA mais realistas |
| Retorno de teste | Qualquer retorno punia dev/peer/formal | Só retorno **legítimo** pune qualidade do dev; **indevido** só o tester | Menos injustiça em avaliação |
| Revisão em par | Podia parecer “retrabalho/falha” | Sugestão aceita = qualidade; escape só formal/teste legítimo | Relatório de peer mais justo |
| Revisor formal | Misturado com peer | Agregador e tipo de relatório separados | Gestão vê papéis distintos |
| Jucelio no card | Card inteiro podia sumir das métricas | Só ele não tem linha pessoal | Dev não perde mérito de dupla revisão |
| Gargalos | “Aguardando revisão” zerado; CI/CD Homologação com 0 | Lista real mapeada; CI/CD fora dos gargalos | Painel de gargalos confiável |
| DORA | Completo ou confuso | Parcial (deploy + LT) | Sem métricas inventadas |

---

## 3. Detalhamento por bloco

### 3.1 Calendário operacional

**Novos arquivos**
- `trello_metrics/utils/work_calendar.py`
- `backend/reports/services/calendar_service.py`
- `backend/reports/controllers/calendar_controller.py`
- `backend/reports/migrations/0004_workcalendar_overtime.py`
- `client/src/components/CalendarPanel.tsx` + `client/src/types/calendar.ts`

**O que faz**
- Cadastro de feriados, meio período, janelas excluídas e hora extra por pessoa.
- Integração em `business_hours.py`, SLA e timelines (pessoa do papel quando aplicável).
- UI no frontend para manutenção do calendário.

**Uso**
- Lead/cycle/SLA respeitam dias sem expediente e HE autorizada.

---

### 3.2 Retorno indevido de teste (só o tester é prejudicado)

**Arquivos centrais:** `timeline.py`, `testers.py`, `developers.py`, `reviewers.py`, `formal_reviewers.py`, `collaborators.py`, `first_time_right.py`, `engine.py`, relatórios HTML/PDF/preview.

**Regra**
- **Indevido:** teste/aguardando teste → RETORNO (DEV) → saída direta para aguardando teste/testing.
- **Legítimo:** mesma ida a RETORNO (DEV), mas saída para EM ANDAMENTO.

**Efeito**
- Tester: `undue_test_returns` / taxa (métrica negativa); `prevented_problems` só com legítimo.
- Dev / peer / revisor formal / solicitante / FTR de teste / rework de qualidade: **não** sofrem com indevido.
- Relatórios exibem **“Solução de retorno indevido”** quando houver texto de solução no card.

---

### 3.3 Revisão em par vs revisão formal

- Peer: retorno peer → andamento = **sugestão aceita** (benefício), não punição.
- Novo agregador `formal_reviewers.py` e layouts de relatório específicos.
- Escape de aprovação do peer/formal **não** usa retorno de teste indevido.

---

### 3.4 Ignore de pessoa (Jucelio.Moura)

**Antes:** `ignore_card_people` descartava o **card inteiro** se o nome aparecesse (ex.: como revisor).

**Depois:** `should_ignore_person` — o card permanece no motor; **não** se gera linha pessoal para ele; demais papéis (dev, peer, solicitante, tester) continuam normais, inclusive dupla revisão.

---

### 3.5 Novas métricas de fluxo / previsibilidade

| Métrica | O que responde |
|---------|----------------|
| **FTR (First-Time-Right)** | % que passa no gate (peer/teste) sem devolução relevante |
| **Aging baseline** | Quanto cada etapa costuma demorar (p50/p85/p95) |
| **Net flow** | Por semana: criados − entregues (WIP subindo?) |
| **Rework ratio** | % de horas de fluxo em RETORNO (DEV), sem indevido |
| **Blocked time** | Pausa + retorno suporte no fluxo |
| **Member assignment** | Latência até marcar membro + inconsistência campo vs membros |
| **Due predictability** | Entrega no prazo + taxa de remarcação de due |
| **Board moves** | Cards que entraram/saíram do board |

**Removido:** comunicação (1ª resposta a comentários, silent blocked, retorno com comentário).

Arquivos novos: `first_time_right.py`, `predictability.py`.

---

### 3.6 DORA parcial

- Mantidos: **deployment frequency** e **lead time de deploy**.
- Removidos do produto: Change Failure Rate e Time to Restore (proxies pouco confiáveis no Trello).

---

### 3.7 Correções de workflow / gargalos

Em `workflow.json`:
- `AGUARDANDO REVISÃO` → grupo `waiting_review` (passa a contar em gargalo/SLA/espera).
- Variantes `(Opcional)` continuam neutras (`review_control`).
- `cicd_homologacao` **removido** de `bottleneck_groups` (lista inexistente no fluxo real → não polui o relatório com zeros).

---

### 3.8 Disciplina de processo / hotfixes

Ajustes em `process_discipline.py` para caminhos de deploy (ex.: aguardando deploy → diretamente na produção) e origem de trabalho alinhados ao fluxo INTGEST.

---

### 3.9 Relatórios, IA e frontend

- HTML (`report.js`), PDF (`pdf_intgest`), preview React (`App.tsx`): novas seções/KPIs (FTR, net flow, undue, formal reviewers, calendário).
- Definições sincronizadas nas 3 cópias de `metric_definitions.json`.
- Contexto/prompts de IA atualizados (DORA parcial, antifraude, retornos).
- Opções de métricas no backend (`options_service`, `report_filter`, layouts).

---

### 3.10 CI e qualidade

- `.gitlab-ci.yml`: checagem de sync das 3 cópias de `metric_definitions.json` (+ testes).
- `tests/test_metrics.py`: expansão grande (~+1000 linhas) cobrindo calendário, FTR, undue, Jucelio, SLA, disciplina, etc.

---

### 3.11 Documentação auxiliar (não commitada)

- `GUIA_ATUALIZACAO_METRICAS.md` — guia operacional desta atualização.
- `IMPACT_BASELINE.md` — baseline para medir impacto before/after.

---

## 4. Inventário de arquivos

### Alterados (principais)

| Área | Arquivos |
|------|----------|
| Motor | `timeline.py`, `engine.py`, `workflow.py`, `workflow.json`, `business_hours.py`, agregadores (flow, developers, testers, reviewers, sla, …) |
| Backend | models/serializers calendário, services IA/geração/options, urls |
| Frontend | `App.tsx`, API client, estilos, defs, layouts |
| Relatórios | `report.js`, PDF builder/card_rendering, html_report, charts |
| Testes / CI | `tests/test_metrics.py`, `.gitlab-ci.yml` |

### Novos

| Arquivo | Função |
|---------|--------|
| `work_calendar.py` | Motor de calendário |
| `calendar_*` (backend + UI) | API + painel |
| `first_time_right.py` | FTR |
| `formal_reviewers.py` | Revisor formal |
| `predictability.py` | Member / due / board moves |
| `GUIA_ATUALIZACAO_METRICAS.md` | Guia da atualização |
| `IMPACT_BASELINE.md` | Baseline de impacto |

---

## 5. Validação recomendada antes do commit/deploy

1. Rodar migração `0004_workcalendar_overtime`.
2. Cadastrar 1 feriado de teste e conferir queda de horas no card.
3. Relatório Gestão: FTR, net flow, DORA parcial (sem CFR/TTR).
4. Card com retorno indevido: só tester sobe `undue`; dev sem retrabalho.
5. Card com Jucelio como revisor formal nível 8+: dev sem violação de dupla revisão; Jucelio sem linha pessoal.
6. Gargalos: “Aguardando revisão” com amostras reais; **sem** linha CI/CD Homologação.
7. `pytest tests/test_metrics.py` e job CI de sync das defs.

---

## 6. Fora desta leva (ainda aberto)

Itens de auditoria **não** resolvidos aqui (para não misturar expectativa):

- Hardening de produção (`SECRET_KEY`, `DEBUG`, compose).
- CFR/TTR DORA “de verdade”.
- Geração assíncrona de relatório / timeouts de IA.
- Comunicação por comentários (removida conscientemente).

---

## 7. Conclusão

As mudanças não commitadas elevam a **confiabilidade** e a **justiça** das métricas (calendário, retornos, papéis, ignore de pessoa) e acrescentam **visão de fluxo/previsibilidade** sem inflar o produto com DORA incompleto ou comunicação não usada.

**Status:** código pronto para revisão/commit; ainda **não** está versionado no remoto.

---

*Documento gerado a partir do working tree local em 15/07/2026. Não substitui code review; resume o impacto para gestão.*
