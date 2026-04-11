# Deploying To Render

## Recommended setup

Use:

- Render web service
- Render PostgreSQL database
- A persistent disk mounted at `/var/data` for uploaded QR codes and payment proofs

This keeps local development on SQLite, but uses Postgres in production through `DATABASE_URL`.

## Why not pure SQLite on Render?

Render's docs note:

- web services use an ephemeral filesystem by default
- persistent disks are only available on paid web services
- persistent disks are not available during build or one-off jobs

Because this app stores uploaded files and needs management commands like migrations, Postgres plus a disk for `media/` is the smoother deployment path.

## Files added for deployment

- `render.yaml`
- `build.sh`

## Environment variables used

- `PYTHON_VERSION`
- `DATABASE_URL`
- `SECRET_KEY`
- `DEBUG`
- `MEDIA_ROOT`

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
7. Open the Render Shell for the web service and create an admin user:

```bash
python manage.py createsuperuser
```

## Build and start commands

Build:

```bash
bash build.sh
```

Pre-deploy:

```bash
python manage.py migrate
```

Start:

```bash
python -m gunicorn nyo_dashboard.wsgi:application --bind 0.0.0.0:$PORT --workers 2 --threads 4 --timeout 120
```

## Notes

- Uploaded files are stored under `/var/data/media`.
- The app serves uploaded media through Django in production, so QR codes and proof images still work.
- If you later want a cheaper or more scalable setup, move media to S3 or Cloudinary.
