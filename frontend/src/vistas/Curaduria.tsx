import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, descargar, tokenActual } from "../api";
import { ESTADOS, FORMATOS, SENTIMIENTOS, TIPOS } from "../etiquetas";
import { Portada, Vacio } from "../componentes/Marca";
import type { Activo, Analisis, Formato, Paquete } from "../tipos";

interface Props {
  analisis: Analisis | null;
  alActualizar: () => void;
  alAnalizar: () => void;
  alPublicar: () => void;
}

const ORDEN_FORMATOS: Formato[] = ["post_linkedin", "destaque_newsletter", "sugerencia_faq"];

/** Campos editables de cada formato del Formato B. */
const CAMPOS: Record<Formato, { clave: string; nombre: string; largo?: boolean; lista?: boolean }[]> = {
  post_linkedin: [
    { clave: "titulo", nombre: "Título (hook)" },
    { clave: "copy", nombre: "Texto del post", largo: true },
    { clave: "hashtags", nombre: "Hashtags", lista: true },
  ],
  destaque_newsletter: [
    { clave: "seccion", nombre: "Sección" },
    { clave: "titular", nombre: "Titular" },
    { clave: "resumen", nombre: "Resumen", largo: true },
  ],
  sugerencia_faq: [
    { clave: "tema", nombre: "Pregunta" },
    { clave: "cuerpo", nombre: "Respuesta", largo: true },
  ],
};

const titulo = (a: Activo) =>
  a.contenido.titulo || a.contenido.titular || a.contenido.tema || a.activo_id;

export function Curaduria({ analisis, alActualizar, alAnalizar, alPublicar }: Props) {
  const [paquete, setPaquete] = useState<Paquete | null>(null);
  const [elegido, setElegido] = useState<string | null>(null);
  const [filtro, setFiltro] = useState<"todos" | "borrador" | "aprobado" | "descartado">("todos");
  const hayPaquete = !!analisis?.paquete;

  const cargar = useCallback(async () => {
    try {
      setPaquete(await api.get<Paquete>("/paquete"));
    } catch {
      setPaquete(null);
    }
  }, []);

  // Se recarga cuando llegan borradores o imágenes nuevas (el estado general se consulta en App)
  const firma = `${analisis?.paquete?.paquete_id}-${analisis?.redaccion?.listos}-${analisis?.imagenes?.generadas}-${analisis?.imagenes?.fallidas}`;
  useEffect(() => { if (hayPaquete) cargar(); }, [firma, hayPaquete, cargar]);

  const activos = paquete?.activos ?? [];
  const visibles = activos.filter((a) => filtro === "todos" || a.estado_curaduria === filtro);
  useEffect(() => {
    if (activos.length && !activos.some((a) => a.activo_id === elegido)) setElegido(activos[0].activo_id);
  }, [activos, elegido]);
  const activo = activos.find((a) => a.activo_id === elegido) ?? null;

  function reemplazar(nuevo: Activo) {
    setPaquete((p) => p && { ...p, activos: p.activos.map((a) => (a.activo_id === nuevo.activo_id ? nuevo : a)) });
    alActualizar();
  }

  if (!hayPaquete) {
    return (
      <>
        <Portada titulo="Borradores para revisar"
          bajada="Cada borrador nace de un mensaje real de la comunidad. Solo lo que apruebes se publica." />
        {analisis?.fase === "clasificando" ? (
          <Vacio titulo="El lote se está clasificando">Los borradores aparecen aquí apenas termine.</Vacio>
        ) : (
          <Vacio titulo="No hay borradores en esta sesión"
            acciones={<>
              <button className="boton primario" onClick={alAnalizar}>Analizar un lote</button>
              <button className="boton" onClick={alPublicar}>Ver publicaciones guardadas</button>
            </>}>
            Analiza un lote para que el motor los redacte. Lo que ya se guardó está en Publicación.
          </Vacio>
        )}
      </>
    );
  }

  const conteo = analisis!.paquete!.curaduria;
  const redactando = analisis?.redaccion && !analisis.redaccion.terminado;

  return (
    <>
      <Portada
        titulo="Borradores para revisar"
        bajada="Cada borrador nace de un mensaje real de la comunidad. Ajústalo, apruébalo o descártalo: solo lo aprobado se publica."
        accion={<button className="boton primario" disabled={!!redactando} onClick={alPublicar}>Guardar el paquete</button>}
        cifras={[
          { valor: conteo.borrador, texto: "por revisar" },
          { valor: conteo.aprobado, texto: "aprobados" },
          { valor: conteo.descartado, texto: "descartados" },
        ]}
      />

      <div className="seccion-cabeza">
        <div className="segmentos" role="group" aria-label="Filtrar borradores">
          {(["todos", "borrador", "aprobado", "descartado"] as const).map((f) => (
            <button key={f} aria-pressed={filtro === f} onClick={() => setFiltro(f)}>
              {f === "todos" ? "Todos" : ESTADOS[f]}
              <span className="n">{f === "todos" ? activos.length : conteo[f]}</span>
            </button>
          ))}
        </div>
        <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
          {redactando && (
            <span className="sec num" aria-live="polite">
              <span className="cargando" /> Redactando {analisis!.redaccion!.listos} de {analisis!.redaccion!.total}
            </span>
          )}
          <button className="boton" disabled={!conteo.aprobado}
            onClick={() => descargar("/paquete/media-kit", `${analisis!.paquete!.paquete_id}_media_kit.zip`)}>
            Descargar media kit ({conteo.aprobado})
          </button>
        </div>
      </div>

      {!activos.length ? (
        <Vacio titulo={redactando ? "Redactando los primeros borradores" : "Este lote no dejó borradores"}>
          {redactando ? "Aparecen aquí en unos segundos." : "Ningún mensaje superó el umbral de su tipo."}
        </Vacio>
      ) : (
        <div className="estudio">
          <nav className="hoja borradores" aria-label="Borradores">
            {ORDEN_FORMATOS.map((formato) => {
              const grupo = visibles.filter((a) => a.formato === formato);
              if (!grupo.length) return null;
              return (
                <div key={formato}>
                  <div className="grupo">{FORMATOS[formato]}</div>
                  {grupo.map((a) => (
                    <button key={a.activo_id} className="borrador" aria-current={a.activo_id === elegido}
                      onClick={() => setElegido(a.activo_id)}>
                      <span className={`punto estado-${a.estado_curaduria}`} aria-label={ESTADOS[a.estado_curaduria]} />
                      <span className="titulo">{titulo(a)}</span>
                      <span className="sc">{a.origen.score.toFixed(2)}</span>
                      <span className="meta">{a.origen.autor || "Miembro"} en #{a.origen.channel || "sin canal"}</span>
                    </button>
                  ))}
                </div>
              );
            })}
            {!visibles.length && <p className="vacio">Ningún borrador {ESTADOS[filtro as "borrador"]?.toLowerCase()}.</p>}
          </nav>
          {activo && <Editor key={activo.activo_id} activo={activo} alGuardar={reemplazar} />}
        </div>
      )}
    </>
  );
}

