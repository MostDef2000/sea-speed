#!/usr/bin/env bash
set -Eeuo pipefail

if [[ $# -ne 0 ]]; then
  echo "ERROR sea-speed-nginx-zerotier-wait accepts no arguments" >&2
  exit 2
fi

FIXED_ADDRESS="10.123.239.101"
MAX_ATTEMPTS=24
INTERVAL_SECONDS=5

for required in ip sleep; do
  command -v "$required" >/dev/null 2>&1 || {
    echo "ERROR $required command is required" >&2
    exit 255
  }
done

for ((attempt = 1; attempt <= MAX_ATTEMPTS; attempt += 1)); do
  address_ready=0
  while read -r _ _ family cidr _; do
    if [[ "$family" == "inet" && "${cidr%%/*}" == "$FIXED_ADDRESS" ]]; then
      address_ready=1
      break
    fi
  done < <(ip -o -4 addr show 2>/dev/null)
  if [[ "$address_ready" -eq 1 ]]; then
    echo "NGINX_ZEROTIER_ADDRESS_READY=PASS"
    echo "FIXED_ADDRESS=$FIXED_ADDRESS"
    echo "ATTEMPTS=$attempt"
    exit 0
  fi
  if [[ "$attempt" -lt "$MAX_ATTEMPTS" ]]; then
    echo "NGINX_ZEROTIER_WAIT=attempt $attempt of $MAX_ATTEMPTS" >&2
    sleep "$INTERVAL_SECONDS"
  fi
done

echo "ERROR fixed ZeroTier address $FIXED_ADDRESS did not become locally available after $MAX_ATTEMPTS attempts" >&2
# ExecCondition exit statuses 1..254 skip a unit without marking it failed.
# Status 255 makes nginx fail so Restart=on-failure schedules the bounded retry.
exit 255
