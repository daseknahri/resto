#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Restore PostgreSQL backup into a Coolify-managed container.

Usage:
  restore_postgres.sh --backup-file <path> --resource-uuid <uuid> [options]
  restore_postgres.sh --backup-file <path> --container <postgres-container-name> [options]

Options:
  --backup-file <path>     Required: .dump file created by backup_postgres.sh
  --resource-uuid <uuid>   Coolify resource UUID (used to auto-detect postgres container)
  --container <name>       Explicit postgres container name
  --db-name <name>         Target database name (default: POSTGRES_DB env or kepoli_platform)
  --db-user <name>         Target database owner/user (default: POSTGRES_USER env or kepoli_user)
  --admin-user <name>      Admin DB user for drop/create (default: POSTGRES_USER env or db user)
  --no-drop-recreate       Restore into existing DB without dropping/recreating
  --force                  Skip safety confirmation
  --dry-run                Print actions only
  -h, --help               Show help
EOF
}

BACKUP_FILE=""
RESOURCE_UUID=""
POSTGRES_CONTAINER=""
DB_NAME="${POSTGRES_DB:-kepoli_platform}"
DB_USER="${POSTGRES_USER:-kepoli_user}"
ADMIN_USER="${POSTGRES_USER:-}"
DROP_RECREATE=1
FORCE=0
DRY_RUN=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --backup-file)
      BACKUP_FILE="${2:-}"
      shift 2
      ;;
    --resource-uuid)
      RESOURCE_UUID="${2:-}"
      shift 2
      ;;
    --container)
      POSTGRES_CONTAINER="${2:-}"
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
    --admin-user)
      ADMIN_USER="${2:-}"
      shift 2
      ;;
    --no-drop-recreate)
      DROP_RECREATE=0
      shift
      ;;
    --force)
      FORCE=1
      shift
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
      usage
      exit 2
      ;;
  esac
done

if [[ -z "$ADMIN_USER" ]]; then
  ADMIN_USER="$DB_USER"
fi

if [[ -z "$BACKUP_FILE" ]]; then
  echo "--backup-file is required." >&2
  usage
  exit 2
fi
if [[ ! -f "$BACKUP_FILE" ]]; then
  echo "Backup file not found: $BACKUP_FILE" >&2
  exit 1
fi
if [[ ! "$DB_NAME" =~ ^[A-Za-z0-9_]+$ ]]; then
  echo "Unsafe --db-name. Use letters/numbers/underscore only." >&2
  exit 2
fi
if [[ ! "$DB_USER" =~ ^[A-Za-z0-9_]+$ ]]; then
  echo "Unsafe --db-user. Use letters/numbers/underscore only." >&2
  exit 2
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "docker command not found." >&2
  exit 1
fi

detect_container() {
  if [[ -n "$POSTGRES_CONTAINER" ]]; then
    echo "$POSTGRES_CONTAINER"
    return 0
  fi

  local matches
  if [[ -n "$RESOURCE_UUID" ]]; then
    matches="$(docker ps --format '{{.Names}}' | grep -E "^postgres-${RESOURCE_UUID}-" || true)"
  else
    matches="$(docker ps --format '{{.Names}}' | grep -E "^postgres-" || true)"
  fi

  local count
  count="$(echo "$matches" | awk 'NF>0{c++} END{print c+0}')"
  if [[ "$count" -eq 0 ]]; then
    echo "No running postgres container found. Pass --container explicitly." >&2
    exit 1
  fi
  if [[ "$count" -gt 1 ]]; then
    echo "Multiple postgres containers found. Pass --container explicitly." >&2
    echo "$matches" >&2
    exit 1
  fi
  echo "$matches"
}

POSTGRES_CONTAINER="$(detect_container)"
CHECKSUM_FILE="${BACKUP_FILE}.sha256"
if [[ -f "$CHECKSUM_FILE" ]] && command -v sha256sum >/dev/null 2>&1; then
  echo "Verifying checksum..."
  sha256sum -c "$CHECKSUM_FILE"
fi

echo "Postgres container: $POSTGRES_CONTAINER"
echo "Restore file: $BACKUP_FILE"
echo "Target DB: $DB_NAME (owner: $DB_USER)"

if [[ "$FORCE" -ne 1 ]]; then
  read -r -p "This will overwrite database \"$DB_NAME\". Continue? [y/N] " answer
  if [[ "${answer:-}" != "y" && "${answer:-}" != "Y" ]]; then
    echo "Restore cancelled."
    exit 0
  fi
fi

if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "[dry-run] restore commands not executed."
  exit 0
fi

if [[ "$DROP_RECREATE" -eq 1 ]]; then
  docker exec "$POSTGRES_CONTAINER" sh -lc \
    "psql -v ON_ERROR_STOP=1 -U \"$ADMIN_USER\" -d postgres \
      -c \"SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='${DB_NAME}' AND pid <> pg_backend_pid();\" \
      -c \"DROP DATABASE IF EXISTS \\\"${DB_NAME}\\\";\" \
      -c \"CREATE DATABASE \\\"${DB_NAME}\\\" OWNER \\\"${DB_USER}\\\";\""
fi

docker exec -i "$POSTGRES_CONTAINER" sh -lc \
  "pg_restore -v -U \"$DB_USER\" -d \"$DB_NAME\" --no-owner --no-privileges --exit-on-error" < "$BACKUP_FILE"

echo "Restore completed successfully."
