#!/usr/bin/env sh

set -eu

echo "Starting NYO Admin Dashboard container..."

mkdir -p /app/media /app/staticfiles

if [ "${DB_ENGINE:-sqlite}" = "mysql" ]; then
  echo "Waiting for MySQL at ${DB_HOST:-db}:${DB_PORT:-3306}..."
  python - <<'PY'
import os
import sys
import time

import MySQLdb

host = os.environ.get("DB_HOST", "db")
port = int(os.environ.get("DB_PORT", "3306"))
user = os.environ.get("DB_USER", "nyo_user")
password = os.environ.get("DB_PASSWORD", "nyo_password")
database = os.environ.get("DB_NAME", "nyo_dashboard")

for attempt in range(1, 61):
    try:
        connection = MySQLdb.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
            charset="utf8mb4",
        )
        connection.close()
        print("MySQL is ready.")
        break
    except Exception as exc:
        print(f"Attempt {attempt}/60: waiting for MySQL ({exc})")
        time.sleep(2)
else:
    sys.exit("MySQL did not become ready in time.")
PY
fi

echo "Applying migrations..."
python manage.py migrate --noinput

if [ "${RUN_COLLECTSTATIC:-1}" = "1" ]; then
  echo "Collecting static files..."
  python manage.py collectstatic --noinput
fi

if [ "${AUTO_SEED_DATA:-1}" = "1" ]; then
  echo "Ensuring starter data exists..."
  python manage.py bootstrap_system_data
fi

echo "Launching application..."
exec "$@"
