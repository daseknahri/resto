#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Check DNS email deliverability records (SPF, DMARC, DKIM).

Usage:
  check_email_dns.sh --domain <domain> [options]

Options:
  --domain <domain>            Root sending domain (required), e.g. kepoli.com
  --dkim-selector <selector>   DKIM selector to verify (repeatable), e.g. s1
  --require-dkim               Fail if no --dkim-selector provided
  --resolver <dns-server>      DNS server for dig (optional), e.g. 1.1.1.1
  --json                       Output JSON summary
  -h, --help                   Show help

Examples:
  check_email_dns.sh --domain kepoli.com
  check_email_dns.sh --domain kepoli.com --dkim-selector s1 --dkim-selector s2
EOF
}

DOMAIN=""
RESOLVER=""
OUTPUT_JSON=0
REQUIRE_DKIM=0
DKIM_SELECTORS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --domain)
      DOMAIN="${2:-}"
      shift 2
      ;;
    --dkim-selector)
      DKIM_SELECTORS+=("${2:-}")
      shift 2
      ;;
    --require-dkim)
      REQUIRE_DKIM=1
      shift
      ;;
    --resolver)
      RESOLVER="${2:-}"
      shift 2
      ;;
    --json)
      OUTPUT_JSON=1
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

if [[ -z "$DOMAIN" ]]; then
  echo "--domain is required." >&2
  exit 2
fi

if [[ "$REQUIRE_DKIM" -eq 1 && ${#DKIM_SELECTORS[@]} -eq 0 ]]; then
  echo "--require-dkim is set but no --dkim-selector provided." >&2
  exit 2
fi

resolver_args=()
if [[ -n "$RESOLVER" ]]; then
  resolver_args=("@$RESOLVER")
fi

resolve_txt_with_dig() {
  local fqdn="$1"
  dig "${resolver_args[@]}" +short TXT "$fqdn" 2>/dev/null | sed 's/" "//g; s/^"//; s/"$//; s/"//g'
}

resolve_txt_with_nslookup() {
  local fqdn="$1"
  local out
  out="$(nslookup -type=txt "$fqdn" 2>/dev/null || true)"
  echo "$out" | sed -n 's/^[[:space:]]*text = "\(.*\)"/\1/p'
}

resolve_txt() {
  local fqdn="$1"
  if command -v dig >/dev/null 2>&1; then
    resolve_txt_with_dig "$fqdn"
    return 0
  fi
  if command -v nslookup >/dev/null 2>&1; then
    resolve_txt_with_nslookup "$fqdn"
    return 0
  fi
  echo "Neither dig nor nslookup is available on this host." >&2
  exit 1
}

if ! command -v dig >/dev/null 2>&1 && ! command -v nslookup >/dev/null 2>&1; then
  echo "Neither dig nor nslookup is available on this host. Install dnsutils or bind-tools." >&2
  exit 1
fi

join_lines() {
  if [[ $# -eq 0 ]]; then
    printf ""
    return
  fi
  local first=1
  for line in "$@"; do
    if [[ $first -eq 1 ]]; then
      printf "%s" "$line"
      first=0
    else
      printf " | %s" "$line"
    fi
  done
}

readarray -t root_txt_records < <(resolve_txt "$DOMAIN")
readarray -t dmarc_txt_records < <(resolve_txt "_dmarc.$DOMAIN")

spf_records=()
for rec in "${root_txt_records[@]}"; do
  if [[ "$rec" =~ ^[Vv]=spf1[[:space:]].* || "$rec" =~ ^[Vv]=spf1$ ]]; then
    spf_records+=("$rec")
  fi
done

dmarc_records=()
for rec in "${dmarc_txt_records[@]}"; do
  if [[ "$rec" =~ ^[Vv]=DMARC1[[:space:]].* || "$rec" =~ ^[Vv]=DMARC1$ ]]; then
    dmarc_records+=("$rec")
  fi
done

spf_ok=0
dmarc_ok=0
spf_count="${#spf_records[@]}"
dmarc_count="${#dmarc_records[@]}"

if [[ "$spf_count" -eq 1 ]]; then
  spf_ok=1
fi
if [[ "$dmarc_count" -ge 1 ]]; then
  dmarc_ok=1
fi

dkim_fail_count=0
dkim_results=()
for selector in "${DKIM_SELECTORS[@]}"; do
  fqdn="${selector}._domainkey.${DOMAIN}"
  readarray -t dkim_txt_records < <(resolve_txt "$fqdn")
  dkim_ok=0
  for rec in "${dkim_txt_records[@]}"; do
    if [[ "$rec" =~ ^[Vv]=DKIM1[[:space:]].* || "$rec" =~ ^[Vv]=DKIM1$ ]]; then
      dkim_ok=1
      break
    fi
  done
  if [[ "$dkim_ok" -eq 0 ]]; then
    dkim_fail_count=$((dkim_fail_count + 1))
  fi
  dkim_results+=("${selector}:${dkim_ok}:$(join_lines "${dkim_txt_records[@]}")")
done

exit_code=0
if [[ "$spf_ok" -eq 0 ]]; then
  exit_code=1
fi
if [[ "$dmarc_ok" -eq 0 ]]; then
  exit_code=1
fi
if [[ "${#DKIM_SELECTORS[@]}" -gt 0 && "$dkim_fail_count" -gt 0 ]]; then
  exit_code=1
fi

if [[ "$OUTPUT_JSON" -eq 1 ]]; then
  printf '{"domain":"%s","spf_ok":%s,"spf_count":%s,"dmarc_ok":%s,"dmarc_count":%s,"dkim_checked":%s,"dkim_failures":%s}\n' \
    "$DOMAIN" \
    "$([[ "$spf_ok" -eq 1 ]] && echo "true" || echo "false")" \
    "$spf_count" \
    "$([[ "$dmarc_ok" -eq 1 ]] && echo "true" || echo "false")" \
    "$dmarc_count" \
    "${#DKIM_SELECTORS[@]}" \
    "$dkim_fail_count"
else
  echo "Domain: $DOMAIN"
  echo "SPF records found: $spf_count"
  if [[ "$spf_count" -eq 1 ]]; then
    echo "SPF status: OK"
  elif [[ "$spf_count" -eq 0 ]]; then
    echo "SPF status: FAIL (no v=spf1 record found)"
  else
    echo "SPF status: FAIL (multiple SPF records found; must be exactly one)"
  fi
  if [[ "${#spf_records[@]}" -gt 0 ]]; then
    echo "SPF value(s): $(join_lines "${spf_records[@]}")"
  fi

  echo "DMARC records found: $dmarc_count"
  if [[ "$dmarc_ok" -eq 1 ]]; then
    echo "DMARC status: OK"
    echo "DMARC value(s): $(join_lines "${dmarc_records[@]}")"
  else
    echo "DMARC status: FAIL (no v=DMARC1 record found at _dmarc.$DOMAIN)"
  fi

  if [[ "${#DKIM_SELECTORS[@]}" -gt 0 ]]; then
    echo "DKIM checks:"
    for item in "${dkim_results[@]}"; do
      selector="${item%%:*}"
      rest="${item#*:}"
      ok="${rest%%:*}"
      value="${rest#*:}"
      if [[ "$ok" == "1" ]]; then
        echo "- ${selector}._domainkey.$DOMAIN: OK"
      else
        echo "- ${selector}._domainkey.$DOMAIN: FAIL"
      fi
      if [[ -n "$value" ]]; then
        echo "  value(s): $value"
      fi
    done
  fi
fi

exit "$exit_code"
