#!/usr/bin/env bash
# Corre en la VM de OCI (lo invoca el workflow por SSH desde ~/communitylab): baja la imagen IMAGEN,
# reinicia el contenedor y espera a que la API responda. También sirve a mano (el workflow deja una copia en
# ~/communitylab; a mano usa el login de ghcr.io que tenga la VM, si lo hay):
#   cd ~/communitylab && IMAGEN=ghcr.io/no-country-simulation/g10_latam_team_26:<sha> bash actualizar.sh
set -euo pipefail

: "${IMAGEN:?Falta IMAGEN}"
test -f .env || { echo "Falta $(pwd)/.env en el servidor (ver docs/despliegue-oci.md)"; exit 1; }

# Desde el workflow llega GHCR_USER y el token temporal de GitHub Actions por stdin: el login se hace en una
# configuración de Docker temporal que se borra al salir, así que en la VM no queda ninguna credencial
if [ -n "${GHCR_USER:-}" ]; then
  DOCKER_CONFIG=$(mktemp -d)
  export DOCKER_CONFIG
  trap 'rm -rf "$DOCKER_CONFIG"' EXIT
  docker login ghcr.io -u "$GHCR_USER" --password-stdin >/dev/null
fi

echo "IMAGEN=$IMAGEN" > .imagen.env

# Un communitylab_web que no salió de este compose (por ejemplo, uno levantado a mano) ocupa el nombre y el
# puerto 8000: se retira antes de levantar el nuevo
proyecto=$(docker inspect -f '{{ index .Config.Labels "com.docker.compose.project" }}' communitylab_web 2>/dev/null || echo "-")
if [ "$proyecto" != "-" ] && [ "$proyecto" != "$(basename "$(pwd)")" ]; then
  echo "Retirando communitylab_web levantado fuera de este compose (proyecto: ${proyecto:-ninguno})"
  docker rm -f communitylab_web >/dev/null
fi

docker compose --env-file .imagen.env pull
docker compose --env-file .imagen.env up -d --remove-orphans

for _ in $(seq 1 30); do
  if curl -fs -o /dev/null http://127.0.0.1:8000/api/openapi.json; then
    echo "Desplegado $IMAGEN"
    docker image prune -f >/dev/null
    exit 0
  fi
  sleep 2
done

echo "La app no respondió tras el despliegue"
docker compose --env-file .imagen.env logs --tail 80
exit 1
