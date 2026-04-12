#!/usr/bin/env sh

set -eu

DOMAIN="${DOMAIN:-}"
WWW_DOMAIN="${WWW_DOMAIN:-}"
LETSENCRYPT_EMAIL="${LETSENCRYPT_EMAIL:-}"
LETSENCRYPT_STAGING="${LETSENCRYPT_STAGING:-false}"
WEBROOT="/var/www/certbot"
CERT_FILE="/etc/letsencrypt/live/$DOMAIN/fullchain.pem"

if [ -z "$DOMAIN" ]; then
  echo "DOMAIN is required for Let's Encrypt." >&2
  exit 1
fi

if [ -z "$LETSENCRYPT_EMAIL" ]; then
  echo "LETSENCRYPT_EMAIL is required for Let's Encrypt." >&2
  exit 1
fi

mkdir -p "$WEBROOT"

request_certificate() {
  if [ -n "$WWW_DOMAIN" ]; then
    if [ "$LETSENCRYPT_STAGING" = "true" ]; then
      certbot certonly --staging --webroot -w "$WEBROOT" --email "$LETSENCRYPT_EMAIL" \
        --agree-tos --no-eff-email --non-interactive -d "$DOMAIN" -d "$WWW_DOMAIN"
    else
      certbot certonly --webroot -w "$WEBROOT" --email "$LETSENCRYPT_EMAIL" \
        --agree-tos --no-eff-email --non-interactive -d "$DOMAIN" -d "$WWW_DOMAIN"
    fi
  else
    if [ "$LETSENCRYPT_STAGING" = "true" ]; then
      certbot certonly --staging --webroot -w "$WEBROOT" --email "$LETSENCRYPT_EMAIL" \
        --agree-tos --no-eff-email --non-interactive -d "$DOMAIN"
    else
      certbot certonly --webroot -w "$WEBROOT" --email "$LETSENCRYPT_EMAIL" \
        --agree-tos --no-eff-email --non-interactive -d "$DOMAIN"
    fi
  fi
}

renew_certificate() {
  if [ "$LETSENCRYPT_STAGING" = "true" ]; then
    certbot renew --staging --webroot -w "$WEBROOT" --quiet
  else
    certbot renew --webroot -w "$WEBROOT" --quiet
  fi
}

echo "Starting Let's Encrypt loop for $DOMAIN..."

while true; do
  if [ ! -f "$CERT_FILE" ]; then
    echo "No certificate found yet. Requesting initial certificate..."
    if request_certificate; then
      echo "Initial certificate issued successfully."
      sleep 12h
    else
      echo "Certificate request failed. Retrying in 60 seconds."
      sleep 60
    fi
  else
    echo "Checking for certificate renewals..."
    if renew_certificate; then
      echo "Certificate renewal check completed."
      sleep 12h
    else
      echo "Certificate renewal check failed. Retrying in 60 seconds."
      sleep 60
    fi
  fi
done
