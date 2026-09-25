# 📐 spec.md — Formatos de datos acordados (CommunityLab AI)

**Estado:** 🧊 CONGELADO (pendiente de ratificación en la reunión del equipo)
**Versión:** 1.0
**Última actualización:** 2026-09-25

## Propósito y reglas de uso

Este documento define las **interfaces JSON entre los módulos del sistema**. Es el acuerdo que permite que todos los carriles (ingesta, IA, orquestación, cloud, frontend) desarrollen **en paralelo contra mocks**, sin esperarse entre sí.

**Reglas:**

1. Una vez ratificado, ningún módulo cambia un formato unilateralmente. Cambios = PR a este archivo + acuerdo de los carriles afectados + subir la versión.
2. Cada módulo **valida con Pydantic** lo que recibe y lo que entrega. Si un JSON no cumple el formato, el error es del módulo emisor.
3. Los campos marcados `opcional` pueden faltar; todos los demás son obligatorios.
4. Fechas siempre en **ISO 8601 UTC** (`2026-09-18T15:30:00Z`). Identificadores según el patrón de cada tipo: `MSG-####` (lo asigna la ingesta), `OPP-###` y `POST-###` / `NEWS-###` / `FAQ-###` (los asigna el núcleo, correlativos por lote).

**Mapa de formatos en el pipeline:**

```
[Ingesta] ──Formato A──> [Núcleo IA/Orquestación] ──Formato B──> [OCI Storage] ──> [Panel Streamlit]
                                    │
                          (Formato P: análisis por mensaje,
                           interno del núcleo)
```

**Módulos del repositorio:** ingesta en `src/adapters/ingestion/`, núcleo (grafo LangGraph) en `src/core/`, almacenamiento en `src/adapters/cloud/` y panel en `run_app.py` + `src/ui/`. Los contratos Pydantic de estos formatos están en `src/domain/schemas.py`.

---

## 🅰️ FORMATO A — Lote de interacciones

**Emisor:** módulo de Ingesta (`src/adapters/ingestion/`)
**Receptor:** núcleo de orquestación (`src/core/`)
**Descripción:** lote de interacciones de la comunidad ya **normalizadas, limpias, deduplicadas y anonimizadas**. Es la única puerta de entrada al pipeline — da igual si el origen fue JSON, CSV o el bot de Discord: todo se convierte a esta forma.

### Estructura

```json
{
  "formato_version": "1.0",
  "origen_comunidad": "Discord_Grupo_ONE_G10",
  "periodo_referencia": "Semana_04",
  "fecha_ingesta": "2026-09-18T15:30:00Z",
  "interacciones": [
    {
      "message_id": "MSG-8921",
      "source": "discord",
      "channel": "logros-y-empleos",
      "timestamp": "2026-09-17T15:30:00Z",
      "autor": "Mariana S.",
      "tipo_declarado": "testimonio",
      "texto": "Comunidad, quedé seleccionada para el puesto de Desarrolladora Junior de IA! El proyecto del curso de LangChain y OCI que construí en mi portfolio marcó toda la diferencia en la entrevista técnica.",
      "metadata": {
        "reacciones": 24,
        "respuestas": 7
      }
    }
  ]
}
```

### Campos

