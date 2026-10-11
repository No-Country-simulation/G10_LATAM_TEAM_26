import type { EstadoCuraduria, Formato, Sentimiento, TipoOportunidad } from "./tipos";

// Nombres que ve el equipo; el motor y los archivos guardan los códigos en inglés (spec.md).
export const TIPOS: Record<TipoOportunidad, string> = {
  SUCCESS_STORY: "Historia de éxito",
  MILESTONE: "Logro",
  FAQ: "Pregunta frecuente",
  OPERATIONAL_QUERY: "Consulta operativa",
  FEEDBACK: "Feedback",
  NONE: "Sin valor de contenido",
};

export const SENTIMIENTOS: Record<Sentimiento, string> = {
  positive: "Positivo",
  neutral: "Neutral",
  negative: "Negativo",
};

export const FORMATOS: Record<Formato, string> = {
  post_linkedin: "Post de LinkedIn",
  destaque_newsletter: "Destaque de newsletter",
  sugerencia_faq: "Entrada de FAQ",
};

export const ESTADOS: Record<EstadoCuraduria, string> = {
  borrador: "Por revisar",
  aprobado: "Aprobado",
  descartado: "Descartado",
  publicado: "Publicado",
};

export const TIPOS_DECLARADOS: Record<string, string> = {
  testimonio: "Testimonios",
  pregunta_tecnica: "Dudas técnicas",
  feedback: "Feedback",
  logro: "Logros",
  conversacion: "Conversación",
  otro: "Otros",
};

export const tema = (t: string) => t.replace(/_/g, " ");

export function fecha(iso: string) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString("es-PE", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
}

export const plural = (n: number, uno: string, varios: string) => `${n} ${n === 1 ? uno : varios}`;
