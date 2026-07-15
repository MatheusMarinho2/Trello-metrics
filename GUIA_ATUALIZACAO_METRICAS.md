# Guia de uso — Atualização do Sistema de Métricas (INTGEST)

**Data:** 2026-07-15  
**Escopo:** alterações **uncommitted** (44 modificados + 11 novos) vs baseline `0845c9c`  
**Referências:** `ANALISE_COMPLETA_PROJETO.md`, `AUDITORIA_METRICAS.md`, `IMPACT_BASELINE.md`

Este documento responde: **o que muda para quem usa o sistema**, **o que foi corrigido** em relação às auditorias, e **como operar** a nova versão.

---

## 1. Resumo em uma página

| Tema | Antes | Agora |
|------|--------|--------|
| Horas úteis | Sem feriados / HE | Calendário operacional (feriados, exceções, hora extra) |
| Cards arquivados | Horas infladas até “agora” | Span fecha no arquivamento |
| Aceitação pós-retorno | Semântica conflitante | Uma regra única |
| Revisão em par | Retorno = “falha” | Sugestão aceita (qualidade); escape só em revisão formal/teste |
| Revisores | Só peer no relatório | Aba **Revisão em par** vs **Revisores** (formal) |
| Deploy direto | Regra ambígua | Válido: → **Diretamente na produção**; ilegal: Aguardando deploy → **Em produção** |
| DORA | 4 métricas (CFR/TTR com proxy fraco) | Só **frequência de deploy** + **lead time** |
| Memória de cálculo | 3 JSONs dessincronizados | Cópias alinhadas + check no CI |
| Novas métricas | — | FTR, aging baseline, net flow, previsibilidade, board moves, etc. |

---

## 2. O que você precisa fazer ao subir esta versão

1. **Migrar o banco** (calendário):
   ```bash
   python backend/manage.py migrate
   ```
   Migration: `0004_workcalendar_overtime`.

2. **Reiniciar** backend + frontend (o server de debug precisa recarregar o engine).

3. **Cadastrar o calendário** na UI (painel de calendário): feriados, exceções por pessoa, horas extras. Sem isso, o cálculo usa só o horário padrão do `workflow.json` (já com suporte a holidays/HE se preenchidos).

4. **Gerar um relatório novo** do mês — relatórios antigos no histórico **não** recalculam sozinhos.

5. **Comparar impacto** (opcional): seguir `IMPACT_BASELINE.md` (mesmo board + mesmo mês before/after).

---

## 3. Como usar o sistema (guia prático)

### 3.1 Tipos de relatório (o que olhar)

| Tipo | Para quem | O que muda nesta versão |
|------|-----------|-------------------------|
| **Geral** | Time completo | Fluxo enriquecido, DORA parcial, FTR, calendário aplicado |
| **Gestão** | Liderança | KPIs: entregues, SLA, **Deploys**, **LT deploy P85**, conformidade, risco, WIP |
| **Desenvolvedores** | Devs | Peer review ≠ retrabalho; retorno de sugestão não pune FTR do mesmo jeito |
| **Revisão em par** | Revisores de par | Conta **sugestões aceitas**; não baixa aprovação por voltar ao dev |
| **Revisores** | Revisão formal | Aba/agregador separado (`formal_reviewers`) |
| **Testers / Solicitantes** | Papéis | Mesma lógica de janela; disciplina de deploy atualizada |
| **Métricas específicas** | Recorte | Opção **DORA (freq. + lead time)** disponível de novo |

### 3.2 Calendário operacional

- Abra o **CalendarPanel** na aplicação.
- Cadastre:
  - **Feriados** (time inteiro)
  - **Exceções** (folga / expediente especial por pessoa/dia)
  - **Hora extra** (janelas que contam além do expediente)
- Nos relatórios novos, confira `calendar_applied` no payload (confirma que o calendário entrou no cálculo).
- **Efeito:** lead time, cycle, SLA, aging e DORA lead time passam a refletir dias úteis reais.

### 3.3 Regra de produção direta (disciplina de processo)

