# Platform Monorepo

Production-ready Docker monorepo scaffold for a SaaS platform designed to run on Coolify as a Docker Compose application.

## Structure

```text
platform/
  apps/
    frontend/
    api/
    admin/
  services/
    postgres/
    redis/
  docker-compose.yml
  docker-compose.local.yml
  .env.example
  README.md
```

## Services

- `frontend`: customer-facing web app listening on container port `3000`
- `api`: backend API listening on container port `4000`
- `admin`: admin dashboard listening on container port `4100`
- `postgres`: PostgreSQL 16 with persisted data
- `redis`: Redis 7 with persisted data

## Production characteristics

- Multi-stage Node 20 Alpine builds for `frontend`, `api`, and `admin`
- Small runtime images with only production dependencies
- Health checks for every HTTP service plus PostgreSQL and Redis
- Restart policies enabled with `unless-stopped`
- Named persistent volumes for PostgreSQL and Redis
- Internal service networking through Compose service discovery
- Coolify-friendly deployment without hardcoded host port bindings
- `TRUST_PROXY` support for reverse-proxy deployments

## Coolify deployment mode

Use `platform/docker-compose.yml` in Coolify.

This file is production-first:

- no host `ports` bindings
- no hardcoded Docker network names
- no custom Traefik labels in the repository

Coolify should manage the public proxy and service routing.

## Local Docker run

Use the local override when you want direct access on your machine:

```bash
cd platform
docker compose -f docker-compose.yml -f docker-compose.local.yml up --build -d
```

That publishes:

- `frontend` on `http://localhost:3000`
- `api` on `http://localhost:4000`
- `admin` on `http://localhost:4100`

Stop the stack:

```bash
docker compose -f docker-compose.yml -f docker-compose.local.yml down
```

Stop and remove volumes:

```bash
docker compose -f docker-compose.yml -f docker-compose.local.yml down -v
```

## Environment variables

Example values are included in `./.env.example`.

Important variables:

- `APP_ENV`
- `TRUST_PROXY`
- `LOG_LEVEL`
- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `DATABASE_URL`
- `REDIS_URL`

## Health endpoints

- Frontend: `GET /health`
- API: `GET /health`
- Admin: `GET /health`

## Deployment guide

Use [DEPLOY_COOLIFY.md](/c:/Users/user/resto/platform/DEPLOY_COOLIFY.md) for the exact Coolify flow.
