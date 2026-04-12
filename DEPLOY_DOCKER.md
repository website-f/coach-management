# Deploying With Docker On Your VPS

## What this setup gives you

- Django app in Docker
- MySQL in Docker
- automatic startup migration
- automatic static collection
- automatic starter-data bootstrap
- idempotent seed behavior

When the containers start:

1. MySQL waits until healthy
2. Django runs migrations
3. Django collects static files
4. Django checks whether the starter dataset exists
5. If missing, it seeds the system accounts and sample data once
6. Gunicorn starts the app

If the starter data already exists, it is skipped.

## Files added for Docker

- `Dockerfile`
- `docker-compose.yml`
- `docker/entrypoint.sh`
- `.env.example`

## First-time setup on VPS

1. Install Docker and Docker Compose plugin on the VPS.
2. Copy the project to the server.
3. Create your environment file:

```bash
cp .env.example .env
```

4. Edit `.env` and change at least:

- `SECRET_KEY`
- `DB_PASSWORD`
- `MYSQL_ROOT_PASSWORD`
- `ALLOWED_HOSTS`

5. Start everything:

```bash
docker compose up -d --build
```

6. Open the app:

```text
http://YOUR_SERVER_IP:8000
```

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

## Common commands

Start:

```bash
docker compose up -d --build
```

Stop:

```bash
docker compose down
```

View logs:

```bash
docker compose logs -f
```

Recreate only the app:

```bash
docker compose up -d --build web
```

Reset everything including MySQL data:

```bash
docker compose down -v
```

## Persistence

- MySQL data is stored in the `mysql_data` Docker volume
- uploaded QR codes and payment proofs are stored in the `media_data` Docker volume

## Reverse proxy

If you later put Nginx or Traefik in front of this app with HTTPS:

- set `ENABLE_HTTPS=true`
- set `CSRF_TRUSTED_ORIGINS=https://your-domain.com`
- set `ALLOWED_HOSTS=your-domain.com`