| Movimento | Resultado |
|-----------|-----------|
| Em andamento / Revisão em par / Em revisão / **Aguardando deploy** → **Diretamente na produção** | **Válido** (atalho de hotfix) |
| **Aguardando deploy** → **Em produção** | **Violação** (deve usar Diretamente na produção) |

Hotfixes pela coluna correta **contam como deploy DORA** e **não exigem** etapas de teste na conformidade do fluxo padrão.

### 3.4 Revisão em par (semântica nova)

- Peer review → Em andamento = **sugestão aceita** (garantia de qualidade).
- **Não** trata isso como retrabalho / falha de aprovação do revisor de par.
- Escape que reduz aprovação: retorno em **revisão formal** ou **teste**.

### 3.5 DORA (parcial)

Ativo com apenas:

1. **Deployment Frequency** — entradas em **Em produção** ou **Diretamente na produção** (cards problema), por semana/sistema/caminho.
2. **Lead Time for Changes** — de **Aguardando produção** até o deploy (direto usa o momento da entrada).

**Fora desta versão:** Change Failure Rate e Time to Restore (proxies pouco confiáveis).

### 3.6 Novas leituras no fluxo / qualidade

Procure no preview / HTML / PDF (conforme layout):

- `flow.aging_baseline` — aging por etapa com percentis  
- `flow.net_flow` — entradas vs saídas (tendência de WIP)  
- `flow.flow_efficiency_distribution` / `rework_ratio` / `blocked_time`  
- `first_time_right` — acerto na primeira passagem pelos gates  
- `member_assignment`, `due_predictability`, `board_moves`  
- `data_quality.unknown_lists` — listas do board **não mapeadas** no workflow (renomeação / lista nova)

### 3.7 Antifraude e IA

- Contexto de IA prioriza `antifraud_insights` (não some mais por truncamento).
- Batches de colaborador batem nome com/sem prefixo de papel (`Matheus.Marinho` ≈ `D-Matheus.Marinho`).
- Prompts de gestão citam **DORA parcial** (sem inventar CFR/TTR).

---

## 4. O que foi corrigido vs as auditorias

### 4.1 `ANALISE_COMPLETA_PROJETO.md` — Top 15

| # | Item da análise | Status nesta atualização |
|---|-----------------|--------------------------|
| 1 | Sync 3× `metric_definitions.json` + CI | **Feito** (job CI compara as 3 cópias) |
| 2 | PDF risk gate `include("risk")` | Verificar no builder se ainda aplicável / já coberto nos layouts |
| 3 | XSS HTML | Parcial / fora do foco desta leva se não estiver no diff |
| 4–6 | SECRET_KEY, DEBUG, compose, secrets | **Não** nesta leva (ops/segurança) |
| 7 | Spans no `archived` | **Feito** (`timeline.py`) |
| 8 | Unificar `accepted_without_dev_return` | **Feito** |
| 9–11 | Backup SQLite, erros Trello, atomic/IA | **Não** / parcial (IA contexto melhorado) |
| 12 | Unknown lists + feriados | **Feito** (calendário + alerta de listas) |
| 13 | Testes P0 | **Ampliado** (`tests/test_metrics.py` +~500 linhas) |
| 14–15 | Healthcheck/throttle; action_filter Trello | **Parcial** (parser/client ampliado para eventos de membro/due/board/comentários) |

### 4.2 Engine / `AUDITORIA_METRICAS.md`

| Achado | Status |
|--------|--------|
| C2 Horas de arquivados até `now` | **Corrigido** |
| C4 Sem feriados | **Corrigido** (WorkCalendar + HE) |
| C5 Listas `unknown` silenciosas | **Mitigado** (`data_quality`) |
| C1 Aceitação conflitante | **Corrigido** |
| DORA CFR proxy fraco [W2/auditoria] | **Removido do produto**; DF + LT mantidos |
| Peer review como “falha” | **Corrigido** (sugestões aceitas) |
| Revisor formal misturado com peer | **Corrigido** (`formal_reviewers` + tipo de relatório) |
| A3 First-Time-Right | **Implementado** |
| A1/A2/A4/A5/A10 flow extras | **Implementados** no `flow.py` |
| B1–B3 membro / due | **Implementados** (assignment, due predictability) |
| B5 board moves | **Implementado** |
| B6 CFR por label timestamp | **Não** (CFR desligado de propósito) |

