#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Create a restorable full-stack backup for the Coolify production app.

Usage:
  backup_full_stack.sh --resource-uuid <uuid> [options]

Options:
  --resource-uuid <uuid>   Required: Coolify resource UUID
  --repo-dir <path>        Repo root path (default: /opt/resto)
  --db-name <name>         Database name (default: kepoli_platform)
  --db-user <name>         Database user (default: kepoli_user)
  --base-domain <domain>   Tenant namespace base domain (default: menu.kepoli.com)
  --output-root <path>     Root backup directory (default: /var/backups/kepoli)
  --tag-prefix <prefix>    Git tag prefix (default: backup)
  --skip-git-tag           Do not create/push a git tag
  --skip-media             Do not archive media volume
  --skip-env               Do not export api env
  --skip-wildcard          Do not backup wildcard proxy/certs
  --retention-days <days>  Passed through to postgres backup script (default: 30)
  --dry-run                Print planned actions only
  -h, --help               Show help
EOF
}

RESOURCE_UUID=""
REPO_DIR="/opt/resto"
DB_NAME="${POSTGRES_DB:-kepoli_platform}"
DB_USER="${POSTGRES_USER:-kepoli_user}"
BASE_DOMAIN="menu.kepoli.com"
OUTPUT_ROOT="/var/backups/kepoli"
TAG_PREFIX="backup"
SKIP_GIT_TAG=0
SKIP_MEDIA=0
SKIP_ENV=0
SKIP_WILDCARD=0
RETENTION_DAYS=30
DRY_RUN=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --resource-uuid)
      RESOURCE_UUID="${2:-}"
      shift 2
      ;;
    --repo-dir)
      REPO_DIR="${2:-}"
      shift 2
      ;;
    --db-name)
      DB_NAME="${2:-}"
      shift 2
      ;;
    --db-user)
      DB_USER="${2:-}"
      shift 2
      ;;
    --base-domain)
      BASE_DOMAIN="${2:-}"
      shift 2
      ;;
    --output-root)
      OUTPUT_ROOT="${2:-}"
      shift 2
      ;;
    --tag-prefix)
      TAG_PREFIX="${2:-}"
      shift 2
      ;;
    --skip-git-tag)
      SKIP_GIT_TAG=1
      shift
      ;;
    --skip-media)
      SKIP_MEDIA=1
      shift
      ;;
    --skip-env)
      SKIP_ENV=1
      shift
      ;;
    --skip-wildcard)
      SKIP_WILDCARD=1
      shift
      ;;
    --retention-days)
      RETENTION_DAYS="${2:-}"
      shift 2
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ -z "$RESOURCE_UUID" ]]; then
  echo "--resource-uuid is required." >&2
  exit 1
fi

if [[ ! -d "$REPO_DIR" ]]; then
  echo "Repo directory not found: $REPO_DIR" >&2
  exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "docker command not found." >&2
  exit 1
fi

if ! command -v git >/dev/null 2>&1; then
  echo "git command not found." >&2
  exit 1
fi

TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP_DIR="${OUTPUT_ROOT%/}/${TIMESTAMP}"
TAG_NAME="${TAG_PREFIX}-${TIMESTAMP}"

API_CONTAINER="$(docker ps --format '{{.Names}}' | grep -E "^api-${RESOURCE_UUID}-" | head -n1 || true)"
if [[ -z "$API_CONTAINER" && "$SKIP_ENV" -eq 0 ]]; then
  echo "No running api container found for resource UUID: $RESOURCE_UUID" >&2
  exit 1
fi

MEDIA_VOLUME=""
if [[ "$SKIP_MEDIA" -eq 0 ]]; then
  MEDIA_VOLUME="$(docker volume ls --format '{{.Name}}' | grep -E "${RESOURCE_UUID}.*media" | head -n1 || true)"
  if [[ -z "$MEDIA_VOLUME" ]]; then
    echo "No media volume found for resource UUID: $RESOURCE_UUID" >&2
    exit 1
  fi
fi

mkdir -p "$BACKUP_DIR"

if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "repo_dir=$REPO_DIR"
  echo "backup_dir=$BACKUP_DIR"
  echo "resource_uuid=$RESOURCE_UUID"
  echo "api_container=$API_CONTAINER"
  echo "media_volume=${MEDIA_VOLUME:-skipped}"
  echo "base_domain=$BASE_DOMAIN"
  echo "git_tag=${TAG_NAME}"
  exit 0
fi

cd "$REPO_DIR"

git fetch origin --tags >/dev/null 2>&1 || true
git rev-parse HEAD > "$BACKUP_DIR/git-commit.txt"
git status --short > "$BACKUP_DIR/git-status.txt" || true
git remote -v > "$BACKUP_DIR/git-remote.txt" || true

if [[ "$SKIP_GIT_TAG" -eq 0 ]]; then
  if git rev-parse "$TAG_NAME" >/dev/null 2>&1; then
    echo "Git tag already exists locally: $TAG_NAME" >&2
    exit 1
  fi
  git tag "$TAG_NAME"
  git push origin "$TAG_NAME"
fi

bash "$REPO_DIR/infra/coolify/backup_postgres.sh" \
  --resource-uuid "$RESOURCE_UUID" \
  --db-name "$DB_NAME" \
  --db-user "$DB_USER" \
  --output-dir "$BACKUP_DIR" \
  --retention-days "$RETENTION_DAYS"

if [[ "$SKIP_ENV" -eq 0 ]]; then
  docker inspect "$API_CONTAINER" --format '{{range .Config.Env}}{{println .}}{{end}}' | sort > "$BACKUP_DIR/api.env"
  chmod 600 "$BACKUP_DIR/api.env"
fi

if [[ "$SKIP_MEDIA" -eq 0 ]]; then
  docker run --rm -v "${MEDIA_VOLUME}:/source:ro" -v "${BACKUP_DIR}:/backup" alpine \
    sh -lc "cd /source && tar -czf /backup/media_${TIMESTAMP}.tar.gz ."
fi

if [[ "$SKIP_WILDCARD" -eq 0 ]]; then
  if [[ -f /data/coolify/proxy/dynamic/kepoli-tenant-wildcard.yml ]]; then
    cp /data/coolify/proxy/dynamic/kepoli-tenant-wildcard.yml "$BACKUP_DIR/kepoli-tenant-wildcard.live.yml"
  fi
  if [[ -d "/data/coolify/proxy/certs/${BASE_DOMAIN}" ]]; then
    tar -czf "$BACKUP_DIR/${BASE_DOMAIN//./-}-certs_${TIMESTAMP}.tar.gz" -C /data/coolify/proxy/certs "$BASE_DOMAIN"
  fi
fi

cat > "$BACKUP_DIR/manifest.txt" <<EOF
timestamp=${TIMESTAMP}
resource_uuid=${RESOURCE_UUID}
repo_dir=${REPO_DIR}
git_tag=${TAG_NAME}
git_commit=$(cat "$BACKUP_DIR/git-commit.txt")
db_name=${DB_NAME}
db_user=${DB_USER}
api_container=${API_CONTAINER}
media_volume=${MEDIA_VOLUME:-}
base_domain=${BASE_DOMAIN}
EOF

echo "Full-stack backup completed."
echo "Backup directory: $BACKUP_DIR"
echo "Git tag: $TAG_NAME"
