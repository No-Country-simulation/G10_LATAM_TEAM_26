# 📐 spec.md — Formatos de datos acordados (CommunityLab AI)

**Estado:** 🧊 CONGELADO (pendiente de ratificación en la reunión del equipo)
**Versión:** 1.0
**Última actualización:** 2026-09-18

## Propósito y reglas de uso

Este documento define las **interfaces JSON entre los módulos del sistema**. Es el acuerdo que permite que todos los carriles (ingesta, IA, orquestación, cloud, frontend) desarrollen **en paralelo contra mocks**, sin esperarse entre sí.

**Reglas:**

1. Una vez ratificado, ningún módulo cambia un formato unilateralmente. Cambios = PR a este archivo + acuerdo de los carriles afectados + subir la versión.
2. Cada módulo **valida con Pydantic** lo que recibe y lo que entrega. Si un JSON no cumple el formato, el error es del módulo emisor.
3. Los campos marcados `opcional` pueden faltar; todos los demás son obligatorios.
4. Fechas siempre en **ISO 8601 UTC** (`2026-09-18T15:30:00Z`). Identificadores según el patrón de cada tipo (`MSG-####`, `OPP-####`, `POST-####`).

**Mapa de formatos en el pipeline:**

```
[Ingesta] ──Formato A──> [Núcleo IA/Orquestación] ──Formato B──> [OCI Storage] ──> [Panel Streamlit]
                                    │
                          (Formato P: objeto procesado,
                           interno entre los 3 agentes)
```

---

## 🅰️ FORMATO A — Lote de interacciones

**Emisor:** módulo de Ingesta (`ingesta/`)
**Receptor:** núcleo de orquestación (`orquestacion/`)
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
| `interacciones[].tipo_declarado` | enum | `testimonio` \| `pregunta_tecnica` \| `feedback` \| `logro` \| `conversacion` \| `otro` — clasificación *heurística* de ingesta; el análisis real lo hace el Agente 1 |
| `interacciones[].texto` | string | Texto limpio, sin menciones crudas ni PII |
| `interacciones[].metadata` | object, opcional | `reacciones` (int), `respuestas` (int) — insumo del score de engagement |

### Responsabilidades de Ingesta (antes de emitir)

- ✅ Deduplicar por `message_id` y por texto casi idéntico
- ✅ Anonimizar PII: emails, teléfonos, apellidos completos, handles
- ✅ Descartar mensajes vacíos o de menos de 10 caracteres ("gracias!", "+1")
- ✅ Validar el lote completo contra este formato con Pydantic

---

## 🅿️ FORMATO P — Objeto procesado (interno del núcleo)

**Emisor/Receptor:** los 3 agentes del núcleo entre sí (Analyst → Detector → Strategist)
**Descripción:** cada interacción, tras pasar por análisis y detección de oportunidad. Basado en la sección 6 de la especificación técnica del proyecto. Es interno al carril de orquestación, pero se congela porque el carril de IA escribe los prompts que lo producen.

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
    "relevance_score": 0.95
  },
  "opportunity": {
    "opportunity_id": "OPP-021",
    "type": "SUCCESS_STORY",
    "opportunity_score": 0.94,
    "reason": "La usuaria reporta su contratación exitosa como Desarrolladora Junior de IA."
  }
}
```

| Campo | Tipo | Reglas |
|---|---|---|
| `analysis.sentiment` | enum | `positive` \| `neutral` \| `negative` |
| `analysis.topics[]` | array de string | 1 a 5 temas, en minúsculas |
| `analysis.intent` | string | Intención detectada (ej. `compartir_logro`, `pedir_ayuda`) |
| `analysis.relevance_score` | float | 0.00 – 1.00 |
| `opportunity.opportunity_id` | string | Patrón `OPP-####` |
| `opportunity.type` | enum | `SUCCESS_STORY` \| `FAQ` \| `TREND` \| `FEEDBACK` \| `MILESTONE` \| `NONE` |
| `opportunity.opportunity_score` | float | 0.00 – 1.00 |
| `opportunity.reason` | string | Justificación en una frase (auditable por el curador) |

**Reglas de enrutamiento (Opportunity Score):**

| Score | Acción |
|---|---|
| 0.90 – 1.00 | Generación multicanal: LinkedIn + Newsletter |
| 0.70 – 0.89 | Borrador único según tipo (`FAQ` → FAQ educativa; `SUCCESS_STORY` → LinkedIn) |
| 0.00 – 0.69 | Solo analítica; NO genera borrador |

---

## 🅱️ FORMATO B — Paquete de activos de distribución

**Emisor:** núcleo de orquestación (`orquestacion/`)
**Receptores:** módulo de storage (`storage/`) y panel de curaduría (`app.py`)
**Descripción:** resultado consolidado del procesamiento de un lote: resumen de la comunidad + activos generados con su estado de curaduría + referencia de almacenamiento. Su forma sigue el ejemplo de respuesta del brief de la hackathon, extendida con trazabilidad y estados.

### Estructura

