# Platform Monorepo

Production-ready Docker monorepo scaffold for a SaaS platform designed to run as a Compose stack on Coolify with Traefik routing.

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
  .env
  README.md
```

## Services

- `frontend`: customer-facing web app on `http://localhost:3000`
- `api`: backend API on `http://localhost:4000`
- `admin`: internal admin dashboard service on internal port `4100`
- `postgres`: PostgreSQL 16 with persisted data
- `redis`: Redis 7 with persisted data

## Production characteristics

- Multi-stage Node 20 Alpine builds for `frontend`, `api`, and `admin`
- Small runtime images with only production dependencies
- Health checks for every HTTP service plus PostgreSQL and Redis
- Restart policies enabled with `unless-stopped`
- Named persistent volumes for PostgreSQL and Redis
- Traefik labels for `frontend` and `api`
- Coolify-friendly routing through environment-driven domains
- `TRUST_PROXY` support for reverse-proxy deployments

## Run locally

```bash
cd platform
docker compose up --build -d
```

Stop the stack:

```bash
docker compose down
```

Stop and remove volumes:

```bash
docker compose down -v
```

## Environment variables

Example values are included in `./.env`.

Important variables:

- `APP_ENV`
- `TRUST_PROXY`
- `LOG_LEVEL`
- `FRONTEND_PORT`
- `API_PORT`
- `ADMIN_PORT`
- `FRONTEND_DOMAIN`
- `API_DOMAIN`
- `ADMIN_DOMAIN`
- `TRAEFIK_ENTRYPOINTS`
- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `DATABASE_URL`
- `REDIS_URL`

## Coolify notes

- Deploy the `platform/` directory as a Docker Compose application.
- Expose `frontend` publicly on port `3000` and point `FRONTEND_DOMAIN` to it.
- Expose `api` publicly on port `4000` and point `API_DOMAIN` to it.
- Route `admin` through `ADMIN_DOMAIN` if you want the dashboard publicly reachable.
- Keep `admin`, `postgres`, and `redis` on internal Docker networking unless you explicitly need external access.
- Coolify can read the Traefik labels from [docker-compose.yml](/c:/Users/user/resto/platform/docker-compose.yml) for host-based routing.
- Set real domains, credentials, and secrets before deployment.
- Replace the default credentials in `./.env` before production use.
- Exact deployment steps are documented in [DEPLOY_COOLIFY.md](/c:/Users/user/resto/platform/DEPLOY_COOLIFY.md).

## Health endpoints

- Frontend: `GET /health`
- API: `GET /health`
- Admin: `GET /health`
