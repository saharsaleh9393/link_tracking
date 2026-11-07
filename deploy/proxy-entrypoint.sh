#!/bin/sh
set -eu
DASHBOARD_PROXY_SECRET="$(cat /run/secrets/dashboard_proxy_secret)"
[ "${#DASHBOARD_PROXY_SECRET}" -ge 32 ] || { echo 'proxy_secret_not_configured' >&2; exit 1; }
export DASHBOARD_PROXY_SECRET
# Runtime env placeholder keeps the secret out of Caddy's saved JSON configuration.
if [ "$#" -eq 0 ]; then
    set -- caddy run --config /etc/caddy/Caddyfile --adapter caddyfile
fi
exec "$@"
