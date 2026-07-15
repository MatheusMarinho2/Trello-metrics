# Auditoria de Métricas — Engine `trello_metrics/` (INTGEST)

**Data:** 15/07/2026 · **Complemento de:** [ANALISE_COMPLETA_PROJETO.md](ANALISE_COMPLETA_PROJETO.md)

Escopo: `metrics/engine.py`, `metrics/timeline.py`, 20 agregadores em `metrics/aggregators/`, `utils/` e `parsers/`. Baseline verificado: `pytest tests/test_metrics.py -q` → 33 passed. Convenções desta auditoria: **✅ correta** (fiel à intenção e numericamente sã), **⚠️ questionável** (funciona, mas com viés, semântica ambígua ou fragilidade), **❌ incorreta** (produz número errado em cenários reais).

Bugs estruturais referenciados ao longo do documento (identificados na análise geral e confirmados no código):

- **[C1]** `accepted_without_dev_return` sobrescrito: `timeline.py:333-337` calcula "sem retorno antes da entrega", mas `timeline.py:587-588` (via `_apply_return_metrics`, chamado em `timeline.py:368`) sobrescreve para `return_dev_count == 0` (qualquer retorno, inclusive pós-entrega).
- **[C2]** Cards arquivados sem `date_closed` acumulam horas até `now`: `_list_spans` (`timeline.py:654-719`) ignora eventos `archived`; `date_closed` vem de `dateClosed/dateCompleted` (`export_loader.py:135`), campos não confiáveis no export.
- **[C3]** Spans duplicados com semântica divergente: `engine._timeline_spans` (`engine.py:388-417`) e `engine._cycle_time_hours` (`engine.py:419-434`) reimplementam o que `timeline._list_spans`/`cycle_time_hours` já fazem, com regras diferentes.
- **[C4]** `business_hours_between` (`utils/business_hours.py:32-59`) não considera feriados.
- **[C5]** `group_for_list` → `"unknown"` silencioso (`domain/workflow.py:39-44`); grupos unknown ficam fora de `QUEUE_GROUPS`/`WORK_GROUPS`/SLA sem alerta.
- **[W1]** `week_key` em UTC (`common.py:143-147`).
- **[W2]** `_production_deploy_window_start` usa a primeira fila de produção para todos os deploys (`dora.py:99-109`).
- **[W3]** `trends.cards_delivered` só soma devs `D-` (`trends.py:26`), divergindo de `team_summary.cards_delivered`.
- **[W4]** `human_hours` converte horas úteis em dias corridos `/24` (`utils/dates.py:49-52`).
- **[W5]** `pause_count = max(movimentos, blocos de descrição)` (`timeline.py:365-366`).

---

## PARTE 1 — Inventário e revisão de todos os cálculos

### 1.1 Fundamentos (timeline.py) — base de tudo

| Métrica | Onde | Fórmula implementada | Veredito |
|---|---|---|---|
| `group_hours[g]` / `group_visits[g]` | `timeline.py:292-296` | Para cada span (lista, start, end): `hours = duration_hours(start, end)` em horas úteis; soma por grupo da lista | ⚠️ **[C2]** infla grupos de cards arquivados; **[C4]** superestima em feriados; **[C5]** horas de listas não mapeadas caem em `unknown` e somem das métricas derivadas |
| `delivered_at` | `timeline.py:298-307` | `start` do primeiro span cujo grupo ∈ `delivery_groups_for_kind(kind)`; fallback: primeiro span em `done_groups` | ✅ Correta como definição. ⚠️ Card que entra em `waiting_production`, volta e re-entrega mantém o 1º timestamp — coerente com a política "abrir novo card", mas não documentado no payload |
| `lead_time_hours` | `timeline.py:340` | `duration_hours(created_at, date_closed ∨ now)` | ❌ Para card aberto, é "idade", não lead time; para arquivado sem `date_closed` **[C2]** cresce para sempre. Deveria ser `created_at → delivered_at` (ou explicitamente renomeada para `age_hours` quando aberto) |
| `cycle_time_hours` | `timeline.py:341-346` | `duration_hours(created_at, delivered_at)` | ⚠️ É idêntico ao lead time clássico (criação→entrega); "cycle time" de mercado começa no início do trabalho. O flow.py usa outra definição (ver 1.2) — três definições coexistem **[C3]** |
| `metric_cycle_hours` | `timeline.py:403-407` | `duration_hours(flow_start, delivered_at)`, onde `flow_start` = fim do último span `pre_flow` ou início do 1º span fora de `pre_flow` | ✅ Boa definição operacional; `_metric_flow_start_at` (`timeline.py:410-421`) verificado correto |
| `dev_work_hours` / `pipeline_wait_hours` / `flow_hours_until_delivery` | `timeline.py:381-402` | Soma de `_clipped_stage_hours(stage, delivered_at)` para stages fora de `excluded_flow_groups`, particionada em `developer_work_groups` vs `pipeline_wait_groups` | ✅ Clipping na entrega correto (`timeline.py:424-433`). ⚠️ Stages em grupos fora das duas listas (ex.: `production`, `unknown`) entram em `total` mas em nenhuma partição → `dev_work + pipeline_wait ≠ flow_hours_until_delivery` em alguns cards; consumidores que calculam `wait/(work+wait)` (developers.py:75) ignoram silenciosamente essas horas |
| `return_dev_count` / `return_sup_count` / `pause_count` | `timeline.py:319-325` | Contagem de eventos `moved` com target `return_developer`/`return_support`/`paused` | ✅ contagens; ⚠️ `pause_count` depois vira `max(eventos, len(pausas da descrição))` **[W5]** — mistura fontes sem reconciliação (`pause_hours` só reflete os eventos) |
| `peer_review_returns` / `peer_review_sent_back` | `timeline.py:327-329` | `+1` quando transição `peer_review → development` | ⚠️ Retorno de revisão em par que passa pela lista RETORNO (DEV) (`peer_review → return_developer`) NÃO conta aqui (conta em `return_dev_by_revisao_count`). Dois caminhos de devolução da mesma etapa alimentam métricas distintas — inconsistência semântica |
| `developer_penalty_return_count` | `timeline.py:581` | `= return_dev_count` (todos os retornos, sempre) | ⚠️ Inclui retornos pós-entrega/pós-terminal; a "penalidade" do dev deveria considerar só até a entrega **[C1]** |
| `accepted_without_dev_return` | `timeline.py:333-337` + `587-588` | Efetivamente `return_dev_count == 0` | ❌ **[C1]** — o cálculo "antes da entrega" é código morto; a política efetiva penaliza retornos pós-terminal, que já são tratados como violação separada (`return_after_terminal`). Dupla penalização |
| `return_dev_by_teste_count` / `return_dev_by_revisao_count` | `timeline.py:614-633` | Atribuição por grupo de origem do evento: `testing → tester`; `{review, waiting_review, peer_review, waiting_peer_review} → revisor`; senão `desconhecido` | ⚠️ Origem `waiting_test → return_developer` cai em "desconhecido" (tester devolveu antes de iniciar? acontece). `_attribute_dev_return` (`timeline.py:546-563`) usado no histórico usa também o subtipo textual, mas `_dev_return_event_attributions` (usado nas contagens) não — as duas atribuições podem divergir para o mesmo evento |
| `test_cycles` / `retest_cycles` | `timeline.py:589-592`, `126-127` | `test_cycles = visits(waiting_test) + visits(testing)`; `retest = max(0, test_cycles - 1)` | ❌ Um único ciclo de teste normal (`waiting_test → testing`) dá `test_cycles = 2` → `retest_cycles = 1` mesmo sem reteste. Fórmula correta: `test_cycles = visits(testing)`; `retest = max(0, visits(testing) - 1)` |
| `test_return_missing_reason_count` | `timeline.py:595-607` | Para cada retorno atribuído a tester, procura entrada de histórico com `at` idêntico e `motivo` não vazio | ⚠️ O casamento é posicional (`_build_retorno_history`, `timeline.py:479-537`); se o dev registrou os retornos fora de ordem ou pulou um número, o `at` casa errado e gera falso "sem motivo" |
| `double_review_required/recommended/violation` | `timeline.py:354-360`, `129-135` | `required = nível ≥ 8`; `recommended = 5 ≤ nível < 8`; `done = visitou peer_review ∧ visitou review`; `violation = required ∧ ¬done` | ✅ Correta e parametrizada no workflow (`workflow.py:199-205`) |
| `return_after_terminal` | `timeline.py:722-751` | Primeiro evento para grupo terminal define `terminal_at`; qualquer `moved` posterior para grupo de retorno é violação | ✅ Correta |
| `gestor_premature_approval` | `timeline.py:754-763` | `∃ (approval→development) ∧ ∃ (development→return_support)` | ⚠️ Não exige ordem temporal entre os dois fatos. Melhor: exigir `t(dev→sup) > t(approval→dev)` |

