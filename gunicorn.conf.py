import multiprocessing
import os


bind = "0.0.0.0:8000"
worker_class = "gthread"
workers = int(os.environ.get("WEB_CONCURRENCY", max(1, min(2, multiprocessing.cpu_count()))))
threads = int(os.environ.get("GUNICORN_THREADS", "2"))
timeout = int(os.environ.get("GUNICORN_TIMEOUT", "120"))
graceful_timeout = int(os.environ.get("GUNICORN_GRACEFUL_TIMEOUT", "30"))
keepalive = int(os.environ.get("GUNICORN_KEEPALIVE", "10"))
preload_app = os.environ.get("GUNICORN_PRELOAD", "1") == "1"
worker_tmp_dir = "/dev/shm"
max_requests = int(os.environ.get("GUNICORN_MAX_REQUESTS", "1000"))
max_requests_jitter = int(os.environ.get("GUNICORN_MAX_REQUESTS_JITTER", "100"))
accesslog = "-"
errorlog = "-"
capture_output = True
loglevel = os.environ.get("GUNICORN_LOG_LEVEL", "info")
