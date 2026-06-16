#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Backup freshness probe with optional webhook alerts.

Alerts if the newest Postgres backup dump is missing or older than a staleness
threshold (default 26h). This catches the case where the backup cron silently
stopped running -- the on-failure alert in the backup runner cannot fire if cron
never runs at all, so this independent probe is the safety net.

Usage:
  backup_freshness_probe.sh [options]

Examples:
  backup_freshness_probe.sh \
    --output-dir /var/backups/ibnbatoutaweb \
    --db-name ibnbatoutaweb_platform \
    --webhook-url "https://hooks.example.com/..."

Options:
  --output-dir <path>         Backup directory to scan (default: /var/backups/kepoli)
  --db-name <name>            Database name prefix of dump files (default: POSTGRES_DB env or kepoli_platform)
  --max-age-hours <n>         Staleness threshold in hours (default: 26)
  --webhook-url <url>         Webhook URL for alert payload (Slack/Discord/custom)
  --alert-format <name>       Alert payload format: generic|slack|discord (default: generic)
  --cooldown-minutes <n>      Minimum minutes between repeated stale alerts (default: 360)
  --state-file <path>         State file path (default: /var/tmp/kepoli-backup-freshness.state)
  --dry-run                   Print result, do not send webhook
  -h, --help                  Show help

Environment:
  UPTIME_ALERT_WEBHOOK        Default webhook URL (same var used by uptime_probe.sh)
  UPTIME_ALERT_FORMAT         Default alert format (same var used by uptime_probe.sh)

Exit status:
  0  newest dump is fresh
  1  newest dump is stale or missing (so cron logs / cron-level alerting also see it)
EOF
}

OUTPUT_DIR="/var/backups/kepoli"
DB_NAME="${POSTGRES_DB:-kepoli_platform}"
MAX_AGE_HOURS=26
ALERT_WEBHOOK="${UPTIME_ALERT_WEBHOOK:-}"
ALERT_FORMAT="${UPTIME_ALERT_FORMAT:-generic}"
COOLDOWN_MINUTES=360
STATE_FILE="/var/tmp/kepoli-backup-freshness.state"
DRY_RUN=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --output-dir)
      OUTPUT_DIR="${2:-}"
      shift 2
      ;;
    --db-name)
      DB_NAME="${2:-}"
      shift 2
      ;;
    --max-age-hours)
      MAX_AGE_HOURS="${2:-26}"
      shift 2
      ;;
    --webhook-url)
      ALERT_WEBHOOK="${2:-}"
      shift 2
      ;;
    --alert-format)
      ALERT_FORMAT="${2:-generic}"
      shift 2
      ;;
    --cooldown-minutes)
      COOLDOWN_MINUTES="${2:-360}"
      shift 2
      ;;
    --state-file)
      STATE_FILE="${2:-/var/tmp/kepoli-backup-freshness.state}"
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

if [[ -z "$OUTPUT_DIR" ]]; then
  echo "--output-dir must not be empty." >&2
  exit 2
fi
if [[ -z "$DB_NAME" ]]; then
  echo "--db-name must not be empty." >&2
  exit 2
fi
if ! [[ "$MAX_AGE_HOURS" =~ ^[0-9]+$ ]]; then
  echo "Invalid --max-age-hours: $MAX_AGE_HOURS (expected a positive integer)" >&2
  exit 2
fi

case "${ALERT_FORMAT,,}" in
  generic|slack|discord)
    ALERT_FORMAT="${ALERT_FORMAT,,}"
    ;;
  *)
    echo "Invalid --alert-format: $ALERT_FORMAT (expected: generic|slack|discord)" >&2
    exit 2
    ;;
esac

json_escape() {
  local raw="$1"
  raw="${raw//\\/\\\\}"
  raw="${raw//\"/\\\"}"
  raw="${raw//$'\n'/\\n}"
  raw="${raw//$'\r'/}"
  printf "%s" "$raw"
}

build_alert_payload() {
  local kind="$1"
  local ts="$2"
  local details="$3"
  local title
  if [[ "$kind" == "stale" ]]; then
    title="[KEPOLI][STALE] DB backup freshness probe failed"
  else
    title="[KEPOLI][RECOVERED] DB backup is fresh again"
  fi

  case "$ALERT_FORMAT" in
    slack)
      printf '{"text":"%s\nTime: %s\nDetails: %s"}' \
        "$(json_escape "$title")" \
        "$(json_escape "$ts")" \
        "$(json_escape "$details")"
      ;;
    discord)
      printf '{"content":"%s\nTime: %s\nDetails: %s"}' \
        "$(json_escape "$title")" \
        "$(json_escape "$ts")" \
        "$(json_escape "$details")"
      ;;
    *)
      printf '{"event":"backup_freshness_%s","timestamp":"%s","message":"%s"}' \
        "$kind" \
        "$ts" \
        "$(json_escape "$details")"
      ;;
  esac
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
MAX_AGE_SECONDS=$((MAX_AGE_HOURS * 3600))