function Editor({ activo, alGuardar }: { activo: Activo; alGuardar: (a: Activo) => void }) {
  const [contenido, setContenido] = useState<Record<string, any>>(activo.contenido);
  const [indicaciones, setIndicaciones] = useState("");
  const [ocupado, setOcupado] = useState<string | null>(null);
  const [error, setError] = useState("");
  const original = useRef(activo.contenido);

  // Si el servidor cambia el contenido (regeneración), el editor lo toma
  useEffect(() => {
    if (JSON.stringify(original.current) !== JSON.stringify(activo.contenido)) {
      original.current = activo.contenido;
      setContenido(activo.contenido);
    }
  }, [activo.contenido]);

  const editado = useMemo(() => JSON.stringify(contenido) !== JSON.stringify(activo.contenido), [contenido, activo.contenido]);

  async function guardar(estado?: string) {
    setOcupado(estado ?? "guardar");
    setError("");
    try {
      const nuevo = await api.patch<Activo>(`/activos/${activo.activo_id}`, { contenido, ...(estado ? { estado } : {}) });
      original.current = nuevo.contenido;
      alGuardar(nuevo);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setOcupado(null);
    }
  }

  async function regenerar() {
    setOcupado("regenerar");
    setError("");
    try {
      alGuardar(await api.post<Activo>(`/activos/${activo.activo_id}/regenerar`, { indicaciones }));
      setIndicaciones("");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setOcupado(null);
    }
  }

  const campos = CAMPOS[activo.formato];
  const o = activo.origen;
  return (
    <div className="editor">
      <blockquote className="fuente-cita" style={{ margin: 0 }}>
        <div className="mensaje-cabeza">
          <span className="autor">{o.autor || "Miembro"}</span>
          <span className="canal">#{o.channel || "sin canal"}</span>
          <span className="marcas">
            <span className={`sent ${o.sentiment}`}>{SENTIMIENTOS[o.sentiment]}</span>
            <span className={`chip ${o.type}`}>{TIPOS[o.type]} {o.score.toFixed(2)}</span>
          </span>
        </div>
        <p className="cita burbuja">{o.message}</p>
        <p className="razon">{o.reason}</p>
      </blockquote>

      <section className="hoja">
        <div className={`editor-cuerpo ${activo.formato === "post_linkedin" ? "" : "una"}`}>
          <div style={{ display: "grid", gap: 14, alignContent: "start" }}>
            <div className="seccion-cabeza">
              <h2>{FORMATOS[activo.formato]}</h2>
              <span className="sec">{ESTADOS[activo.estado_curaduria]}</span>
            </div>
            {campos.map((c) => (
              <div className="campo" key={c.clave}>
                <label htmlFor={`campo-${c.clave}`}>{c.nombre}</label>
                {c.largo ? (
                  <textarea id={`campo-${c.clave}`} className="area" rows={activo.formato === "sugerencia_faq" ? 9 : 8}
                    value={contenido[c.clave] ?? ""} onChange={(e) => setContenido({ ...contenido, [c.clave]: e.target.value })} />
                ) : (
                  <input id={`campo-${c.clave}`} className={`entrada ${c.lista ? "" : "serif"}`}
                    value={c.lista ? (contenido[c.clave] ?? []).join(" ") : contenido[c.clave] ?? ""}
                    onChange={(e) => setContenido({ ...contenido,
                      [c.clave]: c.lista ? e.target.value.split(/\s+/).filter(Boolean) : e.target.value })} />
                )}
              </div>
            ))}
            {activo.formato === "sugerencia_faq" && contenido.origen_descripcion && (
              <p className="tenue" style={{ fontSize: 13.5 }}>Origen: {contenido.origen_descripcion}</p>
            )}
            {editado && activo.estado_curaduria === "aprobado" && (
              <p className="nota aviso">Si guardas cambios en un borrador aprobado, vuelve a «Por revisar».</p>
            )}
          </div>
          {activo.formato === "post_linkedin" && <VistaLinkedin contenido={contenido} activo={activo} />}
        </div>

        <ImagenActivo activo={activo} alCambiar={alGuardar} />
        <Exportar activo={activo} contenido={contenido} />

        <div className="acciones">
          <input className="entrada" style={{ flex: "1 1 240px", width: "auto" }} value={indicaciones}
            placeholder="Indicación para la IA: más breve, cierra con una pregunta…" aria-label="Indicación para regenerar"
            onChange={(e) => setIndicaciones(e.target.value)} />
          <button className="boton" onClick={regenerar} disabled={!!ocupado}>
            {ocupado === "regenerar" && <span className="cargando" />} Regenerar con IA
          </button>
          <span className="espacio" />
          {editado && <button className="boton fantasma" onClick={() => guardar()} disabled={!!ocupado}>Guardar cambios</button>}
          <button className="boton peligro" onClick={() => guardar("descartado")} disabled={!!ocupado}>Descartar</button>
          <button className="boton primario" onClick={() => guardar("aprobado")} disabled={!!ocupado}>
            {activo.estado_curaduria === "aprobado" && !editado ? "Aprobado" : "Aprobar"}
          </button>
        </div>
        {error && <p className="nota error" role="alert" style={{ margin: "0 22px 18px" }}>{error}</p>}
      </section>
    </div>
  );
}

