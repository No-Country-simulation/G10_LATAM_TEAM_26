# 📋 Tablero de tareas — CommunityLab AI

**Cómo funciona esto:**

1. Elegí una tarea libre y anunciala en Discord: *"Tomo la Tarea N"* (una por persona; las marcadas 👥 aceptan pareja).
2. Trabajá en una rama: `git checkout -b tarea-N-tu-nombre`. Al terminar, abrí un Pull Request a `main`.
3. Cada tarea tiene un **✅ Definición de Hecho**: si eso se cumple, la tarea está terminada — no hace falta preguntar.
4. ¿Bloqueado más de 30 minutos? Escribí en el canal qué intentaste. No te quedes trabado en silencio.
5. Daily asincrónica: un mensaje por día en Discord — *qué hice / qué haré / qué me bloquea*.

**Antes de arrancar cualquier tarea (todos, 15 min):**

```bash
git clone https://github.com/No-Country-simulation/G10_LATAM_TEAM_26.git
cd G10_LATAM_TEAM_26
python -m venv .venv
.venv\Scripts\activate        # Linux/Mac: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env        # Linux/Mac: cp .env.example .env
```

Después leé `spec.md` (10 minutos): define los **Formatos A, P y B** — cómo se ven los datos entre módulos. Todo tu trabajo entrega o recibe datos en uno de esos formatos, y en `data/fixtures/` hay un ejemplo real de cada uno. **Regla de oro: si tu módulo funciona contra el fixture, funciona contra el sistema.**

---

## Tarea 1 · Obtener tu API key de Gemini
**👤 TODOS (10 min cada uno) · 🔓 Sin dependencias — hacela hoy**

**Contexto:** elegimos Google Gemini como LLM. Cada uno usa su propia key para desarrollo (así no compartimos límites de cuota).

**Pasos:**
1. Entrá a https://aistudio.google.com con tu cuenta de Google → botón **"Get API key"** → **Create API key**.
2. Pegala en tu `.env` local: `LLM_API_KEY=AIza...` (el `.env` NUNCA se sube — ya está protegido por `.gitignore`).
3. Verificá que funciona:
```python
import os, google.generativeai as genai
from dotenv import load_dotenv
load_dotenv()
genai.configure(api_key=os.environ["LLM_API_KEY"])
print(genai.GenerativeModel("gemini-2.0-flash").generate_content("hola").text)
```
4. Reportá en Discord los límites que muestre tu consola de AI Studio (requests por minuto y por día del free tier).

**✅ Definición de Hecho:** el script de prueba imprime una respuesta + reportaste tus límites en Discord.

---

## Tarea 2 · Prompts del sistema (notebook) 👥
**👤 1-2 personas (perfil: prompts / IA) · 🔗 Necesita: tu Tarea 1**

**Contexto:** el corazón inteligente del sistema son 3 prompts que analizan mensajes de la comunidad y generan contenido. Se desarrollan y prueban en un notebook, contra los 30 mensajes de ejemplo del fixture. **Este notebook además es un entregable oficial de la hackathon.**

**Entregable:** `ia/notebooks/exploracion_prompts.ipynb`