| Campo | Tipo | Reglas |
|---|---|---|
| `formato_version` | string | Versión de este formato ("1.0") |
| `origen_comunidad` | string | Identificador de la comunidad/servidor |
| `periodo_referencia` | string | Etiqueta del lote (ej. "Semana_04") |
| `fecha_ingesta` | datetime | Momento en que el lote fue procesado por ingesta |
| `interacciones[]` | array | Mínimo 1 elemento |
| `interacciones[].message_id` | string | Patrón `MSG-####`, único en el lote |
| `interacciones[].source` | enum | `discord` \| `slack` \| `forum` \| `form` \| `csv` \| `json` |
| `interacciones[].channel` | string | Nombre del canal sin `#` |
| `interacciones[].timestamp` | datetime | Fecha original del mensaje |
| `interacciones[].autor` | string | **Anonimizado**: nombre + inicial, o alias (nunca datos de contacto) |
| `interacciones[].tipo_declarado` | enum, **opcional** (default `otro`) | `testimonio` \| `pregunta_tecnica` \| `feedback` \| `logro` \| `conversacion` \| `otro` — pista opcional, NO es tarea de ingesta clasificar; la clasificación real la hace el Opportunity Detector |
| `interacciones[].texto` | string | Texto limpio, sin menciones crudas ni PII |
| `interacciones[].metadata` | object, opcional | `reacciones` (int), `respuestas` (int) — insumo del score de engagement |

### Responsabilidades de Ingesta (antes de emitir)

- ⏳ Deduplicar por `message_id` y por texto casi idéntico *(pendiente de implementar)*
- ✅ Anonimizar PII: emails, teléfonos, apellidos completos, handles *(el núcleo vuelve a enmascarar el texto antes de enviarlo a la IA)*
- 🟡 Descartar mensajes vacíos o de menos de 10 caracteres ("gracias!", "+1") *(hoy se descartan los vacíos; falta el mínimo de 10)*
- ✅ Validar el lote completo contra este formato con Pydantic

---

## 🅿️ FORMATO P — Objeto procesado (interno del núcleo)

**Emisor:** la etapa de clasificación del núcleo — por defecto un clasificador compacto (análisis y detección en una llamada por lote); en modo completo, analista + detector
**Receptor:** la etapa de redacción del núcleo y el panel (vista de Detección & Scoring)
**Descripción:** cada interacción, tras pasar por análisis y detección de oportunidad. Es interno al carril de orquestación, pero se congela porque el carril de IA escribe los prompts que lo producen.

```json
{
  "tracking": {
    "message_id": "MSG-8921",
    "source": "discord",
    "channel": "logros-y-empleos",
    "timestamp": "2026-09-17T15:30:00Z"
  },
  "analysis": {
    "sentiment": "positive",
    "topics": ["empleo", "langchain", "oci"],
    "intent": "compartir_logro",
    "relevance_score": 0.94
  },
  "opportunity": {
    "opportunity_id": "OPP-021",
    "type": "SUCCESS_STORY",
    "opportunity_score": 0.94,
    "reason": "Reporta su contratación en un puesto junior de IA gracias a un proyecto del curso."
  }
}
```

| Campo | Tipo | Reglas |
|---|---|---|
| `analysis.sentiment` | enum | `positive` \| `neutral` \| `negative` |
| `analysis.topics[]` | array de string | 1 a 5 temas, en minúsculas (el clasificador compacto usa 1 a 3); `social` para charla social |
| `analysis.intent` | string | Intención detectada (ej. `compartir_logro`, `pedir_ayuda`); puede ir vacío en el modo compacto |
| `analysis.relevance_score` | float | 0.00 – 1.00; igual al `opportunity_score` |
| `opportunity.opportunity_id` | string \| null | Patrón `OPP-###` si el mensaje supera el umbral de su tipo; `null` si no es oportunidad |
| `opportunity.type` | enum | `SUCCESS_STORY` \| `MILESTONE` \| `FAQ` \| `OPERATIONAL_QUERY` \| `FEEDBACK` \| `NONE` (ver taxonomía) |
| `opportunity.opportunity_score` | float | 0.00 – 1.00 |
| `opportunity.reason` | string | Justificación en una frase (auditable por el curador) |

**Taxonomía de tipos:**

