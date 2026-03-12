#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Trigger login throttling and verify security throttle logs in a Coolify API container.

Usage:
  verify_throttle_alerts.sh --login-url <url-or-host> [options]
  verify_throttle_alerts.sh --resource-uuid <uuid> --login-url <url-or-host> [options]
  verify_throttle_alerts.sh --container <api-container-name> --login-url <url-or-host> [options]

Options:
  --login-url <url-or-host>      API login endpoint or host (examples:
                                 menu.kepoli.com, https://menu.kepoli.com, https://admin.menu.kepoli.com/api/login/)
  --resource-uuid <uuid>         Coolify resource UUID (auto-detect api container)
  --container <name>             Explicit api container name
  --attempts <n>                 Number of bad login attempts (default: 10)
  --expect-status <code>         Status code expected after throttle (default: 429)
  --identifier <value>           Login identifier to use (default: throttle-test@invalid.local)
  --password <value>             Login password to use (default: not-the-right-password)
  --log-grep <pattern>           Pattern to detect throttle logs (default: throttle.blocked)
  --skip-log-check               Only verify HTTP throttle status, skip docker log verification
  --dry-run                      Print commands without executing
  -h, --help                     Show help

Examples:
  bash infra/coolify/verify_throttle_alerts.sh --resource-uuid <RESOURCE_UUID> --login-url menu.kepoli.com
  bash infra/coolify/verify_throttle_alerts.sh --container api-xxxx --login-url https://admin.menu.kepoli.com/api/login/
EOF
}

RESOURCE_UUID=""
API_CONTAINER=""
LOGIN_URL=""
ATTEMPTS=10
EXPECT_STATUS=429
IDENTIFIER="throttle-test@invalid.local"
PASSWORD="not-the-right-password"
LOG_GREP="throttle.blocked"
SKIP_LOG_CHECK=0
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
    --login-url)
      LOGIN_URL="${2:-}"
      shift 2
      ;;
    --attempts)
      ATTEMPTS="${2:-10}"
      shift 2
      ;;
    --expect-status)
      EXPECT_STATUS="${2:-429}"
      shift 2
      ;;
    --identifier)
      IDENTIFIER="${2:-}"
      shift 2
      ;;
    --password)
      PASSWORD="${2:-}"
      shift 2
      ;;
    --log-grep)
      LOG_GREP="${2:-throttle.blocked}"
      shift 2
      ;;
    --skip-log-check)
      SKIP_LOG_CHECK=1
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

if [[ -z "$LOGIN_URL" ]]; then
  echo "--login-url is required." >&2
  exit 2
fi
if ! [[ "$ATTEMPTS" =~ ^[0-9]+$ ]] || [[ "$ATTEMPTS" -lt 1 ]]; then
  echo "--attempts must be a positive integer." >&2
  exit 2
fi
if ! [[ "$EXPECT_STATUS" =~ ^[0-9]{3}$ ]]; then
  echo "--expect-status must be an HTTP status code (3 digits)." >&2
  exit 2
fi
if [[ -z "$IDENTIFIER" ]]; then
  echo "--identifier cannot be empty." >&2
  exit 2
fi
if [[ -z "$PASSWORD" ]]; then
  echo "--password cannot be empty." >&2
  exit 2
fi
if ! command -v curl >/dev/null 2>&1; then
  echo "curl command not found." >&2
  exit 1
fi
if ! command -v docker >/dev/null 2>&1; then
  echo "docker command not found." >&2
  exit 1
fi

normalize_login_url() {
  local raw="$1"
  if [[ "$raw" != http://* && "$raw" != https://* ]]; then
    raw="https://$raw"
  fi
  raw="${raw%/}"
  if [[ "$raw" == */api/login ]]; then
    echo "${raw}/"
    return 0
  fi
  if [[ "$raw" == */api ]]; then
    echo "${raw}/login/"
    return 0
  fi
  echo "${raw}/api/login/"
}

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

LOGIN_URL="$(normalize_login_url "$LOGIN_URL")"
API_CONTAINER="$(detect_container)"

echo "API container: $API_CONTAINER"
echo "Login URL: $LOGIN_URL"
echo "Attempts: $ATTEMPTS (expect status $EXPECT_STATUS)"
echo "Identifier: $IDENTIFIER"

if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "[dry-run] Would execute $ATTEMPTS invalid login attempts to $LOGIN_URL"
  if [[ "$SKIP_LOG_CHECK" -eq 0 ]]; then
    echo "[dry-run] Would inspect container logs for pattern: $LOG_GREP"
  fi
  exit 0
fi

start_ts="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
matched_expected=0
status_trace=()

for i in $(seq 1 "$ATTEMPTS"); do
  status_code="$(
    curl -sS -o /dev/null -w "%{http_code}" \
      -X POST "$LOGIN_URL" \
      -H "Content-Type: application/json" \
      --data "{\"identifier\":\"${IDENTIFIER}\",\"password\":\"${PASSWORD}\"}"
  )"
  status_trace+=("$status_code")
  if [[ "$status_code" == "$EXPECT_STATUS" ]]; then
    matched_expected=1
  fi
done

echo "HTTP statuses: ${status_trace[*]}"
if [[ "$matched_expected" -ne 1 ]]; then
  echo "Did not observe expected status $EXPECT_STATUS after $ATTEMPTS attempts." >&2
  echo "Tip: increase --attempts or verify throttle rates in DRF settings." >&2
  exit 1
fi

if [[ "$SKIP_LOG_CHECK" -eq 1 ]]; then
  echo "Throttle status confirmed ($EXPECT_STATUS). Log verification skipped."
  exit 0
fi

log_hits="$(docker logs --since "$start_ts" "$API_CONTAINER" 2>&1 | grep -E "$LOG_GREP" || true)"
if [[ -z "$log_hits" ]]; then
  echo "No throttle log entries detected in container logs since $start_ts using pattern '$LOG_GREP'." >&2
  echo "Expected logger: security.throttle with message containing throttle.blocked." >&2
  exit 1
fi

echo "Throttle log entries detected:"
echo "$log_hits" | sed -n '1,5p'

sentry_capture="$(docker exec "$API_CONTAINER" sh -lc 'printf "%s" "${DJANGO_SENTRY_CAPTURE_THROTTLE:-}"')"
sentry_wait="$(docker exec "$API_CONTAINER" sh -lc 'printf "%s" "${DJANGO_SENTRY_THROTTLE_MIN_WAIT_SECONDS:-}"')"
if [[ -z "$sentry_capture" ]]; then
  sentry_capture="(unset)"
fi
if [[ -z "$sentry_wait" ]]; then
  sentry_wait="(unset)"
fi
echo "Sentry throttle capture env: DJANGO_SENTRY_CAPTURE_THROTTLE=$sentry_capture, DJANGO_SENTRY_THROTTLE_MIN_WAIT_SECONDS=$sentry_wait"

echo "Throttle alert verification completed successfully."