**Pasos:**
1. Cargá `data/fixtures/lote_ejemplo_formato_a.json` (30 mensajes simulados: logros, dudas, quejas, ruido).
2. **Prompt 1 — Analista:** recibe el texto de UN mensaje → devuelve JSON con `sentiment` (positive/neutral/negative), `topics` (lista, minúsculas), `intent` y `relevance_score` (0.00-1.00). El formato exacto de salida está en el spec, sección "Formato P" → bloque `analysis`. Usá `generation_config={"response_mime_type": "application/json"}` para que Gemini responda JSON puro.
3. **Prompt 2 — Detector:** recibe el mensaje + el análisis anterior → devuelve `type` (SUCCESS_STORY / FAQ / TREND / FEEDBACK / MILESTONE / NONE), `opportunity_score` (0.00-1.00) y `reason` (una frase justificando). Formato: spec → "Formato P" → bloque `opportunity`.
4. **Prompt 3 — Estratega:** recibe una oportunidad → genera el contenido según el tipo: post de LinkedIn (título, copy, hashtags), destaque de newsletter (sección, titular, resumen) o FAQ (tema, cuerpo). Formatos exactos: spec → "Formato B" → `activos[].contenido`. **Tip clave:** copiá los copys del fixture `paquete_ejemplo_formato_b.json` dentro del prompt como ejemplos ("escribí con este estilo:") — eso se llama few-shot y es lo que más mejora el resultado.
5. Corré los 3 prompts sobre TODOS los mensajes del fixture y revisá especialmente los casos trampa:
   - `MSG-0003` ("¡Felicitaciones Valeria!") → debe dar NONE con score bajo (es reacción, no historia).
   - `MSG-0015` (el meme) → NONE.
   - `MSG-0028` (el cambio de carrera a los 42) → SUCCESS_STORY con score ≥ 0.90.
   - `MSG-0029` (quinta duda sobre OCI) → idealmente TREND.

**✅ Definición de Hecho:** el notebook corre de punta a punta, los 4 casos trampa dan lo esperado, y las salidas tienen exactamente los campos del Formato P / Formato B.

---

## Tarea 3 · Pipeline LangGraph (con piezas simuladas)
**👤 1 persona (perfil: Python / lógica) · 🔓 Sin dependencias — NO necesita Gemini ni los prompts**

**Contexto:** el pipeline es un grafo de 4 pasos que procesa un lote completo. Para no esperar a que los prompts estén listos, los pasos de IA se **simulan**: en vez de llamar a Gemini, leen las respuestas ya hechas del fixture P. Así el pipeline completo funciona hoy, y en la semana 2 se enchufan los prompts reales cambiando 2 líneas.

**Entregable:** `orquestacion/pipeline.py` + `orquestacion/scoring.py`

**Pasos:**
1. Grafo LangGraph con 4 nodos: `analizar → enrutar → generar → empaquetar`.
2. Nodo `analizar` (SIMULADO): busca el mensaje por `message_id` en `data/fixtures/procesados_ejemplo_formato_p.json` y devuelve su bloque `analysis` + `opportunity`. Dejá un comentario `# TODO semana 2: reemplazar por llamada real a Gemini (Tarea 2)`.
3. Nodo `enrutar` (REAL — esto es código, no IA), en `scoring.py`:
   - score ≥ 0.90 → generar post LinkedIn + newsletter (multicanal)
   - 0.70 ≤ score < 0.90 → generar UN activo según el tipo (FAQ → faq; SUCCESS_STORY → post)
   - score < 0.70 → no generar nada, solo contar para las métricas
4. Nodo `generar` (SIMULADO): devuelve activos de ejemplo copiados del fixture B, con el `lineage` correcto (los ids del mensaje real que lo originó).
5. Nodo `empaquetar` (REAL): arma el paquete completo del Formato B — `resumen_comunidad` con los conteos reales del lote, lista de `activos`, todos con `estado_curaduria: "borrador"`.
6. Validá la salida con Pydantic contra el Formato B (modelos en el mismo archivo o en `orquestacion/modelos.py`).

**Cómo probar:** `python -m orquestacion.pipeline data/fixtures/lote_ejemplo_formato_a.json` debe imprimir un paquete JSON válido.

**✅ Definición de Hecho:** ese comando corre sin errores, el paquete pasa la validación Pydantic, y los conteos del resumen coinciden con el lote de entrada (30 procesados, ~12 oportunidades).

---

## Tarea 4 · Panel de curaduría (Streamlit) 👥
**👤 1-2 personas (perfil: frontend / UI) · 🔓 Sin dependencias — NO necesita el pipeline**

**Contexto:** la pantalla donde un humano revisa lo que la IA generó: aprueba, edita o descarta cada borrador. Se construye contra el fixture B — un paquete de ejemplo con 6 activos en distintos estados — sin esperar a que el pipeline exista.

**Entregable:** `app.py` en la raíz del repo