| Tipo | Qué es |
|---|---|
| `SUCCESS_STORY` | El autor consiguió trabajo, fue seleccionado o hizo una transición profesional |
| `MILESTONE` | El autor terminó un curso, certificación o proyecto destacable |
| `FAQ` | Duda técnica o conceptual con contexto suficiente, útil para muchos miembros |
| `OPERATIONAL_QUERY` | Duda logística sobre clases, grabaciones, links, horarios, accesos o la plataforma; su respuesta depende de información interna del programa |
| `FEEDBACK` | Opinión, sugerencia, queja o crítica sobre cursos, clases, mentorías o la plataforma |
| `NONE` | Charla social, memes, felicitaciones, anuncios y preguntas sin contexto suficiente |

Las tendencias no son un tipo de mensaje: se calculan por agregación en el Formato B (`tendencias_detectadas`).

**Reglas de enrutamiento (umbral por tipo):** el umbral lo aplica el código, no el modelo.

| Tipo | Umbral | Borradores generados |
|---|---|---|
| `SUCCESS_STORY` | ≥ 0.80 | Post de LinkedIn + destacado del newsletter |
| `MILESTONE` | ≥ 0.80 | Post de LinkedIn |
| `FAQ` | ≥ 0.70 | Entrada de FAQ |
| `OPERATIONAL_QUERY` · `FEEDBACK` · `NONE` | — | Solo analítica; nunca generan borrador (se cuentan en el resumen para el equipo del programa) |

---

## 🅱️ FORMATO B — Paquete de activos de distribución

**Emisor:** núcleo de orquestación (`src/core/`)
**Receptores:** módulo de almacenamiento (`src/adapters/cloud/`) y panel de curaduría (`run_app.py` + `src/ui/`)
**Descripción:** resultado consolidado del procesamiento de un lote: resumen de la comunidad + activos generados con su estado de curaduría + referencia de almacenamiento. Su forma sigue el ejemplo de respuesta del brief de la hackathon, extendida con trazabilidad y estados.

### Estructura

```json
{
  "formato_version": "1.0",
  "status": "exito",
  "paquete_id": "PKG-2026-S04-160000",
  "origen_comunidad": "Discord_Grupo_ONE_G10",
  "periodo_referencia": "Semana_04",
  "fecha_generacion": "2026-09-18T16:00:00Z",
  "resumen_comunidad": {
    "total_interacciones_procesadas": 24,
    "sentimiento_predominante": "positive",
    "distribucion_sentimiento": { "positive": 15, "neutral": 7, "negative": 2 },
    "temas_principales": ["empleo", "langgraph", "oci"],
    "oportunidades_detectadas": 5,
    "consultas_operativas": 2,
    "feedback_recibido": 3,
    "tendencias_detectadas": [
      { "tema": "oci", "menciones": 6, "descripcion": "6 mensajes sobre oci en semana 04 (4 preguntas técnicas, 1 historia de éxito, 1 feedback)" }
    ]
  },
  "activos": [
    {
      "activo_id": "POST-034",
      "formato": "post_linkedin",
      "estado_curaduria": "borrador",
      "origen": {
        "message_id": "MSG-8921",
        "opportunity_id": "OPP-021",
        "channel": "logros",
        "autor": "Mariana S.",
        "message": "Comunidad, quedé seleccionada para el puesto de Desarrolladora Junior de IA!...",
        "sentiment": "positive",
        "topics": ["empleo", "langchain", "oci"],
        "type": "SUCCESS_STORY",
        "score": 0.94,
        "reason": "Logro concreto ya ocurrido, contado con detalles."
      },
      "contenido": {
        "titulo": "Un proyecto del curso, una entrevista ganada",
        "copy": "Un proyecto con LangChain y OCI hecho en el curso. Una entrevista técnica. Y un puesto nuevo en desarrollo de IA.\n\n...",
        "hashtags": ["#TalentosTech", "#InteligenciaArtificial", "#OracleCloud", "#CarreraDev"],
        "canal_recomendado": "LinkedIn Oficial",
        "potencial_engagement": "alto"
      }
    },
    {
      "activo_id": "NEWS-012",
      "formato": "destaque_newsletter",
      "estado_curaduria": "borrador",
      "origen": {
        "message_id": "MSG-8921",
        "opportunity_id": "OPP-021",
        "channel": "logros",
        "autor": "Mariana S.",
        "message": "Comunidad, quedé seleccionada para el puesto de Desarrolladora Junior de IA!...",
        "sentiment": "positive",
        "topics": ["empleo", "langchain", "oci"],
        "type": "SUCCESS_STORY",
        "score": 0.94,
        "reason": "Logro concreto ya ocurrido, contado con detalles."
      },
      "contenido": {
        "seccion": "Logro de la Semana",
        "titular": "Un portfolio con IA en Oracle Cloud abre su primer empleo",
        "resumen": "La entrevista técnica giró en torno al proyecto con LangChain y OCI del curso, y eso definió la contratación."
      }
    },
    {
      "activo_id": "FAQ-007",
      "formato": "sugerencia_faq",
      "estado_curaduria": "borrador",
      "origen": { "message_id": "MSG-8934", "opportunity_id": "OPP-022", "channel": "dudas-langgraph", "autor": "Lucas A.", "message": "…", "sentiment": "neutral", "topics": ["langgraph"], "type": "FAQ", "score": 0.82, "reason": "…" },
      "contenido": {
        "tema": "¿Cómo crear nodos de reintento en LangGraph?",
        "cuerpo": "Cuando la respuesta del LLM necesita reintento, puedes definir un nodo router que evalúe la salida...\n1. ...\n2. ...",
        "origen_descripcion": "Duda frecuente planteada en el canal de soporte"
      }
    }
  ],
  "almacenamiento_oci": {
    "bucket": "communitylab-bucket",
    "ruta_objeto": "generated/2026-09-18/PKG-2026-S04-160000.json",
    "status": "guardado_con_exito"
  }
}
```