### 4.3 Frontend / relatórios

- Layout gestão com DORA parcial e KPIs de deploy/LT.
- Seções HTML/PDF/JS/guia alinhadas.
- Painel de calendário redesenhado (uso em tela cheia).
- Definições de métrica sincronizadas nas 3 cópias.

---

## 5. Inventário técnico da atualização (diff)

### Novos arquivos

| Arquivo | Função |
|---------|--------|
| `work_calendar.py` + `calendar_service` / `calendar_controller` / migration `0004` | Calendário no backend |
| `CalendarPanel.tsx` + `calendar.ts` | UI do calendário |
| `first_time_right.py` | Métrica FTR |
| `formal_reviewers.py` | Agregador de revisão formal |
| `predictability.py` | Member assignment, due, board moves |
| `IMPACT_BASELINE.md` | Como medir before/after |

### Áreas com maior volume de mudança

- `flow.py`, `timeline.py`, `business_hours.py`, `engine.py`, `export_loader.py`, `ai_context_builder.py`, `tests/test_metrics.py`
- `dora.py` (simplificado)
- `process_discipline.py`, `reviewers.py`, `collaborators.py`
- Relatórios: `report.js`, `html_report.py`, `pdf_intgest/builder.py`, defs JSON ×3
- `.gitlab-ci.yml` (sync defs + pytest)

---

## 6. Checklist rápido de validação pós-deploy

- [ ] `migrate` aplicado  
- [ ] Calendário: 1 feriado de teste → lead time do card cai (ou não conta o dia)  
- [ ] Card arquivado no meio do mês → não “envelhece” até hoje  
- [ ] Hotfix: Aguardando deploy → Diretamente na produção → **sem** violação  
- [ ] Hotfix errado: Aguardando deploy → Em produção → **com** violação  
- [ ] Relatório **Revisão em par**: sugestões aceitas ↑, aprovação não cai por retorno ao dev  
- [ ] Relatório **Revisores**: só formal  
- [ ] Gestão: Deploys + LT deploy P85; **sem** CFR/TTR  
- [ ] `pytest tests/` e CI sync de `metric_definitions` verdes  
- [ ] Gerar PDF/HTML e conferir seção DORA parcial + guia  

---

## 7. O que ainda **não** resolve esta atualização

Itens das auditorias que **continuam abertos** (não espere correção automática):

- Defaults perigosos de produção (`SECRET_KEY`, `DEBUG`, bind HTTP do compose)
- Revogação de token / rate limit de login / delete em massa de histórico
- Geração assíncrona de relatório (timeout longo com IA)
- Decomposição do `App.tsx` / ESLint-vitest no frontend
- CFR/TTR DORA “de verdade” (precisa sinal melhor que proxy de CORREÇÃO)
- Backup automatizado do SQLite

---

## 8. Glossário rápido para o time

| Termo | Significado no sistema |
|-------|------------------------|
| **Lead time** | Criação/início útil → entrega (horas úteis + calendário) |
| **Cycle time** | Fim do pré-fluxo → entrega |
| **Deploy (DORA)** | Entrada em Em produção **ou** Diretamente na produção |
| **LT deploy** | Aguardando produção → deploy |
| **Sugestão aceita** | Peer review devolveu ao Em andamento |
| **FTR** | First-Time-Right — passou no gate sem retorno indevido |
| **Net flow** | Entrou vs saiu do fluxo no período |
| **calendar_applied** | Prova de que feriados/HE entraram no cálculo |

---

*Documento gerado a partir do working tree atual (uncommitted). Atualize este guia quando CFR/TTR voltarem ou quando itens de segurança/ops das auditorias forem fechados.*
