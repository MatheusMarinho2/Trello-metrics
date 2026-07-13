# Sistema de Métricas Trello INTGEST

**Autor:** Matheus Marinho  
**Organização:** INTGEST — Inteligência e Gestão Tecnológica  
**Versão do documento:** julho/2026  
**Repositórios:** GitHub (`origin`) · GitLab INTGEST (`gitlab`)

---

## 1. Visão geral

Este projeto é um **sistema completo de analytics** para o fluxo de trabalho Trello da INTGEST (LegisVoto). Ele substitui o processo manual de acompanhamento de cards por uma plataforma que:

1. **Coleta** dados do quadro Trello (API ou export JSON)
2. **Calcula** dezenas de métricas de engenharia (fluxo, SLA, DORA, Fibonacci, qualidade, etc.)
3. **Gera relatórios** em PDF, HTML interativo e JSON
4. **Disponibiliza** uma interface web para gestão, preview e exportação
5. **Persiste** histórico de relatórios e snapshots do board

O sistema foi desenvolvido do zero por **Matheus Marinho**, incluindo:

- Engine de métricas Python (`trello_metrics`)
- API REST Django
- Frontend React/TypeScript
- Pipeline Docker para produção (VPS)
- Relatório PDF com layout corporativo IntGest (HTML + Playwright)
- Integração opcional com IA para análise gerencial

**Produção:** `http://trello.intgest.com.br:8080` (VPS `200.150.193.162`)  
**HTTPS:** suporte via Caddy + Let's Encrypt (ver seção 8)

---

## 2. Arquitetura

```
┌─────────────────────────────────────────────────────────────────┐
│                         USUÁRIO / CLI                           │
└───────────────┬───────────────────────────────┬─────────────────┘
                │                               │
         Interface Web                    python -m trello_metrics
         (React + Vite)                         (CLI)
                │                               │
                ▼                               ▼
┌───────────────────────────┐     ┌─────────────────────────────┐
│  nginx (porta 80)         │     │  trello_metrics/            │
│  ├── React build (SPA)    │     │  ├── trello_client.py       │
│  └── proxy /api/ ─────────┼─────┼──► parsers/                  │
└───────────────┬───────────┘     │  ├── metrics/engine.py      │
                │                 │  └── reports/ (PDF/HTML)    │
                ▼                 └──────────────┬──────────────┘
┌───────────────────────────┐                    │
│  gunicorn + Django REST   │◄───────────────────┘
│  backend/reports/         │
│  └── SQLite (/data/)      │
└───────────────┬───────────┘
                │
                ▼
┌───────────────────────────┐
│  Trello REST API          │
│  api.trello.com/1/        │
└───────────────────────────┘
```

### Camadas

| Camada | Tecnologia | Responsabilidade |
|---|---|---|
| **Core** | Python 3.12 | Cálculo de métricas, parse Trello, exportação |
| **Backend** | Django 5 + DRF + gunicorn | API REST, persistência, autenticação |
| **Frontend** | React 19 + TypeScript + Vite 6 | UI de geração, preview e export |
| **PDF** | Playwright + Chromium | Renderização HTML → PDF layout IntGest |
| **HTML** | Chart.js 4 | Relatório interativo com gráficos |
| **Infra** | Docker + nginx + Caddy | Deploy VPS, HTTPS automático |
| **CI/CD** | GitLab CI | Test → Build → Deploy SSH |

---

## 3. Estrutura de pastas

```
Metricas Trello/
├── trello_metrics/          # Biblioteca core (métricas + relatórios)
│   ├── cli.py               # Interface de linha de comando
│   ├── trello_client.py     # Cliente HTTP da API Trello
│   ├── config.py            # Carrega .env e workflow.json
│   ├── domain/              # Modelos de domínio (BoardData, Card, Movement)
│   ├── parsers/             # Parse export JSON + descrições de cards
│   ├── metrics/             # Engine + agregadores + timeline
│   ├── reports/             # PDF IntGest, HTML, charts, layouts
│   ├── resources/           # workflow.json (regras de negócio)
│   └── utils/               # Horas úteis, Fibonacci, datas
├── backend/                 # API Django
│   ├── intgest_reports/     # Settings, URLs, middleware CORS
│   └── reports/             # Models, controllers, services, clients
├── client/                  # Frontend React
│   └── src/                 # App.tsx, api, types, components
├── docker/                  # nginx.conf, Caddyfile, entrypoint.sh
├── docs/                    # Documentação (este arquivo + guias)
├── tests/                   # pytest
├── Dockerfile               # Build multi-stage (Node + Python)
├── docker-compose.yml       # app + caddy (profile https)
└── requirements.txt         # Dependências Python
```

