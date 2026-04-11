# Shortly Studio

Shortly Studio is a Flask-based URL shortener with custom aliases, redirect tracking, Redis caching, optional async click processing, and a clean portfolio-ready UI.

## What this project does

- Create short links with custom codes
- Redirect short links to original URLs
- Track clicks per short link
- Show recent links via dashboard and JSON API
- Handle high traffic better using Redis cache + queue worker

## Tech stack

- Python, Flask
- SQLAlchemy (SQLite locally, PostgreSQL in production)
- Redis (cache + async queue)
- Flask-Limiter (rate limiting)
- Jinja + vanilla CSS/JS

## Project structure

- `URLshort.py` → main web app
- `click_worker.py` → background worker for queued click events
- `templates/` and `static/` → frontend
- `docker-compose.prod.yml` + `Dockerfile` → containerized deployment
- `.github/workflows/deploy.yml` → CI/CD deploy to VM

## Environment variables

Copy `.env.example` to `.env` for local run, and `.env.production.example` to `.env.production` for server run.

Main variables:

- `SECRET_KEY`
- `DATABASE_URL`
- `REDIS_URL`
- `ENABLE_ASYNC_CLICKS`
- `CLICK_QUEUE_NAME`
- `RATE_LIMIT_DEFAULT`

If `DATABASE_URL` is not set, local SQLite (`shortly.db`) is used.

## Run locally (recommended first)

1. Install dependencies

	`pip install -r requirements.txt`

2. Create `.env`

	Example:

	```env
	SECRET_KEY=dev-secret
	DATABASE_URL=sqlite:///shortly.db
	REDIS_URL=redis://localhost:6379/0
	ENABLE_ASYNC_CLICKS=true
	CLICK_QUEUE_NAME=shortly:click-events
	RATE_LIMIT_DEFAULT=300 per minute
	```

3. Start web app

	`flask --app URLshort run --debug`

4. (Optional but recommended) Start worker in another terminal

	`python click_worker.py`

5. Open in browser

	`http://127.0.0.1:5000`

## Run Redis locally

With Docker:

`docker run -d --name shortly-redis -p 6379:6379 redis:7-alpine`

Check:

`redis-cli -h 127.0.0.1 -p 6379 ping`

## Run with Docker (production-style)

1. Copy and configure env file

	`cp .env.production.example .env.production`

2. Start full stack

	`docker compose -f docker-compose.prod.yml up -d --build`

Services started:

- `web`
- `worker`
- `db` (Postgres)
- `redis`

If you are already using Traefik on your VM, route the `web` service through Traefik and remove the Caddy service.

## Deploy to VM (GitHub Actions)

1. Prepare VM

- Install Docker + Compose plugin
- Create deploy directory (example `/opt/projects/url-shortner`)
- Create `.env.production` on the VM (example `/opt/projects/url-shortner/.env.production`)

2. Add GitHub repository variables

- `VM_USER` (example `ubuntu`)
- `DEPLOY_PATH` (example `/opt/projects/url-shortner`)
- `COMPOSE_FILE` (optional, defaults to `$DEPLOY_PATH/docker-compose.prod.yml`)
- `ENV_FILE` (optional, defaults to `$DEPLOY_PATH/.env.production`)
- `VM_PORT` (optional, default SSH is `22`)

3. Add GitHub repository secrets

- `VM_HOST`
- `SSH_PRIVATE_KEY`
- `VM_HOST_KEY` (recommended)

4. Push to `master`

Workflow `.github/workflows/deploy.yml` connects over SSH, clones the latest `master` into `DEPLOY_PATH`, validates compose config, and deploys with Docker Compose from that path.

### How to get `SSH_PRIVATE_KEY`, `VM_HOST`, and `VM_HOST_KEY`

On your local machine:

1. Generate a dedicated deploy key pair:

	`ssh-keygen -t ed25519 -C "github-actions-url-shortner" -f ~/.ssh/urlshortner_actions`

2. Add the public key to the VM user:

	`ssh-copy-id -i ~/.ssh/urlshortner_actions.pub ubuntu@YOUR_VM_IP`

3. Copy private key into GitHub secret `SSH_PRIVATE_KEY`:

	`cat ~/.ssh/urlshortner_actions`

4. Set `VM_HOST` secret to your VM IP or DNS name.

5. Get host key and save as `VM_HOST_KEY` secret:

	`ssh-keyscan -H YOUR_VM_IP`

	Copy the full output line (e.g. `your-host ssh-ed25519 AAAA...`) into the secret.

## Notes

- For HTTPS certificates, `APP_DOMAIN` and `ACME_EMAIL` are required in `.env.production`.
- If you do not have a domain yet, use DuckDNS and point it to your VM public IP.

## Screenshots

Home page  
![Home Page](screenshots/1.png?raw=true)

Create short link  
![Create Link](screenshots/3.png?raw=true)

Result page  
![Result Page](screenshots/2.png?raw=true)
