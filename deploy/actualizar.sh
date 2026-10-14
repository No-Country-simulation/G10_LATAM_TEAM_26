#!/usr/bin/env bash
# Corre en la VM de OCI (lo invoca el workflow por SSH desde ~/communitylab): baja la imagen IMAGEN,
# reinicia el contenedor y espera a que la API responda. También sirve a mano:
#   cd ~/communitylab && IMAGEN=ghcr.io/no-country-simulation/g10_latam_team_26:latest bash actualizar.sh
set -euo pipefail

: "${IMAGEN:?Falta IMAGEN}"
test -f .env || { echo "Falta $(pwd)/.env en el servidor (ver docs/despliegue-oci.md)"; exit 1; }

echo "IMAGEN=$IMAGEN" > .imagen.env
docker compose --env-file .imagen.env pull
docker compose --env-file .imagen.env up -d --remove-orphans

for _ in $(seq 1 30); do
  if curl -fs -o /dev/null http://127.0.0.1:8510/api/openapi.json; then
    echo "Desplegado $IMAGEN"
    docker image prune -f >/dev/null
    exit 0
  fi
  sleep 2
done

echo "La app no respondió tras el despliegue"
docker compose --env-file .imagen.env logs --tail 80
exit 1