---

## 4. Integração com Trello

### 4.1 Endpoints utilizados

| Endpoint | Uso |
|---|---|
| `GET /members/me` | Validar credenciais |
| `GET /boards/{id}?fields=all&lists=all&cards=all&...` | Board completo |
| `GET /boards/{id}/actions?filter=...&limit=1000` | Histórico paginado |

**Filtro de actions:** `createCard`, `updateCard:idList`, `updateCard:closed`, `copyCard`, `deleteCard`, `updateCustomFieldItem`

A action `updateCustomFieldItem` é essencial para calcular latência de atribuição de desenvolvedor e reconstituir trocas de campos personalizados.

### 4.2 Parse e normalização

O módulo `parsers/export_loader.py` converte o JSON bruto do Trello em `BoardData`:

- Cards com custom fields (Desenvolvedor, Tester, Revisor, Sistema, Prioridade, etc.)
- Movimentos entre listas (timeline)
- Mudanças de campos personalizados
- Parse de descrição para **retornos** (`[Retorno N ...]`) e **pausas**

### 4.3 Regras de negócio (`workflow.json`)

| Regra | Comportamento |
|---|---|
| Templates | Cards template são ignorados nas métricas |
| Labels `NAO METRICAR` / `CONTROLE` | Ignorados |
| Tipos de card | **Problema** (PM CLIENTE, PROBLEMA) vs **Análise** (ANALISE) |
| Horas úteis | Seg–sex, 08:00–18:00/17:30, almoço excluído |
| Atribuição | Por coluna → campo custom (D-, R-, RP-, S-, T-) |
| Dupla revisão | Obrigatória nível 8/13, recomendada nível 5 |
| Selo de qualidade | Ouro / Prata / Bronze conforme taxas do time |

Documentação detalhada de SLA e níveis: [`sla_medicacao_e_niveis.md`](sla_medicacao_e_niveis.md)  
Guia para desenvolvedores nivelarem cards: [`guia_nivelacao_tarefas.md`](guia_nivelacao_tarefas.md)

---

## 5. Métricas calculadas

O `MetricsEngine` (`trello_metrics/metrics/engine.py`) orquestra os agregadores. Com `--month YYYY-MM` gera métricas mensais; sem mês, gera overview estático.

### 5.1 Agregadores principais

| Módulo | Chave JSON | O que mede |
|---|---|---|
| `developers.py` | `developers`, `developer_profiles` | Entregas, Fibonacci, retrabalho, aceitação, tempo dev |
| `reviewers.py` | `reviewers` | Revisão em par e formal, taxa aprovação |
| `testers.py` | `testers` | Testes, problemas evitados, 1ª passagem |
| `requesters.py` | `requesters` | Cards criados/entregues, planejamento |
| `flow.py` | `flow` | WIP, aging, lead/cycle time, CFD, Little's Law |
| `priority.py` | `priority` | Distribuição, inflação, furos de fila |
| `dora.py` | `dora` | DORA adaptado (deploy, CFR, time to restore) |
| `fibonacci_points.py` | `fibonacci_points` | Pontos por desenvolvedor entregue |
| `sla.py` | `sla` | Conformidade SLA por etapa/dev/card |
| `bottlenecks.py` | `bottlenecks` | Gargalos por etapa e sistema |
| `quality_gates.py` | `quality_gates` | Dupla revisão obrigatória/recomendada |
| `process_discipline.py` | `process_discipline` | Campos obrigatórios, ordem de etapas |
| `risk.py` | `risk_board` | Score de risco (aging + prioridade + nível) |
| `projects.py` | `projects` | Métricas por sistema/projeto |
| `collaborators.py` | `collaborators` | Visão unificada por pessoa (todos os papéis) |
| `card_dossier.py` | `card_dossier` | Dossiê detalhado por card |
| `trends.py` | `trends_6m` | Tendência de 6 meses |
| `analysis_workflow.py` | `analysis_workflow` | Fluxo de cards de análise |
| `antifraud.py` | `antifraud` | Cópias suspeitas (reset de métricas), lineage da fonte |

