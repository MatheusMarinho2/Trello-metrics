# Análise Completa e Crítica do Projeto — Trello Analytics (INTGEST)

**Data:** 15/07/2026
**Método:** 7 análises paralelas por agentes especialistas — engine de métricas, backend Django, frontend React, camada de relatórios, QA/testes, DevOps/infra e auditoria da integração com a API REST do Trello (contra a documentação oficial da Atlassian). Todos os achados citam arquivo:linha e foram verificados no código atual do branch `main`.

---

## Sumário executivo

O projeto tem **fundações arquiteturais corretas**: engine puro sem Django, timeline como fonte única de verdade por card, controllers finos sobre services, frontend sem dependências pesadas, multi-stage build no Docker, e uma suíte de 48 testes determinísticos que passa em 0,3s. A integração com o Trello acerta nos pontos difíceis (paginação `before={id}` com `limit=1000`, `updateCustomFieldItem` no filtro, `customFieldItems` aninhado no board fetch).

Porém, a análise encontrou **problemas críticos reais em todas as camadas**, e três padrões transversais explicam a maioria deles:

### Padrão 1 — Duplicação sem fonte única (a classe de bug mais recorrente)
- As **3 cópias de `metric_definitions.json` estão dessincronizadas HOJE** (confirmado por MD5 por dois agentes independentes): o commit `8327b65` (antifraude) atualizou só `resources/`; PDF, HTML e frontend exibem memória de cálculo defasada.
- Existem **3 vocabulários de layout divergentes** (Python, report.js, reportLayouts.ts): a seção de Risco nunca renderiza no PDF de gestão (bug de chave `risk_board` vs `risk`), `analysis_workflow` existe no HTML mas não no PDF, e o relatório `general` mostra 4 seções a mais no HTML que no PDF.
- O engine calcula **spans e cycle time duas vezes com regras diferentes** (`engine._timeline_spans` vs `timeline._list_spans`) — números divergentes no mesmo relatório.
- Convenção de papéis/prefixos (`D-`, `T-`...) espalhada em 4+ lugares.

### Padrão 2 — Corretude silenciosa das métricas (o produto pode estar errando sem ninguém perceber)
- **Cards arquivados continuam acumulando horas úteis até hoje** (evento `archived` é ignorado no fechamento de spans) — infla lead time, SLA e bottlenecks.
- **Sem feriados** no cálculo de horas úteis — todo SLA multi-dia é superestimado no Brasil (falsos "estourados" que alimentam avaliação individual).
- **Semântica conflitante de `accepted_without_dev_return`** (um cálculo correto é sobrescrito por outro com regra diferente) — afeta taxa de aceitação de devs, colaboradores e projetos.
- **Listas não mapeadas viram `"unknown"` silenciosamente** — um rename no Trello faz cards sumirem das métricas sem nenhum alerta.
- Nenhum desses bugs é detectado pela suíte atual (cobertura global de 54%; parsers a 16–23%, backend e relatórios a 0%).

### Padrão 3 — Segurança e operação com defaults perigosos
- `SECRET_KEY` com fallback fixo público **assina os tokens de auth** — sem a env var na VPS, qualquer um forja login; `DEBUG` default `1`; credenciais default `gestor`/`intgest` públicas no repo; sem throttle no login; token não revogável.
- **XSS real no relatório HTML** (nome de card pode injetar `</script>`) e injeção de HTML nas tabelas do PDF.
- **Porta HTTP 8080 exposta mesmo com Caddy/HTTPS ativo** (bypass de TLS); Chromium roda **como root sem sandbox** no mesmo container do banco.
- **Sem backup automatizado do SQLite** — o volume Docker é o único lugar do histórico; healthcheck não detecta gunicorn morto; `desc_dump.txt` com dados do board commitado no repo.
- Transação atômica segura o write-lock do SQLite durante chamadas de IA de minutos; sem retry/backoff para 429 do Trello.

---

## Top 15 — plano de ação consolidado (impacto × esforço)

Itens ordenados para o maior retorno imediato; os 8 primeiros são um "dia de correções" que elimina os riscos mais graves.

| # | Ação | Área | Impacto | Esforço |
|---|------|------|---------|---------|
| 1 | Ressincronizar as 3 cópias de `metric_definitions.json` + check de `diff` no CI (fonte única: `resources/`) | Relatórios/Frontend/CI | Alto | Trivial |
| 2 | Corrigir `include("risk_board")` → `"risk"` no builder do PDF | Relatórios | Alto | Trivial |
| 3 | Escapar `</script>` e `page_title` no HTML interativo (XSS) | Relatórios | Alto | Trivial |
| 4 | Fail-fast no boot com `DEBUG=0` + `SECRET_KEY`/senha default; default `DJANGO_DEBUG=0` | Backend | Alto | Trivial |
| 5 | Bind `127.0.0.1:8080:80` no compose (fechar bypass HTTP) | DevOps | Alto | Trivial |
| 6 | Remover `desc_dump.txt` do git; remover `reportlab` e código morto | DevOps/Relatórios | Alto | Trivial |
| 7 | Encerrar spans no evento `archived` (horas de cards arquivados) | Engine | Alto | Baixo |
| 8 | Unificar semântica de `accepted_without_dev_return` | Engine | Alto | Baixo |
| 9 | Backup automatizado do SQLite (`sqlite3 .backup` + cron + offsite) e teste de restore | DevOps | Alto | Baixo |
| 10 | Try/except no `GenerateReportView` (erros do Trello → 4xx/502 claros) + retry/backoff para 429/5xx no `TrelloClient` | Backend/API Trello | Alto | Baixo |
| 11 | Estreitar `@transaction.atomic` (IA e engine fora da transação); `.defer()` no histórico; sync de colaboradores fora do GET | Backend | Alto | Baixo |
| 12 | Alerta de listas não mapeadas em `data_quality` + suporte a feriados nas horas úteis | Engine | Alto | Baixo/Médio |
| 13 | Testes P0: export_loader, auth, description_parser, golden file de regressão, sincronia dos JSONs | QA | Alto | Médio |
| 14 | Healthcheck da API (não do SPA) + throttle no login + logs no stdout + `/api/health/` | Backend/DevOps | Alto | Baixo |
| 15 | Ampliar `action_filter` do Trello (`addMemberToCard`, `commentCard`, `moveCardTo/FromBoard`, `convertToCardFromCheckItem`) + parada de paginação por página vazia | API Trello | Médio-Alto | Baixo |

**Direções estruturais de médio prazo** (depois dos itens acima): geração assíncrona de relatórios (202 + polling — resolve timeout de gunicorn, lock do SQLite e double-submit de uma vez); decomposição do `App.tsx` (plano detalhado na seção Frontend) e do `builder.py` (módulos `sections/`, depois Jinja2 com autoescape); registry declarativo de agregadores no engine; fetch incremental do Trello com `since` + webhooks com validação HMAC; push de imagem para registry no CI com rollback por tag; ESLint/vitest/tsc no pipeline.

---

## Índice