```json
{
  "formato_version": "1.0",
  "status": "exito",
  "paquete_id": "PKG-2026-S04-001",
  "origen_comunidad": "Discord_Grupo_ONE_G10",
  "periodo_referencia": "Semana_04",
  "fecha_generacion": "2026-09-18T16:00:00Z",
  "resumen_comunidad": {
    "total_interacciones_procesadas": 24,
    "sentimiento_predominante": "positive",
    "distribucion_sentimiento": { "positive": 15, "neutral": 7, "negative": 2 },
    "temas_principales": ["contratacion/logros", "langgraph", "oci"],
    "oportunidades_detectadas": 5
  },
  "activos": [
    {
      "activo_id": "POST-034",
      "formato": "post_linkedin",
      "estado_curaduria": "borrador",
      "lineage": {
        "opportunity_id": "OPP-021",
        "message_id": "MSG-8921"
      },
      "contenido": {
        "titulo": "De la Comunidad al Mercado: el impacto de los proyectos prácticos de IA",
        "copy": "Nada nos da más orgullo que ver a nuestros talentos conquistando el mercado tech! 🚀 Nuestra estudiante Mariana acaba de ser contratada como Desarrolladora Junior de IA...",
        "hashtags": ["#TalentosTech", "#InteligenciaArtificial", "#OracleCloud", "#CarreraDev"],
        "canal_recomendado": "LinkedIn Oficial",
        "potencial_engagement": "alto"
      }
    },
    {
      "activo_id": "NEWS-012",
      "formato": "destaque_newsletter",
      "estado_curaduria": "borrador",
      "lineage": {
        "opportunity_id": "OPP-021",
        "message_id": "MSG-8921"
      },
      "contenido": {
        "seccion": "Logro de la Semana",
        "titular": "Estudiante consigue empleo dev con portfolio de IA en Oracle Cloud",
        "resumen": "Mariana obtuvo su primera oportunidad como Dev Jr de IA destacando proyectos desarrollados durante la formación."
      }
    },
    {
      "activo_id": "FAQ-007",
      "formato": "sugerencia_faq",
      "estado_curaduria": "borrador",
      "lineage": {
        "opportunity_id": "OPP-022",
        "message_id": "MSG-8934"
      },
      "contenido": {
        "tema": "Tip Rápido: cómo crear nodos de reintento en LangGraph",
        "cuerpo": "Cuando la respuesta del LLM necesita reintento, definí un nodo router que evalúe la salida...",
        "origen_descripcion": "Duda frecuente planteada en el canal de soporte"
      }
    }
  ],
  "almacenamiento_oci": {
    "bucket": "communitylab-bucket",
    "ruta_objeto": "generated/2026-09-18/PKG-2026-S04-001.json",
    "status": "guardado_con_exito"
  }
}
```

### Campos

| Campo | Tipo | Reglas |
|---|---|---|
| `status` | enum | `exito` \| `parcial` \| `error` |
| `paquete_id` | string | Patrón `PKG-<año>-S<semana>-###`, único |
| `resumen_comunidad` | object | Métricas del lote — es lo que alimenta el dashboard |
| `activos[]` | array | 0 o más activos; cada uno autocontenido |
| `activos[].activo_id` | string | `POST-####` (LinkedIn) \| `NEWS-####` (newsletter) \| `FAQ-####` |
| `activos[].formato` | enum | `post_linkedin` \| `destaque_newsletter` \| `sugerencia_faq` |
| `activos[].estado_curaduria` | enum | `borrador` \| `aprobado` \| `publicado` \| `descartado` — **siempre nace como `borrador`**; solo el panel lo cambia |
| `activos[].lineage` | object | Trazabilidad obligatoria: `opportunity_id` + `message_id` de origen |
| `activos[].contenido` | object | Estructura según `formato` (ver ejemplos arriba) |
| `almacenamiento_oci` | object | Referencia real del objeto en el bucket |

### Reglas de curaduría (transiciones de estado)

```
borrador ──aprobar──> aprobado ──publicar──> publicado
borrador ──descartar──> descartado
aprobado ──editar──> borrador (vuelve a revisión)
```

- El **panel** es el único módulo que muta `estado_curaduria`. Al hacerlo, persiste el paquete actualizado de vuelta al bucket (mismo `ruta_objeto`, sobrescribe).
- El **pipeline** nunca genera activos con estado distinto de `borrador`.

---

## 🗂️ Convención de rutas en el bucket OCI

| Etapa | Ruta | Contenido |
|---|---|---|
| Crudo | `raw/YYYY-MM-DD/<archivo original>` | Lote tal como llegó (pre-Formato A) |
| Procesado | `processed/YYYY-MM-DD/<lote>.json` | Lote en Formato A + objetos en Formato P |
| Generado | `generated/YYYY-MM-DD/<paquete_id>.json` | Paquete completo en Formato B |
| Reportes | `reports/YYYY-MM-DD/<reporte>.json` | Consolidados de salud comunitaria |

---

## 🧪 Fixtures compartidos (mocks oficiales)

Para que todos los carriles usen **los mismos datos falsos**, el repo incluye en `data/fixtures/`:

- `lote_ejemplo_formato_a.json` — 30 interacciones simuladas válidas según Formato A
- `procesados_ejemplo_formato_p.json` — las mismas interacciones ya analizadas
- `paquete_ejemplo_formato_b.json` — un paquete completo con 4 activos en distintos estados

**Regla:** si tu módulo funciona contra el fixture, funciona contra el sistema. Cualquier duda sobre "¿cómo viene este campo?" se responde mirando el fixture, no preguntando en el canal.

---

## 📋 Registro de cambios

| Versión | Fecha | Cambio | Aprobado por |
|---|---|---|---|
| 1.0 | 2026-09-18 | Versión inicial: formatos A, P y B | *pendiente de ratificación en reunión* |
