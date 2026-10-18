#!/usr/bin/env bash
# Corre en la VM de OCI (lo invoca el workflow por SSH desde ~/communitylab): baja la imagen IMAGEN,
# reinicia el contenedor y espera a que la API responda. También sirve a mano (el workflow deja una copia en
# ~/communitylab; a mano usa el login de ghcr.io que tenga la VM, si lo hay):
#   cd ~/communitylab && IMAGEN=ghcr.io/no-country-simulation/g10_latam_team_26:<sha> bash actualizar.sh
set -euo pipefail

: "${IMAGEN:?Falta IMAGEN}"
test -f .env || { echo "Falta $(pwd)/.env en el servidor (ver docs/despliegue-oci.md)"; exit 1; }

# Docker Compose v2 (plugin "docker compose") o v1 (docker-compose): la VM de OCI trae el v1 de Ubuntu
if docker compose version >/dev/null 2>&1; then
  COMPOSE=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE=(docker-compose)
else
  echo "Falta Docker Compose en el servidor (docker compose o docker-compose)"; exit 1
fi

# Desde el workflow llega GHCR_USER y el token temporal de GitHub Actions por stdin: el login se hace en una
# configuración de Docker temporal que se borra al salir, así que en la VM no queda ninguna credencial
if [ -n "${GHCR_USER:-}" ]; then
  DOCKER_CONFIG=$(mktemp -d)
  export DOCKER_CONFIG
  trap 'rm -rf "$DOCKER_CONFIG"' EXIT
  docker login ghcr.io -u "$GHCR_USER" --password-stdin >/dev/null
fi

# HTTPS: si el .env define DOMINIO se levanta Caddy (perfil "https") y el panel deja de publicarse en el 8000 abierto
# al mundo: queda solo en 127.0.0.1. Sin DOMINIO todo sigue como antes (HTTP en el 8000).
DOMINIO="$(grep -E '^DOMINIO=' .env | tail -n1 | cut -d= -f2- | tr -d '\r"' | tr -d "'" || true)"
{
  echo "IMAGEN=$IMAGEN"
  if [ -n "$DOMINIO" ]; then
    echo "DOMINIO=$DOMINIO"
    echo "WEB_PUBLICAR=127.0.0.1:8000"
  fi
} > .imagen.env
PERFIL=()
if [ -n "$DOMINIO" ]; then
  test -f Caddyfile || { echo "Falta $(pwd)/Caddyfile (lo copia el workflow desde deploy/Caddyfile)"; exit 1; }
  PERFIL=(--profile https)
fi

# Se baja la imagen antes de tocar nada: si falla, la app que está corriendo sigue en pie
docker pull "$IMAGEN"
if [ -n "$DOMINIO" ]; then
  docker pull caddy:2
fi

# La app escribe en data/ (capturas de Discord, paquetes, base local) como el usuario de la imagen. Si la carpeta
# es de otro usuario (la creó root o el usuario de la VM), falla con PermissionError: se le pasa a ese usuario
# con un contenedor temporal de la misma imagen, sin necesitar sudo
mkdir -p data fixtures
if ! docker run --rm --entrypoint sh -v "$(pwd)/data:/app/data" "$IMAGEN" \
     -c 'test -d /app/data/fixtures && test -w /app/data && test -z "$(find /app/data ! -writable -print -quit)"'; then
  echo "Ajustando el dueño de $(pwd)/data al usuario de la app"
  docker run --rm -u 0 --entrypoint sh -v "$(pwd)/data:/app/data" "$IMAGEN" \
    -c 'mkdir -p /app/data/fixtures && chown -R app:app /app/data'  # data/fixtures: punto de montaje de fixtures/
fi
# Imagen que corre ahora: si la nueva no levanta o no responde, se vuelve a esta
PREVIA="$(docker inspect -f '{{.Config.Image}}' communitylab_web 2>/dev/null || true)"

# Un communitylab_web que no salió de este compose (por ejemplo, uno levantado a mano) ocupa el nombre y el
# puerto 8000: se retira recién ahora, justo antes de levantar el nuevo
proyecto="-"
if [ -n "$(docker ps -aq -f name='^communitylab_web$')" ]; then
  proyecto=$(docker inspect -f '{{ index .Config.Labels "com.docker.compose.project" }}' communitylab_web)
fi
if [ "$proyecto" != "-" ] && [ "$proyecto" != "$(basename "$(pwd)")" ]; then
  echo "Retirando communitylab_web levantado fuera de este compose (proyecto: ${proyecto:-ninguno})"
  docker rm -f communitylab_web >/dev/null
fi

levantar() {
  # docker-compose v1 falla al recrear un contenedor con Docker reciente (KeyError: 'ContainerConfig') y lo deja
  # renombrado como <id>_communitylab_web y detenido: con v1 se borra antes y se crea de cero
  if [ "${COMPOSE[0]}" = docker-compose ]; then
    docker ps -aq -f name='^communitylab_web$' -f name='_communitylab_web$' | xargs -r docker rm -f >/dev/null
  fi
  "${COMPOSE[@]}" --env-file .imagen.env "${PERFIL[@]}" up -d --remove-orphans || return 1
  for _ in $(seq 1 30); do
    curl -fs -o /dev/null http://127.0.0.1:8000/api/openapi.json && return 0
    sleep 2
  done
  return 1
}

if levantar; then
  echo "Desplegado $IMAGEN"
  docker image prune -f >/dev/null
  exit 0
fi

echo "La app no levantó o no respondió con $IMAGEN"
"${COMPOSE[@]}" --env-file .imagen.env "${PERFIL[@]}" logs --tail 80 || true
if [ -n "$PREVIA" ] && [ "$PREVIA" != "$IMAGEN" ]; then
  echo "Volviendo a la versión anterior: $PREVIA"
  sed -i "s|^IMAGEN=.*|IMAGEN=$PREVIA|" .imagen.env
  if levantar; then echo "La app sigue en pie con $PREVIA"; else echo "Tampoco levantó la versión anterior"; fi
fi
exit 1
