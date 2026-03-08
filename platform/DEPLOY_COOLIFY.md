# Deploy To Coolify

This is the correct deployment path for this repository if you want to submit the GitHub repository URL in Coolify and let Coolify build from source.

## Recommended deployment mode

Use a **Docker Compose** application in Coolify.

Do not use:

- Static Site
- Dockerfile-only application
- Raw Compose Deployment

This repository is prepared for the standard Coolify Docker Compose flow.

## What Coolify should point to

- Repository: your GitHub repository URL
- Branch: `main`
- Build pack / App type: `Docker Compose`
- Base directory: `platform`
- Compose file: `docker-compose.yml`

## Why this Compose file is correct for Coolify

The repository Compose file is production-first:

- no hardcoded host `ports`
- no repository-managed Traefik labels
- no custom Docker network names

That is intentional. Coolify should manage:

- the public proxy
- the external domains
- the deployment network

## Domains you should prepare first

Create DNS records that point to your Coolify VPS:

- `platform.example.com`
- `api.example.com`
- `admin.example.com`

Replace those with your real domains.

## Environment variables to define in Coolify

Set these in the Coolify environment section for the application:

```env
APP_ENV=production
TRUST_PROXY=true
LOG_LEVEL=info

POSTGRES_DB=platform
POSTGRES_USER=platform_user
POSTGRES_PASSWORD=replace_with_strong_password
POSTGRES_HOST=postgres
POSTGRES_PORT=5432

REDIS_HOST=redis
REDIS_PORT=6379
REDIS_URL=redis://redis:6379

DATABASE_URL=postgresql://platform_user:replace_with_strong_password@postgres:5432/platform
```

The same example block is committed in [platform/.env.example](/c:/Users/user/resto/platform/.env.example). Do not rely on a repository `.env` file in Coolify; set these values in the Coolify UI.

## Exact Coolify setup flow

1. Push this repository to GitHub.
2. In Coolify, create a new `Application`.
3. Choose the repository.
4. Choose `Docker Compose`.
5. Set the base directory to `platform`.
6. Confirm the compose file is `docker-compose.yml`.
7. Add the environment variables listed above.
8. Deploy once.

## Domain binding inside Coolify

After the first deploy, bind domains to the correct service ports in Coolify:

1. Bind `platform.example.com:3000` to the `frontend` service.
2. Bind `api.example.com:4000` to the `api` service.
3. Bind `admin.example.com:4100` to the `admin` service.

Important: in Coolify, the `:3000`, `:4000`, and `:4100` suffixes tell the proxy which internal service port to target. External users will still access standard HTTPS URLs.

## GitHub Actions redeploy hook

This repository already includes [deploy.yml](/c:/Users/user/resto/.github/workflows/deploy.yml).

To make redeploy on `push` work:

1. Open the application in Coolify.
2. Copy the deploy webhook URL.
3. In GitHub repository secrets, add `COOLIFY_DEPLOY_WEBHOOK`.

## Optional local Docker run

For local machine access with published host ports, use:

```bash
cd platform
docker compose -f docker-compose.yml -f docker-compose.local.yml up --build -d
```

That local override is only for development or verification. Do not use it for Coolify deployment.

## Post-deploy checks

Verify:

- `https://platform.example.com/health`
- `https://api.example.com/health`
- `https://admin.example.com/health`

Then verify the app roots:

- `https://platform.example.com/`
- `https://api.example.com/`
- `https://admin.example.com/`
