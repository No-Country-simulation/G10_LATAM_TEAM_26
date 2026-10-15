# Guía para quien trabaje en este repositorio (personas y agentes de IA)

CommunityLab AI convierte mensajes reales de una comunidad (Discord, archivos JSON) en borradores de contenido
(post de LinkedIn, destaque de newsletter, entrada de FAQ) que una persona revisa antes de publicar.
Más contexto: `README.md` (visión general) y `spec.md` (contratos de datos).

## Estructura

| Carpeta | Qué hay |
|---|---|
| `src/domain/` | Contratos Pydantic (Formato A de entrada, Formato B de salida). No depende de nada externo. |
| `src/adapters/` | Todo lo que habla con el exterior: Discord, LLM (Gemini con respaldo en Groq), OCI, base de datos. |
| `src/core/` | Motor de agentes (LangGraph): clasificación, redacción, empaquetado, salud de la comunidad. |
| `src/api/` | API FastAPI; también sirve el front compilado (`frontend/dist`). |
| `frontend/` | Panel web en React + Vite + TypeScript (vistas en `src/vistas/`). |
| `tests/unit/` | Pruebas con pytest. Corren sin claves ni red (modo simulado). |
| `deploy/`, `.github/workflows/` | Docker Compose de producción y CI/CD (pytest, build del front y de la imagen, despliegue desde `main`). |

## Comandos

```bash
python -m venv .venv && source .venv/bin/activate     # en Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m pytest -q                                    # debe pasar completo antes de abrir un PR

cd frontend && npm ci && npm run build && cd ..        # compila el front (tsc + vite)
uvicorn src.api.app:app --port 8000                    # API + front en http://localhost:8000
cd frontend && npm run dev                             # front con recarga en http://localhost:5173
```

Sin claves de IA se puede trabajar igual: en la pantalla de Clasificación, marca «Modo simulado».

## Reglas que no se negocian

- **Nunca subas secretos.** `.env`, llaves `.pem`, el wallet de OCI (`data/wallet/`), tokens de Discord y
  `data/discord/` están en `.gitignore`: déjalos ahí. Si algo así llegó a un commit, no basta con borrarlo en el
  siguiente: hay que rotarlo. Pasos en `docs/seguridad.md`.
- Los datos reales de la comunidad (`data/raw/`) pueden tener datos personales: no se suben ni se pegan en issues.
- Todo texto que llega al LLM pasa por `src/utils/sanitizer.py`. Si agregas una fuente nueva, haz lo mismo.
- `.env.example` documenta cada variable nueva (con valor de ejemplo, nunca uno real).

## Convenciones

- Nombres de código, mensajes de la interfaz y comentarios están en español; respeta ese estilo.
- Cambios pequeños y acotados, en una rama propia (`fix/...`, `feat/...`) y PR hacia `main`.
- Cada cambio de comportamiento lleva su prueba en `tests/unit/`. Las pruebas no deben llamar a servicios externos.
- El front debe compilar sin errores de `tsc` (`npm run build`), igual que en CI.
- Finales de línea: el repositorio usa LF (`.gitattributes`). Si Git te muestra decenas de archivos modificados sin
  que los hayas tocado, ejecuta una vez `git add --renormalize .` y revisa `git status`.