1. [Engine de métricas (`trello_metrics/`)](#análise-crítica--engine-de-métricas-trello_metrics)
2. [Backend Django (`backend/`)](#análise-crítica-do-backend-django--trello-analytics-intgest)
3. [Frontend React (`client/`)](#análise-crítica--frontend-client-react-19--typescript--vite)
4. [Camada de relatórios (PDF/HTML/charts)](#análise-crítica--camada-de-relatórios-trello_metricsreports)
5. [QA e testes](#análise-crítica-de-qualidade-e-cobertura-de-testes)
6. [DevOps e infraestrutura](#análise-crítica-da-infraestrutura--trello-analytics-intgest)
7. [Integração com a API REST do Trello](#auditoria-da-integração-com-a-api-rest-do-trello)

---


---

# Análise Crítica — Engine de Métricas `trello_metrics/`

Escopo revisado: `metrics/engine.py`, `metrics/timeline.py`, os 20 agregadores, `utils/business_hours.py`, `utils/period.py`, `utils/dates.py`, `parsers/`, `domain/workflow.py` + `resources/workflow.json`. Suite executada: `pytest tests/test_metrics.py -q` → **33 passed**.

---

## Pontos fortes

- **Separação limpa de camadas**: parser → `BoardData` → timeline → agregadores → dict JSON. O engine é 100% livre de Django, agregadores são majoritariamente funções puras que recebem `CardTimeline` e devolvem dicts serializáveis.
- **`timeline.py` como fonte única de verdade por card**: a reconstrução via `_list_spans` (from→to com âncora em `created_at` quando `createCard` não está no export, `timeline.py:654-719`) é bem pensada, inclusive o fallback `trello_id_datetime` para o timestamp embutido no ObjectId (`utils/dates.py:21`).
- **Honestidade metodológica**: proxies documentados no próprio payload (`dora.py:66-74` — nota explicando que CFR é proxy; `timeline.py:484-487` — retorno↔descrição é "best-effort").
- **`normalize_key` com tabela de correção de mojibake** (`utils/text.py:22-36`) é uma solução pragmática que torna o matching robusto às strings quebradas reais do board.
- **Antifraude** (`antifraud.py`) é sofisticado e defensivo: whitelisting de templates, cópias cross-board, reconstrução de lineage com histórico parcial e notas de recuperação.
- **Dataclasses frozen para eventos**, mutáveis para agregados, `from __future__ import annotations` em todos os módulos — coerente com as convenções do projeto.
- **Parsers tolerantes**: `export_loader` usa `.get` em tudo, ignora itens sem id, ordena movimentos; `parse_trello_datetime` devolve `None` em vez de explodir.

---

## Problemas CRÍTICOS

### C1. `accepted_without_dev_return` calculado duas vezes com semânticas conflitantes — o primeiro cálculo é código morto
`timeline.py:333-337` calcula corretamente "aceito sem retorno **antes da entrega**" via `_had_return_before`. Porém `_apply_return_metrics` (chamado depois, em `timeline.py:368`) **sobrescreve** incondicionalmente em `timeline.py:587-588`:
```python
if timeline.delivered_at:
    timeline.accepted_without_dev_return = timeline.developer_penalty_return_count == 0
```
Como `developer_penalty_return_count = return_dev_count` (todos os retornos, inclusive pós-entrega, `timeline.py:581`), um card entregue e que voltou a RETORNO (DEV) *depois* do terminal é penalizado na taxa de aceitação — semântica diferente da que o código morto sugere ser a intencional. Impacta `acceptance_rate_pct` no `team_summary`, `developers`, `collaborators` e `projects` (bônus de qualidade 0.7 em `projects.py:27`).

### C2. Tempo de cards arquivados continua acumulando até `now`
`_list_spans` (`timeline.py:667-669`) só consome eventos `created/copied/moved`; eventos `archived`/`unarchived` (produzidos pelo parser em `export_loader.py:238-251`) são ignorados. O fechamento do último span depende de `card.date_closed`, que vem de `raw.get("dateClosed") or raw.get("dateCompleted")` (`export_loader.py:135`) — campos que **não existem de forma confiável no export padrão do Trello**. Resultado: card arquivado há 6 meses em "EM ANDAMENTO" segue somando horas úteis em `group_hours["development"]` até hoje, poluindo `lead_time_hours`, `stage_time`, SLA e bottlenecks. O evento `archived` está disponível e deveria encerrar o span.

### C3. Dupla implementação de spans com resultados divergentes
`MetricsEngine._timeline_spans` (`engine.py:388-417`) reimplementa a lógica de `timeline._list_spans` com regra diferente: usa **qualquer** evento com `to_list_name` (incluindo `archived`, `unarchived` e `deleted`, que têm `to_list == from_list`), o que infla `spans` e fragmenta `time_by_list`. O mesmo vale para `MetricsEngine._cycle_time_hours` (`engine.py:419-434`) vs `timeline.cycle_time_hours` (`timeline.py:341-346`): definições diferentes de fim (primeiro evento em done_groups vs início do span em delivery_groups) → o campo `cycle_time_hours` de `cards[]` diverge do `cycle_time` de `flow`. Além de bug em potencial, é o cálculo mais caro (horas úteis) executado **duas vezes** por card.

### C4. Sem feriados no cálculo de horas úteis
`business_hours_between` (`utils/business_hours.py:32-59`) considera apenas weekdays + janela + almoço. Não há suporte a feriados em lugar algum (`grep feriado/holiday` → zero ocorrências). Em um contexto brasileiro (Carnaval, feriados nacionais/municipais), todo SLA de múltiplos dias é sistematicamente **superestimado em horas decorridas** → falsos "estourados" em `sla.py`. Para um sistema cuja seção inteira de SLA alimenta avaliação individual (by_developer/by_tester), isso é grave.

### C5. Listas não mapeadas viram `"unknown"` silenciosamente
`WorkflowConfig.group_for_list` (`domain/workflow.py:39-44`) devolve `"unknown"` sem qualquer alerta estruturado. Se alguém renomear uma lista no Trello (o histórico do board mostra que typos/renames acontecem: `"AGUADANDO APROVAÃ‡ÃƒO"`, `"Opicional"`), os cards somem das métricas de fluxo/SLA (grupos `unknown` não estão em `QUEUE_GROUPS`/`WORK_GROUPS` de `flow.py:21-44`, nem em SLA) e nada quebra visivelmente — as métricas apenas ficam erradas. O único vestígio é a linha "Nao mapeado" em `overview.cards_by_current_group`. Falta um item de `data_quality` listando **nomes de listas** sem grupo, com contagem de eventos afetados.

---

## Problemas médios

### Corretude
1. **`engine.py:96`** — `card_kinds` construído com `zip(cards, timelines)`: depende de `build_card_timelines` preservar ordem. Funciona hoje, mas é acoplamento posicional frágil; `CardTimeline` já carrega `card_id`.
2. **`engine.py:221-231` (`_custom_field_metrics`)** — dupla contagem: `tracked_fields` inclui `"Nível"` e `"Nivel"`, e o parser cria alias `"Nivel"` para todo `"Nível"` (`export_loader.py:163-167`) → o payload sai com duas séries idênticas. Além disso, o filtro `if field in card.custom_fields or field in ("Prioridade", "Sistema")` cria denominadores inconsistentes entre campos (só Prioridade/Sistema contam "Nao informado").
3. **`flow.py:275-282` (`_current_non_terminal_stage`)** — loop `for ... reversed()` com `return None` no corpo: itera no máximo uma vez. Funciona como "se o último stage não é terminal", mas é enganoso e o nome mente; deveria ser um `if`.
4. **`common.py:143-147` (`week_key`)** — semana ISO calculada em UTC, não em `America/Sao_Paulo`: deploy de domingo ~21h+ local cai na semana seguinte em `dora.deployment_frequency.by_week`.
5. **`dora.py:99-109`** — `_production_deploy_window_start` retorna o **primeiro** `waiting_production` do card para *todos* os deployments; para cards com múltiplas entradas em produção, o lead de deploy do 2º ciclo usa a fila do 1º. Também não valida `queue_start < production_stage.start_at`.
6. **`trends.py:26`** — `cards_delivered` da tendência = soma de devs com prefixo `D-` (via `aggregate_developers`), enquanto `team_summary.cards_delivered` (`engine.py:481`) conta todas as entregas. Dois números "entregas do mês" diferentes no mesmo relatório.
7. **`timeline.py:365-366`** — `pause_count = max(movimentos, len(pausas descritas))` mistura duas fontes sem reconciliar; um card com 2 pausas em lista e 3 blocos `[Motivo Pause]` reporta 3, mas `pause_hours` só reflete as 2 reais.
8. **`utils/dates.py:38-52` (`human_hours`)** — converte horas *úteis* em "dias" dividindo por 24: 30h úteis (≈3 dias de trabalho) viram "1.25 dias". Comunicação enganosa em todo o relatório.
9. **`sla.py:197-209`** — se o card foi entregue no período, **todos** os stages entram nos checks, mesmo os de meses anteriores; a "compliance do mês" mistura violações antigas. É defensável (avaliação por entrega), mas não está documentado no payload como o resto.
10. **Empates de timestamp**: todos os sorts de eventos usam apenas `item.at` (`timeline.py:288`, `export_loader.py:282`); ações do Trello no mesmo segundo ficam com ordem instável — desempate por `action_id` seria determinístico.
11. **`period.py:22-32`** — `parse_month` não valida formato: `"2026-7"` passa e gera `label` não normalizado (inconsistente com `month_range` que gera zero-padded); `"abc"` estoura `ValueError` cru até a CLI.

### Arquitetura / acoplamento
12. **Acoplamento entre agregadores**: `sla.py:10` importa `ROLE_CONFIGS` de `collaborators`; `collaborators.py:9` importa a função **privada** `_card_entry` de `card_dossier`. Config de papéis e prefixos (`D-`, `T-`, `RP-`...) está espalhada em pelo menos 4 lugares: `sla.ROLE_PREFIXES`, `collaborators._ROLE_PREFIX_RE`, `workflow._ROLE_PREFIX_RE` (`domain/workflow.py:277-279`) e literais hardcoded `startswith("D-")` em `engine.py:479`, `fibonacci_points.py:56`, `developers.py:154/176`. Uma mudança de convenção de nomes exige caça ao tesouro.
13. **`engine.calculate` é um bloco monolítico de 20 chamadas posicionais** (`engine.py:118-182`), cada agregador com assinatura ad-hoc. Não há registro declarativo (nome → função → dependências), o que torna impossível calcular métricas seletivamente (o `report_filter` filtra *depois* de calcular tudo).
14. **Impureza**: `bottlenecks.py:62` chama `datetime.now(timezone.utc)` dentro do agregador, violando a regra "funções puras" do projeto e furando a testabilidade com `now` injetado — o resto do engine recebe `now` por parâmetro.
15. **Duplicação quase total** entre `aggregate_developers` e `aggregate_developer_profiles` (`developers.py:144-189`): mesma iteração, mesmos filtros, executados duas vezes.
16. **Código morto**: `sla.py:280` (`_sla_limit_hours`) e `sla.py:401` (`_by_developer`) não são referenciados; `MetricsResult` (`engine.py:36-41`) é um wrapper sem valor.
17. **`testers.py:34`** — `"tester_return_rate_pct": 0.0` hardcoded no `to_dict()` e corrigido depois de fora (`testers.py:82-84`); e `reviewers.py` chama-se "reviewers" mas agrega apenas `revisor_par` — o revisor formal só aparece em `collaborators`.

### Performance (boards grandes)
18. **`business_hours_between` é O(dias do intervalo)** e é a operação mais chamada do engine (todo span, todo clip de SLA, todo aging). Card aberto há 2 anos = ~730 iterações com 2-4 `datetime.combine` cada. Com milhares de cards × spans, mais o **recálculo triplicado** (spans da timeline + `engine._timeline_spans` + re-cômputo em `sla._elapsed_hours` e `_clipped_stage_hours`), isso domina o tempo total. Não há nenhum cache (`grep lru_cache` → zero).
19. **`group_for_list` é O(nº de grupos) por chamada** (`workflow.py:39-44`) e é invocado milhões de vezes; um dict reverso `normalized_name → group` construído no `__init__` tornaria O(1).
20. **`priority._queue_jumps` é O(n²)** sobre entregues (`priority.py:65-97`); ok para dezenas/centenas, arriscado se o mês tiver milhares.
21. **`trends` recalcula `aggregate_bottlenecks` por mês** (`trends.py:23`), incluindo `stuck_now` (estado *atual*, idêntico nos 6 meses) — desperdício e conceito errado para meses históricos.
22. **Memória**: `BoardData.raw` e `TrelloCard.raw` retêm o payload inteiro do export duplicado em cada card (`models.py:66,108`) — em boards com dezenas de MB de actions, o consumo dobra sem uso pelo engine.
23. **`should_ignore_card`** reconstrói os sets de labels ignoradas a cada card (`workflow.py:87-101`), e o engine o executa 2× por card (filtro em `engine.py:82` + overview em `engine.py:206`).

### Parsers
24. **`export_loader` não emite nenhuma telemetria de descarte**: ações sem `card.id`/data são silenciosamente puladas (`export_loader.py:192-193`), sem contadores em `data_quality`. Payload que não é dict estoura `AttributeError` cru; não há validação mínima de schema nem mensagem amigável.
25. **`description_parser`**: sólido no geral, mas `_PLACEHOLDER_MARKERS` usa `startswith` — um motivo real que comece com "Informe..." é descartado como placeholder (falso negativo em `test_return_missing_reason_count`). Datas de pausa assumem `dd/mm/yyyy HH:MM` sem tolerância a variações (`dd/mm/yy`, hífen).
26. **Ausência total de `logging`** no pacote (`grep logging` → zero) — qualquer investigação de divergência exige debugger.

---

## Melhorias sugeridas (priorizadas por impacto × esforço)

| # | Ação | Impacto | Esforço |
|---|------|---------|---------|
| 1 | **Encerrar spans no evento `archived`** e tratar `date_closed` ausente (C2) — corrige inflação sistêmica de horas | Alto | Baixo |
| 2 | **Unificar semântica de `accepted_without_dev_return`** (C1): decidir se retorno pós-entrega penaliza e apagar o caminho morto | Alto | Baixo |
| 3 | **Suporte a feriados** em `business_hours` (lista em `sla_rules.holidays` no workflow.json, ou pacote `holidays` BR) | Alto | Médio |
| 4 | **Alerta de listas não mapeadas** em `data_quality` (nomes + nº de cards/eventos em `unknown`) | Alto | Baixo |
| 5 | **Deletar `engine._timeline_spans`/`_cycle_time_hours`** e reutilizar `stage_timeline`/`cycle_time_hours` da timeline (C3) | Alto | Médio |
| 6 | **Cache/otimização de `business_hours_between`**: pré-computar minutos úteis por dia (ou fórmula fechada semanal + resto) | Alto | Médio |
| 7 | **Centralizar convenção de papéis/prefixos** (`roles.py` único) e promover `_card_entry` a helper público em `common.py` | Médio | Baixo |
| 8 | **Registry declarativo de agregadores** no engine (`{key: (fn, deps)}`) — habilita cálculo seletivo | Médio | Médio |
| 9 | Injetar `now` em `aggregate_bottlenecks` e separar `stuck_now` do cálculo por período usado em `trends` | Médio | Baixo |
| 10 | Dict reverso em `group_for_list` + pré-compilar sets de `should_ignore_card` no `__init__` | Médio | Baixo |
| 11 | Corrigir `_custom_field_metrics` (dedupe Nível/Nivel, denominador uniforme) | Médio | Baixo |
| 12 | `week_key` e CFD com timezone do período (não UTC) | Médio | Baixo |
| 13 | `human_hours` com modo "dias úteis" quando a origem for horas úteis | Médio | Médio |
| 14 | Remover código morto, fundir `aggregate_developers`/`_profiles`, transformar `_current_non_terminal_stage` em `if` | Baixo | Baixo |
| 15 | `logging` estruturado (descartes do parser, listas unknown, fallbacks de created_at) + contadores no payload | Médio | Médio |
| 16 | Desempate determinístico por `action_id` nos sorts; validação estrita em `parse_month` | Baixo | Baixo |
| 17 | Parar de reter `raw` completo em `TrelloCard`/`BoardData` (ou torná-lo opt-in) | Baixo | Baixo |
| 18 | Testes dirigidos aos edge cases achados: card arquivado sem `dateClosed`, retorno pós-terminal, lista renomeada → unknown, deploy múltiplo (DORA), empate de timestamps | Alto | Médio |

---

## Veredito

A base é boa — arquitetura em camadas correta, timeline central bem desenhada, agregadores legíveis. Os riscos reais estão em **corretude silenciosa**: horas de cards arquivados (C2), semântica dupla de aceitação (C1), triplicação divergente do cálculo de spans (C3), ausência de feriados (C4) e o `"unknown"` mudo (C5). Nenhum deles é detectado pela suíte atual. Os cinco itens críticos são corrigíveis com esforço baixo/médio e deveriam preceder qualquer nova métrica.


---

# Análise Crítica do Backend Django — Trello Analytics (INTGEST)

## 1. Pontos fortes

- **Arquitetura em camadas respeitada**: controllers finos (`report_controller.py` tem 136 linhas para 10 views), services orquestrando, engine desacoplado do Django. Injeção de dependência manual em `ReportGenerationService.__init__` (backend/reports/services/report_generation_service.py:21-31) facilita testes.
- **Login com `hmac.compare_digest`** (backend/reports/controllers/auth_controller.py:24-25) — comparação constante de usuário E senha, sem short-circuit no usuário. Timing attack no login está mitigado.
- **Token com `TimestampSigner` + `max_age`** (backend/reports/utils/auth.py:27-30): expiração embutida, e o `unsign` do Django usa comparação constant-time internamente.
- **Serializers com validação real**: `ReportGenerationSerializer` valida regex de mês, limites de `history_months` (1–24), choices, validação cruzada — backend/reports/serializers.py:66-102.
- **`resolve_model`/`effective_max_output_tokens`** (backend/reports/services/ai_models.py:88-111): allowlist de modelos por provider com fallback — impede injeção de nome de modelo arbitrário.
- **Falha de IA não derruba o relatório**: `AIAnalysisService.generate` captura exceções e devolve `AIAnalysisResult(status="error")` persistido em `ai_error` (backend/reports/services/ai_analysis_service.py:84-90).
- **`bulk_create` com `batch_size`** no snapshot (backend/reports/services/trello_snapshot_service.py:51-128) e índices compostos coerentes.
- **Timeouts existem** nos clients HTTP (60s Trello, 90s IA).
- **CORS por allowlist exata de Origin** (backend/intgest_reports/middleware.py:18), não wildcard.

---

## 2. Problemas CRÍTICOS

### C1. `SECRET_KEY` com fallback fraco assina os tokens de autenticação
**backend/intgest_reports/settings.py:17**
```python
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-only-intgest-reports-secret")
```
O token de acesso é assinado com esse `SECRET_KEY` (via `TimestampSigner`). Se `DJANGO_SECRET_KEY` não estiver no `.env` da VPS, **qualquer pessoa que leia o repositório forja um token válido** para `INTGEST_ADMIN_USER` (cujo default também é público: `gestor`). O sistema deveria **recusar iniciar** com `DEBUG=0` e secret default — hoje sobe silenciosamente.

### C2. `DEBUG` default é `1`
**backend/intgest_reports/settings.py:18** — `DEBUG = os.getenv("DJANGO_DEBUG", "1") == "1"`. O docker-compose mitiga, mas qualquer execução fora do compose cai em DEBUG ligado → traceback, settings e caminhos expostos. Default seguro é `"0"`.

### C3. Sem revogação de token, sem rate limit no login, credencial única compartilhada
- O token é apenas `sign(username)` (backend/reports/utils/auth.py:20-21): **não há como revogar** um token vazado antes do TTL (12h). Trocar a senha do admin **não invalida tokens já emitidos**.
- **Nenhum throttle** em `LoginView` nem `DEFAULT_THROTTLE_CLASSES` no settings — brute-force da senha é ilimitado, e a senha default é `intgest` (settings.py:66, .env.example).
- Correção barata: incluir hash da senha no salt/payload do signer + `AnonRateThrottle` no login.

### C4. Erros da API do Trello viram 500 genérico na geração de relatório
**backend/reports/controllers/report_controller.py:48-56** — `GenerateReportView.post` chama `ReportGenerationService().generate(...)` **sem nenhum try/except**. O `TrelloClient`:
- levanta `ValueError` se faltam credenciais (trello_metrics/trello_client.py:17) → 500;
- deixa `HTTPError`/`URLError` de `urlopen` propagarem crus → 500.

O `CollaboratorSyncView` (report_controller.py:87-96) faz o tratamento correto — o endpoint mais importante do sistema, não. Agravante: `except Exception as exc: return Response({"detail": str(exc)}, status=502)` no sync repassa mensagem crua da exceção ao cliente.

### C5. Transação atômica segura o write-lock do SQLite durante chamadas de IA de vários minutos
**backend/reports/services/report_generation_service.py:33-63** — `@transaction.atomic` no `generate` envolve:
1. `snapshot_service.persist_board(...)` (linha 47) — **abre a transação de escrita**;
2. `MetricsEngine.calculate` (CPU-bound);
3. `ai_service.generate` (linha 63) — **até ~5 chamadas HTTP sequenciais de 90s cada**.

Em SQLite, a transação de escrita aberta **bloqueia qualquer outra escrita** (`database is locked`) durante toda a análise de IA. Além disso, o pior caso **estoura o `GUNICORN_TIMEOUT=300`** → worker morto por SIGKILL no meio da transação. A transação deveria cobrir apenas o `persist_board`, e a geração deveria ser assíncrona.

### C6. `DELETE /api/reports/` apaga TODO o histórico com uma única chamada
**backend/reports/controllers/report_controller.py:39-45** — sem confirmação, sem soft-delete, sem auditoria. Token vazado = destruição irreversível do histórico. E como `GeneratedReport.trello_snapshot` é `SET_NULL` (models.py:167), os snapshots (com `raw_payload` gigante) **ficam órfãos ocupando disco para sempre**.

---

## 3. Problemas MÉDIOS

### Segurança
- **M1. CSRF/cookies: configuração morta.** `CsrfViewMiddleware` e `SessionMiddleware` não estão em `MIDDLEWARE` (settings.py:30-34), mas settings.py:78-88 configura `CSRF_COOKIE_SECURE` etc. — código morto que sugere proteção inexistente. O comentário na linha 77 ("cookies e CSRF funcionam corretamente") é falso.
- **M2. `Access-Control-Allow-Credentials: true` desnecessário** (middleware.py:21). O middleware também **sobrescreve `Vary`** (linha 20) e responde `200` a qualquer `OPTIONS` antes da autenticação; sem `Access-Control-Max-Age`.
- **M3. Headers de segurança ausentes**: sem `SECURE_HSTS_SECONDS`, sem `XFrameOptionsMiddleware`. Falta também `X-Forwarded-Proto` correto: o nginx interno seta `$scheme` = `http` (docker/nginx.conf:16), sobrescrevendo o header do Caddy — `SECURE_PROXY_SSL_HEADER` (settings.py:79) nunca vê `https`.
- **M4. `hmac.compare_digest` com `str` lança `TypeError` para não-ASCII** — login com acento gera 500 em vez de 401 (auth_controller.py:24-25). Encodar para bytes.
- **M5. API keys de IA: a do Gemini vai na query string** (ai_client.py:60) — tende a vazar em logs/proxies. Nunca logar essas URLs.
- **M6. Prompt injection**: nomes/descrições de cards entram crus nos prompts de IA. Um card malicioso pode manipular a "análise gerencial".

### Robustez / Dados
- **M7. Armazenamento triplicado e sem limite**: cada geração persiste raw_payload + raw por card + metrics/filtered_metrics — 3–4 cópias de payloads de vários MB por relatório, em SQLite, sem retenção/expurgo.
- **M8. `ReportHistoryView.get` carrega os JSONs gigantes de 50 relatórios**: sem `.defer("metrics", "filtered_metrics")` (report_controller.py:32); o list serializer só precisa de 3 chaves.
- **M9. `GET /api/collaborators/` dispara `sync_collaborators_from_saved_reports()` a cada chamada** (report_controller.py:109), que itera **todos os `GeneratedReport.metrics` da história** — O(N relatórios × tamanho do JSON) num GET.
- **M10. Mismatch de limites de upload**: nginx aceita 20M, Django default (`DATA_UPLOAD_MAX_MEMORY_SIZE` = 2,5MB) rejeita `source_json` grandes — o caminho "gerar por JSON" provavelmente quebrado para boards grandes.
- **M11. Sem retries/backoff em nenhum client**: Trello não trata 429; `_post_json` da IA faz uma única tentativa. Falha transitória = relatório perdido após minutos.
- **M12. Idempotência zero na geração**: double-submit = dois fetchs + dois snapshots + duas cobranças de IA.
- **M13. `GeneratedReport` sem índices para `report_type`/`created_at`.
- **M14. `_looks_incomplete` frágil** (ai_analysis_service.py:245-252): exige literal `"## conclusao para gestao"` — variação com acento dispara chamada extra de continuação (custo dobrado).

### Configuração / Observabilidade
- **M15. Sem `LOGGING` configurado** — sem request-id, sem log de login falho (impossível detectar brute-force).
- **M16. Sem healthcheck de API**: se o gunicorn morrer, nginx responde 502 e o container é considerado saudável.
- **M17. Sem paginação DRF**: histórico `[:50]` hard-coded, colaboradores ilimitado.
- **M18. gunicorn 2 workers sync**: 2 gerações simultâneas = API inteira (login incluso) indisponível.

---

## 4. Observações menores

- `LoginSerializer` sem `write_only=True` no password.
- Fallback para env vars do servidor no `TrelloApiClient`: **qualquer usuário autenticado usa as credenciais Trello do servidor implicitamente** — documentar.
- `TrelloCardRecord`/`TrelloCustomFieldChangeRecord` nunca lidos por endpoint algum — custo de escrita sem consumidor.
- `Collaborator.name` `unique=True` + `get_or_create` por nome mais longo do alias: colisão causaria `IntegrityError` não tratado.

---

## 5. Melhorias priorizadas (impacto × esforço)

| # | Ação | Impacto | Esforço |
|---|------|---------|---------|
| 1 | **Falhar o boot se `DEBUG=0` e `SECRET_KEY`/senha forem os defaults** + default `DJANGO_DEBUG=0` | Alto (C1, C2) | Trivial |
| 2 | **Try/except no `GenerateReportView`** mapeando `ValueError`→400, `HTTPError/URLError`→502 com mensagem amigável | Alto (C4) | Baixo |
| 3 | **Estreitar a transação**: `@transaction.atomic` apenas em `persist_board` e no `create` final; IA e engine fora | Alto (C5) | Baixo |
| 4 | **Throttle no login** (`AnonRateThrottle` ~5/min) + log de tentativas falhas | Alto (C3) | Baixo |
| 5 | **`.defer("metrics","filtered_metrics")` no histórico** e tirar o sync do GET de colaboradores | Alto (M8, M9) | Baixo |
| 6 | **Endpoint `/api/health/`** + `healthcheck` no compose + entrypoint que derruba container se gunicorn morrer | Alto (M16) | Baixo |
| 7 | **Token revogável**: derivação da senha no salt do signer | Médio-alto (C3) | Médio |
| 8 | **Geração assíncrona** (202 + polling): elimina dependência do timeout de 300s | Alto (C5, M12, M18) | Alto |
| 9 | **Retenção de dados**: expurgo de snapshots órfãos; avaliar não persistir `TrelloCardRecord.raw` | Médio (M7, C6) | Médio |
| 10 | **Retry com backoff (2–3 tentativas) para 429/5xx** no `TrelloClient` e `_post_json` | Médio (M11) | Baixo |
| 11 | Confirmação no `DELETE /reports/` | Médio (C6) | Trivial |
| 12 | `LOGGING` estruturado + `--access-logfile -` no gunicorn | Médio (M15) | Baixo |
| 13 | Índices em `GeneratedReport.report_type`/`created_at` | Baixo (M13) | Trivial |
| 14 | Alinhar `DATA_UPLOAD_MAX_MEMORY_SIZE` com o nginx (20M) | Médio (M10) | Trivial |
| 15 | Limpar config morta de CSRF/cookies; remover `Allow-Credentials` do CORS | Baixo (M1, M2) | Trivial |


---

# Análise Crítica — Frontend `client/` (React 19 + TypeScript + Vite)

Escopo lido: `App.tsx` (2.146 linhas), `api/client.ts`, `types/report.ts`, `lib/*`, `utils/aiMarkdown.tsx`, `components/*`, `vite.config.ts`, `tsconfig.json`, `package.json`, `index.html`, `styles.css` (1.785 linhas), além de verificação de sincronização dos JSONs e da configuração Docker/nginx.

---

## Pontos fortes

- **Camada de API centralizada e disciplinada** (`src/api/client.ts`): nenhum `fetch` solto em componente; `apiFetch` genérico com token e parse de erro unificado.
- **Separação de conhecimento de domínio**: `lib/reportLayouts.ts` (seções por tipo de relatório) e `lib/metricDefinitions.ts` (labels/fórmulas/guias) são módulos limpos, tipados e testáveis.
- **Zero dependências pesadas**: apenas `react`, `react-dom`, `lucide-react` (tree-shakeable via named imports). Sem axios, sem UI framework, sem lodash. Bundle base tende a ser pequeno.
- **`HelpTip` bem resolvido** (`components/HelpTip.tsx`): portal, `role="tooltip"`, `aria-label`, funciona com foco de teclado (`onFocus`/`onBlur`).
- **`LoadingOverlay` com `role="status"` e `aria-live="polite"`** — bom padrão de acessibilidade para loading global.
- **CSS responsivo real**: 8 media queries incluindo `@media print` (`styles.css:730–1783`), viewport correto no `index.html`.
- **Renderização de markdown de IA sem `dangerouslySetInnerHTML`** (`utils/aiMarkdown.tsx`) — parse manual para React nodes elimina risco de XSS via resposta da IA. Escolha correta.
- **Detalhes de UX cuidados**: fechamento do dropdown de histórico por clique-fora e Escape (`App.tsx:175–196`), `document.title` restaurado após impressão (`App.tsx:433–444`), extração de filename do `Content-Disposition` no download (`api/client.ts:80–84`).

---

## Problemas CRÍTICOS

### C1. `client/src/data/metric_definitions.json` está DESSINCRONIZADO (drift real, hoje)
Verificado com `diff`: a cópia do client diverge de `trello_metrics/resources/metric_definitions.json` nas descrições de antifraude (falta "arquivada" e "updateCard:closed" — chaves `antifraud`, linhas ~410 e ~675 do JSON canônico). **A cópia `trello_metrics/reports/` também diverge.** O risco previsto no CLAUDE.md ("3 cópias, manter sincronizadas") já se materializou: o usuário vê descrição desatualizada do detector antifraude — exatamente a feature do último commit (`8327b65 antifraude e memoria de calculO`). Não há nenhum check automatizado (script de build, teste, CI) que compare as cópias.

### C2. Corrida de efeitos no login: `bootstrap` e `loadHistoryForTab` disparam simultaneamente
`App.tsx:164–173`: o effect `[token]` chama `bootstrap()` (que faz `listReports` + `getReport` e seta `reports`/`currentReport`) e o effect `[activeTab, token]` chama `loadHistoryForTab()` (que faz **as mesmas chamadas** e seta os mesmos estados). No login, ambos rodam em paralelo → 2× `listReports` + 2× `getReport`, e o último a resolver vence (não determinístico). Sem `AbortController` em lugar nenhum (0 ocorrências em `src/`), uma seleção de relatório antiga pode sobrescrever a atual se o usuário trocar de aba rápido.

### C3. Aba "Metricados" e truncamentos silenciosos mentem para o usuário
- `App.tsx:1432–1435` (`MetricTable`): colunas derivadas **apenas de `rows[0]`** — se a primeira linha não tiver uma chave presente nas demais, a coluna some. `.slice(0, 8)` colunas e `.slice(0, 12)` linhas (`App.tsx:1454`) **sem nenhum indicador** de "mostrando 12 de N". Em relatório gerencial, truncar dados sem avisar é falha grave.
- `App.tsx:1699`: `CardDossier` corta em 40 cards, também sem aviso.
- `App.tsx:967`: o KPI "Metricados" é adicionado **incondicionalmente**, ignorando `allowedSectionsForReport` — vaza métrica em relatórios `specific_metrics` que não a selecionaram.

### C4. `mergeCardWithDossier` reconstrói o índice inteiro por card — O(n²)
`App.tsx:1941–1946`: `mergeCardWithDossier` chama `indexDossierCards(dossier)` (que percorre todos os buckets do dossiê) **a cada card** dentro do `.map()` de `PersonRoleSections` (`App.tsx:1369–1371`) e `PeopleTabSections` (`App.tsx:1317`). Com 40 cards × N colaboradores × M papéis, isso é reexecutado em **todo re-render do App** (ou seja, a cada tecla digitada no formulário — ver C5). O índice deveria ser construído uma vez com `useMemo`.

### C5. Arquitetura monolítica: cada keystroke re-renderiza o preview inteiro
Todo o estado do formulário (`month`, `boardId`, `trelloApiKey`, `sourceJson`, `aiKey`, `newCollaboratorName`... 20+ `useState` em `App.tsx:130–162`) vive no mesmo componente que renderiza o preview (`KpiStrip`, `MetricSections`, `CardDossier`, `AntifraudPanel`, `MetricCalculationGuide`). Digitar no campo "API key" re-renderiza a árvore inteira do relatório — incluindo `collectCards`, `dossierCardsForPerson`, filtros e o O(n²) do C4. Nenhum `memo`, nenhum `useMemo` sobre `filtered_metrics` (que pode ter megabytes). Nenhum subcomponente do preview é memoizado.

### C6. Zero tooling de qualidade: sem ESLint, sem Prettier, sem testes
Verificado: não existe `eslint.config.*`, `.prettierrc*`, `vitest`/`testing-library` em `package.json`. Consequências já visíveis:
- `humanize` (`App.tsx:2088`) é **dead code** — definida, nunca usada; `tsc` passa porque `tsconfig.json` não tem `noUnusedLocals`.
- As dependências dos effects (`App.tsx:164–173`) violam `exhaustive-deps` (`bootstrap` usa `activeTab` do closure fora das deps) — um lint teria pegado o C2.
- Lógica não trivial e frágil (`normalizePersonKey` `App.tsx:1981–1986` com regex de prefixos de papel; `collectCards`; `formatCell`; parser de markdown) **sem um único teste**. O pipeline CI (`.gitlab-ci.yml`) só roda pytest — o frontend não é validado nem com `tsc`.

---

## Problemas médios

### API / segurança
- **M1. Token em `localStorage`** (`api/client.ts:4–16`): vulnerável a exfiltração via XSS. Mitigado pelo fato de não haver `dangerouslySetInnerHTML`, mas o correto seria cookie `HttpOnly` + `SameSite` (exige coordenação com backend-django). No mínimo, documentar o trade-off. Chaves Trello/IA digitadas no form transitam no payload — ok — mas o `aiKey` fica em estado React sem nunca ser limpo após uso.
- **M2. `parseResponse(): Promise<any>`** (`api/client.ts:155`) — o único `any` explícito da camada API contamina `login` (`data.access` sem validação, `client.ts:24–26`). Se o backend mudar o shape, o erro aparece longe da causa. `apiFetch<T>` faz cast cego sem validação de runtime (zod ou type guards manuais).
- **M3. Erros HTTP sem status/estrutura**: `parseResponse` joga `Error(message)` genérico — o caller não distingue 401 (deveria deslogar) de 500 de erro de rede. Hoje qualquer erro no `bootstrap` **apaga o token e desloga o usuário** (`App.tsx:221–224`), inclusive falha transitória de rede.
- **M4. Sem timeout nem cancelamento**: geração de relatório com IA pode levar minutos; sem `AbortSignal.timeout()` nem botão cancelar — o overlay bloqueia a UI inteira sem saída.
- **M5. `deleteAllReports` sem `report_type` apaga tudo** (`client.ts:50–53`): o parâmetro é opcional na assinatura; um caller distraído (`deleteAllReports(token)`) deletaria todas as abas. Deveria ser obrigatório.

### Tipagem
- **M6. 34 ocorrências de `Record<string, any>` em `App.tsx`** — todo o payload de métricas (`filtered_metrics?: Record<string, any>` em `types/report.ts:76`) é untyped. `MetricSections`, `ManagementSections`, `PeopleTabSections`, `CardDossier`, `AntifraudPanel` fazem acesso profundo (`metrics.process_discipline.post_terminal_returns?.count`, `App.tsx:1209`) sem nenhuma garantia. O `AntifraudAlert` (`App.tsx:1512–1553`) mostra que dá para tipar — mas está definido dentro do App.tsx em vez de `types/report.ts`. Nada é gerado do backend (sem OpenAPI/schema), então cada campo novo do engine exige sincronização manual e silenciosamente quebra em runtime.
- **M7. `tsconfig.json` defasado para Vite**: `moduleResolution: "Node"` (deveria ser `"Bundler"`), sem `noUnusedLocals`, `noUnusedParameters`, `noUncheckedIndexedAccess`.

### UX / acessibilidade
- **M8. Itens do histórico não são operáveis por teclado**: `App.tsx:554–563` usa `<div role="button" tabIndex={0}>` **sem `onKeyDown`** — Enter/Espaço não abrem o relatório. Além disso há `<button>` (delete) aninhado dentro de elemento com `role="button"` — inválido para leitores de tela.
- **M9. Um único estado de erro global** (`error`, `App.tsx:143`): erro de "adicionar colaborador" aparece no mesmo banner que erro de geração de relatório, sem contexto, sem auto-dismiss, e é sobrescrito pela próxima ação. O banner (`App.tsx:612`) não tem `role="alert"`.
- **M10. `historyMonths` aceita `NaN`**: `Number(event.target.value)` (`App.tsx:636`) com campo vazio vira `NaN` e vai para o payload. Sem validação de formulário em geral (board_id vazio, JSON inválido só estoura no `JSON.parse` dentro do `handleGenerate`, `App.tsx:282` — a mensagem crua do `SyntaxError` vai para o usuário).
- **M11. Credenciais dev hardcoded** (`App.tsx:132–133`): `"gestor"/"intgest"` pré-preenchidos sob `import.meta.env.DEV`. É código morto em produção, mas documenta a senha real no bundle-fonte do repositório. Inputs de login sem `autoComplete="username"/"current-password"` e sem `name`.
- **M12. Textos sem acentos** ("Usuario", "Relatorio", "Gestao", "Metricas", "Analise") por toda a UI. Se é decisão deliberada (medo de mojibake), está inconsistente com a regra "textos de UI em português"; `index.html` já usa UTF-8 corretamente, não há razão técnica.
- **M13. `formatDate(new Date(value))`** (`App.tsx:2085`) lança `RangeError` no `Intl.DateTimeFormat.format` se `created_at` vier inválido — sem guard. E `currentMonth()` (`App.tsx:2044–2046`) usa `toISOString()` = UTC: no dia 1º do mês entre 21h–00h em São Paulo, sugere o mês errado (viola a convenção de timezone do projeto).

### Build / tooling
- **M14. `@vitejs/plugin-react` em `dependencies`** (`package.json:12`) — é build tooling, pertence a `devDependencies`.
- **M15. Sem proxy de dev no `vite.config.ts`**: o client em dev bate direto em `http://127.0.0.1:8000/api` (default em `client.ts:3`), exigindo CORS aberto no Django em dev. Um `server.proxy: { "/api": "http://127.0.0.1:8000" }` eliminaria a divergência dev/prod (prod usa path relativo `/api` via `ARG` do Dockerfile).
- **M16. Sem code splitting**: tudo num chunk único — App.tsx (77KB) + `metric_definitions.json` (**50KB inlined no bundle JS**) + lucide icons. O JSON poderia ser importado com `?url`/fetch ou o preview lazy-loaded. Não é crítico dado o tamanho total modesto, mas o JSON de 50KB no bundle é o item mais gordo e desnecessário.
- **M17. `tsconfig.tsbuildinfo` commitado** na raiz de `client/` — artefato de build, deveria estar no `.gitignore`.

### Menores
- `AiMarkdown` (`utils/aiMarkdown.tsx:36–45`): `isUnfairCallout` decide estilo por substring matching do texto da IA ("indevido", "id trello") — heurística frágil acoplada ao prompt do backend; mudança no prompt quebra o destaque silenciosamente.
- `HelpTip`: tooltip não reposiciona em scroll/resize enquanto aberto; em touch não há como abrir (só hover/focus).
- `KpiStrip`/`MetricSections` com `report.filtered_metrics ?? {}` recalculado a cada render sem memo (agrava C5).
- `window.confirm` para exclusões (`App.tsx:348, 361`) — funcional, mas inconsistente com o resto do design system.

---

## Plano de refatoração priorizado (impacto × esforço)

### Fase 0 — Correções pontuais (alto impacto, esforço baixo — 1 dia)
1. **Sincronizar as 3 cópias de `metric_definitions.json`** (C1) e adicionar um check: script npm `"check:defs": "diff ..."` chamado no `build`, ou teste pytest comparando os 3 arquivos (coordenar com qa-testes). Isso transforma o risco documentado em garantia.
2. **Eliminar a corrida de effects** (C2): remover a chamada de histórico do `bootstrap` e deixar o effect `[activeTab, token]` como única fonte; ou consolidar num effect só.
3. **Fixes cirúrgicos**: KPI "Metricados" condicionado a `allowed` (C3); `onKeyDown` nos history-items + trocar div por `<button>` (M8); indicador "mostrando X de N" nas tabelas truncadas (C3); guard em `formatDate`; `currentMonth` com timezone local; remover `humanize` morta; mover `@vitejs/plugin-react` para devDependencies; ignorar `tsbuildinfo`.
4. **`useMemo` no índice do dossiê** (C4): construir `indexDossierCards` uma vez por `report` e passar por prop/contexto.

### Fase 1 — Tooling (alto impacto preventivo, esforço baixo — 1 dia)
5. ESLint flat config com `typescript-eslint` + `react-hooks` (pega C2/M-deps automaticamente) + Prettier. Adicionar `tsc -b && eslint` ao estágio `test` do `.gitlab-ci.yml` (hoje o frontend não é validado no CI).
6. `tsconfig`: `moduleResolution: "Bundler"`, `noUnusedLocals`, `noUnusedParameters`.
7. Vitest + Testing Library, começando pelos módulos puros que já são testáveis sem refactor: `formatCell`, `normalizePersonKey`, `collectCards`, `allowedSectionsForReport`, `AiMarkdown`.

### Fase 2 — Decomposição do App.tsx (alto impacto, esforço médio — 3–5 dias, incremental)
A boa notícia: as ~1.100 linhas finais do App.tsx já são componentes/funções puras que **não usam nenhum estado do App** — a extração é mecânica e de baixo risco. Ordem sugerida (cada passo é um PR pequeno com `npm run build` verde):

```
src/
├── components/
│   ├── report/                    # extração mecânica, sem mudança de lógica
│   │   ├── ReportPreview.tsx      # preview-header + composição (App.tsx:826–865)
│   │   ├── KpiStrip.tsx           # App.tsx:871–982
│   │   ├── MetricSections.tsx     # 1033–1172 + ManagementSections 1174–1262
│   │   ├── PeopleSections.tsx     # PeopleTabSections/CollaboratorsSections/PersonRoleSections
│   │   ├── MetricTable.tsx        # 1421–1488 (+ MetricLegend, ObjectPanel)
│   │   ├── AntifraudPanel.tsx     # 1512–1688 (mover AntifraudAlert p/ types/)
│   │   ├── CardDossier.tsx        # 1690–1843
│   │   └── CalculationGuide.tsx   # 1388–1419
│   ├── HistoryDropdown.tsx        # App.tsx:516–584 + effect de clique-fora
│   ├── ReportForm.tsx             # form 615–824 (recebe estado via hook abaixo)
│   ├── CollaboratorPanel.tsx      # 781–818
│   ├── AiConfigPanel.tsx          # 727–779
│   └── LoginPage.tsx              # 468–502
├── hooks/
│   ├── useAuth.ts                 # token, login/logout, getMe
│   ├── useReports.ts              # reports, currentReport, selectedByTabRef,
│   │                              #   generate/select/delete + AbortController
│   ├── useCollaborators.ts        # lista, add, sync, toggle
│   └── useReportForm.ts           # estado do formulário (isola re-renders → resolve C5)
├── lib/
│   ├── format.ts                  # formatCell, formatDate, isSimple, slugify,
│   │                              #   reportFileBaseName, currentMonth
│   └── dossier.ts                 # collectCards, indexDossierCards, namesMatch, merge...
└── types/metrics.ts               # tipos das seções de filtered_metrics (substituir
                                   #   Record<string, any> progressivamente)
```
Marcar `ReportPreview` com `memo` (só depende de `report`) — junto com `useReportForm`, elimina o re-render do preview por keystroke (C5). Rotas (react-router) são **desnecessárias** neste app de tela única com abas; não adicionar.

### Fase 3 — Camada de API robusta (impacto médio, esforço médio — 2 dias)
8. `apiFetch` com: classe `ApiError { status, detail }` (M3 — deslogar só em 401), `AbortSignal` opcional propagado dos hooks (C2/M4), timeout default. `report_type` obrigatório em `deleteAllReports` (M5).
9. Tipar `parseResponse` (`unknown` + narrowing) e a resposta de login (M2).
10. Erros contextuais: estado de erro por área (form, colaboradores, preview) em vez do banner global (M9), com `role="alert"`.

### Fase 4 — Tipagem do payload de métricas (impacto alto a longo prazo, esforço alto — coordenar com backend-django)
11. Definir em `types/metrics.ts` interfaces para as seções consumidas (`TeamSummary`, `FlowTeam`, `SlaSection`, `DossierCard`, `Antifraud`...) — mesmo sem geração automática, elimina os 34 `Record<string, any>`. Ideal: expor schema OpenAPI no DRF e gerar tipos (`openapi-typescript`), tornando C1/M6 estruturalmente impossíveis para os tipos (o JSON de definições ainda precisa do diff-check da Fase 0).

### Não fazer (custo > benefício agora)
- Migrar para framework de UI ou state manager (Redux/Zustand) — o estado é simples após a Fase 2.
- React Router — app de tela única.
- Trocar fetch por axios/react-query — a Fase 3 cobre as necessidades reais; react-query só se o padrão de cache/refetch crescer.


---

# Análise crítica — camada de relatórios (`trello_metrics/reports/`)

---

## 1. Resultado do diff das 3 cópias de `metric_definitions.json`

**Estão DESSINCRONIZADAS hoje.**

```
MD5 trello_metrics/resources/metric_definitions.json  = 4395bcbe...  (mais nova)
MD5 trello_metrics/reports/metric_definitions.json    = f49b9080...  (desatualizada)
MD5 client/src/data/metric_definitions.json           = f49b9080...  (desatualizada)
```

- `reports/` e `client/src/data/` são idênticas entre si, mas **ambas estão atrasadas** em relação a `resources/`.
- Diferença semântica (2 descrições de antifraude): `resources/` menciona `updateCard:closed` e fonte "arquivada"; as outras duas cópias ainda dizem apenas `deleteCard` e "viva, excluida ou missing_history".
- Origem: o commit `8327b65` ("antifraude e memoria de calculO") atualizou **apenas** a cópia de `resources/`, violando a própria regra do CLAUDE.md.
- **Impacto prático**: o PDF e o HTML interativo leem a cópia de `reports/` (`trello_metrics/reports/metric_definitions.py:13` e `html_report.py:17`) — os relatórios gerados hoje exibem a memória de cálculo de antifraude **defasada** em relação ao engine.

**Solução definitiva proposta** (fonte única + geração no build):
1. Eleger `trello_metrics/resources/metric_definitions.json` como única fonte de verdade.
2. `metric_definitions.py` e `html_report.py` passam a carregar de `trello_metrics.resources` (troca de 1 linha em cada) — elimina a cópia de `reports/` imediatamente.
3. Para o frontend: script de sync (`prebuild` no `package.json`) + verificação no CI (`diff -q` no estágio `test`) que **falha o pipeline** se `client/src/data/` divergir. Alternativa mais robusta: endpoint `/api/metric-definitions` servindo o JSON do engine.

---

## 2. Pontos fortes

- **Separação HTML→PDF bem resolvida**: `pdf.py` (56 linhas) isola o Playwright; `styles.py` isola CSS; `card_rendering.py` e `helpers.py` extraem componentes reutilizáveis.
- **Nenhum label hardcoded crítico**: guias, fórmulas e legendas vêm de `metric_definitions` via `_table_intro`/`_section_guide` (builder.py:124-160).
- **Defensividade nos dados**: uso quase universal de `.get(...)` com defaults — seção ausente = seção omitida, sem crash. `charts.py` degrada graciosamente sem matplotlib.
- **PDF não depende de rede**: fontes de sistema deliberadamente, gráficos embutidos em base64 — bom para Docker.
- **`report.js` tem bom nível de polimento**: escape consistente, roteamento por hash, markdown renderer próprio, layout por tipo de relatório.

---

## 3. Problemas CRÍTICOS

### C1. Bug de gating: seção de Risco nunca aparece no PDF de gestão
`builder.py:363` e `builder.py:419` verificam `self.include("risk_board")`, mas os layouts declaram a seção como `"risk"` (`report_layouts.py:67`). Como `allows_section("management", "risk_board")` → `False`, o bloco "Cards que merecem atencao agora" **jamais é renderizado** no relatório de gestão em PDF — enquanto o HTML interativo (`report.js:615`) o exibe normalmente. Divergência silenciosa entre PDF e HTML no relatório mais sensível.

### C2. Injeção de HTML no relatório HTML interativo (XSS)
`html_report.py:29` interpola `page_title` no `<title>` **sem escape**, e `html_report.py:211-212` embute `defs` e `metrics_json` dentro de `<script>` sem neutralizar `</script>`. `json.dumps` não escapa `</`; um card do Trello nomeado `</script><script>...` quebra o script e executa código arbitrário no navegador de quem abre o relatório. Dados do board são controláveis por qualquer membro do Trello. Correção barata: `metrics_json.replace("</", "<\\/")` + `escape(page_title)`.

### C3. `table()` do PDF não escapa células — injeção de HTML no PDF
`helpers.py:147-152` insere valores crus no HTML. Muitos callers passam strings do Trello sem `esc()`: `builder.py:688` (`r["name"]`), `builder.py:825` (`r["title"]`), `builder.py:833` (`r["sistema"]`), `builder.py:874` (`r["card_name"]`), `builder.py:1000/1006` (nomes de lista), `_cfd_rows` (builder.py:1073-1075). Um card chamado `<img src=x>` ou com `&` corrompe o layout do PDF. O design é ambíguo: `table()` aceita HTML (pills/badges) e texto cru ao mesmo tempo — sem contrato claro, cada caller decide, e a maioria decide errado. Mesmo problema em `metric_card` (helpers.py:161).

### C4. Vazamento de diretórios temporários de gráficos
`charts.py:33` cria `tempfile.mkdtemp(prefix="trello_metrics_")` e **ninguém apaga**. Cada geração de PDF deixa ~15 PNGs órfãos em `/tmp` do container. Em produção, crescimento indefinido de disco até restart. O backend usa `TemporaryDirectory` corretamente para o PDF final (export_service.py:35), mas os charts intermediários escapam.

### C5. Dependência morta: `reportlab` + código morto associado
`requirements.txt:1` ainda instala `reportlab>=4.2.0`, mas o único código que o usa são funções mortas (`metric_definitions.py:85-172`) — nenhum caller. Infla a imagem Docker e confunde (docstring de builder.py:1 ainda diz "ReportLab"). Também morto: `PdfReportBuilder._role_table_section` (builder.py:670-678).

---

## 4. Problemas médios

### M1. Três vocabulários de layout divergentes (PDF ≠ HTML ≠ frontend)
Existem **três** definições independentes de "quais seções cada tipo de relatório mostra": `report_layouts.py:6-84`, `report.js:16-45` e `reportLayouts.ts:29-72` — com nomes diferentes (`quality_gates` vs `quality`, `ai` vs `ai-analysis`, `risk` vs `risk_board`) e conteúdo diferente:
- `general` no Python **não** inclui `risk`, `priority`, `dora`, `discipline`; o do report.js **inclui** todos os quatro. O relatório geral em HTML mostra Risco/Prioridade/DORA/Disciplina; o mesmo em PDF, não.
- `analysis_workflow` está nos layouts Python e tem renderer no HTML (`report.js:797`), mas **o PDF não tem nenhum método `_analysis_workflow`** — a seção "Cards de analise" não existe no PDF, apesar de declarada no layout.

### M2. Duplicação massiva de lógica de apresentação entre PDF e HTML
Cada tabela é definida duas vezes — headers, colunas, formatação — em Python (builder.py) e JS (report.js), mais uma terceira vez parcial no preview React. `COLORS` é copiado byte a byte (charts.py:8-17 ≡ report.js:3-12), e há dois renderizadores markdown independentes. Mitigação viável: mover a **especificação declarativa de cada tabela** para `metric_definitions.json`/`tables` (que já tem `columns`!) e fazer builder.py e report.js consumirem a mesma spec.

### M3. builder.py — monólito de 1077 linhas com HTML inline em f-strings
`_operational_metrics` tem **216 linhas** (builder.py:361-577) cobrindo 5 domínios distintos — devia ser 5 métodos; `_antifraud` tem 94 linhas com lógica de lineage embutida; linhas com 400+ caracteres. **Proposta**: (a) curto prazo, quebrar em módulos `sections/`; (b) médio prazo, **Jinja2** com um template por seção (autoescape resolveria C3 na raiz), migrando seção a seção — não big bang.

### M4. Playwright/Chromium: peso e fragilidade justificáveis, mas mal cercados
- Cada PDF **lança um browser novo** (pdf.py:39) — 1.5-3s de overhead por requisição, sem pool/reuso, bloqueando worker gunicorn.
- **Sobre WeasyPrint**: seria ~10x mais leve, porém o CSS atual usa flexbox extensivamente e WeasyPrint tem suporte historicamente parcial a flex. Veredito: **manter Playwright**, mas considerar reuso do browser e mover PDF para fora do ciclo request/response se o volume crescer.

### M5. HTML "self-contained" que não é
O docstring (`html_report.py:10`) promete relatório self-contained, mas o `<head>` puxa Google Fonts e **Chart.js de CDN** (html_report.py:30-33). Aberto offline (anexo de e-mail), `Chart` fica indefinido, `makeChart` (report.js:217-222) lança `ReferenceError` **sem guard**, e como `init()` não tem try/catch por seção, **a primeira falha aborta a renderização de todas as seções seguintes**. Correções: vendorizar chart.umd.min.js (~200KB), guard em `makeChart`, try/catch por seção.

### M6. Gráficos matplotlib: acessibilidade e consistência
- **Cores não são colorblind-safe**: pares verde/vermelho lado a lado em `_quality_chart`, `_dev_quality_chart`, `_trends_quality_chart` — indistinguíveis para ~8% dos homens. Recomendo paleta Okabe-Ito ou "tableau-colorblind10".
- **Duas paletas concorrentes**: charts usam paleta "Tailwind" (charts.py:8) enquanto a identidade do PDF usa NAVY `#133968`/TEAL `#428BA5` (helpers.py:9-10).
- `alt=""` em todos os gráficos (helpers.py:193) — nulo para acessibilidade.
- Acesso direto `row["month"]` em `_trends_team_chart` (charts.py:316-318) — KeyError se o histórico vier incompleto, e como `render_charts` não tem try/except por gráfico, **um chart quebrado derruba a geração inteira do PDF**.

### M7. Filtragem de seções do HTML é só cosmética
`configureReportLayout` (report.js:61-67) esconde seções com `display:none`, mas `html_report.py` embute **todo** o JSON de métricas independentemente do tipo. Se o backend não filtrar antes, um relatório "individual" entregue a um colaborador carrega dados de todo o time visíveis no view-source. Vale filtro defensivo na própria camada de relatório.

### M8. Performance de geração
Custo por PDF: ~15 figuras matplotlib (~1-3s), HTML monolítico com PNGs base64 (+33% de tamanho; com dossiê completo passa de 5-10MB em memória), launch de Chromium (~1.5-3s) + render. Estimativa: 5-15s e centenas de MB de RSS, tudo síncrono no worker. O `_dossier` sem paginação/limite (builder.py:1011-1047 renderiza **todos** os cards) é o maior multiplicador de tamanho.

---

## 5. Melhorias priorizadas (impacto × esforço)

| # | Ação | Impacto | Esforço | Referência |
|---|------|---------|---------|------------|
| 1 | Ressincronizar as 3 cópias de `metric_definitions.json` agora | Alto | Trivial | §1 |
| 2 | Corrigir `include("risk_board")` → `"risk"` no PDF | Alto | Trivial | C1 |
| 3 | Escapar `</script>` e `page_title` no HTML interativo | Alto (XSS) | Trivial | C2 |
| 4 | Fonte única de metric_definitions: engine lê de `resources/`, client sincroniza no build, CI valida | Alto | Baixo | §1 |
| 5 | Limpar temp dir dos charts | Alto em produção | Baixo | C4 |
| 6 | Guard de `Chart` + try/catch por seção no `init()` + vendorizar Chart.js | Alto | Baixo | M5 |
| 7 | Escape default em `table()`/`metric_card` com opt-out explícito | Alto | Médio | C3 |
| 8 | Unificar vocabulário de seções (gerar layouts JS/TS a partir do Python ou JSON único); adicionar `_analysis_workflow` ao PDF | Alto | Médio | M1 |
| 9 | Remover `reportlab` + código morto | Médio | Trivial | C5 |
| 10 | Quebrar `_operational_metrics` em 5 métodos e extrair `sections/` | Médio | Médio | M3 |
| 11 | Paleta colorblind-safe única + alt text nos charts | Médio | Baixo | M6 |
| 12 | try/except por gráfico em `render_charts` | Médio | Baixo | M6 |
| 13 | Migração incremental do builder para Jinja2 (autoescape) | Alto a longo prazo | Alto | M3 |
| 14 | Pool/reuso de browser Playwright ou geração assíncrona | Médio | Alto | M4/M8 |
| 15 | Limite/paginação no dossiê do PDF | Médio | Baixo | M8 |

## 6. Veredito: "as mesmas métricas aparecem igual nos três?"

**Não.** Pelo menos quatro divergências concretas: (1) Risco ausente do PDF de gestão por bug de chave; (2) `analysis_workflow` existe no HTML e no frontend, mas não no PDF; (3) o layout `general` mostra Risco/Prioridade/DORA/Disciplina no HTML e os omite no PDF; (4) as definições de métricas exibidas estão uma versão atrás do engine. A causa raiz comum é a ausência de fonte única tanto para *layouts* quanto para *definições*.


---

# Análise crítica de qualidade e cobertura de testes

## 1. Estado atual (números reais)

### Execução da suíte

- Comando: `PYTHONPATH=".:backend" pytest tests/ -q`
- Resultado: **48 passed em ~0,3s** (33 em `tests/test_metrics.py` + 15 em `tests/test_ai_analysis.py`). Zero falhas, zero skips.
- Suíte extremamente rápida — há muito espaço orçamentário para crescer.

### Cobertura (medida de verdade, não estimada)

`pytest-cov` não está instalado no ambiente padrão; medição feita em venv isolado (Python 3.13). Resultado global: **54% (6.248 statements, 2.900 não cobertos)**.

| Camada | Cobertura | Observação |
|---|---|---|
| `metrics/engine.py` | 98% | Excelente |
| `metrics/timeline.py` | 91% | 37 linhas descobertas |
| Agregadores (20) | 83–100% | Maioria via engine, nem tudo assertado |
| `utils/business_hours.py` | 87% | Só 3 testes diretos |
| `domain/workflow.py` | 88% | Cobertura por efeito colateral, sem teste dedicado |
| `metrics/report_filter.py` | **43%** | 1 teste apenas |
| `parsers/description_parser.py` | **23%** | Praticamente sem teste |
| `parsers/export_loader.py` | **16%** | Porta de entrada de TODOS os dados, sem teste |
| Serviços de IA (backend) | 74–87% | Bem cobertos |
| `backend/` restante (controllers, models, serializers, auth, middleware, services) | **0%** | Nenhum teste |
| `reports/` (pdf_intgest/builder 494 stmts, charts 317, html_report) | **0%** | Nenhum teste |
| `cli.py`, `trello_client.py` | 0–59% | Sem teste |

Achado colateral de ambiente: no PATH local, `~/.pyenv/versions/3.8.17/bin` vem **antes** de tudo; `pytest` só funciona porque resolve para o Homebrew Python 3.13. Qualquer `pip install` casual cai no 3.8 (incompatível — `zoneinfo` não existe). O CI usa 3.12; local roda 3.13 — nenhum dos dois fixado.

## 2. Lacunas CRÍTICAS

1. **Backend Django com 0% de teste fora da camada de IA**:
   - `backend/reports/utils/auth.py` (token assinado caseiro) — **código de segurança sem um único teste**: expiração, assinatura inválida, tampering.
   - `controllers/` — nenhum request test; nem serializers, nem models, nem middleware.
   - `metrics_selection_service.py` (156 stmts) e `report_generation_service.py` — orquestram o produto inteiro, 0%.
2. **`parsers/export_loader.py` a 16%**: é o único caminho de entrada de dados. Um bug aqui corrompe todas as métricas silenciosamente e nenhum teste pegaria.
3. **`parsers/description_parser.py` a 23%**: extrai retornos, pausas e motivos. `RetornoDetail`/`PausaDetail` **nunca aparecem em teste algum**.
4. **Ausência de teste de regressão com export real anonimizado (golden file)**: os testes atuais são boards sintéticos de 1–3 cards. Regressões de agregação num board com 200 cards passam invisíveis.
5. **Camada de relatórios 0%**: nem um smoke test "gera HTML sem exceção". E não há teste garantindo que as **3 cópias de `metric_definitions.json` estão idênticas** — regra explícita do projeto, trivialmente automatizável.

## 3. Lacunas médias

1. **Agregadores executados mas sem asserts dedicados**: `card_dossier`, `projects`, `quality_gates`, `fibonacci_points` (parcial), `developer_profiles`, `common.py`. Cobertura de linha alta ≠ output verificado.
2. **`business_hours`**: só 3 testes. Faltam: intervalo atravessando fim de semana, `start > end`, timestamps naive, múltiplos dias. E **não existe suporte a feriados no código** — lacuna de produto que um teste de caracterização deveria documentar.
3. **Timeline — edge cases ausentes**: card sem movements, card template, listas não mapeadas → `unknown`, mês sem dados, eventos fora de ordem/duplicados.
4. **`domain/workflow.py` sem teste dedicado**: o matching literal com mojibake é a armadilha nº 1 do projeto e não tem teste que a proteja.
5. **`report_filter.py` a 43%** com 1 único caso feliz.
6. **Frontend: zero testes** — sem vitest, sem testing-library, sem ESLint. `App.tsx` (77KB) é intocável com segurança hoje.
7. **CI roda apenas `pytest tests/ -q`**: sem cobertura/threshold, sem lint, sem mypy, sem `tsc`/build do client — erro de compilação TypeScript passa pelo pipeline e só explode no `docker build`.

## 4. Qualidade dos testes existentes

**Pontos fortes**:
- Determinismo exemplar: `now` sempre injetado, helper `_dt()` timezone-aware.
- Asserts de valores exatos na maioria dos casos.
- Cenários de negócio sofisticados bem cobertos: antifraude (whitelist, cross-board, deleted/archived), SLA por base, retornos multi-papel.
- IA testada com fakes, zero rede.

**Pontos fracos**:
- **O helper `_board()` aceita só 1 card** — testes multi-card reconstroem `BoardData` à mão; sem builder de movimentos, cada teste tem 40–80 linhas repetitivas (2.000 linhas para 33 testes).
- **Asserts fracos pontuais**: `assertGreater(little_law..., 0)`; `test_prompt_has_five_questions` é quase tautológico.
- **Acoplamento à implementação nos testes de IA**: asserts em strings literais de prompt quebram a cada ajuste editorial sem indicar bug real.
- Testes dependem do `resources/workflow.json` real — mudança operacional no board quebra a suíte inteira.
- `unittest` sem parametrização.

## 5. Frontend

Nenhum teste. `client/package.json` não tem script `test`, nenhuma dependência de teste, nenhum linter.

## 6. CI

`.gitlab-ci.yml`: `test` (pytest) → `build` (docker) → `deploy` (SSH). **Não cobre**: cobertura/threshold, lint Python, mypy, ESLint, tsc, build do client, sincronia das 3 cópias de `metric_definitions.json`.

## 7. Plano de testes priorizado

**P0 — risco de corrupção silenciosa de dados e segurança (1ª sprint)**
1. `tests/test_export_loader.py`: fixture de export Trello anonimizado mínimo → assert de BoardData completo.
2. `tests/test_auth.py`: token assinado — happy path, expirado, adulterado, usuário errado.
3. `tests/test_description_parser.py`: descrições reais anonimizadas → `RetornoDetail`/`PausaDetail`; descrição vazia/malformada.
4. Golden test de regressão: export anonimizado médio → `calculate().to_dict()` comparado a snapshot JSON versionado.
5. Teste trivial de sincronia das 3 cópias de `metric_definitions.json`.

**P1 — backend e edge cases do engine (2ª sprint)**
6. API tests (DRF APIClient + fakes): GenerateReport, History, Exports, Collaborators; services unitários.
7. Timeline edge cases: card sem movements, template, lista `unknown`, mês vazio, eventos duplicados/fora de ordem.
8. `business_hours`: fim de semana, multi-dia, naive datetime, start>end; caracterização da ausência de feriados.
9. `workflow.py`: matching literal incluindo mojibake; `report_filter.py` além do caso feliz.
10. Asserts dedicados para `card_dossier`, `projects`, `quality_gates`, `fibonacci_points`, `developer_profiles`.

**P2 — infraestrutura de qualidade (contínuo)**
11. Smoke tests de relatório: `html_report` e seções do builder renderizam sem exceção.
12. Refatorar fixtures: `BoardBuilder` com `move(card, from, to, at)` encadeável — reduzir test_metrics.py em ~50%; migrar para parametrize.
13. CI: `pytest --cov` com threshold (~55% subindo), ruff, job Node (`tsc -b` + `npm run build`); fixar versão de Python.
14. Frontend: vitest + testing-library começando por `src/lib/` e `src/api/client.ts`.


---

# Análise Crítica da Infraestrutura — Trello Analytics (INTGEST)

> Análise somente leitura. Não foi possível executar `docker compose config`/build local: o CLI `docker` não está disponível neste ambiente — recomendo validar na VPS/máquina com Docker.

---

## 1. Pontos fortes

- **Multi-stage build** correto (`Dockerfile:1-13`): frontend Node isolado, só o `dist/` vai para a imagem final. Ordem de layers boa (deps antes do código → cache eficiente tanto no npm quanto no pip).
- **`npm ci` com lockfile** (`Dockerfile:5-6`) — build de frontend reprodutível.
- **`.dockerignore` completo** (exclui `.env`, `.git`, sqlite, node_modules, PDFs).
- **`.env` não commitado**; `.gitignore` cobre `.env`, `db.sqlite3`, `/data/`.
- **HEALTHCHECK definido** no Dockerfile (`Dockerfile:47-48`) e `restart: unless-stopped` no compose.
- **Deploy condicional** (`.gitlab-ci.yml:52`): só roda se `VPS_HOST` e `SSH_PRIVATE_KEY` existirem; chave SSH via variável CI, nunca em código.
- **Gunicorn timeout 300s** + `proxy_read_timeout 300s` no nginx (`docker/nginx.conf:17`) — coerentes entre si e com a geração de PDF longa via Playwright.
- **Caddy com `{$APP_DOMAIN}`** parametrizado, volumes persistentes para certificados (`caddy_data`), profile opcional bem isolado.
- **CI com cache pip por branch**, `interruptible: true`, e regra de MR + default branch no estágio de teste.
- **Backup documentado** em `docs/deploy_vps.md:188` (ainda que manual — ver seção de riscos).

---

## 2. Riscos CRÍTICOS

### C1. Healthcheck não detecta gunicorn morto + gunicorn órfão em background
`docker/entrypoint.sh:7-13`: gunicorn é lançado com `&` e o nginx vira PID 1. Consequências:
- Se o **gunicorn morrer**, o container continua "healthy": o `HEALTHCHECK` (`Dockerfile:48`) testa `http://127.0.0.1/` — que é o **SPA estático servido pelo nginx**, retorna 200 sempre. A API fica em 502 indefinidamente e nada reinicia o container.
- Sem supervisão de processos (supervisord/s6) nem propagação de sinais para o gunicorn → shutdown não-gracioso (requisições de PDF em andamento são mortas).

**Correção mínima**: healthcheck apontar para um endpoint da API (ex.: `curl -f http://127.0.0.1/api/...`) e/ou usar um supervisor; idealmente separar em dois containers (ver M1).

### C2. Tudo roda como root
`Dockerfile` não cria usuário: **gunicorn/Django e Chromium (Playwright) rodam como root**. Chromium como root é especialmente ruim — exige `--no-sandbox` (daí o `PLAYWRIGHT_CHROMIUM_ARGS` no código), ou seja: renderização de HTML em navegador **sem sandbox, como root**, no mesmo processo/container do banco de dados. Um exploit no Chromium = acesso root ao container e ao SQLite.

### C3. `desc_dump.txt` commitado no repositório
Arquivo rastreado no git (raiz do repo, 15 KB, UTF-16) contendo dump de descrições de cards do board Trello. Hoje o conteúdo visível parece template, mas é **dado do board de cliente versionado em dois remotes (GitHub + GitLab)** e não está no `.gitignore`. Deveria ser removido do índice (e do histórico, se contiver dados reais).

### C4. Sem backup automatizado do SQLite / sem plano de DR
- Único mecanismo: comando manual em `docs/deploy_vps.md:188` (`docker cp ...`).
- Nenhum cron, nenhum backup offsite, nenhum teste de restore. O volume `trello_data` (`docker-compose.yml:20`) é o **único** lugar onde vive todo o histórico de relatórios/snapshots. `docker volume rm` acidental, disco corrompido ou perda da VPS = perda total.
- Agravante: `docker cp` de um SQLite **em uso** pode gerar cópia corrompida — o backup correto é `sqlite3 /data/db.sqlite3 ".backup '/data/backup.sqlite3'"` ou parar escrita antes.

### C5. Porta HTTP exposta mesmo com o profile `https` ativo
`docker-compose.yml:10-11`: `app` publica `${APP_PORT:-8080}:80` **incondicionalmente**. Com Caddy no ar, `http://IP-da-VPS:8080` continua acessível em texto plano (login `INTGEST_ADMIN_USER/PASSWORD` e token trafegam sem TLS), bypassando o HTTPS. Deveria ser `127.0.0.1:8080:80` ou remover o mapeamento no profile https (Caddy fala com `app:80` pela rede interna — `docker/Caddyfile:4`).

### C6. Defaults inseguros de produção no settings
- `backend/intgest_reports/settings.py:17`: `SECRET_KEY` com fallback fixo `"dev-only-intgest-reports-secret"` — se `DJANGO_SECRET_KEY` faltar no `.env` da VPS, os **tokens assinados de auth ficam forjáveis** (a auth caseira depende de assinatura).
- `settings.py:18`: `DEBUG` default `1` (compose força `0`, mas qualquer execução fora do compose sobe com debug).
- `settings.py:65-66` + `.env.example:8-9`: credenciais default `gestor`/`intgest` — se o operador não trocar, é senha conhecida publicamente (está no repo).
- **Recomendação**: falhar no boot (`RuntimeError`) se `DEBUG=0` e `SECRET_KEY`/senha forem os defaults.

---

## 3. Problemas médios

### M1. nginx + gunicorn no mesmo container (antipadrão)
Funciona, mas: um processo por container é o modelo Docker; logs misturados; impossível escalar/atualizar independentemente; healthcheck ambíguo (ver C1). Aceitável para o porte atual, mas se mantiver, adote supervisor + healthcheck da API. Alternativa de baixo custo: dois serviços no compose (nginx e app) compartilhando rede.

### M2. Deploy: build na VPS, sem rollback, imagem do CI descartada
- `.gitlab-ci.yml:42-43`: o estágio `build` constrói `trello-analytics:${CI_COMMIT_SHORT_SHA}` **e joga fora** (não faz push para registry). Depois (`:67`) a VPS **rebuilda do zero** — build do Playwright/Chromium (~1 GB) consumindo CPU/disco da VPS de produção a cada deploy.
- `docker compose pull` (`:66`) é no-op para serviço com `build:`.
- **Sem rollback**: se a nova imagem quebrar, não há tag anterior para voltar; o caminho é `git reset` para commit antigo + rebuild (minutos de downtime).
- **Downtime**: `up -d --build` recria o container (segundos a mais por causa do migrate no entrypoint); sem estratégia blue/green — tolerável para app interno, mas documente.
- Melhoria: push para o GitLab Container Registry no `build`, e na VPS `docker compose pull && up -d` com `image:` tageada por SHA.

### M3. `git reset --hard` no deploy + segurança SSH
- `.gitlab-ci.yml:65`: `git reset --hard origin/main` apaga qualquer hotfix local não commitado na VPS (o `.env` sobrevive por ser untracked, mas é frágil por convenção).
- `:59` + `:62`: `ssh-keyscan ... || true` seguido de `StrictHostKeyChecking=accept-new` = TOFU a cada job (runner efêmero) — MITM teórico no primeiro contato. Melhor: variável CI `VPS_HOST_KEY` fixa em `known_hosts`.
- Garanta que `SSH_PRIVATE_KEY` esteja marcada **Protected + Masked** (e idealmente tipo *File*) no GitLab; o YAML não controla isso.

### M4. Sem pinning de versões Python / pyproject dessincronizado
- `requirements.txt`: tudo `>=` — builds não reprodutíveis; um `docker build --pull` pode trazer Django/matplotlib novos e quebrar produção sem mudança de código. Falta lockfile (pip-tools/uv).
- **`pyproject.toml` não lista `playwright`**, mas `requirements.txt:2` sim — viola a regra 1 do projeto (dependências devem refletir nos dois arquivos).
- Imagens base sem digest (`python:3.12-slim-bookworm`, `node:22-alpine`, `caddy:2-alpine`, `alpine:3.21`).

### M5. Tamanho da imagem
`playwright install --with-deps chromium` (`Dockerfile:30`) adiciona ~500 MB–1 GB (Chromium + dezenas de libs X11/gtk). Somado a matplotlib + nginx, imagem final provavelmente **>1,5 GB**. Não há alternativa fácil enquanto o PDF depender de Playwright, mas: (a) o browser é baixado a cada rebuild na VPS (sem cache entre builds se o layer de requirements mudar); (b) `libfreetype6/libpng16-16` (`Dockerfile:22-23`) são provavelmente redundantes — `--with-deps` já os instala.

### M6. Observabilidade quase nula
- **nginx instalado via apt**: por padrão loga em `/var/log/nginx/access.log|error.log` **dentro do container** — invisível em `docker logs` e crescendo sem rotação. Precisa de symlink para stdout/stderr (como a imagem oficial faz) ou `access_log /dev/stdout`.
- Gunicorn sem `--access-logfile -` → sem log de acesso da API.
- Nenhum monitoramento, alerta ou métrica (nem um uptime check externo). Falha só é descoberta por usuário. Mínimo viável: logs no stdout + UptimeRobot/healthchecks.io no domínio + alerta.
- Compose sem `logging:` limits → json-file logs do Docker crescem sem cap na VPS.

### M7. Compose sem limites de recursos e sem healthcheck/depends_on condicionais
- Sem `mem_limit`/`cpus`: geração de PDF (Chromium) + matplotlib pode estourar RAM da VPS e derrubar o host junto (OOM killer aleatório).
- `caddy.depends_on: app` (`docker-compose.yml:37-38`) sem `condition: service_healthy` — inócuo na prática, mas o healthcheck existente não é aproveitado.
- Chromium + `GUNICORN_WORKERS=2` + timeout 300s: dois PDFs simultâneos = 2 Chromiums; com pouca RAM na VPS, avalie limitar concorrência de PDF na aplicação.

### M8. nginx sem hardening/otimização
`docker/nginx.conf`: sem `gzip`, sem `Cache-Control`/`expires` para os assets hashed do Vite, sem headers de segurança (`X-Content-Type-Options`, `X-Frame-Options`, CSP). Atrás do Caddy, o `X-Forwarded-Proto $scheme` (`:16`) sobrescreve com `http` — se o Django algum dia usar `SECURE_PROXY_SSL_HEADER`, isso vai enganá-lo; o correto atrás de proxy é repassar o header recebido.

### M9. CI não testa frontend nem faz scan
- Nenhum `tsc --noEmit`/lint/test do `client/` no pipeline — quebra de TypeScript só aparece no `docker build` (estágio build), tarde e com mensagem ruim.
- Sem scan de vulnerabilidade (trivy/grype) nem `pip-audit`/`npm audit` — relevante dado o Chromium embarcado.
- Estágio `test` reinstala apt+pip a cada job (cache só do pip); sem `coverage` publicado.

### M10. `.env.example` incompleto vs. código
Variáveis usadas pelo código e ausentes do `.env.example`: `INTGEST_AUTH_TOKEN_TTL_SECONDS`, `INTGEST_DEFAULT_TIMEZONE`, `PLAYWRIGHT_CHROMIUM_ARGS`; `DJANGO_CSRF_TRUSTED_ORIGINS` só aparece comentada no bloco de produção. Ponto positivo: as chaves de IA **não** vêm de env (chegam por request nos serializers) — mas isso significa que **API keys de IA trafegam no corpo de requisições** (mais um motivo para C5/HTTPS obrigatório) e podem parar em logs de acesso se um dia forem via querystring.

### M11. `.gitignore` ignora arquivos rastreados
`.gitignore:14-15` ignora `.claude/` e `CLAUDE.md`, mas `CLAUDE.md` existe no working tree (e o projeto o trata como fonte de verdade). Ignorar arquivo que se pretende versionar gera confusão (mudanças silenciosamente não commitadas). `.coverage` na raiz também não está ignorado.

---

## 4. Melhorias priorizadas (impacto × esforço)

| # | Ação | Impacto | Esforço | Referência |
|---|------|---------|---------|------------|
| 1 | Backup automatizado do SQLite (cron na VPS com `sqlite3 .backup` + cópia offsite: S3/rclone) e teste de restore documentado | Alto | Baixo | C4 |
| 2 | Bind da porta do app em `127.0.0.1:8080:80` (ou removê-la no profile https) para fechar o bypass HTTP | Alto | Trivial | C5, `docker-compose.yml:11` |
| 3 | Healthcheck apontando para endpoint da API (não o SPA) + `restart` reagindo (ou autoheal) | Alto | Baixo | C1, `Dockerfile:48` |
| 4 | Fail-fast no settings: recusar boot em produção com `SECRET_KEY`/senha default | Alto | Baixo | C6, `settings.py:17,65-66` |
| 5 | Remover `desc_dump.txt` do git (e avaliar limpeza de histórico) + ignorar | Alto | Trivial | C3 |
| 6 | Usuário não-root no Dockerfile (gunicorn e Chromium); nginx pode continuar root só no master | Alto | Médio | C2 |
| 7 | Logs de nginx/gunicorn para stdout + `logging.options.max-size` no compose + uptime check externo com alerta | Médio-Alto | Baixo | M6 |
| 8 | Lockfile Python (pip-tools/uv) + adicionar `playwright` ao `pyproject.toml` (regra 1 do projeto) | Médio | Baixo | M4 |
| 9 | Push da imagem para o GitLab Registry no `build`; VPS faz `pull` em vez de rebuild → deploy rápido e rollback por tag | Médio-Alto | Médio | M2 |
| 10 | `mem_limit`/`cpus` no serviço app (dimensionar pela RAM da VPS e pelo Chromium) | Médio | Baixo | M7 |
| 11 | Job de frontend no CI (`tsc --noEmit` + `npm run build`) e `pip-audit`/trivy | Médio | Baixo-Médio | M9 |
| 12 | `known_hosts` fixo via variável CI; conferir Protected+Masked nas variáveis | Médio | Trivial | M3 |
| 13 | Completar `.env.example`; gzip/cache headers/security headers no nginx | Baixo-Médio | Baixo | M8, M10 |
| 14 | Separar nginx e gunicorn em containers distintos (ou supervisor no container único) | Médio | Médio-Alto | M1 |


---

# Auditoria da integração com a API REST do Trello

## 1. Como está hoje

Toda a integração vive em um único cliente: `trello_metrics/trello_client.py` (~80 linhas, `urllib` puro). O cliente do backend (`backend/reports/clients/trello_client.py`) é apenas um wrapper que delega para o do engine (ou usa JSON enviado pelo usuário).

**O que o cliente faz:**
- `GET /members/me` — validação de credenciais.
- `GET /boards/{id}` com nested resources: `fields=all`, `lists=all`, `cards=all`, `card_fields=all`, `card_customFieldItems=true`, `customFields=true`, `labels=all`, `members=all`, `checklists=all`. Ou seja, **já usa** `customFieldItems` direto nos cards — bem alinhado com os nested resources oficiais.
- `GET /boards/{id}/actions` paginado com `limit=1000` e `before={id da última action}` — **correto** conforme a documentação. O filtro é `createCard,updateCard:idList,updateCard:closed,copyCard,deleteCard,updateCustomFieldItem` — inclui `updateCustomFieldItem` como exigido pelo CLAUDE.md.
- Autenticação por `key`/`token` na query string; `timeout=60` fixo; **nenhum** tratamento de erro HTTP, retry, backoff ou leitura de headers de rate limit.

**O que o parser consome** (`trello_metrics/parsers/export_loader.py`): `lists`, `labels`, `customFields`, `cards`, `actions`. Data de criação cai no fallback de extrair timestamp do ObjectId do card quando não há action `createCard`. Campos do export **não usados**: `members` e `checklists` são baixados mas ignorados; `idMembers` do card não é lido; `due`/`start` não são lidos.

## 2. Rate limits — situação e risco

Limites oficiais ([rate-limits](https://developer.atlassian.com/cloud/trello/guides/rest-api/rate-limits/)):
- **300 req/10s por API key** e **100 req/10s por token**;
- Exceder retorna **429** com `API_TOKEN_LIMIT_EXCEEDED`; mais de 200 respostas 429 em 10s bloqueiam a key pelo resto do intervalo;
- Headers informativos: `x-rate-limit-api-token-{interval-ms,max,remaining}`.

**O código não trata nada disso.** Um 429 vira exceção crua de `urllib` e derruba o fetch inteiro. Na prática o risco é moderado — um fetch completo faz ~21 requests para 20k actions, bem abaixo de 100/10s. O risco real aparece com múltiplos relatórios em paralelo ou token compartilhado com outra automação.

## 3. Paginação e tipos de action

- Paginação: **correta** (`limit=1000` + `before=último id`). Detalhe sutil: o loop para quando `len(page) < limit` — se o Trello retornar menos que o `limit` numa página intermediária (não garantido contratualmente), haveria truncamento silencioso. Mais robusto: parar apenas quando `page` vier vazia.
- Janela de histórico: a documentação **não impõe** janela de retenção para actions paginadas via `before`. O teto de ~300 actions só afeta actions aninhadas — que o código evita corretamente ao usar o endpoint dedicado.
- Tipos **não coletados** e impacto ([action-types](https://developer.atlassian.com/cloud/trello/guides/rest-api/action-types/)):
  - `addMemberToCard`/`removeMemberFromCard` — atribuição de dev depende só de custom field; membros nativos do card são invisíveis.
  - `commentCard` — perdem-se sinais de colaboração/atividade (útil para antifraude).
  - `moveCardToBoard`/`moveCardFromBoard` — cards que entram/saem entre boards ficam com buraco na timeline.
  - `convertToCardFromCheckItem` — cards nascidos de checklist sem evento de criação (fallback ObjectId cobre a data, mas sem lista de origem nem ator).
  - `updateCard:due` — sem ele não dá para auditar mudanças de prazo (relevante para SLA).
  - Nota: `addLabelToCard`/`removeLabelFromCard` só chegam via webhook — impossível coletar por REST.

## 4. Recursos da API que não aproveitamos

- **`since` no endpoint de actions**: o fetch sempre baixa o histórico completo. Com snapshots persistidos em SQLite, daria para buscar só actions novas — fetch incremental, ordens de magnitude menos requests.
- **`members` do board e `idMembers` do card**: baixados mas ignorados — cruzar com custom fields validaria identidade de colaboradores (antifraude).
- **Batch API (`GET /1/batch`)**: até 10 GETs numa chamada — **pouco aplicável aqui** (páginas de actions são sequenciais/dependentes).
- **`filter=open`**: hoje `cards=all` traz arquivados — intencional para as métricas, está certo.

## 5. Webhooks como complemento ao polling

Modelo ([webhooks](https://developer.atlassian.com/cloud/trello/guides/rest-api/webhooks/)):
- Criação: `POST /1/tokens/{token}/webhooks/` com `idModel` (board) + `callbackURL`; o Trello faz `HEAD` na criação e exige 200 + SSL válido (Caddy/HTTPS já disponível — pré-requisito atendido).
- Payload: `{action, model, webhook}` — a `action` tem o mesmo formato das actions REST; o `export_loader` existente poderia consumi-la quase sem mudanças.
- Verificação: header `X-Trello-Webhook` = base64(HMAC-SHA1(body + callbackURL, OAuth secret)) — obrigatório validar.
- Retry: 3 tentativas (30s/60s/120s); desativação após >1000 falhas E 30 dias sem sucesso.
- Bônus: webhooks entregam os 24 tipos de action **excluídos** do REST (ex.: `addLabelToCard`, `updateCheckItem`, `updateComment`).

Encaixe: um endpoint `POST /api/trello/webhook` que persiste a action manteria o SQLite quase em tempo real; o fetch completo viraria reconciliação periódica.

## 6. Robustez do cliente — lacunas concretas

1. **Sem tratamento de HTTP errors**: 401, 404 e 429 estouram como `urllib.error.HTTPError` sem mensagem amigável.
2. **Sem retry/backoff**: nenhuma resiliência a 429/5xx/timeout transitório.
3. **Sem validação de resposta**: `json.loads` sem verificar estrutura.
4. **Credenciais na query string**: padrão do Trello, mas a URL completa (com key/token) pode vazar em traceback do `HTTPError` — mascarar ao propagar erros.
5. **Timeout fixo de 60s**: razoável, mas não configurável.

## 7. Recomendações priorizadas

1. **[Alta] Tratamento de 429 + retry com backoff** no `_get`: capturar `HTTPError`, em 429/5xx aguardar (usando headers de rate limit quando disponíveis) e re-tentar 3–5x; em 401/404 erro claro em português sem expor key/token.
2. **[Alta] Ampliar o `action_filter`** com `addMemberToCard,removeMemberFromCard,commentCard,convertToCardFromCheckItem,moveCardToBoard,moveCardFromBoard` (e avaliar `updateCard:due`). Ganho: timeline sem buracos e novos sinais para antifraude/colaboradores.
3. **[Média] Fetch incremental com `since`**: buscar apenas actions novas desde o último snapshot, com fetch completo como reconciliação.
4. **[Média] Endurecer a parada da paginação**: continuar até página vazia.
5. **[Baixa/Média] Webhooks**: endpoint Django com validação HMAC-SHA1 — dados em tempo quase real + tipos de action exclusivos.
6. **[Baixa] Batch API**: não priorizar.

**Corretos e intocáveis**: paginação `before={id}` com `limit=1000`, `updateCustomFieldItem` no filtro, `card_customFieldItems=true`, endpoint dedicado de actions.

Fontes: [Rate limits](https://developer.atlassian.com/cloud/trello/guides/rest-api/rate-limits/) · [Nested resources](https://developer.atlassian.com/cloud/trello/guides/rest-api/nested-resources/) · [Action types](https://developer.atlassian.com/cloud/trello/guides/rest-api/action-types/) · [Webhooks](https://developer.atlassian.com/cloud/trello/guides/rest-api/webhooks/) · [Boards](https://developer.atlassian.com/cloud/trello/rest/api-group-boards/) · [Cards](https://developer.atlassian.com/cloud/trello/rest/api-group-cards/) · [Batch](https://developer.atlassian.com/cloud/trello/rest/api-group-batch/)
