# Metricas Trello

Projeto Python para baixar/exportar dados do Trello, calcular metricas por card, coluna, movimentacao, template e campo personalizado, e gerar um relatorio PDF com ReportLab.

## Seguranca primeiro

O token enviado na conversa deve ser revogado/gerado novamente no Trello/Atlassian, porque chave e token de API sao credenciais. Este projeto nao grava key/token no codigo; use `.env`.

Crie um arquivo `.env` baseado no `.env.example`:

```env
TRELLO_API_KEY=sua_key
TRELLO_TOKEN=seu_token
TRELLO_BOARD_ID=yo4qzLai
```

## Endpoints principais

Validar credenciais:

```text
GET https://api.trello.com/1/members/me?key=SUA_KEY&token=SEU_TOKEN
```

Buscar o quadro com listas, cards, campos personalizados e metadados:

```text
GET https://api.trello.com/1/boards/{board_id}?fields=all&lists=all&cards=all&card_fields=all&card_customFieldItems=true&customFields=true&labels=all&members=all&checklists=all&key=SUA_KEY&token=SEU_TOKEN
```

Buscar historico de movimentacoes e campos personalizados paginado:

```text
GET https://api.trello.com/1/boards/{board_id}/actions?filter=createCard,updateCard:idList,updateCard:closed,copyCard,deleteCard,updateCustomFieldItem&limit=1000&key=SUA_KEY&token=SEU_TOKEN
```

Use `before={ultimo_action_id}` para buscar as paginas antigas. O filtro
`updateCustomFieldItem` e importante para calcular a latencia ate atribuir
desenvolvedor e reconstituir trocas de campos personalizados.

## Instalar

```powershell
python -m pip install -r requirements.txt
```

## Aplicacao web Django + React

O projeto agora tambem possui uma camada web:

- `backend/`: Django + Django REST Framework, com controllers, urls, services, dataclasses, clients e utils.
- `client/`: React + TypeScript + Vite.
- Banco: somente a tabela funcional `reports_generatedreport` para guardar relatorios gerados, alem da tabela tecnica de migrations do Django.
- Autenticacao simples: usuario/senha via variaveis `INTGEST_ADMIN_USER` e `INTGEST_ADMIN_PASSWORD`, com token assinado.

Subir backend:

```powershell
python backend\manage.py migrate
python backend\manage.py runserver 127.0.0.1:8000
```

Subir frontend:

```powershell
cd client
npm install
npm run dev
```

A UI fica em `http://127.0.0.1:5173` e consome a API em `http://127.0.0.1:8000/api`.

## Deploy com Docker (VPS)

Um unico container sobe nginx (frontend React) + gunicorn (Django). O banco SQLite fica no volume `trello_data`.

Na VPS:

```bash
git clone ssh://git@git.intgest.com.br:10022/root/trello-analytics.git
cd trello-analytics
cp .env.example .env
# edite .env: DJANGO_SECRET_KEY, DJANGO_ALLOWED_HOSTS, credenciais Trello, senha admin
docker compose up -d --build
```

A aplicacao fica em `http://<vps>:8080` (porta configuravel via `APP_PORT` no `.env`).

Atualizar apos push:

```bash
git pull
docker compose up -d --build
```

Remotes Git configurados:

- `origin` → GitHub
- `gitlab` → GitLab INTGEST (`ssh://git@git.intgest.com.br:10022/root/trello-analytics.git`)

Push para GitLab:

```bash
git push gitlab main
```

### GitLab CI/CD

Desative o **Auto DevOps** no projeto GitLab: **Settings → CI/CD → Auto DevOps → Disable**.

A pipeline usa `.gitlab-ci.yml` com 3 estagios:

- `test` — roda pytest
- `build` — valida a imagem Docker (sem Container Registry)
- `deploy` — opcional, via SSH na VPS

Variaveis CI/CD para deploy automatico (**Settings → CI/CD → Variables**):

| Variavel | Exemplo |
|---|---|
| `SSH_PRIVATE_KEY` | chave privada SSH da VPS (tipo File ou Variable, masked) |
| `VPS_HOST` | IP ou dominio da VPS |
| `VPS_USER` | `root` ou usuario deploy |
| `VPS_SSH_PORT` | `22` (opcional) |
| `DEPLOY_PATH` | `/opt/trello-analytics` (opcional) |
| `APP_URL` | `http://seu-dominio:8080` (opcional) |

