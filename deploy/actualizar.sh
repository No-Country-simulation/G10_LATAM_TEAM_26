#!/usr/bin/env bash
# Corre en la VM de OCI (lo invoca el workflow por SSH desde ~/communitylab): baja la imagen IMAGEN,
# reinicia el contenedor y espera a que la API responda. También sirve a mano:
#   cd ~/communitylab && IMAGEN=ghcr.io/no-country-simulation/g10_latam_team_26:latest bash actualizar.sh
set -euo pipefail

: "${IMAGEN:?Falta IMAGEN}"
test -f .env || { echo "Falta $(pwd)/.env en el servidor (ver docs/despliegue-oci.md)"; exit 1; }

# HTTPS: si el .env define DOMINIO se levanta Caddy (perfil "https") y el panel deja de publicarse en el 8510 abierto
# al mundo: queda solo en 127.0.0.1. Sin DOMINIO todo sigue como antes (HTTP en el 8510).
DOMINIO="$(grep -E '^DOMINIO=' .env | tail -n1 | cut -d= -f2- | tr -d '\r"' | tr -d "'" || true)"
{
  echo "IMAGEN=$IMAGEN"
  if [ -n "$DOMINIO" ]; then
    echo "DOMINIO=$DOMINIO"
    echo "WEB_PUBLICAR=127.0.0.1:8510"
  fi
} > .imagen.env
PERFIL=()
if [ -n "$DOMINIO" ]; then
  test -f Caddyfile || { echo "Falta $(pwd)/Caddyfile (lo copia el workflow desde deploy/Caddyfile)"; exit 1; }
  PERFIL=(--profile https)
fi

docker compose --env-file .imagen.env "${PERFIL[@]}" pull
docker compose --env-file .imagen.env "${PERFIL[@]}" up -d --remove-orphans

for _ in $(seq 1 30); do
  if curl -fs -o /dev/null http://127.0.0.1:8510/api/openapi.json; then
    echo "Desplegado $IMAGEN"
    docker image prune -f >/dev/null
    exit 0
  fi
  sleep 2
done

echo "La app no respondió tras el despliegue"
docker compose --env-file .imagen.env "${PERFIL[@]}" logs --tail 80
exit 1
