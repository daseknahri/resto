# Deploy To Coolify

This is the exact deployment path for this repository if you want to submit the GitHub link in Coolify and let Coolify build from source.

## Recommended deployment mode

Use a **Docker Compose** application in Coolify.

Do not choose a static site, Dockerfile-only app, or prebuilt image app for this repository.

## What Coolify should point to

- Repository: your GitHub repository URL
- Branch: `main`
- Build pack / App type: `Docker Compose`
- Base directory: `platform`
- Compose file: `docker-compose.yml`

## Domains you should prepare first

Create DNS records that point to your Coolify VPS:

- `platform.example.com` -> frontend
- `api.example.com` -> api
- `admin.example.com` -> admin

Replace these with your real domains.

## Environment variables to define in Coolify

Set these in the Coolify environment section for the application:

```env
APP_ENV=production
TRUST_PROXY=true
LOG_LEVEL=info

FRONTEND_PORT=3000
API_PORT=4000
ADMIN_PORT=4100

FRONTEND_DOMAIN=platform.example.com
API_DOMAIN=api.example.com
ADMIN_DOMAIN=admin.example.com
TRAEFIK_ENTRYPOINTS=websecure

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

## Exact Coolify setup flow

1. Push this repository to GitHub.
2. In Coolify, create a new resource.
3. Choose `Application`.
4. Choose `Public Repository` or `Private Repository`, depending on your GitHub setup.
5. Select `Docker Compose`.
6. Set the repository and branch.
7. Set the base directory to `platform`.
8. Confirm Coolify is using `platform/docker-compose.yml`.
9. Add the environment variables listed above.
10. Add the three domains in Coolify:
    - frontend domain -> `FRONTEND_DOMAIN`
    - api domain -> `API_DOMAIN`
    - admin domain -> `ADMIN_DOMAIN`
11. Deploy.

## GitHub Actions redeploy hook

This repository already includes [deploy.yml](/c:/Users/user/resto/.github/workflows/deploy.yml).

To make redeploy on `push` work:

1. Open the app in Coolify.
2. Copy the deploy webhook URL for that application.
3. In GitHub repository secrets, add:
   - `COOLIFY_DEPLOY_WEBHOOK`
4. Ensure GitHub Packages permissions are enabled if you want the GHCR image push part of the workflow to succeed.

## Important note about the workflow

The GitHub Actions workflow pushes images to `ghcr.io`, but the recommended Coolify mode for this repository is still **Git source + Docker Compose**.

That means:

- Coolify builds directly from the repository source
- GitHub Actions provides validation, image publishing, and a redeploy trigger
- You do not need to manually reference the GHCR images in Coolify for the basic deployment flow

## After deployment

Verify these URLs:

- `https://platform.example.com/health`
- `https://api.example.com/health`
- `https://admin.example.com/health`

Then verify the app root URLs:

- `https://platform.example.com/`
- `https://api.example.com/`
- `https://admin.example.com/`