Na VPS, clone o repo uma vez antes do primeiro deploy:

```bash
git clone ssh://git@git.intgest.com.br:10022/root/trello-analytics.git /opt/trello-analytics
cd /opt/trello-analytics
cp .env.example .env
# configure .env
docker compose up -d --build
```

### Endpoints web

```text
POST /api/auth/login/
GET  /api/auth/me/
GET  /api/reports/options/
GET  /api/reports/
POST /api/reports/generate/
GET  /api/reports/{id}/
GET  /api/reports/{id}/export/pdf/
GET  /api/reports/{id}/export/html/
GET  /api/reports/{id}/export/json/
DELETE /api/reports/{id}/
DELETE /api/reports/            (limpa a aba; use ?report_type=)
```

Guia completo de deploy em VPS: [`docs/deploy_vps.md`](docs/deploy_vps.md).

Tipos de relatorio disponiveis:

- `general`: relatorio geral com tudo.
- `individual`: relatorio individual por colaborador.
- `developers`: relatorio de todos os desenvolvedores.
- `requesters`: relatorio de solicitantes.
- `testers`: relatorio de testers/suporte.
- `management`: relatorio de gestao.
- `specific_metrics`: relatorio com metricas selecionadas.

### IA opcional

A analise por IA so e chamada quando `ai.enabled=true` e `ai.api_key` e informada
na requisicao. A chave nao e persistida no banco. Provedores suportados:

- GPT/OpenAI via Responses API.
- Gemini via `generateContent`.
- Claude via Messages API.

Cada relatorio pode ser exportado como PDF ou JSON. Quando a IA e usada, a analise
entra no JSON e tambem aparece no PDF.

## Gerar relatorio mensal

```powershell
python -m trello_metrics monthly --month 2026-06 --board yo4qzLai
```

Ou em duas etapas:

```powershell
python -m trello_metrics fetch --board yo4qzLai --output data\trello_board_export.json
python -m trello_metrics report --source data\trello_board_export.json --month 2026-06 --history-months 6 --output reports\relatorio_2026-06.pdf --metrics-json reports\metricas_2026-06.json
```

O relatorio mensal inclui metricas por desenvolvedor, revisor, tester, solicitante,
projetos, gargalos, SLA, fluxo do time, prioridade, DORA adaptado, disciplina de
processo, risco por card e tendencia de 6 meses (PDF + JSON + **dashboard HTML interativo**).

### Dashboard HTML (visual)

Alem do PDF, e gerado automaticamente um relatorio HTML com graficos Chart.js, KPIs e navegacao lateral:

```powershell
python -m trello_metrics report --source data\trello_board_export.json --month 2026-07 --output reports\relatorio_2026-07.pdf --metrics-json reports\metricas_2026-07.json
# Gera tambem: reports\relatorio_2026-07.html
```

So a partir do JSON ja calculado:

```powershell
python -m trello_metrics dashboard --metrics-json reports\metricas_2026-07.json --output reports\relatorio_2026-07.html
```

Abra o `.html` no navegador - arquivo unico, sem servidor.

## Documentacao das metricas

O documento `reports/documentacao_metricas_calculos.md` explica cada metrica
gerada pelo sistema, as fontes de dados e as formulas usadas nos calculos.

### SLA e nivelamento

- [`docs/sistema_metricas_trello.md`](docs/sistema_metricas_trello.md) — documentacao completa do sistema (arquitetura, metricas, deploy, API) — by Matheus Marinho
- [`docs/sla_medicacao_e_niveis.md`](docs/sla_medicacao_e_niveis.md) — como o SLA e medido, tabela por coluna, niveis Fibonacci, analise e retornos por prioridade
- [`docs/guia_nivelacao_tarefas.md`](docs/guia_nivelacao_tarefas.md) — guia para desenvolvedores nivelarem cards (problema e analise) em projetos Django/regra de negocio

## Gerar relatorio pelo JSON exportado

```powershell
python -m trello_metrics report --source "C:\Users\matheus.nascimento\Downloads\yo4qzLai - fluxo-trabalho-intgest.json" --output reports\relatorio_metricas_trello.pdf
```