### 1.2 `flow` (flow.py)

| Métrica | Onde | Fórmula | Veredito |
|---|---|---|---|
| `team.lead_time` | `flow.py:60-64` | `time_stats([duration_hours(created_at, delivered_at)])` sobre entregues no período | ✅ (em horas úteis — declarar no payload). Afetada por **[C4]** |
| `team.cycle_time` | `flow.py:65-69` | `time_stats([duration_hours(first_stage_start('development'), delivered_at)])` | ✅ Boa definição. ⚠️ Terceira definição de cycle time no sistema — consolidar **[C3]** |
| `planning_to_approval_time` | `flow.py:262-272` | Horas do span `planning` imediatamente seguido de `approval` (primeiro par) | ✅ ⚠️ só o primeiro par; múltiplos ciclos de replanejamento invisíveis |
| `flow_efficiency` | `flow.py:72-88, 206-217` | `work = Σ horas em WORK_GROUPS (clipped à entrega)`, `wait = Σ QUEUE_GROUPS`; `eff = 100·work/(work+wait)` | ⚠️ (a) `WORK_GROUPS` inclui `planning` e `analysis_planning` (`flow.py:36-44`) — planejamento como "touch time" infla a eficiência; o próprio timeline os trata como `pre_flow`. (b) Horas de meses anteriores entram na eficiência do mês — aceitável, mas documentar. (c) Grupos fora das duas listas (ex. `unknown` **[C5]**) somem do denominador |
| `wip_total` / `wip_by_stage` | `flow.py:220-235` | Cards não fechados cujo grupo atual ∉ TERMINAL | ⚠️ Cards em `unknown` contam como WIP **[C5]**; snapshot no momento do cálculo — para relatório de mês fechado é o WIP *de hoje*, não do fim do mês |
| `little_law_predicted_lead_time_days` | `flow.py:89-90, 100-104` | `throughput/dia = entregues_no_mês / max(1, dias_corridos)`; `lead previsto = WIP_atual / throughput` | ⚠️ Mistura WIP instantâneo atual com throughput do mês selecionado (que pode ser passado). Little's Law exige médias no mesmo período estacionário: usar WIP médio do período (integrável do CFD) |
| `stage_time` | `flow.py:74-88, 107-114` | `time_stats` das horas por grupo (clipped à entrega) dos entregues no mês | ✅ com ressalvas **[C2][C4]** |
| `aging_wip` | `flow.py:125-179` | Para cards abertos: idade = `duration_hours(start do stage atual, now)`; baseline p50/p85 = percentis de TODOS os spans históricos fechados do grupo (all-time) | ⚠️ (a) Baseline contaminado por **[C2]**. (b) `_current_non_terminal_stage` (`flow.py:275-282`) tem loop que itera uma única vez — funciona, mas é enganoso. (c) `_percentile_from` (`flow.py:298-299`) devolve `median_hours` para qualquer pct ≠ 85 — chamada com `pct=50` funciona por coincidência; chamar com 95 devolveria a mediana ❌ latente |
| `cfd` | `flow.py:182-203` | Para cada dia do mês (até `now`), conta cards por grupo vigente no cutoff 23:59:59 local | ✅ Algoritmo correto. ⚠️ O(dias×cards×stages); cards arquivados aparecem "parados" para sempre **[C2]**; terminal aparece como estoque (atípico, mas aceitável) |
| `open_cards[]` | `flow.py:238-259` | Idade do stage atual + campos do card | ✅ |

### 1.3 `sla` (sla.py)

| Métrica | Onde | Fórmula | Veredito |
|---|---|---|---|
| Limite por etapa | `_sla_limit_info`, `sla.py:212-267` | Cascata: excluded → wip_only → análise por nível → development por nível (só `problem`) → retorno por prioridade → `stage_hours` → `stage_calendar_hours` | ✅ Bem estruturada e parametrizada no workflow.json |
| `elapsed` por check | `sla.py:296-307` | `business_hours_between(start, end ∨ now)` ou horas corridas se `stage_calendar_hours` | ✅ mecânica; ❌ herda **[C2]** (stage aberto de card arquivado estoura SLA para sempre) e **[C4]** (feriado conta como expediente → falso estouro) |
| `status` (ok/em_risco/estourado) | `sla.py:130-137` | `estourado` se `elapsed > limit`; `em_risco` se stage aberto e `usage ≥ risk_threshold` | ✅ |
| `team.compliance_pct` | `sla.py:95` | `100·(checks − breached)/checks` | ⚠️ `_stage_in_period_scope` (`sla.py:197-209`) inclui **todos** os stages (de qualquer mês) quando o card foi entregue no período — a "compliance do mês" mistura violações antigas; defensável mas não documentado |
| `by_developer/tester/...` | `sla.py:352-385` | Agrupa checks por pessoa cujo grupo ∈ `ROLE_CONFIGS[role].groups`, filtrando por prefixo | ⚠️ `waiting_review` não pertence a nenhum papel → estouros de "Aguardando revisão formal" não aparecem em `by_revisor` (caem em "Pipeline") |
| `current_alerts` | `sla.py:56-67, 173-194` | Último stage de cards não fechados com status ≠ ok | ✅; ⚠️ `is_open_stage` via `_same_instant(end_at, now)` com tolerância de 1s — acoplamento frágil |
| Dead code | `sla.py:280-286, 401-402` | `_sla_limit_hours` e `_by_developer` sem uso | ⚠️ remover |

