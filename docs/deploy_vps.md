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

## 7. DNS e acesso

| Item | Valor |
|---|---|
| Dominio | `trello.intgest.com.br` |
| IP publico (A record) | `200.150.193.162` |
| URL (HTTP) | `http://trello.intgest.com.br` |
| URL (HTTPS) | `https://trello.intgest.com.br` |

O nginx dentro do container ja responde com `server_name trello.intgest.com.br`.
O Django so aceita requisicoes cujo header `Host` esteja em `DJANGO_ALLOWED_HOSTS`
(inclua dominio **e** IP para acesso direto por IP durante testes).

Confirme na VPS:

```bash
curl -I http://trello.intgest.com.br/
curl -I http://200.150.193.162/ -H "Host: trello.intgest.com.br"
```

Libere as portas **80** e **443** no firewall da VPS (`ufw allow 80/tcp`, `ufw allow 443/tcp`).

## 8. HTTPS (Let's Encrypt automatico)

O projeto inclui **Caddy** como proxy na frente do container, com certificado
gratuito e renovacao automatica.

### Pre-requisitos

1. DNS `trello.intgest.com.br` apontando para o IP da VPS (registro A).
2. Portas **80** e **443** abertas no firewall e no provedor (security group).
3. Nada mais escutando na porta 80/443 na VPS (pare nginx/apache do host se existir).

### Configurar `.env`

```env
APP_DOMAIN=trello.intgest.com.br
APP_PORT=8080
DJANGO_DEBUG=0
DJANGO_ALLOWED_HOSTS=trello.intgest.com.br,200.150.193.162,localhost,127.0.0.1
DJANGO_CSRF_TRUSTED_ORIGINS=https://trello.intgest.com.br
```

> `APP_PORT=8080` expoe o app so internamente; o Caddy publica 80/443 com HTTPS.
> Se ainda nao usar HTTPS, mantenha `APP_PORT=80` e suba sem o profile `https`.

### Subir com HTTPS

```bash
docker compose --profile https up -d --build
```

Na primeira subida o Caddy pede o certificado ao Let's Encrypt (leva alguns segundos).
Acesse: **https://trello.intgest.com.br**

Verificar certificado:

```bash
curl -I https://trello.intgest.com.br/
docker compose logs -f caddy
```

O Caddy redireciona HTTP → HTTPS automaticamente. Os certificados ficam no volume
`caddy_data` e sao renovados sozinhos.

### Voltar para HTTP (sem Caddy)

```bash
docker compose --profile https down
# no .env: APP_PORT=80
docker compose up -d
```

## 9. Backup do banco

O SQLite fica no volume `trello_data` (`/data/db.sqlite3` dentro do container):

```bash
docker cp trello-analytics:/data/db.sqlite3 ./backup-$(date +%F).sqlite3
```

## 10. Problemas comuns

| Sintoma | Causa provavel | Solucao |
|---|---|---|
| `Bad Request (400)` no navegador | dominio fora de `DJANGO_ALLOWED_HOSTS` | adicionar o dominio/IP e `up -d` |
| Login sempre invalido | `INTGEST_ADMIN_*` nao configurados | definir no `.env` e reiniciar |
| Download vem como `intgest-report` | versao antiga (CORS nao expunha `Content-Disposition`) | atualizar o codigo e rebuild |
| PDF/HTML vazio | periodo sem cards entregues | conferir mes/board |
| Container reinicia | ver `docker compose logs -f app` | corrigir `.env`/migracao |
| Certificado HTTPS nao emite | DNS nao aponta para a VPS ou porta 80 bloqueada | conferir A record e `ufw allow 80/tcp` |
| Cookie/CSRF invalido apos HTTPS | origem errada | definir `DJANGO_CSRF_TRUSTED_ORIGINS=https://...` |

## 11. Comandos uteis

```bash
docker compose restart app        # reiniciar
docker compose down               # parar (mantem volume/dados)
docker compose down -v            # parar e APAGAR o banco (cuidado)
docker compose exec app sh        # shell dentro do container
```
