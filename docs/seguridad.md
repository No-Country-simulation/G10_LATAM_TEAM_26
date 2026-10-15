# Seguridad: qué hacer si una credencial llegó al repositorio

Regla general: **una credencial que estuvo en un commit público hay que tratarla como filtrada**. Borrar el archivo
o la rama no basta, porque los forks, las cachés de GitHub y las copias locales conservan los commits. Lo que
resuelve el problema es **rotar** la credencial; limpiar el historial es un complemento.

## Caso conocido: wallet de OCI en `65018c0`

El commit `65018c0` subió `data/wallet/Wallet_communitylabdb/` (`cwallet.sso`, `ewallet.p12`, `ewallet.pem`,
`keystore.jks`, `truststore.jks`, `tnsnames.ora`, `sqlnet.ora`…). Solo está en la rama
`feature/oci-database-multiformat-integration`; `main` no lo contiene.

El wallet por sí solo no da acceso a la base (falta usuario y contraseña), pero revela el host y el servicio de la
base y permite abrir la conexión mTLS. Aun así se rota.

### 1. Rotar (lo que de verdad cierra el problema)

1. Consola de OCI → **Autonomous Database** → la base → **Database connection** → **Rotate wallet**.
   Rotar invalida el wallet anterior. Descarga el nuevo.
2. En la misma base: **More actions → Administrator password** y cambia la contraseña de `ADMIN`.
   Actualiza `OCI_DB_PASSWORD` en el `.env` local y en el del servidor.
3. Opcional pero recomendable: en **Network → Access control list** limita la base a la IP del servidor y de
   quien desarrolla.
4. Copia el wallet nuevo a `data/wallet/Wallet_communitylabdb/` (ya está en `.gitignore`) y, en el servidor, a la
   carpeta `data/` que monta Docker.

### 2. Quitar el commit del repositorio

Lo hace quien administre el repositorio, y conviene avisar antes al equipo porque reescribe el historial.

```bash
# 1. Cerrar o rehacer el PR #6 y borrar la rama
git push origin --delete feature/oci-database-multiformat-integration

# 2. En un clon nuevo (mirror), sacar la carpeta de todo el historial
pip install git-filter-repo
git clone --mirror https://github.com/No-Country-simulation/G10_LATAM_TEAM_26.git limpio.git
cd limpio.git
git filter-repo --path data/wallet --invert-paths
git push --force --all && git push --force --tags
```

Después, cada integrante debe volver a clonar (o `git fetch --all && git reset --hard origin/<rama>` en sus
ramas), y no volver a subir ramas viejas que contengan el commit. Pide a GitHub Support que purgue las vistas en
caché de los commits si el repositorio es público.

### 3. Comprobar que quedó limpio

```bash
git log --all --name-only --pretty=format: | sort -u | grep -Ei 'wallet|\.pem|\.p12|\.sso|\.jks|\.env$'
```

No debe imprimir nada.

## Antes de cada PR

- `git diff --cached --name-only` no incluye `.env`, `*.pem`, `data/wallet/`, `data/discord/` ni `data/raw/`.
- Buscar valores pegados por error: `git diff --cached | grep -Ei 'AIza|gsk_|ocid1\.|BEGIN .*PRIVATE KEY|token'`.
- Si usas un archivo `.env` de prueba, comprueba que `git status` no lo lista (debe estar ignorado).

## Ya resuelto en el código

- **HTTPS.** `deploy/Caddyfile` y el perfil `https` del compose de producción. Falta activarlo en la VM con
  `DOMINIO` en el `.env` (ver `docs/despliegue-oci.md`); mientras no se active, el panel sigue por HTTP.
- **Token fuera de la URL.** Las imágenes se piden con una cookie `HttpOnly` y `SameSite=Strict`; ya no hay
  `?token=` en ninguna URL.
- **Sesiones y login.** Caducan por inactividad (`SESION_HORAS`), el ingreso tiene límite de intentos
  (`LOGIN_INTENTOS_MAX`) y la clave del admin se compara en tiempo constante.

## Pendientes de seguridad conocidos (por prioridad)

1. **Activar el HTTPS en producción** y cerrar el puerto 8510 en la Security List de OCI.
2. **Sesiones en memoria**: se pierden al reiniciar la API. Con varias réplicas habría que guardarlas en la base.
3. **Anonimización**: `src/utils/sanitizer.py` solo enmascara correos, teléfonos y menciones de Discord. Los nombres
   dentro del texto libre llegan al LLM.
4. **Dependencias sin fijar**: `requirements.txt` usa `>=`. Fijar versiones (o un lockfile) para que CI y las máquinas
   locales coincidan.
