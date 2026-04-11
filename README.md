# Shortly Studio

Shortly Studio is a Flask URL shortener with custom aliases, click tracking, Redis-backed caching, async click processing, and a simple dashboard for guest or signed-in usage.

## Features

- Custom short codes
- Redirect tracking with click counts
- Redis cache for fast redirect lookups
- Async click queue worker
- Guest session history and optional user accounts
- Rate limiting with Flask-Limiter
- Docker-based production deployment behind Traefik

## Stack

- Python 3.12
- Flask + Jinja
- Flask-SQLAlchemy / SQLAlchemy
- PostgreSQL in production, SQLite locally
- Redis for cache and click queue
- Gunicorn for app serving
- Docker Compose for deployment

## Project layout

- `URLshort.py` — main Flask app
- `click_worker.py` — background worker for queued click increments
- `templates/` — HTML templates
- `static/` — CSS and browser-side JS
- `docker-compose.prod.yml` — production stack
- `.github/workflows/deploy.yml` — VM deployment workflow

## Environment variables

Copy `.env.example` to `.env` for local development and `.env.production.example` to `.env.production` on the server.

Core variables:

- `SECRET_KEY`
- `APP_DOMAIN`
- `DATABASE_URL`
- `REDIS_URL`
- `ENABLE_ASYNC_CLICKS`
- `CLICK_QUEUE_NAME`
- `RATE_LIMIT_DEFAULT`

Database notes:

- local SQLite: `sqlite:///shortly.db`
- production PostgreSQL: `postgresql+psycopg://shortly:password@db:5432/shortly`

## Local development

1. Install dependencies

	`pip install -r requirements.txt`

2. Create `.env`

	Example:

	```env
	SECRET_KEY=dev-secret
	APP_DOMAIN=localhost
	DATABASE_URL=sqlite:///shortly.db
	REDIS_URL=redis://127.0.0.1:6379/0
	ENABLE_ASYNC_CLICKS=true
	CLICK_QUEUE_NAME=shortly:click-events
	RATE_LIMIT_DEFAULT=300 per minute
	```

3. Start Redis (optional but recommended)

	`docker run -d --name shortly-redis -p 6379:6379 redis:7-alpine`

4. Start the Flask app

	`flask --app URLshort run --debug`

5. Start the click worker in a second terminal

	`python click_worker.py`

6. Open the app

	`http://127.0.0.1:5000`

## Production with Docker Compose

1. Create `/opt/projects/url-shortner/.env.production`
2. Fill it with production values
3. Start the stack:

	`docker compose --env-file .env.production -f docker-compose.prod.yml up -d --build`

Services:

- `web`
- `worker`
- `db`
- `redis`

The app is designed to sit behind your existing Traefik instance. Set `APP_DOMAIN` to your DuckDNS or custom domain so Traefik can route the service.

## GitHub Actions VM deployment

The workflow in `.github/workflows/deploy.yml` deploys on push to `master`.

### Repository variables

- `VM_USER` — example `ubuntu`
- `DEPLOY_PATH` — example `/opt/projects/url-shortner`
- `COMPOSE_FILE` — optional, defaults to `$DEPLOY_PATH/docker-compose.prod.yml`
- `ENV_FILE` — optional, defaults to `$DEPLOY_PATH/.env.production`

### Repository secrets

- `VM_HOST`
- `SSH_PRIVATE_KEY`
- `VM_HOST_KEY` — recommended for host verification

### SSH setup

Generate a dedicated deploy key:

`ssh-keygen -t ed25519 -C "github-actions-url-shortner" -f ~/.ssh/urlshortner_actions`

Authorize it on the VM:

`ssh-copy-id -i ~/.ssh/urlshortner_actions.pub ubuntu@YOUR_VM_IP`

Get the private key for GitHub:

`cat ~/.ssh/urlshortner_actions`

Get the host key for `VM_HOST_KEY`:

`ssh-keyscan -H YOUR_VM_IP`

## Secrets and password generation

Generate a Flask `SECRET_KEY`:

`python -c "import secrets; print(secrets.token_urlsafe(48))"`

Generate a URL-safe PostgreSQL password:

`python -c "import secrets,string; chars=string.ascii_letters+string.digits+'_-'; print(''.join(secrets.choice(chars) for _ in range(40)))"`

Example production database settings:

```env
POSTGRES_DB=shortly
POSTGRES_USER=shortly
POSTGRES_PASSWORD=replace-with-url-safe-password
DATABASE_URL=postgresql+psycopg://shortly:replace-with-url-safe-password@db:5432/shortly
REDIS_URL=redis://redis:6379/0
```

## Troubleshooting

### Invalid SQLAlchemy URL

Use a full `DATABASE_URL` and avoid duplicating the variable name:

```env
DATABASE_URL=postgresql+psycopg://shortly:password@db:5432/shortly
```

### `No module named psycopg2`

This project uses `psycopg` v3. Keep the PostgreSQL URL in `postgresql+psycopg://...` form.

### Postgres password authentication failed

If you changed `POSTGRES_PASSWORD` after the database volume was created, reset the stack volumes for a fresh deploy:

`docker compose --env-file .env.production -f docker-compose.prod.yml down -v`

Then bring it back up:

`docker compose --env-file .env.production -f docker-compose.prod.yml up -d --build`

## Screenshots

Home page  
![Home Page](screenshots/1.png?raw=true)

Create short link  
![Create Link](screenshots/3.png?raw=true)

Result page  
![Result Page](screenshots/2.png?raw=true)