### 1.4 `dora` (dora.py)

| Métrica | Onde | Fórmula | Veredito |
|---|---|---|---|
| `deployment_frequency` | `dora.py:32-41, 75-86` | 1 deploy = 1 span com grupo ∈ {production, direct_production} iniciado no período (cards `problem`); por semana ISO via `week_key` | ⚠️ **[W1]** semana em UTC; card que entra/sai/entra em produção conta 2 deploys — conflita com `return_after_terminal` que classifica a re-entrada como violação |
| `lead_time_deploy` | `dora.py:43-47, 99-109` | `duration_hours(start do primeiro span waiting_production, start do span de produção)`; direct_production → 0h | ❌ **[W2]** múltiplos deploys usam a 1ª fila (lead negativo é mascarado pelo clamp em 0); direct_production sempre contribui 0h, puxando a mediana para baixo. Corrigir: última entrada em `waiting_production` **anterior** ao start do span de produção; excluir direct do stats ou reportar separado |
| `change_failure_rate` | `dora.py:88-94, 112-150` | Falha = ∃ card `problem` + label CORRECAO do mesmo `sistema` criado em `[deploy, deploy+7d]`; `rate = 100·falhas/deploys` | ⚠️ Proxy honesto e documentado. Ressalvas: label pode ser adicionada depois da criação (não observável hoje — ver B6); dois deploys do mesmo sistema na janela contam a mesma correção 2×; `sistema` comparado por string crua sem `normalize_key` |
| `time_to_restore` | `dora.py:54-63` | `time_stats(lead created→delivered)` de correções CORRECAO com prioridade URGENTE/CRITICA entregues no mês | ⚠️ Proxy razoável; usa horas úteis para indicador que o mercado mede em horas corridas — reportar também em calendário |

### 1.5 `fibonacci_points` (fibonacci_points.py:41-88)

Fórmula: para entregues no período com `desenvolvedor` iniciando em `D-`: soma `fibonacci_level ∨ 0` particionado por `kind ∈ {problem, analysis}`.

**Veredito: ✅** com ressalvas: (a) prefixo `D-` hardcoded (também em `developers.py:154/176`, `engine.py:479`); (b) card entregue **sem nível** contribui 0 pontos silenciosamente — deveria ser contado à parte (`cards_sem_nivel`); (c) `parse_fibonacci_level` (`utils/fibonacci.py:8-18`) extrai o primeiro inteiro — entrada malformada como `"1.5"` vira nível 1 válido ⚠️.

### 1.6 `developers` (developers.py)

| Métrica | Onde | Fórmula | Veredito |
|---|---|---|---|
| `rework_rate_pct` | `developers.py:68-73` | `100·cards_com_retorno/entregues`; qualidade = `100 − rework` | ⚠️ herda **[C1]** |
| `acceptance_rate_pct` | `developers.py:63-67` | `100·accepted/entregues` | ⚠️ **[C1]** |
| `avg_hours_per_point` | `developers.py:62` | `dev_work_hours_total / pontos_totais` | ✅ boa métrica; ⚠️ pontos de análise e problema somados no denominador — ok se a intenção é blended |
| `pipeline_wait_ratio_pct` | `developers.py:74-78` | `100·wait/(work+wait)` | ⚠️ horas fora das partições somem (ver 1.1) |
| `aggregate_developer_profiles` | `developers.py:165-189` | Reexecução integral de `aggregate_developers` + lista de cards | ⚠️ duplicação/2× custo |

### 1.7 `reviewers` (reviewers.py:35-63)

`reviews_done` por `revisor_par` de cards **entregues** no mês; `sent_back` se `peer_review_sent_back`; senão `escaped_to_test` se `return_dev_by_teste_count > 0`; senão `approved`. `approval_rate = 100·approved/reviews`.

**Veredito: ⚠️** — (a) o agregador chama-se "reviewers" mas cobre apenas o revisor **em par**; o revisor formal só existe em `collaborators`. (b) `escaped_to_test` culpa o revisor em par por qualquer retorno de teste, mesmo que o defeito tenha nascido depois da revisão. (c) Não exige que o card tenha de fato passado por peer_review — card com `revisor_par` preenchido mas que pulou a etapa conta como review feita ❌ parcial. (d) Cards não entregues com revisão feita no mês não contam (janela por entrega).

### 1.8 `testers` (testers.py:43-88)

Escopo: entregues no mês, `kind=problem`, `passed_test_phase`. `approved_first_pass` se `¬tester_returned_dev`; `prevented_problems += return_dev_by_teste_count`; `tester_return_rate = 100·cards_com_retorno_do_tester/testados`; médias de `waiting_test`/`testing` por card.

**Veredito: ⚠️** — (a) `retest_cycles_total` **herda o ❌** de `test_cycles` (todo card testado 1× soma 1 reteste falso). (b) `avg_wait_test_hours` credita ao tester a espera da fila (`waiting_test`), que frequentemente é gargalo do pipeline, não da pessoa. (c) `to_dict` retorna `tester_return_rate_pct: 0.0` hardcoded corrigido por fora (linhas 82-84) — frágil.

### 1.9 `requesters` (requesters.py:55-86)

`cards_created` (criados no mês) acumula `planning/approval hours` totais do card; `planning_ok_rate = 100·(sem retorno sup ∧ ¬aprovação prematura)/entregues`; `in_production` se `group_hours[production] > 0 ∨ kind == problem`.

**Veredito: ⚠️** — (a) `in_production` com `∨ kind == "problem"` marca **todo** problema entregue como "em produção", mesmo parado em `waiting_production` — quase tautológico para problems ❌ parcial. (b) Médias `avg_planning_hours` dividem horas de todo o ciclo de vida apenas pelos criados no mês — janelas mistas. (c) Herda `gestor_premature_approval` sem ordem temporal (1.1).

### 1.10 `collaborators` (collaborators.py:228-297)

Identidade = nome sem prefixo de papel (`_ROLE_PREFIX_RE`). Por papel: `cards_active`, `cards_delivered`, horas por processo somando `stage.hours` dos grupos do papel.