### Campos

| Campo | Tipo | Reglas |
|---|---|---|
| `status` | enum | `exito` \| `parcial` \| `error` — `parcial` si quedaron mensajes sin analizar o piezas sin redactar, y también mientras los borradores se redactan en segundo plano |
| `paquete_id` | string | Patrón `PKG-<año>-S<semana>-<HHMMSS>` (hora UTC de generación), único sin consultar el almacenamiento |
| `resumen_comunidad` | object | Métricas del lote (alimenta el dashboard): total procesado, sentimiento predominante y distribución, hasta 5 temas principales, `oportunidades_detectadas`, `consultas_operativas` y `feedback_recibido` (conteos de esos tipos, para el equipo del programa) y `tendencias_detectadas` |
| `resumen_comunidad.tendencias_detectadas` | array | Hasta 5 `{tema, menciones, descripcion}` que el sistema calcula por AGREGACIÓN, no por IA: temas con **2 o más** menciones en el lote (sin contar `social`), con el desglose por tipo de mensaje en la descripción |
| `activos[]` | array | 0 o más activos; cada uno autocontenido |
| `activos[].activo_id` | string | `POST-###` (LinkedIn) \| `NEWS-###` (newsletter) \| `FAQ-###`, correlativos por formato dentro del paquete |
| `activos[].formato` | enum | `post_linkedin` \| `destaque_newsletter` \| `sugerencia_faq` |
| `activos[].estado_curaduria` | enum | `borrador` \| `aprobado` \| `publicado` \| `descartado` — **siempre nace como `borrador`**; solo el panel lo cambia |
| `activos[].origen` | object | **Autocontenido**: todo lo que la UI necesita del mensaje que dio nacimiento a la pieza — `message_id`, `opportunity_id`, `channel`, `autor`, `message` (texto original), `sentiment`, `topics`, `type`, `score`, `reason`. El panel no busca en ningún otro archivo |
| `activos[].contenido` | object | Estructura según `formato` (ver ejemplos arriba) |
| `almacenamiento_oci` | object | Referencia del objeto en el bucket: `bucket`, `ruta_objeto` y `status` |
| `almacenamiento_oci.status` | string | `pendiente` (recién generado, aún sin guardar) \| `guardado_local` (copia local en `data/processed/<ruta_objeto>`, mientras no esté la subida al bucket) \| `guardado_con_exito` (subido a OCI) |

