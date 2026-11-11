FROM python:3.14-slim@sha256:9aaa474097d094040649f2162a627c0049b408f52138d980916788d80f04802f

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt ./
# Install the build toolchain, compile deps, then PURGE the toolchain in the SAME
# layer so ~200 MB of build-essential never persists in the runtime image. libpq-dev
# is kept (explicit, small) so psycopg2 retains its runtime libpq.
RUN apt-get update \
    && apt-get upgrade -y \
    && apt-get install -y --no-install-recommends build-essential libpq-dev \
    && pip install --upgrade pip \
    && pip install -r requirements.txt \
    && apt-get purge -y --auto-remove build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY . .

# R13: non-root runtime user (fixed numeric UID 10001).
# collectstatic runs at runtime (entrypoint.sh) not build time, so both
# /app/media and /app/staticfiles must be owned by the same UID before exec.
# The working dir /app is also chowned so manage.py can write .pyc caches.
# Host-mounted volumes (media_data) must be pre-chowned to 10001:10001 on first
# deploy (see runbook: `docker run --rm -v media_data:/d alpine chown -R 10001:10001 /d`).
RUN chmod +x docker/entrypoint.sh \
    && mkdir -p /app/media /app/staticfiles \
    && groupadd -r -g 10001 appuser \
    && useradd -r -u 10001 -g appuser -s /sbin/nologin -M appuser \
    && chown -R appuser:appuser /app

USER 10001

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=5 \
  CMD python -c "import sys, urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health/').getcode() == 200 else 1)"

CMD ["./docker/entrypoint.sh"]