**Veredito: ⚠️** — três problemas de janela/atribuição:
1. **Horas não recortadas ao período**: `add_process` (linhas 94-108) soma `stage.hours` integral de qualquer card *ativo* no mês — um card criado há 4 meses e pausado no mês corrente traz TODAS as horas históricas para o `time_hours` do colaborador no mês. Fórmula correta: interseção do span com `[period.start, period.end)`.
2. `cards_created` por colaborador (linhas 273-276): adiciona para **qualquer papel** (um tester "criou" o card onde é tester) — `summary.cards_created` inflado ❌ parcial.
3. `_ROLE_PREFIX_RE` vs `sla.ROLE_PREFIXES`: os dois módulos discordam sobre quem é pessoa válida.

Acoplamentos: importa `_card_entry` privado de `card_dossier`; `ROLE_CONFIGS` é importado por `sla.py`.

### 1.11 `antifraud` (antifraud.py:25-200)

Pipeline: cópias no período → whitelist (template/nome/cross-board) → lineage da fonte (status, terminal, descarte rápido ≤120s, última lista) → score `high/medium/low`.

**Veredito: ✅** no desenho geral (melhor módulo do engine), com ressalvas: (a) `rapid_copy_dispose` fixo em 120s hardcoded (linha 348) — expor no config; (b) `name_matches_delivered` compara com entregues **do mesmo período** apenas — reset de card entregue no mês anterior escapa do flag; (c) `same_board_copies_evaluated` nome ambíguo; (d) `passed_terminal` sujeito a **[C2]** (baixo impacto).

### 1.12 `bottlenecks` (bottlenecks.py:23-145)

| Métrica | Fórmula | Veredito |
|---|---|---|
| `by_stage` | Para entregues no mês: média/mediana/p95 de `group_hours[g] > 0` por grupo | ⚠️ `group_hours` é vida inteira do card (sem clip ao período nem à entrega — inclui horas pós-entrega!); `_percentile` local (linhas 15-20) usa nearest-rank com `round`, **divergindo** de `common.percentile` (interpolação linear) — dois p95 diferentes no mesmo relatório ❌ de consistência |
| `stuck_now` | `days_stuck = (now − date_last_activity)/86400` com `datetime.now()` **dentro** do agregador (linha 62) | ⚠️ impureza (única do engine); `date_last_activity` inclui comentários/edições, subestimando o tempo parado na lista (o span atual seria mais correto) |
| `by_sistema` | média de `Σ group_hours[gargalos]` por sistema | ✅ (mesmas ressalvas de janela) |
| `management_only_view` | Contagem por lista literal | ✅ ⚠️ comparação por string crua sem `normalize_key` (linhas 138-141) |

### 1.13 `quality_gates` (quality_gates.py:9-51)

`mandatory_compliance = 100·(obrigatórios − violações)/obrigatórios` (100.0 se vazio); `recommended_done_pct` análogo (0.0 se vazio). **Veredito: ✅**. ⚠️ vazio→100% vs vazio→0% é assimétrico (adicionar `insufficient_data`).

### 1.14 `process_discipline` (process_discipline.py)

| Métrica | Fórmula | Veredito |
|---|---|---|
| `flow_conformity` | Sequência compactada de grupos vs `CANONICAL_ORDER`; retrocesso = posição menor que a máxima vista | ✅ desenho bom. ⚠️ `_compact_groups` para na primeira produção; análises nunca são validadas contra etapas core (só problems têm checagem de missing) |
| `skipped_stages` | Reconstrói grupos a partir dos **títulos** (`workflow.title_for_group(group) == title`, linhas 199-203) | ❌ frágil: reverse-lookup título→grupo quebra com títulos duplicados; o check já tem os grupos antes da tradução |
| `required_fields_by_stage` | % de cards ativos que atingiram o grupo com campos exigidos preenchidos | ⚠️ avalia o valor **atual** do campo, não o valor no momento da etapa (o histórico existe em `custom_field_changes` e não é usado) |
| `developer_assignment_latency` | `duration_hours(created_at, primeira mudança de Desenvolvedor)` | ⚠️ **sem filtro de período** (linhas 308-349): estatística all-time num relatório mensal; cards com histórico truncado ficam de fora sem contagem do viés |
| `post_terminal_returns` | contagem de timelines com `return_after_terminal` | ⚠️ também all-time — mistura violações antigas no mês |

### 1.15 `priority` (priority.py)

| Métrica | Fórmula | Veredito |
|---|---|---|
| `lead_time_by_priority` | `time_stats(created→delivered)` por prioridade | ✅ |
| `urgent_critical_pct` | `100·(URGENTE+CRITICA ativos)/ativos`; alerta se > 20 | ✅; ⚠️ threshold 20% hardcoded — expor no workflow |
| `queue_jumps` | Par (lower, higher): lower com prioridade pior, criado **depois** e entregue **antes** → jump; O(n²) com `break` no primeiro | ⚠️ (a) O(n²); (b) conta pares, não vítimas — definir unidade; (c) ignora `kind` e `sistema` |
| `urgent_aging` | linhas do aging com prioridade alta e status ≠ ok | ✅ (herda ressalvas do aging) |

### 1.16 `risk` (risk.py)

`score = 3·(above_p85) ∨ 1·(above_p50) + 2·high_priority + 2·(retornos ≥ 2) ∨ 1·(=1) + 2·(pausado agora) ∨ 1·(já pausou)`; níveis: ≥5 crítico, ≥3 alto, ≥1 médio. **Veredito: ✅** como heurística transparente. ⚠️ pesos hardcoded; herda baseline de aging **[C2]**; `returns` usa `developer_penalty_return_count` **[C1]**.

### 1.17 `trends` (trends.py:12-73)

Reexecuta `aggregate_developers` + `aggregate_bottlenecks` para cada um dos 6 meses. **Veredito: ⚠️/❌** — (a) **[W3]** `cards_delivered` = só devs `D-` → a série de tendência não bate com `team_summary.cards_delivered` do mesmo mês; (b) `aggregate_bottlenecks` computa `stuck_now` com `datetime.now()` seis vezes; (c) `rework_rate` mensal herda **[C1]**.

### 1.18 `card_dossier` (card_dossier.py:72-117)

Agrupamento descritivo por dev/solicitante/tester de cards ativos no mês. **Veredito: ✅** (não é cálculo). ⚠️ expõe `lead_time_hours`/`cycle_time_hours` com os problemas de 1.1; `_card_entry` é a "API interna" mais reutilizada e é privada.

### 1.19 `analysis_workflow` (analysis_workflow.py:12-75)