### Reglas de curaduría (transiciones de estado)

```
borrador ──aprobar──> aprobado ──publicar──> publicado
borrador ──descartar──> descartado
aprobado ──editar──> borrador (vuelve a revisión)
```

- El **panel** es el único módulo que muta `estado_curaduria`. Al hacerlo, persiste el paquete actualizado de vuelta al bucket (mismo `ruta_objeto`, sobrescribe).
- El **pipeline** nunca genera activos con estado distinto de `borrador`.
- ⏳ La transición `aprobado → publicado` está pendiente en el panel; hoy se puede aprobar, editar, regenerar y descartar.

---

## 🗂️ Convención de rutas en el bucket OCI

| Etapa | Ruta | Contenido |
|---|---|---|
| Crudo | `raw/YYYY-MM-DD/<archivo original>` | Lote tal como llegó (pre-Formato A) |
| Procesado | `processed/YYYY-MM-DD/<lote>.json` | Lote en Formato A + objetos en Formato P |
| Generado | `generated/YYYY-MM-DD/<paquete_id>.json` | Paquete completo en Formato B |
| Reportes | `reports/YYYY-MM-DD/<reporte>.json` | Consolidados de salud comunitaria |

Hoy se usa la ruta `generated/`; `raw/`, `processed/` y `reports/` quedan reservadas para la integración con el bucket.

---

## 🧪 Fixtures compartidos (mocks oficiales)

Para que todos los carriles usen **los mismos datos falsos**, el repo incluye en `data/fixtures/`:

- `lote_ejemplo_formato_a.json` — 30 interacciones simuladas válidas según Formato A
- `procesados_ejemplo_formato_p.json` — las mismas interacciones ya analizadas (17 oportunidades)
- `paquete_ejemplo_formato_b.json` — un paquete completo con 6 activos en los cuatro estados de curaduría

**Regla:** si tu módulo funciona contra el fixture, funciona contra el sistema. Cualquier duda sobre "¿cómo viene este campo?" se responde mirando el fixture, no preguntando en el canal. Un test (`tests/unit/test_contrato_formato_b.py`) valida los fixtures contra los contratos, así que un cambio de formato sin actualizarlos hace fallar las pruebas.

---

## 📋 Registro de cambios

| Versión | Fecha | Cambio | Aprobado por |
|---|---|---|---|
| 1.0 | 2026-09-18 | Versión inicial: formatos A, P y B | *pendiente de ratificación en reunión* |
| 1.0 (rev. 22/09) | 2026-09-22 | Formato B: `lineage` → `origen` autocontenido (fusión con el diseño del panel); `tendencias_detectadas` en el resumen; `tipo_declarado` pasa a opcional. Se mantiene como 1.0 por decisión del equipo (nada publicado con la forma anterior) | Gregory |
| 1.0 (rev. 25/09) | 2026-09-25 | Formato P: taxonomía `SUCCESS_STORY`, `MILESTONE`, `FAQ`, `OPERATIONAL_QUERY`, `FEEDBACK`, `NONE` (sale `TREND`: las tendencias se calculan por agregación) y enrutamiento por umbral de tipo; `opportunity_id` solo para oportunidades. Formato B: `consultas_operativas` y `feedback_recibido` en el resumen, tendencias con 2+ menciones, `paquete_id` con la hora y estados de `almacenamiento_oci`. Ids `OPP-###` / `POST-###`, rutas de módulos en `src/` y fixtures alineados. Se mantiene como 1.0 por decisión del equipo | Gregory |
