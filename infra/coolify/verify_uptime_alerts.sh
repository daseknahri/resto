#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Run a safe down/recovered alert drill for uptime_probe.sh.

This script uses a temporary state file so it does not affect the live probe state.

Usage:
  verify_uptime_alerts.sh [options]

Options:
  --repo-dir <path>           Repo root path (default: /opt/resto)
  --webhook-url <url>         Webhook URL for real alert delivery
  --cooldown-minutes <n>      Cooldown passed to probe (default: 0 for drill)
  --state-file <path>         Temp state file path (default: /tmp/kepoli-uptime-drill.state)
  --check <url|code>          Healthy check spec (repeatable)
  --failure-check <url|code>  Failing check spec for the "down" probe
  --dry-run                   Do not call webhook (forces probe --dry-run)
  -h, --help                  Show help

Examples:
  verify_uptime_alerts.sh --webhook-url "https://hooks.example.com/..."
  verify_uptime_alerts.sh --dry-run
EOF
}

REPO_DIR="/opt/resto"
WEBHOOK_URL="${UPTIME_ALERT_WEBHOOK:-}"
COOLDOWN_MINUTES="0"
STATE_FILE="/tmp/kepoli-uptime-drill.state"
FAILURE_CHECK=""
DRY_RUN=0
CHECKS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo-dir)
      REPO_DIR="${2:-}"
      shift 2
      ;;
    --webhook-url)
      WEBHOOK_URL="${2:-}"
      shift 2
      ;;
    --cooldown-minutes)
      COOLDOWN_MINUTES="${2:-0}"
      shift 2
      ;;
    --state-file)
      STATE_FILE="${2:-/tmp/kepoli-uptime-drill.state}"
      shift 2
      ;;
    --check)
      CHECKS+=("${2:-}")
      shift 2
      ;;
    --failure-check)
      FAILURE_CHECK="${2:-}"
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
  CHECKS=(
    "https://kepoli.com/health|200"
    "https://admin.kepoli.com/health|200"
    "https://api.kepoli.com/api/health/|200"
  )
fi

if [[ -z "$FAILURE_CHECK" ]]; then
  FAILURE_CHECK="https://api.kepoli.com/api/health-bad/|200"
fi

PROBE_SCRIPT="${REPO_DIR%/}/infra/coolify/uptime_probe.sh"
if [[ ! -f "$PROBE_SCRIPT" ]]; then
  echo "Probe script not found: $PROBE_SCRIPT" >&2
  exit 1
fi

cleanup() {
  rm -f "$STATE_FILE"
}
trap cleanup EXIT
rm -f "$STATE_FILE"

common_args=(--cooldown-minutes "$COOLDOWN_MINUTES" --state-file "$STATE_FILE")
if [[ "$DRY_RUN" -eq 1 ]]; then
  common_args+=(--dry-run)
elif [[ -n "$WEBHOOK_URL" ]]; then
  common_args+=(--alert-webhook "$WEBHOOK_URL")
else
  echo "No webhook URL provided. Switching to dry-run mode."
  common_args+=(--dry-run)
fi

echo "Step 1/2: triggering down event..."
set +e
down_output="$(
  /bin/bash "$PROBE_SCRIPT" \
    --check "$FAILURE_CHECK" \
    "${common_args[@]}" 2>&1
)"
down_rc=$?
set -e
echo "$down_output"

if [[ "$down_rc" -eq 0 ]]; then
  echo "Expected a failing probe for down event, but it succeeded." >&2
  exit 1
fi

echo "Step 2/2: triggering recovered event..."
up_cmd=(/bin/bash "$PROBE_SCRIPT")
for spec in "${CHECKS[@]}"; do
  up_cmd+=(--check "$spec")
done
up_cmd+=("${common_args[@]}")
"${up_cmd[@]}"

echo "Drill finished. Down + recovered probes executed."
if [[ "$DRY_RUN" -eq 1 || -z "$WEBHOOK_URL" ]]; then
  echo "Webhook was not called (dry-run)."
else
  echo "Webhook calls attempted for down and recovered events."
fi