**Pasos:**
1. Cargá `data/fixtures/paquete_ejemplo_formato_b.json` al iniciar (guardalo en `st.session_state` para que los cambios persistan entre clics).
2. **Fila de métricas** arriba (`st.metric` en columnas): interacciones procesadas, sentimiento predominante, oportunidades detectadas — todo sale de `resumen_comunidad`.
3. **Pestañas por estado** (`st.tabs`): Pendientes (borrador) / Aprobados / Publicados / Descartados. El fixture trae activos en los 4 estados, así podés ver todas las pestañas con contenido.
4. **Tarjeta por activo** (un `st.container` con borde): badge del formato (post_linkedin 🔵 / destaque_newsletter 🟠 / sugerencia_faq 🟢), el contenido en un `st.text_area` editable, y botones según el estado:
   - borrador → [✅ Aprobar] [❌ Descartar]
   - aprobado → [🚀 Publicar] [↩️ Volver a borrador]
5. Los botones cambian `estado_curaduria` del activo en `session_state` y llaman `st.rerun()` para refrescar.
6. **Regla de oro: `app.py` NO tiene lógica de negocio** — no llama a Gemini, no calcula scores. Solo muestra datos y cambia estados.

**Cómo probar:** `streamlit run app.py` → aprobá un activo en Pendientes → debe aparecer en la pestaña Aprobados.

**✅ Definición de Hecho:** el panel muestra métricas y las 4 pestañas, el copy es editable, y el ciclo borrador → aprobado → publicado funciona con clics.

---

## Tarea 5 · Guardado de paquetes (versión local)
**👤 1 persona (ideal: quien luego tome OCI) · 🔓 Sin dependencias**

**Contexto:** los paquetes generados se guardan en Oracle Cloud (OCI), pero dejamos OCI para el final. Mientras tanto, este módulo guarda en una carpeta local **imitando exactamente** la estructura del bucket. La interfaz queda congelada: cuando llegue OCI, se reescribe por dentro y NADIE más cambia una línea.

**Entregable:** `storage/cliente.py`

**Pasos:**
1. Dos funciones con esta firma exacta (no cambiarla — es el enchufe que usarán pipeline y panel):
```python
def subir_paquete(paquete: dict, ruta: str) -> dict:
    """Guarda el paquete y devuelve {"bucket": ..., "ruta_objeto": ruta, "status": "guardado_con_exito"}"""

def leer_paquetes(prefijo: str) -> list[dict]:
    """Devuelve todos los paquetes cuya ruta empiece con el prefijo, ej: 'generated/'"""
```
2. Por dentro escriben/leen en `data/bucket_local/` replicando las rutas del spec: `generated/YYYY-MM-DD/PKG-xxx.json`, `reports/...`, etc.
3. `data/bucket_local/` va al `.gitignore` (agregala).
4. Probá el ciclo completo: subir el fixture B → leerlo con el prefijo `generated/` → verificar que vuelve idéntico.

**✅ Definición de Hecho:** el ciclo subir/leer funciona con el fixture B y las rutas replican la estructura del spec.

---

## Tarea 6 · Limpieza de datos: crudo → Formato A
**👤 1 persona (perfil: datos / Python) · 🔓 Sin dependencias**

**Contexto:** ya capturamos conversaciones reales de Discord (con el bot y con exports de DiscordKit). Esos datos vienen "sucios": mensajes de bots, saludos, duplicados, nombres completos. Este módulo los limpia y los convierte al Formato A — la puerta de entrada al pipeline.

**Entregable:** `ingesta/adaptador.py`

**Pasos:**
1. Función principal: `adaptar(archivo: str) -> dict` que detecta el formato de entrada y devuelve un lote en Formato A.
2. Soportar 2 formatos de entrada:
   - **JSONL del bot** (`data/raw/.../discord_capturas.jsonl`): un JSON por línea, con `author`, `content`, `channel`, etc.
   - **Export de DiscordKit** (JSON con `guild` / `channel` / `messages[]`).