### 5.2 Métricas base (sempre presentes)

- `overview` — totais por lista, tipo, templates ignorados
- `custom_fields` — distribuição de campos personalizados
- `movements` — estatísticas de movimentação
- `data_quality` — completude de campos obrigatórios
- `team_summary` — KPIs consolidados do time (entregas, qualidade, selo)

### 5.3 Memória de cálculo

Cada métrica expõe **fórmula + exemplo** para o analista entender como o número foi obtido:

- Fonte: `formulas` em `trello_metrics/resources/metric_definitions.json` (espelhado em `reports/` e `client/src/data/`)
- Preview web: HelpTip nos KPIs/colunas + bloco “Memória de cálculo” em todos os tipos de relatório
- PDF/HTML: seção `metric_guide` habilitada em todos os layouts

### 5.4 Lacunas conhecidas de métrificação

Eventos/comportamentos do Trello que **ainda distorcem ou ficam de fora** das métricas (documentado; correção futura):

| Prioridade | Lacuna | Impacto |
|---|---|---|
| 1 | Custom fields só no snapshot final (exceto latência de Dev) | SLA/produtividade creditam pessoa errada após troca |
| 2 | Retorno: movimento vs texto na descrição (heurística) | Distorce retrabalho, aceitação e “problemas evitados” |
| 3 | `closed` / `delete` / `reopen` pouco modelados | Lead/cycle/WIP e entregas distorcidas |
| 4 | `actor_name` parseado e ignorado nos agregadores | Não identifica quem moveu o card |
| 5 | Prioridade/nível finais no SLA de retorno | Limite SLA pode estar errado |
| 6 | Listas / `kind` `unknown` | Tempo e WIP misturam ruído com fluxo oficial |
| 7 | Filas `review_control` / `waiting_peer_review` fora do flow hours | Subestima tempo real até deploy |
| 8 | Comentários, checklists, due date, membros nativos | Comportamento real do time fora das métricas |

Também: DORA CFR por label `CORRECAO` (proxy); revisor formal subrepresentado em `reviewers.py`; checklists baixados e não usados.

### 5.5 Antifraude (cópias e reset de métricas)

O agregador `antifraud` detecta `copyCard` com `cardSource`:

- **Whitelist:** templates (`isTemplate`), padrões em `workflow.json`, e **cópias de outro board** (fonte sem actions/card neste quadro)
- **Escopo:** só avalia reset quando a fonte **já existia neste board** (card vivo ou `created`/`moved`/`deleted` local)
- **Lineage da fonte:** timeline viva ou reconstrução via actions + `deleteCard` / `updateCard:closed` (lista na exclusão ou arquivamento)
- **Scores:** `high` (fonte terminal / exclusão ou arquivamento rápido pós-cópia + destino planejamento/backlog), `medium` (mesmo nome / reinício sem evidência terminal)
- **Exports:** chave `antifraud` no JSON; seção no PDF/HTML/preview (`general` e `management`)
- **IA:** `antifraud_insights` no contexto + seção “Antifraude / cópias suspeitas”

Não exclui clones das métricas de entrega nesta versão (só alerta).

---

## 6. Tipos de relatório

| `report_type` | Nome | Seções incluídas |
|---|---|---|
| `general` | Geral | Todas as métricas mensais |
| `individual` | Individual | Métricas de um colaborador específico |
| `developers` | Desenvolvedores | Devs, perfis, fluxo, SLA, dupla revisão, dossiê |
| `requesters` | Solicitantes | Métricas de quem abre demandas |
| `testers` | Testers | Métricas de teste/suporte |
| `management` | Gestão | Resumo executivo, fluxo, DORA, gargalos, tendências |
| `specific_metrics` | Métricas específicas | Subconjunto escolhido pelo usuário |

Layouts definidos em `trello_metrics/reports/report_layouts.py` e espelhados no frontend (`client/src/lib/reportLayouts.ts`).

---

## 7. Formatos de exportação

### 7.1 JSON

Payload completo ou filtrado por tipo de relatório. Inclui metadados (`export_meta`), métricas e análise IA (se gerada).

**Nomenclatura:** `intgest_{tipo}_{colaborador}_{mes}.json`

### 7.2 PDF (layout IntGest)

Gerado via **HTML + Playwright (Chromium)** com design system corporativo:

