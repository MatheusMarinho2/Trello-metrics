# Guia de Deploy na VPS (Docker)

Este guia sobe a aplicacao INTGEST (React + Django + `trello_metrics`) em um unico
container Docker: **nginx** serve o frontend e faz proxy do `/api` para o **gunicorn**
(Django). O banco SQLite fica em um volume persistente (`trello_data`).

## 1. Pre-requisitos na VPS

- Linux (Ubuntu/Debian recomendado)
- Docker + plugin Docker Compose
- Acesso `ssh` e uma porta liberada no firewall (padrao `8080`)

Instalar Docker (Ubuntu/Debian):

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER   # relogar depois
docker compose version          # confirmar plugin
```

## 2. Obter o codigo

```bash
sudo mkdir -p /opt/intgest && sudo chown $USER /opt/intgest
git clone <URL_DO_REPO> /opt/intgest
cd /opt/intgest
```

## 3. Configurar o `.env`

```bash
cp .env.example .env
nano .env
```

Preencha para **producao** (nao deixe os defaults de desenvolvimento):

```env
# Trello
TRELLO_API_KEY=sua_key
TRELLO_TOKEN=seu_token
TRELLO_BOARD_ID=yo4qzLai

# Django
DJANGO_DEBUG=0
DJANGO_SECRET_KEY=<gere_uma_chave_forte>
DJANGO_ALLOWED_HOSTS=trello.intgest.com.br,200.150.193.162,localhost,127.0.0.1

# Login da aplicacao (troque!)
INTGEST_ADMIN_USER=gestor
INTGEST_ADMIN_PASSWORD=<senha_forte>

# HTTP na porta 80 (dominio aponta direto para o container)
APP_PORT=80
GUNICORN_WORKERS=2
GUNICORN_TIMEOUT=300
```

Gerar uma `DJANGO_SECRET_KEY`:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(50))"
```

> **CORS:** no Docker o frontend e a API ficam na **mesma origem** (nginx serve o HTML
> e faz proxy do `/api`), entao nao ha requisicao cross-origin. `INTGEST_CORS_ALLOWED_ORIGINS`
> so importa se voce servir o frontend em outro dominio/porta.

## 4. Subir

```bash
docker compose up -d --build
```

- Build do frontend (Vite) e do backend acontece na imagem.
- O `entrypoint.sh` roda `python manage.py migrate` automaticamente antes de iniciar.
- Acesse em **http://trello.intgest.com.br** (DNS → `200.150.193.162`, porta 80).

Verificar saude/logs:

```bash
docker compose ps
docker compose logs -f app
docker inspect --format '{{.State.Health.Status}}' trello-analytics
```

## 5. Login e primeiro acesso

Nao existe tabela de usuarios do Django nem `createsuperuser`. A autenticacao e de
**usuario unico**, definido pelas variaveis `INTGEST_ADMIN_USER` / `INTGEST_ADMIN_PASSWORD`
do `.env`. Para "criar um usuario" no deploy, basta definir esses dois valores e reiniciar:

```bash
docker compose up -d
```

Em producao (`DJANGO_DEBUG=0`) o formulario de login aparece **vazio** — os defaults de
desenvolvimento (`gestor`/`intgest`) so sao pre-preenchidos em modo dev.

## 6. Atualizar apos mudancas no codigo

```bash
cd /opt/intgest
git pull
docker compose up -d --build
```

Os relatorios ficam no volume `trello_data` e sobrevivem ao rebuild.

## 7. DNS e acesso (sem HTTPS)

| Item | Valor |
|---|---|
| Dominio | `trello.intgest.com.br` |
| IP publico (A record) | `200.150.193.162` |
| URL da aplicacao | `http://trello.intgest.com.br` |

O nginx dentro do container ja responde com `server_name trello.intgest.com.br`.
O Django so aceita requisicoes cujo header `Host` esteja em `DJANGO_ALLOWED_HOSTS`
(inclua dominio **e** IP para acesso direto por IP durante testes).

Confirme na VPS:

```bash
curl -I http://trello.intgest.com.br/
curl -I http://200.150.193.162/ -H "Host: trello.intgest.com.br"
```

Libere a porta **80** no firewall da VPS (`ufw allow 80/tcp` ou equivalente).

## 8. Backup do banco

O SQLite fica no volume `trello_data` (`/data/db.sqlite3` dentro do container):

```bash
docker cp trello-analytics:/data/db.sqlite3 ./backup-$(date +%F).sqlite3
```

## 9. Problemas comuns

| Sintoma | Causa provavel | Solucao |
|---|---|---|
| `Bad Request (400)` no navegador | dominio fora de `DJANGO_ALLOWED_HOSTS` | adicionar o dominio/IP e `up -d` |
| Login sempre invalido | `INTGEST_ADMIN_*` nao configurados | definir no `.env` e reiniciar |
| Download vem como `intgest-report` | versao antiga (CORS nao expunha `Content-Disposition`) | atualizar o codigo e rebuild |
| PDF/HTML vazio | periodo sem cards entregues | conferir mes/board |
| Container reinicia | ver `docker compose logs -f app` | corrigir `.env`/migracao |

## 10. Comandos uteis

```bash
docker compose restart app        # reiniciar
docker compose down               # parar (mantem volume/dados)
docker compose down -v            # parar e APAGAR o banco (cuidado)
docker compose exec app sh        # shell dentro do container
```