| Métrica | Fórmula | Veredito |
|---|---|---|
| `analysis_in_planning_wip` | `visits(analysis_planning) > 0 ∧ ¬entregue no período` | ❌ nome diz "WIP em planejamento", fórmula conta qualquer análise ativa que já **passou** por planejamento — card atualmente em desenvolvimento conta como WIP de planejamento. Correção: grupo do stage atual == `analysis_planning` |
| `planning_wait` | `time_stats(group_hours[analysis_planning] > 0)` de ativos | ⚠️ vida inteira, sem clip de período |
| `descricao_completa_pct` | `100·(analise_realizada ∧ recomendacao)/ativos` | ✅ |
| `highlight_cards` | primeiros 25 ativos na ordem de iteração | ⚠️ amostra arbitrária (ordem do export), não os piores — ordenar por flags/horas |

### 1.20 `engine.py` (payload base + team_summary)

| Métrica | Onde | Fórmula | Veredito |
|---|---|---|---|
| `overview.*` | `engine.py:186-219` | contagens diretas | ✅ |
| `custom_fields` | `engine.py:221-231` | Counter por campo; "Nao informado" só para Prioridade/Sistema | ⚠️ dupla série Nível/Nivel (alias do parser, `export_loader.py:163-167`); denominadores inconsistentes |
| `movements.time_by_list` | `engine.py:243-303, 388-417` | spans próprios do engine | ❌ **[C3]**: usa qualquer evento com `to_list_name` (inclui `archived`/`unarchived`/`deleted` com from==to) → spans fragmentados e contagens infladas vs a timeline oficial |
| `cards[].cycle_time_hours` | `engine.py:419-434` | criado → primeiro evento em done_groups (≠ delivery_groups!) | ❌ **[C3]**: diverge de `flow.cycle_time` e `timeline.cycle_time_hours`; sem done usa `date_closed ∨ now` → herda **[C2]** |
| `team_summary.acceptance_rate_pct` | `engine.py:492, 521` | `100·accepted/entregues` | ⚠️ **[C1]** |
| `team_summary.return_dev_rate_pct` | `engine.py:493, 522` | `100·Σeventos_retorno/entregues` | ⚠️ é razão de **eventos por card** ×100 vestida de percentual — pode passar de 100%. Renomear (`return_events_per_100_cards`) ou trocar numerador para cards com retorno |
| `rework/quality_rate_pct` + `quality_seal` | `engine.py:499-503, 538` | `100·cards_com_retorno/entregues`; selo por thresholds do workflow | ✅ na forma; ⚠️ **[C1]** no insumo |
| `fibonacci_normal/analysis` | `engine.py:482-491` | Σ pontos de entregues com dev `D-` | ✅ (ressalvas de 1.5) |
| `data_quality` | `engine.py:355-386` | % de cards com required fields | ✅; ⚠️ não cobre listas unknown **[C5]** nem ações descartadas pelo parser |

### 1.21 Utilitários numéricos

- `common.percentile` (`common.py:19-31`): interpolação linear — ✅ correta. `time_stats` (34-72): trata vazio, marca `insufficient_data` com `min_sample=10` — ✅.
- `bottlenecks._percentile`: nearest-rank — ❌ inconsistente com o acima (unificar).
- Divisões por zero: todas as taxas checam denominador — ✅ (auditadas todas; nenhuma divisão por zero possível encontrada).
- `human_hours` (`utils/dates.py:38-52`): ❌ **[W4]** — 30h úteis viram "1.25 dias" (são >3 dias de trabalho de ~9h).
- `MonthPeriod.contains` (`period.py:15-19`): `[start, end)` — ✅; `parse_month` sem validação de formato ⚠️.
- `business_hours_between`: janela com almoço e horários por dia ✅; sem feriados ❌ **[C4]**; O(dias) por chamada ⚠️ performance; DST não é problema atual (Brasil sem horário de verão desde 2019) ✅.

---

## PARTE 2 — Melhorias nas métricas existentes

Prioridade decrescente (correção de número errado > semântica > robustez > apresentação).

### 2.1 Correções de fórmula (❌)

1. **Aceitação/retrabalho [C1]** — definir dois contadores explícitos na timeline:
   - `returns_before_delivery = #{moved→return_developer | at < delivered_at}`
   - `returns_after_terminal` (já existe).
   Fórmulas: `acceptance = 100·#{delivered ∧ returns_before_delivery=0}/delivered`; retrabalho idem. Retornos pós-terminal ficam SÓ em `post_terminal_returns` (sem dupla penalização). Remover o código morto de `timeline.py:333-337` ou torná-lo a fonte única.
2. **Spans/arquivamento [C2]** — encerrar o span corrente no primeiro evento `archived` (e reabrir em `unarchived`); `lead_time_hours = duration(created_at, delivered_at ∨ archived_at ∨ now)` e expor `is_open` para o consumidor distinguir idade de lead time.
3. **Unificação de cycle time [C3]** — eleger `metric_cycle_hours` (flow_start→delivered) como "cycle time" oficial; `flow.cycle_time` passa a consumi-lo; deletar `engine._cycle_time_hours` e `engine._timeline_spans` (o `time_by_list` deve agregar `timeline.stage_timeline` por `list_name`).
4. **`test_cycles`** — `test_cycles = group_visits["testing"]`; `retest_cycles = max(0, test_cycles − 1)`. Se quiser manter `waiting_test` como início de ciclo, contar **pares** (entrada na fase = transição de fora do conjunto {waiting_test, testing} para dentro).
5. **`analysis_in_planning_wip`** — `#{analysis ativos | grupo do último stage == analysis_planning ∧ card aberto}`.
6. **`requesters.in_production`** — remover `∨ kind == "problem"`; usar `group_visits["production"] + group_visits["direct_production"] > 0`.
7. **Percentil único** — substituir `bottlenecks._percentile` e `flow._percentile_from` por `common.percentile` (e passar o pct de verdade).
8. **DORA lead de deploy [W2]** — `window_start = max{start(s) | s.group == waiting_production ∧ start(s) ≤ start(prod_span)}`; direct_production reportado como série separada (`lead_time_deploy_direct`).
9. **`skipped_stages`** — usar os grupos do check diretamente, não o reverse-lookup por título.
10. **`human_hours` [W4]** — parâmetro `business_day_hours` (derivado do expediente: ~8,9h média) e formato "X dias úteis" quando a grandeza for horas úteis.

### 2.2 Semântica e janelas (⚠️)