- Capa com selo de qualidade
- Seções numeradas com KPI cards
- Tabelas estilizadas (navy `#133968`, teal `#428BA5`)
- Gráficos matplotlib embutidos
- Dossiê técnico de cards com retornos, pausas e etapas

Módulo: `trello_metrics/reports/pdf_intgest/`

### 7.3 HTML interativo

Self-contained com Chart.js, sidebar navegável, funciona offline após download.

Módulo: `trello_metrics/reports/html_report.py`

---

## 8. Interface web

### 8.1 Autenticação

- **Usuário único** definido por variáveis de ambiente (`INTGEST_ADMIN_USER`, `INTGEST_ADMIN_PASSWORD`)
- Token Bearer assinado (Django `TimestampSigner`), TTL configurável (padrão 12h)
- Sem tabela de usuários Django — login simples para uso interno INTGEST

### 8.2 Funcionalidades da UI

1. **Login** — formulário usuário/senha
2. **7 abas de relatório** — Geral, Individual, Devs, Solicitantes, Testers, Gestão, Métricas
3. **Formulário de geração** — mês, board, credenciais Trello ou JSON inline, IA opcional
4. **Histórico** — relatórios anteriores por tipo
5. **Preview inline** — KPIs e tabelas conforme layout do tipo
6. **Export** — PDF, HTML, JSON + imprimir
7. **Colaboradores** — sync do Trello, CRUD manual, aliases
8. **Memória de cálculo** — fórmulas/exemplos no HelpTip e guia em todos os tipos de relatório

### 8.3 API REST

| Método | Endpoint | Descrição |
|---|---|---|
| `POST` | `/api/auth/login/` | Login → token |
| `GET` | `/api/auth/me/` | Usuário autenticado |
| `GET` | `/api/reports/options/` | Tipos, métricas, provedores IA |
| `GET/DELETE` | `/api/reports/` | Histórico (filtro `?report_type=`) |
| `POST` | `/api/reports/generate/` | Gera relatório |
| `GET/DELETE` | `/api/reports/{uuid}/` | Detalhe / remover |
| `GET` | `/api/reports/{uuid}/export/pdf/` | Download PDF |
| `GET` | `/api/reports/{uuid}/export/html/` | Download HTML |
| `GET` | `/api/reports/{uuid}/export/json/` | Download JSON |
| `GET/POST` | `/api/collaborators/` | Lista / cria colaborador |
| `POST` | `/api/collaborators/sync/` | Sync nomes do Trello |

---

## 9. CLI (linha de comando)

```powershell
# Validar credenciais
python -m trello_metrics me

# Baixar board
python -m trello_metrics fetch --board yo4qzLai --output data/board.json

# Gerar relatório (JSON + PDF + HTML)
python -m trello_metrics report --source data/board.json --month 2026-07

# Fetch + report em um passo
python -m trello_metrics monthly --month 2026-07 --board yo4qzLai

# HTML a partir de JSON já calculado
python -m trello_metrics dashboard --metrics-json reports/metrics.json
```

Flags: `--workflow`, `--include-templates`, `--history-months` (padrão 6), `--timezone` (padrão `America/Sao_Paulo`).

---

## 10. Deploy em produção

### 10.1 Docker (VPS)

Um container `app` sobe nginx + gunicorn + SQLite persistente.

```bash
git clone ssh://git@git.intgest.com.br:10022/root/trello-analytics.git /opt/intgest
cd /opt/intgest
cp .env.example .env
# editar .env (ver seção 10.3)
docker compose up -d --build
```

Guia completo: [`deploy_vps.md`](deploy_vps.md)

### 10.2 HTTPS com Caddy

```bash
# .env
APP_DOMAIN=trello.intgest.com.br
APP_PORT=8080
DJANGO_CSRF_TRUSTED_ORIGINS=https://trello.intgest.com.br

# Firewall
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Subir com HTTPS
docker compose --profile https up -d --build
```

Caddy emite certificado Let's Encrypt automaticamente e renova sozinho.

### 10.3 Variáveis de ambiente

