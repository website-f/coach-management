# Deploying With Docker, Nginx, and HTTPS On Your VPS

## What this setup gives you

- Django app in Docker
- MySQL in Docker
- Nginx reverse proxy in Docker
- automatic Let's Encrypt HTTPS certificates
- automatic certificate renewal checks
- automatic startup migration
- automatic static collection
- automatic starter-data bootstrap
- local Ollama service for the coach AI planner
- direct Nginx serving for static assets
- health checks for the main containers
- idempotent seed behavior

When the stack starts:

1. MySQL starts
2. Django waits for MySQL, then runs migrations
3. Django collects static files into a shared volume served by Nginx
4. Django checks whether the starter dataset exists
5. If missing, it seeds the system accounts and sample data once
6. Ollama starts and pulls the configured Qwen model in the background
7. The web app becomes healthy without waiting for Ollama, so the dashboard can boot faster
8. Nginx opens ports `80` and `443`
9. Certbot requests a Let's Encrypt certificate for your domain
10. Nginx switches from bootstrap mode to full HTTPS mode as soon as the certificate exists

If the starter data already exists, it is skipped.

## Files in the Docker deployment layer

- `Dockerfile`
- `docker-compose.yml`
- `docker/entrypoint.sh`
- `docker/nginx/entrypoint.sh`
- `docker/nginx/templates/bootstrap.conf.template`
- `docker/nginx/templates/https.conf.template`
- `docker/certbot/entrypoint.sh`
- `.env.example`
- `gunicorn.conf.py`

## Before you start

Make sure all of these are ready first:

1. Your domain already points to the VPS public IP.
2. Ports `80` and `443` are open on the VPS firewall.
3. Docker and Docker Compose are installed on the VPS.

Without DNS pointing correctly, Let's Encrypt cannot issue the certificate yet.

## First-time setup

1. Copy the project to the VPS.
2. Create your environment file:

```bash
cp .env.example .env
```

3. Edit `.env` and change these values before first boot:

- `SECRET_KEY`
- `DOMAIN`
- `WWW_DOMAIN` if you also want `www`
- `LETSENCRYPT_EMAIL`
- `ALLOWED_HOSTS`
- `CSRF_TRUSTED_ORIGINS`
- `DB_PASSWORD`
- `MYSQL_ROOT_PASSWORD`

4. Start the full stack:

```bash
docker compose up -d --build
```

5. Watch the first boot:

```bash
docker compose logs -f db web nginx certbot ollama ollama-init
```

6. Open the site once the certificate is issued:

```text
https://your-domain.com
```

## How HTTPS behaves

- Nginx starts immediately on port `80`
- while the certificate is being issued, Nginx serves the ACME challenge used by Let's Encrypt
- once the certificate exists, Nginx reloads itself and starts serving `443`
- after that, all HTTP traffic is redirected to HTTPS
- certificate renewal checks continue automatically in the background

If certificate issuance fails, check:

- DNS points to the correct VPS IP
- ports `80` and `443` are open
- `DOMAIN` and `WWW_DOMAIN` are correct
- `LETSENCRYPT_EMAIL` is valid

## Default seeded system logins

Unless you override them in `.env`, the startup seed uses:

```text
admin / Admin123!
coach / Coach123!
headcount / Head123!
parent / Parent123!
```

You can override the seeded passwords in `.env`:

- `SEED_ADMIN_PASSWORD`
- `SEED_COACH_PASSWORD`
- `SEED_HEADCOUNT_PASSWORD`
- `SEED_PARENT_PASSWORD`
- `DB_CONN_MAX_AGE`
- `WEB_CONCURRENCY`
- `GUNICORN_THREADS`
- `GUNICORN_TIMEOUT`
- `GUNICORN_KEEPALIVE`

## Common commands

Start or rebuild everything:

```bash
docker compose up -d --build
```

Stop everything:

```bash
docker compose down
```

View logs:

```bash
docker compose logs -f
```

Restart only the web app:

```bash
docker compose up -d --build web
```

Restart only Nginx:

```bash
docker compose restart nginx
```

Reset everything including MySQL data and certificates:

```bash
docker compose down -v
```

## Persistence

- MySQL data is stored in the `mysql_data` Docker volume
- uploaded QR codes and payment proofs are stored in the `media_data` Docker volume
- collected static files are stored in the `static_data` Docker volume
- Let's Encrypt certificates are stored in the `letsencrypt_certs` Docker volume
- Ollama models are stored in the `ollama_data` Docker volume

## Local AI Planner

The session planner now supports a floating local AI assistant powered by Ollama.

Default AI settings in `.env`:

- `AI_PLANNER_ENABLED=1`
- `AI_PLANNER_BACKEND=ollama`
- `AI_PLANNER_FALLBACK_ENABLED=1`
- `OLLAMA_BASE_URL=http://ollama:11434`
- `OLLAMA_MODEL=qwen2.5:3b`
- `OLLAMA_KEEP_ALIVE=10m`
- `OLLAMA_MAX_LOADED_MODELS=1`
- `OLLAMA_NUM_PARALLEL=1`

Notes:

- first model pull can take a while depending on VPS network speed
- until the model is ready, the planner can fall back to the built-in deterministic session blueprint
- once pulled, the Qwen model stays cached in the `ollama_data` volume
- repeated prompts can reuse saved session-plan answers for faster responses
- the web container now allows a longer first-boot health window because migration, collectstatic, and initial seed can take a while on smaller VPS instances

## VPS-friendly defaults

The current defaults are tuned to be safer on a modest VPS:

- `WEB_CONCURRENCY=1`
- `GUNICORN_THREADS=2`
- Ollama keeps only one model loaded
- Ollama answers one request at a time by default

If your VPS is stronger, you can raise:

- `WEB_CONCURRENCY`
- `GUNICORN_THREADS`
- `OLLAMA_NUM_PARALLEL`
