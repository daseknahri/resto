#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Backup PostgreSQL from a Coolify-managed container.

Usage:
  backup_postgres.sh --resource-uuid <uuid> [options]
  backup_postgres.sh --container <postgres-container-name> [options]

Options:
  --resource-uuid <uuid>   Coolify resource UUID (used to auto-detect postgres container)
  --container <name>       Explicit postgres container name
  --db-name <name>         Database name (default: POSTGRES_DB env or kepoli_platform)
  --db-user <name>         Database user for pg_dump (default: POSTGRES_USER env or kepoli_user)
  --output-dir <path>      Backup output directory (default: /var/backups/kepoli)
  --retention-days <days>  Remove older backups (default: 14)
  --no-prune               Skip old-backup cleanup
  --dry-run                Print actions only
  -h, --help               Show help
EOF
}

RESOURCE_UUID=""
POSTGRES_CONTAINER=""
DB_NAME="${POSTGRES_DB:-kepoli_platform}"
DB_USER="${POSTGRES_USER:-kepoli_user}"
OUTPUT_DIR="/var/backups/kepoli"
RETENTION_DAYS=14
PRUNE=1
DRY_RUN=0

while [[ $# -gt 0 ]]; do
  case "$1" in
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
    --output-dir)
      OUTPUT_DIR="${2:-}"
      shift 2
      ;;
    --retention-days)
      RETENTION_DAYS="${2:-}"
      shift 2
      ;;
    --no-prune)
      PRUNE=0
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

mkdir -p "$OUTPUT_DIR"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP_FILE="${OUTPUT_DIR}/${DB_NAME}_${TIMESTAMP}.dump"
CHECKSUM_FILE="${BACKUP_FILE}.sha256"

echo "Postgres container: $POSTGRES_CONTAINER"
echo "Database: $DB_NAME"
echo "Output: $BACKUP_FILE"

if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "[dry-run] docker exec \"$POSTGRES_CONTAINER\" pg_dump ..."
  exit 0
fi

docker exec "$POSTGRES_CONTAINER" sh -lc "pg_dump -U \"$DB_USER\" -d \"$DB_NAME\" --format=custom --no-owner --no-privileges" > "$BACKUP_FILE"

if command -v sha256sum >/dev/null 2>&1; then
  sha256sum "$BACKUP_FILE" > "$CHECKSUM_FILE"
elif command -v shasum >/dev/null 2>&1; then
  shasum -a 256 "$BACKUP_FILE" > "$CHECKSUM_FILE"
else
  echo "No sha256 tool found; checksum skipped."
fi

if [[ "$PRUNE" -eq 1 ]]; then
  find "$OUTPUT_DIR" -type f -name "${DB_NAME}_*.dump" -mtime +"$RETENTION_DAYS" -delete || true
  find "$OUTPUT_DIR" -type f -name "${DB_NAME}_*.dump.sha256" -mtime +"$RETENTION_DAYS" -delete || true
fi

echo "Backup completed."
echo "Restore command example:"
echo "  ./infra/coolify/restore_postgres.sh --container \"$POSTGRES_CONTAINER\" --backup-file \"$BACKUP_FILE\" --db-name \"$DB_NAME\" --db-user \"$DB_USER\" --admin-user postgres"
