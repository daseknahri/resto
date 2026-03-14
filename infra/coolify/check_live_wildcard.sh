#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Verify that the live wildcard tenant router is installed and working.

Usage:
  check_live_wildcard.sh [options]

Options:
  --base-domain <domain>      Tenant namespace base domain (default: menu.kepoli.com)
  --tenant-slug <slug>        Tenant slug to probe (default: smoke)
  --proxy-config <path>       Proxy dynamic config path (default: /data/coolify/proxy/dynamic/kepoli-tenant-wildcard.yml)
  --cert-dir <path>           Proxy certificate dir (default: /data/coolify/proxy/certs/menu.kepoli.com)
  --host-ip <ip>              Override public host IP for --resolve probes
  --skip-network              Skip external curl checks
  --dry-run                   Print resolved values only
  -h, --help                  Show help
EOF
}

BASE_DOMAIN="menu.kepoli.com"
TENANT_SLUG="smoke"
PROXY_CONFIG="/data/coolify/proxy/dynamic/kepoli-tenant-wildcard.yml"
CERT_DIR="/data/coolify/proxy/certs/menu.kepoli.com"
HOST_IP=""
SKIP_NETWORK=0
DRY_RUN=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --base-domain)
      BASE_DOMAIN="${2:-}"
      shift 2
      ;;
    --tenant-slug)
      TENANT_SLUG="${2:-}"
      shift 2
      ;;
    --proxy-config)
      PROXY_CONFIG="${2:-}"
      shift 2
      ;;
    --cert-dir)
      CERT_DIR="${2:-}"
      shift 2
      ;;
    --host-ip)
      HOST_IP="${2:-}"
      shift 2
      ;;
    --skip-network)
      SKIP_NETWORK=1
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

TENANT_HOST="${TENANT_SLUG}.${BASE_DOMAIN}"

if [[ -z "$HOST_IP" && "$SKIP_NETWORK" -eq 0 ]]; then
  HOST_IP="$(getent ahostsv4 "$BASE_DOMAIN" | awk 'NR==1{print $1}')"
fi

if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "tenant_host=$TENANT_HOST"
  echo "proxy_config=$PROXY_CONFIG"
  echo "cert_dir=$CERT_DIR"
  echo "host_ip=$HOST_IP"
  exit 0
fi

if [[ ! -f "$PROXY_CONFIG" ]]; then
  echo "Wildcard proxy config not found: $PROXY_CONFIG" >&2
  exit 1
fi

if [[ ! -f "${CERT_DIR%/}/fullchain.pem" || ! -f "${CERT_DIR%/}/privkey.pem" ]]; then
  echo "Wildcard cert files missing in: $CERT_DIR" >&2
  exit 1
fi

grep -q "HostRegexp" "$PROXY_CONFIG" || {
  echo "Wildcard proxy config does not contain HostRegexp rule." >&2
  exit 1
}

grep -q "$BASE_DOMAIN" "$PROXY_CONFIG" || {
  echo "Wildcard proxy config does not target base domain: $BASE_DOMAIN" >&2
  exit 1
}

docker ps --format '{{.Names}}' | grep -q '^coolify-proxy$' || {
  echo "coolify-proxy container is not running." >&2
  exit 1
}

echo "Wildcard proxy config present."
echo "Proxy config: $PROXY_CONFIG"
echo "Tenant host: $TENANT_HOST"

if [[ "$SKIP_NETWORK" -eq 1 ]]; then
  exit 0
fi

if [[ -z "$HOST_IP" ]]; then
  echo "Could not resolve public host IP for $BASE_DOMAIN" >&2
  exit 1
fi

curl -fsSI --resolve "${TENANT_HOST}:80:${HOST_IP}" "http://${TENANT_HOST}/health" >/dev/null
curl -fsSI --resolve "${TENANT_HOST}:443:${HOST_IP}" "https://${TENANT_HOST}/health" >/dev/null

echo "External tenant probes passed."
