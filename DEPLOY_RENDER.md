# Deploying To Render

## Free Tier Setup

Use:

- Render web service
- Render PostgreSQL database

This keeps local development on SQLite, but uses Postgres in production through `DATABASE_URL`.

## Important Free Tier Limits

Render's docs note:

- web services use an ephemeral filesystem by default
- free web services cannot attach persistent disks
- free web services do not provide Render Shell access

That means uploaded QR images and payment proof images are temporary on free tier and can be lost on redeploy, restart, or idle spin-down.

If you want stable file uploads later, upgrade the web service to `Starter` and attach a disk or move uploads to S3/Cloudinary.

## What the build does now

Because free tier does not support `preDeployCommand` for your use case, `build.sh` now runs:

- `collectstatic`
- `migrate`
- `ensure_superuser`

The superuser creation is idempotent:

- if a superuser already exists, it skips
- if the target username already exists, it skips
- if the required env vars are missing, it skips

## Files added for deployment

- `render.yaml`
- `build.sh`

## Environment variables used

- `PYTHON_VERSION`
- `DATABASE_URL`
- `SECRET_KEY`
- `DEBUG`
- `DJANGO_SUPERUSER_USERNAME`
- `DJANGO_SUPERUSER_EMAIL`
- `DJANGO_SUPERUSER_PASSWORD`

`render.yaml` already defines these for Blueprint deploys.

## Deploy steps

1. Push this repo to GitHub.
2. In Render, create a new Blueprint and select the repo.
3. Render will detect `render.yaml`.
4. Review the generated services:
   - web service: `nyo-admin-dashboard`
   - database: `nyo-dashboard-db`
5. Apply the Blueprint.
6. When Render asks for `DJANGO_SUPERUSER_PASSWORD`, enter your admin password.
7. Wait for the first deploy to finish.
8. The build will auto-run migrations and create the first admin user if one does not exist.

## Build and start commands

Build:

```bash
bash build.sh
```

Start:

```bash
python -m gunicorn nyo_dashboard.wsgi:application --bind 0.0.0.0:$PORT --workers 2 --threads 4 --timeout 120
```

## Notes

- Uploaded media works on free tier, but it is not persistent.
- The initial admin user is bootstrapped from environment variables during the build.
- If you later upgrade to a paid plan, you can reintroduce a persistent disk for safer file storage.