11. **Clipping de período nas horas por pessoa** (`collaborators.add_process`, `bottlenecks.by_stage`, `analysis_workflow.planning_wait`): calcular `overlap = duration_hours(max(start, period.start), min(end, period.end))`. Se mantiver "vida inteira do card entregue no mês", gravar `"window": "card_lifetime"` no payload — hoje o leitor não tem como saber.
12. **`collaborators.cards_created`** — só adicionar quando `role_key == "solicitante"`.
13. **`team_summary.return_dev_rate_pct`** — renomear para `return_dev_events_per_card` ou mudar numerador para `cards_with_rework`.
14. **Trends [W3]** — série mensal de entregas do time deve usar `#{delivered_in(period)}` (mesma definição do team_summary); manter a série por dev separada.
15. **SLA por papel** — mapear `waiting_review → revisor` (ou papel "fila do revisor") e documentar em `policy.note` o escopo temporal dos checks.
16. **`gestor_premature_approval`** — exigir ordem temporal (`t(dev→sup) > t(approval→dev)`).
17. **`developer_assignment_latency` e `post_terminal_returns`** — filtrar por período, com opção all-time separada.
18. **DORA CFR** — deduplicar correção por deploy (uma correção só "falha" o deploy mais próximo anterior); normalizar `sistema` com `normalize_key`.
19. **`reviewers`** — exigir `passed_peer_review` para contar `reviews_done`; renomear para `peer_reviewers` ou incluir revisor formal.
20. **Little's Law** — `WIP_médio = média diária de cards em progresso no CFD do mês`; `lead previsto (dias úteis) = WIP_médio/throughput_por_dia_útil`. Se mantiver WIP instantâneo, rotular como `current_wip_projection`.

### 2.3 Parâmetros a expor no workflow.json

| Parâmetro | Hoje | Proposta |
|---|---|---|
| Feriados | inexistente **[C4]** | `sla_rules.holidays: ["2026-01-01", ...]` (+ opcional `holiday_calendar: "BR"`) consumido por `_business_windows_for_day` |
| Prefixos de papel (`D-`, `T-`...) | hardcoded em 4 arquivos | `role_conventions: {desenvolvedor: {prefix: "D-"}, ...}` — fonte única para sla/collaborators/developers/engine |
| Janela CFR (7 dias) | default de função | `dora.change_failure_window_days` |
| `rapid_copy_dispose` 120s | hardcoded `antifraud.py:348` | `antifraud.rapid_dispose_seconds` |
| Inflação de prioridade 20% | hardcoded `priority.py:57` | `priority.inflation_alert_pct` |
| Pesos do risk score | hardcoded `risk.py:56-87` | `risk_score_weights: {...}` |
| `min_sample` do `time_stats` | 10 fixo | `stats.min_sample` |

### 2.4 Notas metodológicas a adicionar ao payload (padrão já existe em `dora.note`)

- `flow.note`: unidade = horas úteis (expediente INTGEST), sem feriados até implementação; eficiência considera planejamento como trabalho (ou não, após correção).
- `sla.policy.scope_note`: regra de inclusão de checks (entrega no mês ⇒ todas as etapas).
- `collaborators.note`: janela de horas (lifetime vs período).
- `data_quality`: acrescentar `unknown_lists: [{list_name, cards, movements}]` **[C5]** e `parser_discards: {actions_sem_data, actions_sem_card}`.

---

## PARTE 3 — Novas métricas implementáveis

Convenções do pseudocódigo: `T` = `CardTimeline`, `S` = `StageTimelineEntry`, `E` = `MovementEvent`, `C` = `TrelloCard`, `P` = `MonthPeriod` (`[P.start, P.end)`, tz `America/Sao_Paulo`), `bh(a,b)` = `duration_hours(a,b,workflow)` (horas úteis), `cal(a,b)` = horas corridas. Todos os stats via `common.time_stats` (já trata vazio/`insufficient_data`).

### GRUPO A — Implementáveis já, com os dados atuais

#### A1. Flow Efficiency por card (touch/lead) — distribuição, não só agregado
**Negócio**: o agregado do time (`flow.flow_efficiency`) esconde cards 5% eficientes atrás de cards 60%. O gestor quer a cauda.
```
para T em delivered_in(P), com flow_hours_until_delivery > 0:
    touch  = T.dev_work_hours + Σ S.hours clipped, S.group ∈ {peer_review, review, testing}   # trabalho real de qualquer papel
    total  = T.flow_hours_until_delivery
    eff(T) = 100 · touch / total
saída: time_stats([eff(T)]), + lista dos k piores (eff < 15%)
edge: total == 0 (entrega no mesmo instante) → excluir da amostra; grupos unknown → registrar em nota
onde: flow.py (nova chave team.flow_efficiency_distribution) — pré-requisito: decidir C2/planning (2.1)
```

#### A2. Percentis de aging por etapa (tabela p50/p85/p95) + SLE de etapa
**Negócio**: transformar o baseline interno do aging (hoje escondido por card) em tabela de referência: "quanto tempo um card normalmente fica em cada etapa".
```
hist[g] = [S.hours | T ∈ timelines, S ∈ T.stage_timeline, S.end_at ≠ None,
           S.group == g, P_12m.contains(S.start_at)]      # janela móvel, não all-time
row(g)  = {p50: percentile(hist[g],50), p85: ..., p95: ..., samples: len}
edge: samples < min_sample → insufficient_data; excluir spans de cards arquivados (C2)
onde: flow.py (aging_baseline) — reusar em aging_wip para eliminar o _percentile_from quebrado
```

#### A3. First-Time-Right por gate
**Negócio**: % de cards que atravessam cada gate (revisão em par, revisão formal, teste) sem NENHUMA devolução — métrica de qualidade de entrada, complementar ao retrabalho.
```
para T em delivered_in(P), kind == "problem":
    ftr_peer(T) = passou(peer_review) ∧ T.peer_review_returns == 0 ∧ T.return_dev_by_revisao_count == 0
    ftr_test(T) = passou(testing) ∧ T.return_dev_by_teste_count == 0
FTR_gate = 100 · #{T | ftr_gate(T)} / #{T | passou(gate)}
edge: denominador 0 → null + insufficient_data; usar contadores corrigidos (C1)
agregações: por time, por dev (D-), por mês (série 6m)
onde: novo aggregator first_time_right.py (ou dentro de quality_gates.py)
```

#### A4. Rework Ratio (horas)
**Negócio**: retrabalho em **horas**, não em contagem — 3 retornos de 10 min ≠ 1 retorno de 3 dias.
```
para T em delivered_in(P):
    rework_h = T.group_hours.get("return_developer", 0)
    ratio(T) = 100 · rework_h / max(T.flow_hours_until_delivery, ε)
team_rework_ratio = 100 · Σ rework_h / Σ flow_hours   (ponderado, não média de razões)
edge: flow_hours == 0 → excluir; clipping à entrega já existe via stage clipped
onde: flow.py ou developers.py (por dev: Σ sobre cards do dev)
```

