#!/usr/bin/env bash
# Primer certificado de Let's Encrypt para nginx en la máquina de la nube (D26).
#
#   sudo bash infra/nginx/letsencrypt.sh
#
# Variables (todas opcionales):
#   DOMINIO              el nombre que apunta a la IP fija. Si no viene, se arma con la IP
#                        externa de la máquina de Compute Engine: 34.56.78.90 -> 34-56-78-90.sslip.io
#   LETSENCRYPT_CORREO   correo para los avisos de vencimiento. Sin él, se registra sin correo.
#   LETSENCRYPT_PRUEBA=1 usa el servidor de pruebas de Let's Encrypt (sin límites, pero nadie
#                        confía en su certificado). Para ensayar antes del real.
#   NUEVO=1              reemplaza el certificado que ya haya (por ejemplo, el de prueba).
#
# Pasos: pone un certificado provisional para que nginx arranque, levanta nginx, pide el
# certificado real por HTTP (puerto 80, /.well-known/acme-challenge/) y recarga nginx. Después,
# certbot lo renueva solo (docker-compose.letsencrypt.yml). Correr este script implica aceptar
# los términos de Let's Encrypt (--agree-tos).
#
# Si Let's Encrypt responde «too many certificates already issued for sslip.io», el límite
# semanal de sslip.io (que no está en la Public Suffix List) ya se agotó: usa un subdominio
# gratuito de DuckDNS (DOMINIO=<nombre>.duckdns.org), que sí cuenta aparte.
set -euo pipefail

INFRA="$(cd "$(dirname "$0")/.." && pwd)"
cd "$INFRA"

if [ -z "${DOMINIO:-}" ]; then
  IP=$(curl -fsS -H "Metadata-Flavor: Google" \
    "http://metadata.google.internal/computeMetadata/v1/instance/network-interfaces/0/access-configs/0/external-ip" \
    || true)
  if [ -z "$IP" ]; then
    echo "No es una máquina de Compute Engine o no tiene IP externa: indica DOMINIO." >&2
    exit 1
  fi
  DOMINIO="${IP//./-}.sslip.io"
fi
export DOMINIO
echo "Dominio: $DOMINIO"

COMPOSE=(docker compose -f docker-compose.yml -f docker-compose.nginx.yml -f docker-compose.letsencrypt.yml)
VIVO="letsencrypt/live/$DOMINIO"
mkdir -p letsencrypt certbot-www

if [ -f "$VIVO/fullchain.pem" ] && [ ! -f "$VIVO/.provisional" ] && [ "${NUEVO:-0}" != "1" ]; then
  echo "Ya hay un certificado para $DOMINIO. Para reemplazarlo: NUEVO=1."
  exit 0
fi

echo "Certificado provisional para que nginx arranque..."
rm -rf "letsencrypt/live/$DOMINIO" "letsencrypt/archive/$DOMINIO" "letsencrypt/renewal/$DOMINIO.conf"
mkdir -p "$VIVO"
openssl req -x509 -nodes -newkey rsa:2048 -days 1 -subj "/CN=provisional" \
  -keyout "$VIVO/privkey.pem" -out "$VIVO/fullchain.pem" 2>/dev/null
touch "$VIVO/.provisional"

"${COMPOSE[@]}" up -d nginx
for _ in $(seq 1 30); do
  curl -fsS "http://127.0.0.1/nginx-salud" >/dev/null 2>&1 && break
  sleep 1
done

# certbot no escribe sobre una carpeta que no creó: se quita la provisional. nginx sigue con
# ella en memoria hasta la recarga.
rm -rf "letsencrypt/live/$DOMINIO"

ARGUMENTOS=(certonly --webroot -w /var/www/certbot -d "$DOMINIO" --agree-tos --non-interactive --no-eff-email)
if [ -n "${LETSENCRYPT_CORREO:-}" ]; then
  ARGUMENTOS+=(--email "$LETSENCRYPT_CORREO")
else
  ARGUMENTOS+=(--register-unsafely-without-email)
fi
if [ "${LETSENCRYPT_PRUEBA:-0}" = "1" ]; then
  ARGUMENTOS+=(--staging)
fi

echo "Pidiendo el certificado a Let's Encrypt..."
"${COMPOSE[@]}" run --rm --entrypoint certbot certbot "${ARGUMENTOS[@]}"
"${COMPOSE[@]}" exec nginx nginx -s reload
"${COMPOSE[@]}" up -d certbot

# curl valida el certificado contra el nombre; cualquier código HTTP sirve. El de prueba no es
# de confianza, así que con LETSENCRYPT_PRUEBA=1 solo se revisa que nginx responda.
VERIFICA=()
[ "${LETSENCRYPT_PRUEBA:-0}" = "1" ] && VERIFICA=(-k)
if curl -sS -o /dev/null "${VERIFICA[@]}" --resolve "$DOMINIO:443:127.0.0.1" "https://$DOMINIO/"; then
  echo "Listo: nginx responde en https://$DOMINIO con el certificado nuevo."
else
  echo "nginx no respondió con el certificado nuevo. Revisa: ${COMPOSE[*]} logs nginx" >&2
  exit 1
fi
