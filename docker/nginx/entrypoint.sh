#!/usr/bin/env sh

set -eu

DOMAIN="${DOMAIN:-}"
WWW_DOMAIN="${WWW_DOMAIN:-}"
NGINX_CLIENT_MAX_BODY_SIZE="${NGINX_CLIENT_MAX_BODY_SIZE:-20M}"

if [ -z "$DOMAIN" ]; then
  echo "DOMAIN is required for the Nginx HTTPS setup." >&2
  exit 1
fi

SERVER_NAMES="$DOMAIN"
if [ -n "$WWW_DOMAIN" ]; then
  SERVER_NAMES="$SERVER_NAMES $WWW_DOMAIN"
fi

export DOMAIN
export SERVER_NAMES
export CERTBOT_CERT_NAME="$DOMAIN"
export NGINX_CLIENT_MAX_BODY_SIZE

CERT_FILE="/etc/letsencrypt/live/$DOMAIN/fullchain.pem"
KEY_FILE="/etc/letsencrypt/live/$DOMAIN/privkey.pem"

render_config() {
  template="/etc/nginx/templates/bootstrap.conf.template"

  if [ -f "$CERT_FILE" ] && [ -f "$KEY_FILE" ]; then
    template="/etc/nginx/templates/https.conf.template"
    echo "TLS certificate detected for $SERVER_NAMES. Enabling HTTPS."
  else
    echo "TLS certificate not found yet for $SERVER_NAMES. Serving bootstrap ACME config."
  fi

  envsubst '${SERVER_NAMES} ${CERTBOT_CERT_NAME} ${NGINX_CLIENT_MAX_BODY_SIZE}' \
    < "$template" \
    > /etc/nginx/conf.d/default.conf

  nginx -t
}

cert_signature() {
  if [ -f "$CERT_FILE" ] && [ -f "$KEY_FILE" ]; then
    sha256sum "$CERT_FILE" "$KEY_FILE" | sha256sum | awk '{print $1}'
  else
    echo "missing"
  fi
}

render_config
LAST_SIGNATURE="$(cert_signature)"

(
  while sleep 30; do
    CURRENT_SIGNATURE="$(cert_signature)"
    if [ "$CURRENT_SIGNATURE" != "$LAST_SIGNATURE" ]; then
      render_config
      nginx -s reload
      LAST_SIGNATURE="$CURRENT_SIGNATURE"
    fi
  done
) &

exec nginx -g 'daemon off;'
