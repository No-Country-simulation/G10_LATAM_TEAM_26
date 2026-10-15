# Despliegue continuo en OCI

El workflow `.github/workflows/ci-cd.yml` hace dos cosas:

- **CI, en cada push y pull request.** Corre `pytest` de la API, compila el front (`tsc` + `vite build`) y compila la imagen Docker.
- **CD, solo en push a `main`.** Publica la imagen en GitHub Container Registry (`ghcr.io/no-country-simulation/g10_latam_team_26`, para amd64 y arm64). Después entra por SSH a una VM de OCI, baja la imagen de ese commit, reinicia el contenedor y verifica que la API responda. Si la API no responde, el job falla y muestra los logs.

```
push a main ─► pytest + build del front ─► imagen a GHCR ─► SSH a la VM ─► docker compose pull/up ─► health check
```

La VM no compila nada. Solo descarga la imagen que ya pasó las pruebas.

## 1. Crear la VM (una sola vez)

1. En la consola de OCI ve a **Compute → Instances → Create instance**.
   - Imagen: **Ubuntu 22.04/24.04**.
   - Shape: **VM.Standard.A1.Flex** (Ampere, Always Free, por ejemplo 1 OCPU y 6 GB) o **VM.Standard.E2.1.Micro**.
   - Sube o genera una llave SSH. Esa es la llave que usarás tú. Para GitHub conviene crear otra (ver el paso 3).
2. Abre el puerto de la app:
   - Ve a **Networking → VCN → Security List** y agrega una regla de ingreso TCP **8000** desde `0.0.0.0/0`. En la VM actual (`159.112.137.35`) ese puerto ya está abierto. Usa **80/443** si pones un proxy delante.
   - Las imágenes de Ubuntu en OCI traen iptables cerrado. Ábrelo en la VM:
     ```bash
     sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 8000 -j ACCEPT
     sudo netfilter-persistent save
     ```
3. Instala Docker en la VM:
   ```bash
   curl -fsSL https://get.docker.com | sudo sh
   sudo usermod -aG docker $USER   # sal y vuelve a entrar por SSH
   ```

## 2. Preparar la app en la VM (una sola vez)

```bash
mkdir -p ~/communitylab/data
nano ~/communitylab/.env   # mismo formato que .env.example, con los valores reales
```

Si usas OCI Object Storage o Autonomous Database, copia la llave `.pem` y la wallet a `~/communitylab/data/` y usa las mismas rutas relativas del `.env` (`data/oci_api_key.pem`, `data/wallet/...`). Esa carpeta se monta como volumen, así que la base SQLite, los paquetes y las capturas se conservan entre despliegues. Como el volumen tapa los datos de ejemplo de la imagen, el workflow copia `data/fixtures/` a la VM en cada despliegue.

La wallet va descomprimida en `~/communitylab/data/wallet/Wallet_communitylabdb/`. Las rutas absolutas dentro del contenedor también sirven: `OCI_DB_WALLET_PATH=/app/data/wallet/Wallet_communitylabdb` y `OCI_KEY_FILE=/app/data/oci_api_key.pem`. Si el `.env` viene de Windows, quítale los fines de línea CRLF con `sed -i 's/\r$//' .env`.

**Acceso a la imagen.** No hay que configurar nada. El paquete de GHCR es privado (la organización no permite hacerlo público) y el workflow lo resuelve solo: en cada despliegue le pasa a la VM el `GITHUB_TOKEN` temporal del job, por stdin. `actualizar.sh` hace el login en una configuración de Docker temporal, baja la imagen y la borra al salir. GitHub invalida ese token cuando termina el job, así que en la VM no queda ninguna credencial guardada.

Solo si quieres bajar imágenes a mano (por ejemplo, para volver a una versión anterior sin pasar por Actions) necesitas un login propio en la VM con un token personal classic de solo lectura (scope `read:packages`):

```bash
docker login ghcr.io -u <tu-usuario>
```

## 3. Secretos en GitHub (una sola vez)

Crea una llave solo para el despliegue y autorízala en la VM:

```bash
ssh-keygen -t ed25519 -f oci_deploy -N "" -C "github-actions"
ssh-copy-id -i oci_deploy.pub ubuntu@<IP_PUBLICA>
ssh-keyscan -H <IP_PUBLICA>     # salida para OCI_SSH_KNOWN_HOSTS
```

Ve a GitHub → repo → **Settings → Environments → New environment `produccion`** y agrega estos secretos:

| Secreto | Valor |
|---|---|
| `OCI_HOST` | IP pública de la VM |
| `OCI_USER` | `ubuntu` (o `opc` en Oracle Linux) |
| `OCI_SSH_KEY` | Contenido de `oci_deploy` (la llave privada) |
| `OCI_SSH_KNOWN_HOSTS` | Salida de `ssh-keyscan` (recomendado; evita aceptar una huella falsa) |

Mientras falten `OCI_HOST` u `OCI_USER`, el job de despliegue se omite con un aviso y el CI sigue funcionando. En el environment `produccion` también puedes exigir una aprobación manual antes de cada despliegue (*Required reviewers*).

## Operación

- **Volver a una versión anterior.** Lo más simple es re-ejecutar en Actions el workflow de ese commit. A mano, en la VM: `cd ~/communitylab && IMAGEN=ghcr.io/no-country-simulation/g10_latam_team_26:<sha> bash actualizar.sh` (el workflow deja ahí una copia del script; necesita el login propio descrito arriba).
- **Logs.** Usa `docker logs -f communitylab_web`.
- **Sesiones.** Las sesiones del panel viven en memoria (`SESIONES` en `src/api/app.py`), así que cada despliegue cierra la sesión de quienes estén conectados.
- **HTTPS.** Para usar un dominio, pon Caddy o nginx delante del puerto 8000, o usa un Load Balancer de OCI con certificado.