| Variável | Descrição |
|---|---|
| `TRELLO_API_KEY`, `TRELLO_TOKEN`, `TRELLO_BOARD_ID` | Credenciais Trello |
| `DJANGO_SECRET_KEY` | Chave secreta Django (gerar forte) |
| `DJANGO_DEBUG` | `0` produção, `1` desenvolvimento |
| `DJANGO_ALLOWED_HOSTS` | Domínio + IP da VPS |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | `https://trello.intgest.com.br` |
| `INTGEST_ADMIN_USER`, `INTGEST_ADMIN_PASSWORD` | Login da aplicação |
| `INTGEST_AUTH_TOKEN_TTL_SECONDS` | TTL do token (padrão 43200) |
| `APP_PORT` | Porta host→container (`8080` com Caddy, `80` sem) |
| `APP_DOMAIN` | Domínio para Caddy |
| `GUNICORN_WORKERS`, `GUNICORN_TIMEOUT` | Config gunicorn |

### 10.4 CI/CD (GitLab)

Pipeline `.gitlab-ci.yml`:

1. **test** — pytest
2. **build** — valida imagem Docker
3. **deploy** — SSH na VPS + `git pull` + `docker compose up -d --build`

---

## 11. Análise por IA (opcional)

Na geração web, é possível solicitar análise gerencial automática via:

- OpenAI (Responses API)
- Google Gemini
- Anthropic Claude

A análise é salva no relatório (`ai_analysis`) e incluída nos exports PDF/HTML.

---

## 12. Modelo de dados (SQLite)

| Tabela | Conteúdo |
|---|---|
| `TrelloBoardSnapshot` | Snapshot normalizado do board |
| `TrelloListRecord` | Listas do snapshot |
| `TrelloCardRecord` | Cards com custom fields e descrição parseada |
| `TrelloMovementRecord` | Movimentos entre listas |
| `TrelloCustomFieldChangeRecord` | Mudanças de campos personalizados |
| `Collaborator` | Colaboradores (sync Trello + manual) |
| `GeneratedReport` | Relatórios gerados (métricas, IA, metadados) |

Volume Docker: `trello_data:/data/db.sqlite3`

**Backup:**
```bash
docker cp trello-analytics:/data/db.sqlite3 ./backup-$(date +%F).sqlite3
```

---

## 13. Desenvolvimento local

### Backend
```powershell
python -m pip install -r requirements.txt
playwright install chromium
python backend\manage.py migrate
python backend\manage.py runserver 127.0.0.1:8000
```

### Frontend
```powershell
cd client
npm install
npm run dev
```

UI: `http://127.0.0.1:5173` → API: `http://127.0.0.1:8000/api`

### Testes
```powershell
python -m pytest tests/ -v
```

---

## 14. Documentação complementar

| Documento | Conteúdo |
|---|---|
| [`deploy_vps.md`](deploy_vps.md) | Deploy Docker, DNS, HTTPS, firewall, troubleshooting |
| [`sla_medicacao_e_niveis.md`](sla_medicacao_e_niveis.md) | SLA, horas úteis, níveis Fibonacci |
| [`guia_nivelacao_tarefas.md`](guia_nivelacao_tarefas.md) | Guia para devs nivelarem cards |
| [`../README.md`](../README.md) | Guia rápido de instalação e uso |
| `trello_metrics/reports/metric_definitions.json` | Definições de métricas (labels, fórmulas) |
| `trello_metrics/resources/workflow.json` | Configuração do fluxo (colunas, SLA, selos) |

---

## 15. Histórico de evolução

| Fase | O que foi feito |
|---|---|
| **v1 — Core Python** | Cliente Trello, parse export, engine de métricas, CLI, PDF ReportLab |
| **v2 — Métricas avançadas** | Fluxo (CFD, aging, Little's Law), DORA, SLA, risco, dossiê de cards |
| **v3 — Web app** | Django REST + React, autenticação, histórico, preview, export |
| **v4 — Relatórios** | HTML interativo (Chart.js), filtros por tipo, análise IA |
| **v5 — PDF IntGest** | Layout corporativo HTML + Playwright, capa, KPI cards, dossiê estilizado |
| **v6 — Produção** | Docker multi-stage, GitLab CI/CD, deploy VPS, HTTPS com Caddy |
| **v7 — Colaboradores** | Sync Trello, visão unificada por pessoa, perfis individuais |

---

## 16. Créditos

**Sistema desenvolvido por Matheus Marinho**  
INTGEST — Inteligência e Gestão Tecnológica · LegisVoto

Repositórios:
- GitHub: `MatheusMarinho2/Trello-metrics`
- GitLab INTGEST: `git.intgest.com.br/root/trello-analytics`