3. **Filtrar** (en este orden): mensajes con `author.bot == true` → fuera; texto de menos de 10 caracteres → fuera; duplicados por id o texto idéntico → fuera.
4. **Anonimizar**:
   - Autor: "Carlos Zambrano" → "Carlos Z."; usernames tipo "carlosz15" → usar el display name si existe, sino "Usuario C."
   - En el texto: reemplazar emails por `[email]`, teléfonos por `[teléfono]`, menciones `@usuario` por `[mención]` (regex simples).
5. Armar el lote con la cabecera del Formato A (`origen_comunidad`, `periodo_referencia`, `fecha_ingesta`) y validarlo con Pydantic.
6. Probá con los DOS archivos reales que ya tenemos (pedíselos a Gregory: el JSONL del bot y el export de DiscordKit).

**Cómo probar:** `python -m ingesta.adaptador data/raw/2026-09-18/discord_capturas.jsonl` imprime el lote limpio y cuántos mensajes se filtraron.

**✅ Definición de Hecho:** ambos formatos de entrada producen un lote válido según Formato A, y el reporte dice cuántos mensajes entraron / se filtraron / quedaron.

---

## Tarea 7 · Integración (semana 2 — todavía NO tomarla)
**🔗 Necesita: Tareas 2+3+4+5+6 terminadas**

Reemplazar las piezas simuladas por las reales, en este orden: (1) prompts reales al pipeline, (2) pipeline guarda vía `storage/cliente.py`, (3) panel lee desde storage en vez del fixture, (4) datos reales del adaptador entran al pipeline. Se detalla en su momento — está listada para que se vea el camino completo.

---

## Tarea 8 · Oracle Cloud (al final — PERO crea tu cuenta ya)
**👤 1 responsable · 🔗 Necesita: Tarea 5 (la interfaz ya congelada)**

**Contexto:** guardar en OCI Object Storage es el único requisito de infraestructura **obligatorio** de la hackathon. La dejamos al final porque la Tarea 5 nos cubre mientras tanto — PERO la *cuenta* de Oracle tarda días en verificarse y pide tarjeta (no cobra), así que **ese trámite hacelo esta semana aunque la tarea sea la última**: https://www.oracle.com/cloud/free/

**Pasos (cuando llegue el momento):**
1. Crear el bucket `communitylab-bucket` en la consola OCI (región más cercana, Always Free).
2. Generar API key del SDK: Perfil → Mi perfil → Claves de API → Agregar — guardar el archivo de configuración en `~/.oci/config`.
3. Reescribir `subir_paquete()` y `leer_paquetes()` usando el SDK `oci` (ya está en requirements.txt), **misma firma** que la versión local.
4. Correr el pipeline completo y verificar los objetos en la consola web de OCI (captura de pantalla → Discord, la vamos a usar en la demo).
5. Documentar el setup completo en `docs/setup_oci.md` — la guía de despliegue es parte de la evaluación.

**✅ Definición de Hecho:** un paquete generado por el pipeline es visible en la consola web de OCI, y otra persona del equipo pudo reproducir el setup siguiendo `docs/setup_oci.md`.

---

## 🗺️ Mapa rápido — quién puede empezar YA

| Tarea | Estado | Puede arrancar |
|---|---|---|
| 1 · Key de Gemini | 🟢 libre | HOY — todos |
| 2 · Prompts 👥 | 🟢 libre | HOY (tras tu key) |
| 3 · Pipeline simulado | 🟢 libre | HOY |
| 4 · Panel Streamlit 👥 | 🟢 libre | HOY |
| 5 · Storage local | 🟢 libre | HOY |
| 6 · Limpieza de datos | 🟢 libre | HOY |
| 7 · Integración | 🔒 semana 2 | cuando 2-6 cierren |
| 8 · OCI | 🔒 al final | (la cuenta, creala ya) |

**Seis tareas arrancan hoy y ninguna espera a otra** — el secreto está en `data/fixtures/`: cada tarea trabaja contra ejemplos ya hechos de los datos que recibirá del resto. 8 personas: parejas en la 2 y la 4, individuales el resto.