#### A5. Blocked Time Ratio
**Negócio**: quanto do lead time foi bloqueio explícito (pausa + retorno suporte) — separa "demora porque trabalhoso" de "demora porque travado".
```
blocked_h(T) = Σ S.hours clipped, S.group ∈ {paused, return_support}
ratio(T)     = 100 · blocked_h / max(flow_hours_until_delivery, ε)
saída: time_stats + top-k cards; série por semana (week_key LOCAL — corrigir W1 antes)
onde: flow.py; cruzar com PausaDetail.motivo (timeline.pausas) para ranking de motivos de pausa:
    Counter(normalize_key(p.motivo[:60]) for T ativos, p in T.pausas if P.contains(p.momento))
```

#### A6. Handoff Count por card
**Negócio**: nº de trocas de responsabilidade — proxy de custo de coordenação; correlaciona com defeito.
```
role_of(g) = papel dono do grupo (ROLE_CONFIGS invertido; grupos de fila herdam o papel do próximo)
para T em delivered_in(P):
    seq = [role_of(g) for (src,g) in T.transitions if role_of(g) ≠ None]
    handoffs(T) = #{i | seq[i] ≠ seq[i-1]}
saída: time_stats(handoffs), por nível Fibonacci (handoffs esperados crescem com nível?)
edge: transitions vazio (card criado direto no terminal) → 0
onde: novo aggregator handoffs.py ou process_discipline.py
```

#### A7. Previsibilidade por nível Fibonacci (CV) + banda de estimativa
**Negócio**: o nível 5 "vale" 12h de SLA — mas qual a dispersão real? Se o CV é 1.8, a estimativa não informa nada.
```
para nível L ∈ {1,2,3,5,8,13}:
    xs = [T.metric_cycle_hours | T delivered_in(P_6m), T.fibonacci_level == L, T.kind == "problem"]
    cv(L) = stdev(xs)/mean(xs)  se len(xs) ≥ 5 e mean > 0
    banda(L) = (p50, p85)
saída: tabela L → {samples, median, p85, cv, sla_atual: development_hours_by_level[L], sla_vs_p85}
insight direto: sla_vs_p85 > 1 ⇒ SLA do workflow.json está irreal para o nível
onde: novo aggregator estimation_accuracy.py; janela 6m via month_range existente
```

#### A8. Service Level Expectation (SLE)
**Negócio**: comunicação probabilística ao solicitante: "85% dos níveis 3 saem em ≤ N dias úteis".
```
para (kind, L): xs = metric_cycle_hours dos entregues (janela 6m)
SLE_85(kind,L) = percentile(xs, 85) → converter p/ dias úteis (h / business_day_hours)
compliance_mes = 100 · #{T delivered_in(P) | metric_cycle ≤ SLE_85 vigente} / #{delivered com nível}
edge: sem histórico → usar development_hours_by_level como SLE provisório e marcar "baseline=sla"
onde: estimation_accuracy.py ou sla.py (nova seção sle)
```

#### A9. Monte Carlo Throughput Forecast (IC 85%)
**Negócio**: "quantos cards cabem no próximo mês?" com intervalo de confiança, em vez de média enganosa.
```
hist_semanas = [#{T | delivered_at ∈ semana_w} for w nas últimas 26 semanas locais]  # week_key local
simulação (n=10_000):
    total_i = Σ_{s=1..semanas_do_próximo_mês} choice(hist_semanas)   # bootstrap
saída: {p15, p50, p85} de total_i  →  "com 85% de confiança entregamos ≥ p15 cards"
mesma máquina para pontos: hist de Σ fibonacci por semana
edge: < 8 semanas de histórico → insufficient_data; semanas com throughput 0 DEVEM entrar na amostra
onde: novo aggregator forecast.py (puro: random.Random(seed fixo) p/ reprodutibilidade do relatório)
```

#### A10. Net Flow / tendência de WIP
**Negócio**: WIP subindo = lead time futuro subindo (Little). Detecta o problema antes do atraso.
```
para cada semana w do período (e 12 anteriores):
    arrivals(w)  = #{T | T.created_at ∈ w}            # ou 1ª entrada em development, p/ fluxo operacional
    departures(w)= #{T | T.delivered_at ∈ w}
    net(w)       = arrivals − departures
saída: série {week, arrivals, departures, net, wip_acumulado}; alerta se média móvel 4s de net > 0
edge: semanas parciais no início/fim → marcar partial=true
onde: flow.py (seção net_flow) — só usa created_at/delivered_at já existentes
```

#### A11. Tempo até primeira movimentação (responsividade de triagem)
**Negócio**: card criado que ninguém toca é backlog invisível.
```
para T com is_created_in(P):
    first_move = min(E.at | E ∈ eventos(T), E.event_type == "moved")
    triage_h(T) = bh(T.created_at, first_move)   ; None se nunca movido → idade atual, flag "never_moved"
saída: time_stats + lista never_moved com idade
onde: process_discipline.py
```

#### A12. Churn de desenvolvimento (re-entradas)
**Negócio**: complementa retornos: quantas vezes o card re-entrou em `development` por qualquer rota.
```
churn(T) = max(0, T.group_visits.get("development", 0) − 1)
saída por dev e por nível; correlação churn × nível (níveis altos com churn alto = decompor melhor)
onde: developers.py (campo novo por card/agregado)
```

#### A13. Tamanho da descrição × lead time (proxy de tamanho de card)
**Negócio**: valida a nivelação Fibonacci contra um proxy objetivo. Dado já disponível: `C.raw["desc"]` é retido no parser.
```
para T delivered_in(P) com nível:
    size = len(clean_spaces(C.raw.get("desc","")))
buckets de size (quartis) × time_stats(metric_cycle_hours); + correlação de postos (Spearman) size×nível
edge: descrições template (placeholders) inflam size → subtrair tamanho do template padrão se detectado
onde: estimation_accuracy.py; ressalva: se TrelloCard.raw for removido por memória (recomendado), promover desc_length a campo do modelo
```

### GRUPO B — Requerem ampliar `action_filter` do fetch e/ou o parser

#### B1. Latência e consistência de atribuição de membro — habilita: `addMemberToCard`, `removeMemberFromCard` (+ parsear `idMembers`/`members` já baixados)
**Negócio**: o campo "Desenvolvedor" é preenchido à mão; o membro do card é o dado nativo. Divergência = disciplina de processo furada; a latência de atribuição real fica precisa.
```
parser: novo evento MemberEvent(card_id, at, member_id, member_name, op ∈ {add, remove})
assign_latency(T) = bh(T.created_at, min(at | op==add))
consistency(T)    = normalize_key(member_name) ≅ collaborator_identity(T.desenvolvedor)   # match fuzzy por nome-base
métricas: time_stats(assign_latency) no período; pct_inconsistentes = 100·#{T | ¬consistency}/#{T com ambos}
WIP pessoal real: #{cards abertos | member ∈ idMembers} por pessoa (multitasking index)
edge: membros múltiplos → usar o 1º add após criação; remove+add = reatribuição (contar reassignments)
onde: process_discipline.py (latência/consistência) + collaborators.py (WIP pessoal)
```

