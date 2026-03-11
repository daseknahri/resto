#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Generate and install the Traefik wildcard tenant proxy config for Coolify.

Usage:
  install_tenant_wildcard_proxy.sh [options]

Options:
  --resource-uuid <uuid>      Coolify resource UUID used to auto-detect frontend container
  --frontend-container <name> Explicit frontend container name
  --base-domain <domain>      Tenant namespace base domain (default: menu.kepoli.com)
  --cert-dir <path>           Cert directory mounted in proxy (default: /traefik/certs/menu.kepoli.com)
  --proxy-config-dir <path>   Host dynamic-config directory (default: /data/coolify/proxy/dynamic)
  --file-name <name>          Output file name (default: kepoli-tenant-wildcard.yml)
  --prefer-ip                 Render proxy target with shared network IP instead of container hostname
  --dry-run                   Print what would be done without writing files
  -h, --help                  Show help
EOF
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RENDER_SCRIPT="${SCRIPT_DIR}/render_tenant_wildcard_proxy.sh"

RESOURCE_UUID=""
FRONTEND_CONTAINER=""
BASE_DOMAIN="menu.kepoli.com"
CERT_DIR="/traefik/certs/menu.kepoli.com"
PROXY_CONFIG_DIR="/data/coolify/proxy/dynamic"
FILE_NAME="kepoli-tenant-wildcard.yml"
PREFER_IP=0
DRY_RUN=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --resource-uuid)
      RESOURCE_UUID="${2:-}"
      shift 2
      ;;
    --frontend-container)
      FRONTEND_CONTAINER="${2:-}"
      shift 2
      ;;
    --base-domain)
      BASE_DOMAIN="${2:-}"
      shift 2
      ;;
    --cert-dir)
      CERT_DIR="${2:-}"
      shift 2
      ;;
    --proxy-config-dir)
      PROXY_CONFIG_DIR="${2:-}"
      shift 2
      ;;
    --file-name)
      FILE_NAME="${2:-}"
      shift 2
      ;;
    --prefer-ip)
      PREFER_IP=1
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
      usage >&2
      exit 2
      ;;
  esac
done

if [[ ! -x "$RENDER_SCRIPT" ]]; then
  chmod +x "$RENDER_SCRIPT"
fi

OUTPUT_PATH="${PROXY_CONFIG_DIR%/}/${FILE_NAME}"
TMP_FILE="$(mktemp)"
cleanup() {
  rm -f "$TMP_FILE"
}
trap cleanup EXIT

render_args=(--base-domain "$BASE_DOMAIN" --cert-dir "$CERT_DIR" --output "$TMP_FILE" --dry-run)
if [[ -n "$RESOURCE_UUID" ]]; then
  render_args+=(--resource-uuid "$RESOURCE_UUID")
fi
if [[ -n "$FRONTEND_CONTAINER" ]]; then
  render_args+=(--frontend-container "$FRONTEND_CONTAINER")
fi
if [[ "$PREFER_IP" -eq 1 ]]; then
  render_args+=(--prefer-ip)
fi

bash "$RENDER_SCRIPT" "${render_args[@]}"

if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "[dry-run] would install wildcard config to: ${OUTPUT_PATH}"
  echo "[dry-run] rendered config:"
  cat "$TMP_FILE"
  exit 0
fi

mkdir -p "$PROXY_CONFIG_DIR"
cp "$TMP_FILE" "$OUTPUT_PATH"
echo "Installed wildcard proxy config to: $OUTPUT_PATH"
echo "Next step: restart the Coolify proxy."
