FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt ./
# Install the build toolchain, compile deps, then PURGE the toolchain in the SAME
# layer so ~200 MB of build-essential never persists in the runtime image. libpq-dev
# is kept (explicit, small) so psycopg2 retains its runtime libpq.
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev \
    && pip install --upgrade pip \
    && pip install -r requirements.txt \
    && apt-get purge -y --auto-remove build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY . .

RUN chmod +x docker/entrypoint.sh \
    && mkdir -p /app/media /app/staticfiles

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=5 \
  CMD python -c "import sys, urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health/').getcode() == 200 else 1)"

CMD ["./docker/entrypoint.sh"]
