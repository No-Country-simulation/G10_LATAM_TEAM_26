// Contratos de la API (src/api/app.py). Formato A, P y B según spec.md.

export type Sentimiento = "positive" | "neutral" | "negative";
export type TipoOportunidad =
  | "SUCCESS_STORY" | "MILESTONE" | "FAQ" | "OPERATIONAL_QUERY" | "FEEDBACK" | "NONE";
export type Formato = "post_linkedin" | "destaque_newsletter" | "sugerencia_faq";
export type EstadoCuraduria = "borrador" | "aprobado" | "descartado" | "publicado";
export type Fase = "inactivo" | "clasificando" | "redactando" | "listo" | "error";

export interface Sesion {
  token: string;
  usuario: string;
  rol: "ADMIN" | "CURATOR" | "VIEWER";
}

export interface Sistema {
  usuario: string;
  rol: string;
  base: string;
  error_base: string;
  oci_conectado: boolean;
  bucket: string;
  discord_configurado: boolean;
  tamano_lote: number;
  max_concurrencia: number;
  imagenes: boolean;
  umbrales: Record<string, number>;
}

export interface Interaccion {
  message_id: string;
  source: string;
  channel: string;
  timestamp: string;
  autor: string;
  tipo_declarado?: string | null;
  texto: string;
  metadata: Record<string, number>;
}

export interface Dataset {
  fuente: "estandar" | "discord" | "archivo";
  archivo?: string | null;
  aviso?: string;
  consultado?: string | null;
  nuevos?: number | null;
  comunidad_discord?: string | null;
  origen_comunidad?: string;
  periodo_referencia?: string;
  total: number;
  tipos_declarados?: Record<string, number>;
  analizados?: string[];
  interacciones: Interaccion[];
}

export interface Mensaje {
  tracking: { message_id: string; source: string; channel: string | null; timestamp: string };
  analysis: { sentiment: Sentimiento; topics: string[]; intent: string; relevance_score: number };
  opportunity: { opportunity_id: string; type: TipoOportunidad; opportunity_score: number; reason: string };
  texto: string;
  autor: string;
  es_oportunidad: boolean;
  necesita_apoyo: boolean;
}

export interface Resumen {
  total_interacciones_procesadas: number;
  sentimiento_predominante: Sentimiento;
  distribucion_sentimiento: Record<Sentimiento, number>;
  temas_principales: string[];
  oportunidades_detectadas: number;
  consultas_operativas: number;
  feedback_recibido: number;
  tendencias_detectadas: { tema: string; menciones: number; descripcion: string }[];
}

export interface Analisis {
  fase: Fase;
  error: string | null;
  simulado: boolean;
  comunidad: string;
  repetidos: number;
  total: number;
  transcurrido: number;
  segundos_clasificacion: number | null;
  segundos_redaccion: number | null;
  guardados_en_base: number | string | null;
  mensajes: Mensaje[];
  resumen: Resumen | null;
  salud: { emoji: string; etiqueta: string } | null;
  avisos: Record<string, number>;
  redaccion: { listos: number; total: number; lotes_listos: number; lotes: number; terminado: boolean } | null;
  imagenes: { generadas: number; fallidas: number; pendientes: number; terminado: boolean } | null;
  paquete: {
    paquete_id: string;
    status: string;
    periodo_referencia: string;
    ruta_objeto: string;
    activos: number;
    curaduria: Record<"borrador" | "aprobado" | "descartado", number>;
  } | null;
  resultado_oci: ResultadoOCI | null;
}

export interface Imagen {
  estado: "pendiente" | "generando" | "lista" | "error" | "omitida";
  prompt: string;
  ruta?: string | null;
  detalle?: string;
}

export interface Activo {
  activo_id: string;
  formato: Formato;
  estado_curaduria: EstadoCuraduria;
  origen: {
    message_id: string;
    opportunity_id: string;
    channel: string | null;
    autor?: string | null;
    message: string;
    sentiment: Sentimiento;
    topics: string[];
    type: TipoOportunidad;
    score: number;
    reason: string;
  };
  contenido: Record<string, any>;
  imagen?: Imagen | null;
}

export interface Paquete {
  paquete_id: string;
  status: string;
  origen_comunidad: string;
  periodo_referencia: string;
  almacenamiento_oci: { bucket: string; ruta_objeto: string; status: string };
  activos: Activo[];
}

export interface ResultadoOCI {
  status: string;
  error?: string;
  imagenes_subidas?: number;
  activos_en_base?: number | string;
  [clave: string]: unknown;
}

export interface Historico {
  base: string;
  mensajes: number;
  tipos?: Record<string, number>;
  sentimientos?: Record<string, number>;
  canales?: Record<string, number>;
  activos?: Record<string, number>;
}

export interface PublicacionGuardada {
  id: string;
  formato: Formato | string;
  titulo: string;
  texto: string;
  hashtags: string[];
  estado: EstadoCuraduria | null;
  autor: string | null;
  canal: string | null;
  mensaje_id: string | null;
  tipo: TipoOportunidad | null;
  score: number | null;
  imagen: string | null;
  fecha: string;
  objeto: string;
  paquete: string | null;
  origen_formato: "paquete" | "version_anterior";
  veces_guardado: number;
}

export interface Guardadas {
  conectado: boolean;
  bucket: string;
  objetos?: number;
  consultado?: string;
  error?: string;
  publicaciones: PublicacionGuardada[];
}

export interface ComunidadDiscord {
  id: string;
  nombre: string;
  servidor: string | null;
  origen: string;
  principal: boolean;
  configurada: boolean;
  token_final: string | null;
}
