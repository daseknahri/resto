#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Uptime probe with optional webhook alerts.

Usage:
  uptime_probe.sh --check <url>|<expected_status> [--check ...] [options]

Examples:
  uptime_probe.sh \
    --check "https://kepoli.com/health|200" \
    --check "https://admin.kepoli.com/health|200" \
    --check "https://api.kepoli.com/api/health/|200"

Options:
  --check <spec>              Check spec format: URL or URL|EXPECTED_STATUS
  --timeout-seconds <n>       HTTP timeout per check (default: 8)
  --max-time-seconds <n>      Max transfer time per check (default: 12)
  --alert-webhook <url>       Webhook URL for alert payload (Slack/Discord/custom)
  --cooldown-minutes <n>      Minimum minutes between repeated down alerts (default: 20)
  --state-file <path>         State file path (default: /var/tmp/kepoli-uptime.state)
  --dry-run                   Print result, do not send webhook
  -h, --help                  Show help
EOF
}

CHECKS=()
TIMEOUT_SECONDS=8
MAX_TIME_SECONDS=12
ALERT_WEBHOOK="${UPTIME_ALERT_WEBHOOK:-}"
COOLDOWN_MINUTES=20
STATE_FILE="/var/tmp/kepoli-uptime.state"
DRY_RUN=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --check)
      CHECKS+=("${2:-}")
      shift 2
      ;;
    --timeout-seconds)
      TIMEOUT_SECONDS="${2:-8}"
      shift 2
      ;;
    --max-time-seconds)
      MAX_TIME_SECONDS="${2:-12}"
      shift 2
      ;;
    --alert-webhook)
      ALERT_WEBHOOK="${2:-}"
      shift 2
      ;;
    --cooldown-minutes)
      COOLDOWN_MINUTES="${2:-20}"
      shift 2
      ;;
    --state-file)
      STATE_FILE="${2:-/var/tmp/kepoli-uptime.state}"
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
      usage
      exit 2
      ;;
  esac
done

if [[ ${#CHECKS[@]} -eq 0 ]]; then
  echo "At least one --check is required." >&2
  usage
  exit 2
fi

if ! command -v curl >/dev/null 2>&1; then
  echo "curl command not found." >&2
  exit 1
fi

json_escape() {
  local raw="$1"
  raw="${raw//\\/\\\\}"
  raw="${raw//\"/\\\"}"
  raw="${raw//$'\n'/\\n}"
  raw="${raw//$'\r'/}"
  printf "%s" "$raw"
}

STATE_STATUS="unknown"
STATE_LAST_ALERT_EPOCH=0
if [[ -f "$STATE_FILE" ]]; then
  # shellcheck source=/dev/null
  source "$STATE_FILE" || true
  STATE_STATUS="${status:-unknown}"
  STATE_LAST_ALERT_EPOCH="${last_alert_epoch:-0}"
fi

NOW_EPOCH="$(date +%s)"
COOLDOWN_SECONDS=$((COOLDOWN_MINUTES * 60))
HAS_FAILURE=0
FAIL_LINES=()
PASS_LINES=()

for spec in "${CHECKS[@]}"; do
  url="$spec"
  expected="200"
  if [[ "$spec" == *"|"* ]]; then
    url="${spec%%|*}"
    expected="${spec##*|}"
  fi

  code="$(curl -sS -o /dev/null -w "%{http_code}" --connect-timeout "$TIMEOUT_SECONDS" --max-time "$MAX_TIME_SECONDS" "$url" || true)"
  if [[ "$code" != "$expected" ]]; then
    HAS_FAILURE=1
    FAIL_LINES+=("$url expected=$expected got=${code:-curl_error}")
  else
    PASS_LINES+=("$url ok=$code")
  fi
done

SUMMARY="uptime_probe_ok"
ALERT_KIND=""
SHOULD_ALERT=0

if [[ "$HAS_FAILURE" -eq 1 ]]; then
  SUMMARY="uptime_probe_failed"
  ALERT_KIND="down"
  if [[ "$STATE_STATUS" != "down" ]]; then
    SHOULD_ALERT=1
  elif [[ $((NOW_EPOCH - STATE_LAST_ALERT_EPOCH)) -ge "$COOLDOWN_SECONDS" ]]; then
    SHOULD_ALERT=1
  fi
  {
    echo "status=down"
    echo "last_alert_epoch=$([[ $SHOULD_ALERT -eq 1 ]] && echo "$NOW_EPOCH" || echo "$STATE_LAST_ALERT_EPOCH")"
  } > "$STATE_FILE"
else
  if [[ "$STATE_STATUS" == "down" ]]; then
    ALERT_KIND="recovered"
    SHOULD_ALERT=1
  fi
  {
    echo "status=up"
    echo "last_alert_epoch=${STATE_LAST_ALERT_EPOCH}"
  } > "$STATE_FILE"
fi

timestamp="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
if [[ "$HAS_FAILURE" -eq 1 ]]; then
  printf '{"timestamp":"%s","event":"%s","failures":"%s"}\n' \
    "$timestamp" \
    "$SUMMARY" \
    "$(json_escape "$(printf '%s; ' "${FAIL_LINES[@]}")")"
else
  printf '{"timestamp":"%s","event":"%s","checks":"%s"}\n' \
    "$timestamp" \
    "$SUMMARY" \
    "$(json_escape "$(printf '%s; ' "${PASS_LINES[@]}")")"
fi

if [[ "$SHOULD_ALERT" -eq 1 && -n "$ALERT_WEBHOOK" ]]; then
  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "[dry-run] alert webhook would be sent ($ALERT_KIND)."
  else
    if [[ "$HAS_FAILURE" -eq 1 ]]; then
      body="$(printf '{"event":"uptime_%s","timestamp":"%s","message":"%s"}' "$ALERT_KIND" "$timestamp" "$(json_escape "$(printf '%s; ' "${FAIL_LINES[@]}")")")"
    else
      body="$(printf '{"event":"uptime_%s","timestamp":"%s","message":"all checks recovered"}' "$ALERT_KIND" "$timestamp")"
    fi
    curl -sS -X POST -H "Content-Type: application/json" --data "$body" "$ALERT_WEBHOOK" >/dev/null || true
  fi
fi

if [[ "$HAS_FAILURE" -eq 1 ]]; then
  exit 1
fi
