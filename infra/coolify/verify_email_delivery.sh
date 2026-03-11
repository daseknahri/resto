#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Verify SMTP wiring and business email templates in a Coolify API container.

Usage:
  verify_email_delivery.sh --resource-uuid <uuid> --to <email> --base-url <host-or-url> [options]
  verify_email_delivery.sh --container <api-container-name> --to <email> --base-url <host-or-url> [options]

Options:
  --resource-uuid <uuid>       Coolify resource UUID (auto-detect api container)
  --container <name>           Explicit api container name
  --to <email>                 Destination email for test delivery
  --base-url <host-or-url>     Frontend host/url used to build owner links (ex: menu.kepoli.com)
  --skip-drill                 Only run config check command, skip email template drill
  --dry-run                    Print commands without executing
  -h, --help                   Show help
EOF
}

RESOURCE_UUID=""
API_CONTAINER=""
TO_EMAIL=""
BASE_URL=""
SKIP_DRILL=0
DRY_RUN=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --resource-uuid)
      RESOURCE_UUID="${2:-}"
      shift 2
      ;;
    --container)
      API_CONTAINER="${2:-}"
      shift 2
      ;;
    --to)
      TO_EMAIL="${2:-}"
      shift 2
      ;;
    --base-url)
      BASE_URL="${2:-}"
      shift 2
      ;;
    --skip-drill)
      SKIP_DRILL=1
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

if [[ -z "$TO_EMAIL" ]]; then
  echo "--to is required." >&2
  exit 2
fi
if [[ -z "$BASE_URL" ]]; then
  echo "--base-url is required." >&2
  exit 2
fi
if ! command -v docker >/dev/null 2>&1; then
  echo "docker command not found." >&2
  exit 1
fi

detect_container() {
  if [[ -n "$API_CONTAINER" ]]; then
    echo "$API_CONTAINER"
    return 0
  fi

  local matches
  if [[ -n "$RESOURCE_UUID" ]]; then
    matches="$(docker ps --format '{{.Names}}' | grep -E "^api-${RESOURCE_UUID}-" || true)"
  else
    matches="$(docker ps --format '{{.Names}}' | grep -E "^api-" || true)"
  fi

  local count
  count="$(echo "$matches" | awk 'NF>0{c++} END{print c+0}')"
  if [[ "$count" -eq 0 ]]; then
    echo "No running api container found. Pass --container explicitly." >&2
    exit 1
  fi
  if [[ "$count" -gt 1 ]]; then
    echo "Multiple api containers found. Pass --container explicitly." >&2
    echo "$matches" >&2
    exit 1
  fi
  echo "$matches"
}

API_CONTAINER="$(detect_container)"
echo "API container: $API_CONTAINER"
echo "Target email: $TO_EMAIL"
echo "Base URL: $BASE_URL"

CHECK_CMD="cd /app && python manage.py check_email_delivery --expect-smtp --expect-no-fail-silently --send-test --to '$TO_EMAIL'"
DRILL_CMD="cd /app && python manage.py email_delivery_drill --to '$TO_EMAIL' --base-url '$BASE_URL'"

if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "[dry-run] docker exec \"$API_CONTAINER\" sh -lc \"$CHECK_CMD\""
  if [[ "$SKIP_DRILL" -ne 1 ]]; then
    echo "[dry-run] docker exec \"$API_CONTAINER\" sh -lc \"$DRILL_CMD\""
  fi
  exit 0
fi

docker exec "$API_CONTAINER" sh -lc "$CHECK_CMD"
if [[ "$SKIP_DRILL" -ne 1 ]]; then
  docker exec "$API_CONTAINER" sh -lc "$DRILL_CMD"
fi

echo "Email verification completed successfully."