Tambem sera gerado `reports\metricas_trello.json` com os dados calculados.

## Baixar direto da API

```powershell
python -m trello_metrics me
python -m trello_metrics fetch --board yo4qzLai --output data\trello_board_export.json
python -m trello_metrics report --source data\trello_board_export.json --output reports\relatorio_metricas_trello.pdf
```

## Regras implementadas

- Cards template sao ignorados por padrao.
- Card de problema: prefixos `PM CLIENTE` ou `PROBLEMA`, nivel em `Nivel`.
- Card de analise: prefixos `ANALISE`/`ANALISES`, nivel em `Nivel (Analise)`.
- Movimento para `RETORNO (DEV)` e atribuido ao campo personalizado `Desenvolvedor`.
- Movimento para `RETORNO (SUP)` e atribuido ao campo personalizado `Tester`.
- `EM ANDAMENTO` tambem e atribuido a `Desenvolvedor`.
- `AGUARDANDO REVISAO EM PAR` e uma fila neutra: aparece no historico, mas nao
  conta como tempo do desenvolvedor nem do revisor em par.
- `REVISAO EM PAR` e atribuida a `Revisor em Par`.
- `AGUARDANDO REVISAO`/`AGUARDANDO REVISAO (Opcional)` sao pontos neutros de
  controle; `EM REVISAO` e atribuida a `Revisor`.
- `AGUARDANDO TESTE`/`EM TESTE` sao atribuidos a `Tester`.
- `AGUARDANDO TESTE (X)` / `AGUARDANDO PRODUCAO (X)` por projeto sao fundidos num unico
  estagio (`waiting_test`/`waiting_production`) para as metricas de gargalo; a quebra
  por lista especifica so aparece na secao "Controle de gestao" do relatorio.
- SLA: regras por etapa, por nivel Fibonacci (Em andamento), por nivel de analise (Analises para planejamento) e por prioridade em retornos; configuracao em `sla_rules` no `workflow.json`. Detalhes em `docs/sla_medicacao_e_niveis.md`.
- Revisao em par que devolve o card para `EM ANDAMENTO` e um pente-fino de qualidade do
  revisor, **nao** conta como retrabalho do desenvolvedor (isso e contado separadamente
  de `RETORNO (DEV)`/`RETORNO (SUP)`).
- Dupla revisao (revisao em par + revisao formal): obrigatoria para cards nivel 8/13
  (violacoes sao listadas nominalmente no relatorio); recomendada (informativo, sem
  penalidade) para nivel 5. Configuravel em `double_review_rule` no `workflow.json`.
- Retrabalho e qualidade: `taxa de retrabalho` = % de cards entregues que voltaram ao
  menos 1x para o desenvolvedor; `taxa de qualidade` e o complemento (ex.: 10 entregues,
  1 voltou = 90% de qualidade); `selo de qualidade` (Ouro/Prata/Atencao) usa os limites
  de `quality_seal_thresholds` no `workflow.json`.
- O motivo/solucao de cada retorno (`RETORNO (DEV)`/`RETORNO (SUP)`) e o motivo de cada
  pausa sao extraidos da descricao do card, usando o padrao de template
  `[Retorno N (dev|sup) (Teste|Revisao)]:` / `[Solucao N ...]:` e `[Motivo Pause N] dd/mm/aaaa - hh:mm:`.
  O casamento entre o texto e o movimento real (data/hora) e feito por ordem cronologica
  e e uma heuristica, pois o Trello nao linka estruturalmente descricao a movimentacao.
- O relatorio mensal inclui um apendice "Detalhamento de cards" com o historico completo
  por desenvolvedor (tarefas normais e cards de analise separados), por solicitante e
  por tester.
- Metricas de tester/suporte: movimento real de `EM TESTE` para `RETORNO (DEV)`
  conta como `Problemas evitados` para o tester. Esse retorno tambem derruba a
  qualidade/aprovacao do desenvolvedor e dos revisores que deixaram o problema chegar
  ao teste. O motivo do retorno deve estar registrado no card; quando faltar, o
  relatorio marca `Sem motivo`. `RETORNO (SUP)` e mantido apenas como etapa/historico
  do card, sem entrar na performance de tester.

As colunas e regras ficam em `trello_metrics/resources/workflow.json`.
