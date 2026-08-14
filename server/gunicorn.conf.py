import os


def env_int(name, default):
    return int(os.getenv(name, str(default)))


bind = os.getenv("GUNICORN_BIND", "0.0.0.0:5000")
worker_class = "gthread"
workers = env_int("GUNICORN_WORKERS", 4)
threads = env_int("GUNICORN_THREADS", 2)

timeout = env_int("GUNICORN_TIMEOUT", 300)
graceful_timeout = env_int("GUNICORN_GRACEFUL_TIMEOUT", 60)
keepalive = env_int("GUNICORN_KEEPALIVE", 5)

max_requests = env_int("GUNICORN_MAX_REQUESTS", 1000)
max_requests_jitter = env_int("GUNICORN_MAX_REQUESTS_JITTER", 100)

worker_tmp_dir = os.getenv("GUNICORN_WORKER_TMP_DIR", "/dev/shm")
accesslog = "-"
errorlog = "-"
capture_output = True
preload_app = False
