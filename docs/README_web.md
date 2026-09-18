# 🧪 CommunityLab AI

**Sistema Multiagente de Inteligencia y Transformación de Comunidades Digitales**

Solución impulsada por IA que transforma las conversaciones no estructuradas de una comunidad digital (Discord, foros, chats) en activos de contenido listos para publicar: posts de LinkedIn, newsletters y FAQs educativas — con curaduría humana antes de cada publicación y almacenamiento trazable en Oracle Cloud Infrastructure.

> 🏆 Proyecto desarrollado para la **Hackathon ONE G10** — Oracle Next Education & Alura.

📦 **Repositorio:** https://github.com/No-Country-simulation/G10_LATAM_TEAM_26

---

## 👥 Integrantes

- **Celeste Box** — Rol por definir — [LinkedIn](https://linkedin.com/in/incbox)
- **Gregory Morales** — Rol por definir — [LinkedIn](https://www.linkedin.com/in/gregory-morales-50827428a/)
- **Anthony Uceda** — Rol por definir — [LinkedIn](https://www.linkedin.com/in/anthony-frank-uceda-alfaro-141b21394/)
- **Carolhay Ttito** — Rol por definir — LinkedIn pendiente
- **Jhon Giraldo** — Rol por definir — LinkedIn pendiente
- **Hernan** — Rol por definir — LinkedIn pendiente
- **Axel Cañete** — Rol por definir — [LinkedIn](https://py.linkedin.com/in/axel-ca%C3%B1ete-a95688299)
- **Juan** — Rol por definir — LinkedIn pendiente

---

## 📌 El problema

Las comunidades digitales activas generan cientos de interacciones diarias. Entre ese volumen conviven testimonios valiosos, casos de éxito, dudas recurrentes y feedback crítico que se pierden en el historial de los canales, porque revisarlos y transformarlos manualmente en contenido consume horas de los equipos de Community Management y Marketing.

**Volumen abrumador.** Cientos de mensajes diarios imposibles de monitorear manualmente.
→ *Solución:* ingestión y procesamiento automático en lote (CSV/JSON) o tiempo real (Discord API).

**Pérdida de valor.** Casos de éxito y FAQs quedan "enterrados" en los canales.
→ *Solución:* agentes de IA dedicados a la clasificación semántica y detección de oportunidades.

**Lentitud en redacción.** Crear posts, guías y reportes toma horas semanales.
→ *Solución:* generación automatizada de borradores para LinkedIn, newsletter y FAQ.

**Falta de trazabilidad.** Imposible asociar un activo publicado con su conversación de origen.
→ *Solución:* mapeo relacional estricto: Contenido → Oportunidad → Mensaje original.

---

## 🏗️ Arquitectura

El sistema adopta una arquitectura por capas modulares:

```
📥 FUENTES DE DATOS
   Discord Bot API (tiempo real) · JSON / CSV (lote)
        ↓
🧹 CAPA 1 · INGESTIÓN Y PREPROCESAMIENTO
   Normalización · Limpieza · Anonimización (PII) · Deduplicación
        ↓
🧠 CAPA 2 · ANÁLISIS LLM Y AGENTES ESPECIALIZADOS
   Community Analyst → Opportunity Detector → Content Strategist
        ↓
👁️ CAPA 3 · INTERFAZ Y CURADURÍA HUMANA
   Dashboard Streamlit · Content Studio (Aprobar / Editar / Rechazar)
        ↓
☁️ CAPA 4 · ALMACENAMIENTO CLOUD
   OCI Object Storage — bucket trazable y persistente (Always Free)
```

### Arquitectura multiagente

En lugar de una única consulta masiva al LLM, el razonamiento se divide en **tres agentes especializados en cadena**:

**🔍 Agente 1 — Community Analyst**
Recibe el mensaje limpio y extrae sentimiento, temas principales e intención. Produce la metadata de análisis semántico.

**🎯 Agente 2 — Opportunity Detector**
Recibe el mensaje + metadata y clasifica el tipo de oportunidad, calculando el *Opportunity Score*. Categorías: SUCCESS_STORY, FAQ, TREND, FEEDBACK, MILESTONE, NONE.

**✍️ Agente 3 — Content Strategist**
Recibe la oportunidad detectada + contexto original y adapta el contenido al formato y tono del canal objetivo. Produce los borradores para LinkedIn, Newsletter o FAQ educativa.

### Algoritmo de priorización (Opportunity Score)

Cada interacción recibe un score de 0.00 a 1.00 que pondera relevancia, engagement, sentimiento y novedad:

- **0.90 – 1.00 · Alta prioridad** → generación inmediata de activos multicanal (LinkedIn + Newsletter) y notificación en el panel.
- **0.70 – 0.89 · Media prioridad** → generación de borrador único específico (FAQ educativa o tip de comunidad).
- **0.00 – 0.69 · Baja prioridad** → registro para analítica global; no genera borrador.

---

## 🔗 Modelo de datos y trazabilidad

Todos los mensajes adoptan una estructura JSON unificada que garantiza trazabilidad total desde el activo publicado hasta la interacción original:

```
{
  "tracking":    { "message_id": "MSG-8921", "source": "discord", "channel": "logros" },
  "analysis":    { "sentiment": "positive", "topics": ["empleo", "data_analysis"], "relevance_score": 0.95 },
  "opportunity": { "type": "SUCCESS_STORY", "opportunity_score": 0.94 }
}
```

**Esquema de lineage:** cada publicación aprobada conserva la referencia exacta del mensaje que la inspiró:

```
POST-034 (LinkedIn) → OPP-021 (Oportunidad) → MSG-8921 (#logros / Discord)
```

---

## ☁️ Almacenamiento en OCI (capa Always Free)

Organización del bucket:

```
communitylab-bucket/
├── raw/          Mensajes en bruto recibidos (JSON/CSV)
├── processed/    Mensajes limpios y analizados
├── generated/    Activos aprobados (linkedin / newsletter / faq)
└── reports/      Reportes de salud comunitaria
```

---

## 🛠️ Stack tecnológico

- **Lenguaje:** Python 3.11+
- **LLM:** por definir (Google Gemini / OpenAI / Anthropic Claude)
- **Orquestación de agentes:** por definir (LangGraph / n8n)
- **Interfaz y curaduría:** Streamlit
- **Almacenamiento:** OCI Object Storage (Always Free)
- **Validación de datos:** Pydantic
- **Ingesta en tiempo real (diferencial):** Discord Bot API

---

## 🎬 Casos de demostración

**Caso 1 — Historia de éxito** · Origen: Discord #logros
"¡Comunidad, logré mi primer trabajo como Data Analyst gracias al bootcamp!" → el sistema detecta alta relevancia y genera un post de LinkedIn con gancho, cuerpo, llamado a la acción y hashtags.

**Caso 2 — Pregunta recurrente (FAQ)** · Origen: Discord #dudas-tecnicas
"¿Alguien sabe cómo configurar los reintentos automáticos en LangGraph?" → se clasifica como consulta técnica de alto interés y genera una guía rápida / FAQ educativa.

**Caso 3 — Tendencia de comunidad** · Origen: lote CSV, múltiples usuarios
Incremento inusual de consultas sobre la API de Oracle en 48 horas → el sistema detecta el patrón y genera un resumen ejecutivo para los administradores.

---

## 🗓️ Roadmap

- **Semana 1 — Fundación:** repositorio, dataset, contratos de datos, esqueleto end-to-end con bucket OCI activo.
- **Semana 2 — Inteligencia:** prompts estructurados, cadena de agentes, scoring — casos 1 y 2 funcionando.
- **Semana 3 — Producto completo:** panel Streamlit integrado con OCI, flujo de curaduría, diferenciales.
- **Semana 4 — Validación:** métricas de clasificación, video demo, presentación final.

---

## 📄 Licencia

Proyecto educativo desarrollado en el marco del programa **Oracle Next Education (ONE)** — Grupo 10, en colaboración con **Alura Latam**. Uso exclusivo de recursos de la capa Always Free de OCI, en conformidad con la gratuidad integral del programa.
