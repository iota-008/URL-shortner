# Shortly Studio

Shortly Studio is a production-oriented Flask URL shortener with custom aliases, authenticated/guest scopes, Redis-backed redirect performance, async click processing, and VM deployment automation.

## Snapshot

- **Product:** Production-ready URL shortener with custom aliases and account/session scoping.
- **Core engineering value:** Fast redirects via Redis cache + DB fallback with queue-backed async click analytics.
- **Backend:** Flask, SQLAlchemy, Redis, PostgreSQL, Gunicorn.
- **DevOps:** Docker Compose, Traefik TLS routing, GitHub Actions SSH deployment to VM.
- **Ownership signal:** Full-stack implementation from app logic to CI/CD and production rollout.

## Feature overview

- Custom short links: Create branded aliases (or auto-generated codes) for long URLs.
- Fast redirect resolution: Redirects are served through Redis cache first, with DB fallback for reliability.
- Click analytics: Every redirect increments click counts, with queue-backed async processing for higher throughput.
- Guest + account scopes: Anonymous users see links created in current session; logged-in users see account-owned links.
- Collision-safe code creation: Duplicate custom aliases are rejected cleanly with user-facing feedback.
- Rate limiting: Request throttling protects both redirect and API endpoints from abuse.
- JSON session API: Scoped link list endpoint (`/api`) for lightweight integration or debugging.
- Production deploy automation: GitHub Actions deploys to VM over SSH with stack/env resolution and compose rollout.

## Architecture

### Request flow

1. User submits a destination URL and optional short code.
2. App validates input, stores link in SQL, and returns the short URL.
3. Redirect requests hit `/<code>`.
4. App resolves code from Redis cache first, then DB fallback.
5. Click count is queued to Redis and processed by worker (or incremented inline if queue unavailable).

### Runtime components

- `web` (`URLshort.py`): Flask app + API + auth + rendering.
- `worker` (`click_worker.py`): consumes click events and persists counts.
- `db` (PostgreSQL in prod / SQLite local): source of truth for users + links.
- `redis`: redirect cache + click event queue.

### Deployment topology

- Reverse proxy: Traefik (external, shared Docker network `web`).
- App stack: Docker Compose (`web`, `worker`, `db`, `redis`).
- CI/CD: GitHub Actions SSH deploy.
- VM file strategy:
  - Source code clone in `/opt/projects/url-shortner`
  - Stack config (`docker-compose*.yml` + `.env.production`) can live in `/home/ubuntu/stacks/url-shortner`

## Technology stack

- Python 3.12
- Flask 3.x + Jinja2
- Flask-SQLAlchemy / SQLAlchemy 2.x
- Flask-Limiter
- Redis
- PostgreSQL 16 (prod)
- Gunicorn
- Docker / Docker Compose
- GitHub Actions (`appleboy/ssh-action`)

## Repository layout

- `URLshort.py`: main application (routes, auth, redirect, API)
- `click_worker.py`: asynchronous click queue worker
- `templates/`: UI templates
- `static/`: CSS/JS/favicon assets
- `docker-compose.prod.yml`: production service definition
- `.github/workflows/deploy.yml`: VM deploy automation

## Environment variables

Use `.env` locally and `.env.production` on VM.

Required/important:

- `SECRET_KEY`
- `APP_DOMAIN`
- `DATABASE_URL`
- `REDIS_URL`
- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `ENABLE_ASYNC_CLICKS` (default `true`)
- `CLICK_QUEUE_NAME` (default `shortly:click-events`)
- `RATE_LIMIT_DEFAULT` (example `300 per minute`)

Database URI examples:

- Local SQLite: `sqlite:///shortly.db`
- Prod PostgreSQL: `postgresql+psycopg://shortly:<password>@db:5432/shortly`

## Local development

1. Install deps: `pip install -r requirements.txt`
2. Create `.env` with local values.
3. Start Redis (recommended): `docker run -d --name shortly-redis -p 6379:6379 redis:7-alpine`
4. Run app: `flask --app URLshort run --debug`
5. Run worker in second terminal: `python click_worker.py`
6. Open `http://127.0.0.1:5000`

## Production deployment (VM + Traefik)

### One-time VM prerequisites

- Docker + Compose plugin installed
- Shared Traefik network exists: `docker network create web`

### GitHub repository variables

- `VM_USER` (for example `ubuntu`)
- `DEPLOY_PATH` (for example `/opt/projects/url-shortner`)
- `COMPOSE_FILE` (optional)
- `ENV_FILE` (optional)

### GitHub repository secrets

- `VM_HOST`
- `SSH_PRIVATE_KEY`
- `VM_HOST_KEY` (recommended)

### Deployment behavior (current workflow)

- Triggers on push to `master`/`main` and manual dispatch.
- Resolves compose/env from configured vars, then stack dir, then deploy dir.
- Cleans stack dir so only compose + env files remain.
- Clones fresh source to `DEPLOY_PATH`.
- Syncs env file into deploy path as `.env.production`.
- Runs compose with `--project-directory $DEPLOY_PATH`.

## Operational endpoints

- `GET /`: dashboard + create short link
- `GET /<code>`: redirect endpoint
- `GET /api`: scoped JSON links for current user/session
- `GET /health` is not defined; use container health + logs for runtime checks

## Security notes

- Rotate secrets if ever committed accidentally.
- Keep `.env` and `.flaskenv` out of Git (already ignored).
- Prefer URL-safe DB passwords to avoid URI parsing issues.
- Keep `FORCE_HTTPS` at proxy layer and secure your VM firewall.

## Troubleshooting

### Compose says `.env.production` missing in `/opt/...`

Workflow should sync stack env into deploy path. If still failing, verify stack env exists and has read permissions.

### `postgres password authentication failed`

If credentials changed after volume creation, recreate DB volume:

`docker compose --env-file .env.production -f docker-compose.prod.yml down -v`

then

`docker compose --env-file .env.production -f docker-compose.prod.yml up -d --build`

### Redis unavailable

Redirects still work but clicks may be incremented inline; verify Redis container and URL.

## Screenshots

<img width="1218" height="1098" alt="image" src="https://github.com/user-attachments/assets/cfe7cebd-1ff6-45d6-af9a-3dfa6e031163" />