#### B2. Tempo de resposta a comentários / colaboração — habilita: `commentCard`
**Negócio**: em RETORNO (DEV)/PAUSADO, o card anda por conversa. Silêncio = card morto.
```
parser: CommentEvent(card_id, at, actor_id, actor_name, text_len)
first_response(T) = para cada comentário c de autor A, menor (c2.at − c.at) com autor ≠ A
métricas: time_stats(bh(c.at, c2.at)) por período; comments_per_card;
silent_blocked = #{T | grupo atual ∈ {paused, return_support} ∧ nenhum comentário nos últimos 5 dias úteis}
justificativa de retorno: % de eventos moved→return_developer com comentário do actor em ±30min
   (substitui a heurística frágil de casamento posicional do test_return_missing_reason_count — 1.1)
edge: comentários de bot/gestor → lista de exclusão no workflow.json
onde: novo aggregator communication.py
```

#### B3. Due date compliance e previsibilidade — habilita: `updateCard:due` (+ parsear `due`/`start` já presentes no JSON do card)
**Negócio**: previsibilidade percebida pelo cliente = entregar quando prometido, não rápido.
```
parser: card.due, card.start (datetime|None); DueChange(card_id, at, old_due, new_due)
on_time(T)      = T.delivered_at ≤ due_vigente_na_entrega   (última DueChange antes de delivered_at, senão card.due)
compliance      = 100 · #{delivered_in(P) ∧ due≠None ∧ on_time} / #{delivered_in(P) ∧ due≠None}
desvio(T)       = bh(due, delivered_at) assinado (negativo = adiantado)  → time_stats do atraso
replan_rate     = 100 · #{T | #DueChanges(T) ≥ 2} / #{T com due}; replans_per_card = média de mudanças
edge: due removido (new_due=None) → card sai do denominador a partir dali; due herdada de template → ignorar due == created_at + 0
onde: novo aggregator predictability.py; agregações por solicitante (quem promete mal) e por dev
```

#### B4. Checklist completion e decomposição — habilita: parsear `checklists` (já baixados) + `convertToCardFromCheckItem`; `updateCheckItem` via webhook
**Negócio**: card grande sem checklist = escopo invisível; % de checklist completo na entrega mede definição de pronto.
```
parser: card.checklists = [{name, items: [{state ∈ {complete,incomplete}, name}]}]
completion(T) = 100 · #complete / #items   (na foto do export — limitação: estado atual, não na entrega)
métricas: pct_cards_with_checklist por nível (esperado: nível ≥5 ⇒ 100%);
          completion médio dos entregues; correlação #items × metric_cycle_hours (tamanho real);
          decomposition_rate = #convertToCardFromCheckItem no período (cards nascidos de itens)
com webhook updateCheckItem: tempo por item = at(complete) − at(complete do item anterior) → ritmo intra-card
edge: checklist de template com 0 marcados → excluir cards não iniciados do completion
onde: estimation_accuracy.py (tamanho) + quality_gates.py (definition of done)
```

#### B5. Fluxo entre boards — habilita: `moveCardToBoard`, `moveCardFromBoard`
**Negócio**: hoje um card movido para fora do board simplesmente "congela" na última lista (parece WIP eterno) e o antifraude trata cópias cross-board às cegas.
```
parser: BoardMoveEvent(card_id, at, direction ∈ {in, out}, other_board_id/name)
timeline: evento out encerra o span corrente (mesma correção do archived/C2); evento in ancora created_at local
métricas: cards_out/in por mês; % do WIP aparente que na verdade saiu do board (limpeza de aging_wip);
antifraude: cópia cuja fonte saiu do board → status "moved_out" em vez de "missing_history"
onde: timeline.py (spans) + antifraud.py + flow.py (WIP corrigido)
```

#### B6. CFR preciso por timestamp de label — habilita: `addLabelToCard` (webhook; na REST, `updateCard` de labels)
**Negócio**: o CFR atual usa a label CORRECAO como se existisse desde a criação do card. Com o evento, sabemos QUANDO o card foi classificado como correção.
```
correção válida p/ deploy D = card com addLabelToCard(CORRECAO) OU criado com a label,
                              com created_at ∈ [D, D + window]
CFR = 100 · #{deploys com ≥1 correção válida} / #{deploys}   (dedup por deploy — ver 2.2 item 18)
onde: dora.py — substitui a heurística atual mantendo o cfr_note atualizado
```

#### B7. Cadência de trabalho real por dev — habilita: `commentCard` + `updateCheckItem` + `updateCustomFieldItem` (já coletado) como "sinais de atividade"
**Negócio**: `dev_work_hours` mede permanência na lista, não trabalho. Sinais de atividade (comentários, checks, mudanças de campo) permitem um "active days per card".
```
active_days(dev, P) = #{dias úteis d | ∃ sinal de atividade do actor==dev em d}
focus(dev)          = cards distintos com sinal por dia (média) → multitasking real
edge: atividade de gestor movendo card do dev → separar por actor, não por campo Desenvolvedor
onde: novo aggregator activity.py; requer manter actor_id em todos os eventos novos (o modelo MovementEvent já tem)
```

### Resumo de habilitadores (fetch/parser)

| Habilitador | Métricas destravadas | Mudança |
|---|---|---|
| Parsear `idMembers`/`members`, `due`, `checklists` (já baixados) | B1 (parcial), B3 (parcial), B4 (parcial), A13 formal | só parser/models |
| `addMemberToCard`, `removeMemberFromCard` | B1 completo, B7 | action_filter |
| `commentCard` | B2, B7, motivo de retorno confiável | action_filter (volume alto — paginação `before` já existente) |
| `updateCard:due` | B3 completo | action_filter |
| `convertToCardFromCheckItem` | B4 (decomposição) | action_filter |
| `moveCardToBoard/FromBoard` | B5, correção de WIP/antifraude | action_filter |
| Webhooks (`updateCheckItem`, `addLabelToCard`, `updateComment`) | B4 fino, B6, auditoria de edição de justificativas | infraestrutura nova (persistir como eventos no backend e injetar em `BoardData.movements`/novas listas) |

### Observação final de sequenciamento

As novas métricas dos grupos A e B herdam a qualidade da timeline. A ordem racional é:

1. Corrigir C1/C2/C3 + `test_cycles` + percentil único;
2. Feriados (C4) e alerta de unknown (C5);
3. Implementar A2/A3/A4/A10 (baixo esforço, alto valor, dados prontos);
4. Ampliar o fetch para members/due/comments e entregar B1–B3, que são as métricas com maior valor gerencial novo (previsibilidade prometida e responsividade).

Cada métrica nova deve seguir a receita do projeto: aggregator + registro no engine + 3 cópias de `metric_definitions.json` + teste em `tests/test_metrics.py`.