# Find the newest <db>_*.dump file in OUTPUT_DIR. Resolve its mtime epoch.
NEWEST_DUMP=""
NEWEST_EPOCH=0
if [[ -d "$OUTPUT_DIR" ]]; then
  while IFS= read -r -d '' line; do
    epoch="${line%% *}"
    path="${line#* }"
    # Strip a leading dot from GNU find's "%T@" which can carry a fractional part.
    epoch="${epoch%%.*}"
    if [[ "$epoch" =~ ^[0-9]+$ ]] && [[ "$epoch" -gt "$NEWEST_EPOCH" ]]; then
      NEWEST_EPOCH="$epoch"
      NEWEST_DUMP="$path"
    fi
  done < <(find "$OUTPUT_DIR" -maxdepth 1 -type f -name "${DB_NAME}_*.dump" -printf '%T@ %p\0' 2>/dev/null || true)
fi

HAS_FAILURE=0
AGE_HOURS="unknown"
if [[ -z "$NEWEST_DUMP" ]]; then
  HAS_FAILURE=1
  DETAILS="no ${DB_NAME}_*.dump found in ${OUTPUT_DIR} (threshold ${MAX_AGE_HOURS}h)"
else
  AGE_SECONDS=$((NOW_EPOCH - NEWEST_EPOCH))
  if [[ "$AGE_SECONDS" -lt 0 ]]; then
    AGE_SECONDS=0
  fi
  AGE_HOURS=$((AGE_SECONDS / 3600))
  if [[ "$AGE_SECONDS" -gt "$MAX_AGE_SECONDS" ]]; then
    HAS_FAILURE=1
    DETAILS="Kepoli DB backup STALE: newest dump ${AGE_HOURS}h old (threshold ${MAX_AGE_HOURS}h); file=${NEWEST_DUMP}"
  else
    DETAILS="newest dump ${AGE_HOURS}h old (threshold ${MAX_AGE_HOURS}h); file=${NEWEST_DUMP}"
  fi
fi

SUMMARY="backup_freshness_ok"
ALERT_KIND=""
SHOULD_ALERT=0

if [[ "$HAS_FAILURE" -eq 1 ]]; then
  SUMMARY="backup_freshness_stale"
  ALERT_KIND="stale"
  if [[ "$STATE_STATUS" != "stale" ]]; then
    SHOULD_ALERT=1
  elif [[ $((NOW_EPOCH - STATE_LAST_ALERT_EPOCH)) -ge "$COOLDOWN_SECONDS" ]]; then
    SHOULD_ALERT=1
  fi
  {
    echo "status=stale"
    echo "last_alert_epoch=$([[ $SHOULD_ALERT -eq 1 ]] && echo "$NOW_EPOCH" || echo "$STATE_LAST_ALERT_EPOCH")"
  } > "$STATE_FILE"
else
  if [[ "$STATE_STATUS" == "stale" ]]; then
    ALERT_KIND="recovered"
    SHOULD_ALERT=1
  fi
  {
    echo "status=fresh"
    echo "last_alert_epoch=${STATE_LAST_ALERT_EPOCH}"
  } > "$STATE_FILE"
fi

timestamp="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
printf '{"timestamp":"%s","event":"%s","details":"%s"}\n' \
  "$timestamp" \
  "$SUMMARY" \
  "$(json_escape "$DETAILS")"

if [[ "$SHOULD_ALERT" -eq 1 && -n "$ALERT_WEBHOOK" ]]; then
  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "[dry-run] alert webhook would be sent ($ALERT_KIND, format=$ALERT_FORMAT)."
  else
    if [[ "$HAS_FAILURE" -eq 1 ]]; then
      details="$DETAILS"
    else
      details="backup is fresh again ($DETAILS)"
    fi
    body="$(build_alert_payload "$ALERT_KIND" "$timestamp" "$details")"
    if command -v curl >/dev/null 2>&1; then
      curl -sS -X POST -H "Content-Type: application/json" --data "$body" "$ALERT_WEBHOOK" >/dev/null || true
    else
      echo "curl not found; webhook alert skipped." >&2
    fi
  fi
fi

if [[ "$HAS_FAILURE" -eq 1 ]]; then
  exit 1
fi
