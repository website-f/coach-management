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
- `bootstrap_system_data`

The system bootstrap is idempotent:

- if the database already has users or members, it skips
- if the database is empty, it seeds the built-in demo accounts and sample data

## Files added for deployment

- `render.yaml`
- `build.sh`

## Environment variables used

- `PYTHON_VERSION`
- `DATABASE_URL`
- `SECRET_KEY`
- `DEBUG`

`render.yaml` already defines these for Blueprint deploys.

## Deploy steps

1. Push this repo to GitHub.
2. In Render, create a new Blueprint and select the repo.
3. Render will detect `render.yaml`.
4. Review the generated services:
   - web service: `nyo-admin-dashboard`
   - database: `nyo-dashboard-db`
5. Apply the Blueprint.
6. Wait for the first deploy to finish.
7. The build will auto-run migrations and seed these system login accounts on a fresh database:

```text
admin / Admin123!
coach / Coach123!
headcount / Head123!
parent / Parent123!
```

## If you deployed manually instead of Blueprint

If your Render URL/service name does not match the one in `render.yaml`, you most likely created a manual web service. That is still fine for this bootstrap path because it no longer depends on extra env vars.

Just redeploy after pushing the latest code.

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
- The initial system login users are bootstrapped during the build on an empty database.
- If you later upgrade to a paid plan, you can reintroduce a persistent disk for safer file storage.