/** Texto listo para publicar, igual al del media kit. */
function textoPublicable(formato: Formato, c: Record<string, any>) {
  if (formato === "post_linkedin") return `${c.copy ?? ""}\n\n${(c.hashtags ?? []).join(" ")}`.trim();
  if (formato === "destaque_newsletter") return `${c.titular ?? ""}\n\n${c.resumen ?? ""}`.trim();
  return `${c.tema ?? ""}\n\n${c.cuerpo ?? ""}`.trim();
}

const escaparHtml = (t: string) => t.replace(/[&<>"]/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[ch]!));

function descargarTexto(nombre: string, contenido: string, tipo: string) {
  const url = URL.createObjectURL(new Blob([contenido], { type: `${tipo};charset=utf-8` }));
  Object.assign(document.createElement("a"), { href: url, download: nombre }).click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/** Atajos para llevar el borrador a donde se publica, sin pasar por el media kit. */
function Exportar({ activo, contenido }: { activo: Activo; contenido: Record<string, any> }) {
  const [copiado, setCopiado] = useState(false);
  const texto = textoPublicable(activo.formato, contenido);
  async function copiar() {
    try {
      await navigator.clipboard.writeText(texto);
      setCopiado(true);
      setTimeout(() => setCopiado(false), 2000);
    } catch {
      /* sin portapapeles */
    }
  }
  return (
    <div className="exportar">
      <span className="etiqueta-campo">Llevarlo a publicar</span>
      <div className="exportar-acciones">
        <button className="boton chico" onClick={copiar}>{copiado ? "Texto copiado" : "Copiar texto"}</button>
        {activo.formato === "post_linkedin" && (
          <a className="boton chico" target="_blank" rel="noopener noreferrer"
            href={`https://www.linkedin.com/feed/?shareActive=true&text=${encodeURIComponent(texto)}`}>Abrir en LinkedIn</a>
        )}
        {activo.formato === "destaque_newsletter" && (
          <button className="boton chico" onClick={() => descargarTexto(`${activo.activo_id}.html`,
            `<!-- Destaque para el newsletter: ${escaparHtml(contenido.seccion ?? "")} -->\n<section style="font-family:Arial,sans-serif;max-width:600px">\n` +
            `  <p style="color:#0e7f78;font-size:12px;text-transform:uppercase;letter-spacing:.08em">${escaparHtml(contenido.seccion ?? "")}</p>\n` +
            `  <h2 style="color:#13284f;margin:4px 0 8px">${escaparHtml(contenido.titular ?? "")}</h2>\n` +
            `  <p style="color:#33414f;line-height:1.6">${escaparHtml(contenido.resumen ?? "").replace(/\n/g, "<br>")}</p>\n</section>\n`,
            "text/html")}>Descargar HTML</button>
        )}
        {activo.formato === "sugerencia_faq" && (
          <button className="boton chico" onClick={() => descargarTexto(`${activo.activo_id}.md`,
            `## ${contenido.tema ?? ""}\n\n${contenido.cuerpo ?? ""}\n`, "text/markdown")}>Descargar Markdown</button>
        )}
      </div>
    </div>
  );
}

function urlImagen(activo: Activo) {
  return `/api/activos/${activo.activo_id}/imagen?token=${encodeURIComponent(tokenActual())}&v=${encodeURIComponent(activo.imagen?.ruta ?? "")}`;
}

function VistaLinkedin({ contenido, activo }: { contenido: Record<string, any>; activo: Activo }) {
  return (
    <div className="seccion" style={{ alignContent: "start" }}>
      <span className="etiqueta-campo">Así se verá en LinkedIn</span>
      <article className="linkedin">
        <div className="linkedin-cabeza">
          <span className="linkedin-avatar">CL</span>
          <span>
            <b style={{ display: "block", fontSize: 14 }}>CommunityLab</b>
            <span className="tenue" style={{ fontSize: 12.5 }}>Oracle Next Education</span>
          </span>
        </div>
        <div className="linkedin-cuerpo">
          {contenido.copy}
          <div className="hashtags">{(contenido.hashtags ?? []).join(" ")}</div>
        </div>
        {activo.imagen?.estado === "lista" && <img src={urlImagen(activo)} alt={activo.imagen.prompt} />}
      </article>
    </div>
  );
}

const TEXTOS_IMAGEN: Record<string, string> = {
  pendiente: "En cola: las imágenes se generan de mayor a menor score.",
  generando: "Generando la imagen…",
  omitida: "Se alcanzó el máximo de imágenes por paquete.",
};

function ImagenActivo({ activo, alCambiar }: { activo: Activo; alCambiar: (a: Activo) => void }) {
  const img = activo.imagen;
  const [pidiendo, setPidiendo] = useState(false);
  const [prompt, setPrompt] = useState(img?.prompt ?? "");
  useEffect(() => { setPrompt(img?.prompt ?? ""); }, [img?.prompt]);
  if (!img) {
    return (
      <div className="imagen-activo" style={{ borderTop: "1px solid var(--linea-suave)", display: "block" }}>
        <p className="tenue" style={{ fontSize: 14 }}>
          Sin imagen: el lote se analizó en modo simulado o las imágenes están desactivadas.
        </p>
      </div>
    );
  }
  async function otra() {
    setPidiendo(true);
    try {
      alCambiar(await api.post<Activo>(`/activos/${activo.activo_id}/imagen`, { prompt }));
    } finally {
      setPidiendo(false);
    }
  }
  return (
    <div className="imagen-activo" style={{ borderTop: "1px solid var(--linea-suave)" }}>
      <div className="marco-img">
        {img.estado === "lista"
          ? <img src={urlImagen(activo)} alt={img.prompt} />
          : <span>{img.estado === "error" ? `No se pudo generar (${img.detalle ?? "error"}).` : TEXTOS_IMAGEN[img.estado]}</span>}
      </div>
      <div style={{ display: "grid", gap: 10, alignContent: "start" }}>
        <h2>Imagen de la publicación</h2>
        <div className="campo">
          <label htmlFor={`prompt-${activo.activo_id}`}>Descripción de la imagen (en inglés, sin personas ni texto)</label>
          <textarea id={`prompt-${activo.activo_id}`} className="entrada prompt-imagen" rows={2} maxLength={400}
            value={prompt} onChange={(e) => setPrompt(e.target.value)} />
        </div>
        <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
          {img.estado === "lista" && (
            <a className="boton chico" href={urlImagen(activo)} download={`${activo.activo_id}`}>Descargar imagen</a>
          )}
          {["lista", "error", "omitida"].includes(img.estado) && (
            <button className="boton chico" onClick={otra} disabled={pidiendo}>
              {prompt.trim() !== (img.prompt ?? "").trim() ? "Generar con esta descripción" : "Generar otra imagen"}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
