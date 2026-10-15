import { useCallback, useEffect, useRef, useState } from "react";
import { api, descargar } from "../api";
import { mismoContenido, useEdicionesPendientes, type Contenido } from "../borradores";
import { ESTADOS, FORMATOS, SENTIMIENTOS, TIPOS, plural } from "../etiquetas";
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

/** LinkedIn corta las publicaciones a 3 000 caracteres (el texto y los hashtags cuentan juntos). */
const LIMITE_LINKEDIN = 3000;

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
  const { pendientes, editar } = useEdicionesPendientes(analisis?.paquete?.paquete_id);
  const conCambios = activos.filter((a) => pendientes[a.activo_id] && !mismoContenido(pendientes[a.activo_id], a.contenido));
  const [guardandoTodos, setGuardandoTodos] = useState(false);
  const [errorLote, setErrorLote] = useState("");

  // El navegador avisa antes de cerrar o recargar la pestaña con ediciones sin guardar
  useEffect(() => {
    if (!conCambios.length) return;
    const avisar = (e: BeforeUnloadEvent) => { e.preventDefault(); e.returnValue = ""; };
    window.addEventListener("beforeunload", avisar);
    return () => window.removeEventListener("beforeunload", avisar);
  }, [conCambios.length]);
  useEffect(() => {
    if (activos.length && !activos.some((a) => a.activo_id === elegido)) setElegido(activos[0].activo_id);
  }, [activos, elegido]);
  const activo = activos.find((a) => a.activo_id === elegido) ?? null;

  const [deshacer, setDeshacer] = useState<{ activo: Activo; anterior: string } | null>(null);
  const sinDeshacer = useRef(false); // el lote no ofrece «Deshacer» por cada borrador
  const plazoDeshacer = useRef<number>();
  useEffect(() => () => window.clearTimeout(plazoDeshacer.current), []);

  function reemplazar(nuevo: Activo) {
    const antes = activos.find((a) => a.activo_id === nuevo.activo_id);
    setPaquete((p) => p && { ...p, activos: p.activos.map((a) => (a.activo_id === nuevo.activo_id ? nuevo : a)) });
    alActualizar();
    // Aprobar o descartar (con el botón o con A/D) deja 8 segundos para arrepentirse
    if (antes && !sinDeshacer.current && antes.estado_curaduria !== nuevo.estado_curaduria
      && nuevo.estado_curaduria !== "borrador") {
      setDeshacer({ activo: nuevo, anterior: antes.estado_curaduria });
      window.clearTimeout(plazoDeshacer.current);
      plazoDeshacer.current = window.setTimeout(() => setDeshacer(null), 8000);
    }
  }

  /** Devuelve el borrador al estado que tenía antes de la última decisión (el texto no se toca). */
  async function deshacerDecision() {
    if (!deshacer) return;
    const { activo: a, anterior } = deshacer;
    window.clearTimeout(plazoDeshacer.current);
    setDeshacer(null);
    sinDeshacer.current = true;
    try {
      reemplazar(await api.patch<Activo>(`/activos/${a.activo_id}`, { estado: anterior }));
      setElegido(a.activo_id);
      setAnuncio(`Se deshizo la decisión: «${titulo(a)}» volvió a ${ESTADOS[anterior as keyof typeof ESTADOS]?.toLowerCase() ?? anterior}.`);
    } catch (err) {
      setErrorLote(`No se pudo deshacer: ${(err as Error).message}`);
    } finally {
      sinDeshacer.current = false;
    }
  }

  /** Guarda de una vez las ediciones pendientes de todos los borradores (sin cambiar su estado). */
  async function guardarTodos() {
    setGuardandoTodos(true);
    setErrorLote("");
    const fallidos: string[] = [];
    for (const a of conCambios) {
      try {
        reemplazar(await api.patch<Activo>(`/activos/${a.activo_id}`, { contenido: pendientes[a.activo_id] }));
        editar(a.activo_id, null);
      } catch {
        fallidos.push(String(titulo(a)));
      }
    }
    if (fallidos.length) setErrorLote(`No se pudo guardar: ${fallidos.join("; ")}. Se conservan tus cambios; reintenta.`);
    setGuardandoTodos(false);
  }

  // ── Revisión con el teclado y aprobación en lote ──────────────────────────
  const orden = ORDEN_FORMATOS.flatMap((f) => visibles.filter((a) => a.formato === f)); // el orden en que se ve la lista
  const [decidiendo, setDecidiendo] = useState(false);
  const [anuncio, setAnuncio] = useState("");
  const [verAtajos, setVerAtajos] = useState(false);
  const [umbralLote, setUmbralLote] = useState(0.9);
  const [confirmarLote, setConfirmarLote] = useState(false);
  const [aprobandoLote, setAprobandoLote] = useState(false);
  const paraLote = activos.filter((a) => a.estado_curaduria === "borrador" && a.origen.score >= umbralLote);
  const lista = useRef<HTMLElement>(null);

  /** Aprueba o descarta un borrador (con su edición pendiente, si la hay). Devuelve si salió bien. */
  async function decidir(a: Activo, estado: "aprobado" | "descartado"): Promise<boolean> {
    try {
      const contenido = pendientes[a.activo_id];
      reemplazar(await api.patch<Activo>(`/activos/${a.activo_id}`, { ...(contenido ? { contenido } : {}), estado }));
      editar(a.activo_id, null);
      return true;
    } catch (err) {
      setErrorLote(`No se pudo ${estado === "aprobado" ? "aprobar" : "descartar"} «${titulo(a)}»: ${(err as Error).message}`);
      return false;
    }
  }

  /** Decide el borrador abierto y pasa al siguiente que todavía esté por revisar. */
  async function decidirYSeguir(estado: "aprobado" | "descartado") {
    if (!activo || decidiendo) return;
    setDecidiendo(true);
    setErrorLote("");
    const i = orden.findIndex((a) => a.activo_id === activo.activo_id);
    const siguiente = (i < 0 ? orden : [...orden.slice(i + 1), ...orden.slice(0, i)])
      .find((a) => a.estado_curaduria === "borrador");
    if (await decidir(activo, estado)) {
      setAnuncio(siguiente ? `Ahora: ${titulo(siguiente)}.` : "No quedan borradores por revisar.");
      if (siguiente) setElegido(siguiente.activo_id);
    }
    setDecidiendo(false);
  }

  function moverse(paso: 1 | -1) {
    if (!orden.length) return;
    const i = orden.findIndex((a) => a.activo_id === elegido);
    const destino = i < 0 ? orden[0] : orden[(i + paso + orden.length) % orden.length];
    setElegido(destino.activo_id);
    setAnuncio(`Borrador: ${titulo(destino)}.`);
  }

  async function aprobarLote() {
    setAprobandoLote(true);
    setErrorLote("");
    setDeshacer(null);
    sinDeshacer.current = true;
    let listos = 0;
    for (const a of paraLote) {
      if (!(await decidir(a, "aprobado"))) break; // si falla uno (p. ej. sesión vencida) no se sigue
      listos++;
    }
    setAnuncio(`Se ${listos === 1 ? "aprobó 1 borrador" : `aprobaron ${listos} borradores`}.`);
    sinDeshacer.current = false;
    setConfirmarLote(false);
    setAprobandoLote(false);
  }

  // Teclas: J/K recorren, A aprueba, D descarta, E edita, ? muestra la ayuda. No actúan mientras se escribe en un campo
  // ni con un diálogo abierto. El manejador se registra una vez y lee siempre el estado más reciente por la ref.
  const teclas = useRef<(e: KeyboardEvent) => void>();
  teclas.current = (e) => {
    if (!hayPaquete || e.ctrlKey || e.metaKey || e.altKey || e.repeat) return;
    const objetivo = e.target as HTMLElement | null;
    if (objetivo?.closest("input, textarea, select, [contenteditable='true']") || document.querySelector("dialog[open]")) return;
    switch (e.key.toLowerCase()) {
      case "j": e.preventDefault(); moverse(1); break;
      case "k": e.preventDefault(); moverse(-1); break;
      case "a": e.preventDefault(); void decidirYSeguir("aprobado"); break;
      case "d": e.preventDefault(); void decidirYSeguir("descartado"); break;
      case "u": e.preventDefault(); void deshacerDecision(); break;
      case "e": e.preventDefault(); document.querySelector<HTMLTextAreaElement>(".editor textarea.area")?.focus(); break;
      case "?": e.preventDefault(); setVerAtajos((v) => !v); break;
      case "escape": setVerAtajos(false); break;
    }
  };
  useEffect(() => {
    const alPulsar = (e: KeyboardEvent) => teclas.current?.(e);
    window.addEventListener("keydown", alPulsar);
    return () => window.removeEventListener("keydown", alPulsar);
  }, []);

  // Al recorrer con J/K el borrador elegido se mantiene a la vista dentro de la lista (sin mover la página)
  useEffect(() => {
    const caja = lista.current;
    const el = caja?.querySelector<HTMLElement>('.borrador[aria-current="true"]');
    if (!caja || !el) return;
    if (el.offsetTop < caja.scrollTop) caja.scrollTop = Math.max(0, el.offsetTop - 40);
    else if (el.offsetTop + el.offsetHeight > caja.scrollTop + caja.clientHeight)
      caja.scrollTop = el.offsetTop + el.offsetHeight - caja.clientHeight + 8;
  }, [elegido]);

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

      {conCambios.length > 0 && (
        <div className="nota aviso aviso-cambios" role="status">
          <span>
            Tienes {plural(conCambios.length, "borrador", "borradores")} con cambios sin guardar. «Guardar el paquete» solo
            incluye lo que ya guardaste; si un borrador estaba aprobado, vuelve a «Por revisar».
          </span>
          <button className="boton chico" onClick={guardarTodos} disabled={guardandoTodos}>
            {guardandoTodos && <span className="cargando" />} Guardar los cambios
          </button>
        </div>
      )}
      {errorLote && <p className="nota error" role="alert">{errorLote}</p>}

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
          <button className="boton chico fantasma" aria-expanded={verAtajos} onClick={() => setVerAtajos(!verAtajos)}>
            Atajos <kbd>?</kbd>
          </button>
          <button className="boton" disabled={!conteo.aprobado}
            onClick={() => descargar("/paquete/media-kit", `${analisis!.paquete!.paquete_id}_media_kit.zip`)}>
            Descargar media kit ({conteo.aprobado})
          </button>
        </div>
      </div>

      {verAtajos && (
        <div className="nota atajos" role="region" aria-label="Atajos de teclado">
          <ul>
            <li><kbd>J</kbd> <kbd>K</kbd> siguiente y anterior</li>
            <li><kbd>A</kbd> aprobar y pasar al siguiente por revisar</li>
            <li><kbd>D</kbd> descartar y pasar al siguiente</li>
            <li><kbd>U</kbd> deshacer la última decisión</li>
            <li><kbd>E</kbd> editar el texto</li>
            <li><kbd>?</kbd> mostrar u ocultar esta ayuda</li>
          </ul>
          <p className="tenue">Funcionan cuando no estás escribiendo en un campo.</p>
        </div>
      )}

      {conteo.borrador > 0 && (
        <div className="lote">
          {confirmarLote ? (
            <>
              <span>¿Aprobar {plural(paraLote.length, "borrador", "borradores")} con score {umbralLote.toFixed(2)} o más?
                Revísalos antes si no los leíste: lo aprobado entra al paquete.</span>
              <button className="boton primario chico" onClick={aprobarLote} disabled={aprobandoLote || !paraLote.length}>
                {aprobandoLote && <span className="cargando" />} Sí, aprobar
              </button>
              <button className="boton chico" onClick={() => setConfirmarLote(false)} disabled={aprobandoLote}>Cancelar</button>
            </>
          ) : (
            <>
              <label htmlFor="umbral-lote">Aprobar de una vez los por revisar con score de</label>
              <select id="umbral-lote" className="entrada" value={umbralLote}
                onChange={(e) => setUmbralLote(Number(e.target.value))}>
                {[0.95, 0.9, 0.85, 0.8].map((u) => <option key={u} value={u}>{u.toFixed(2)} o más</option>)}
              </select>
              <button className="boton chico" disabled={!paraLote.length} onClick={() => setConfirmarLote(true)}>
                Aprobar {paraLote.length}
              </button>
            </>
          )}
        </div>
      )}
      <p className="sr-solo" role="status">{anuncio}</p>
      {deshacer && (
        <div className="aviso-deshacer" role="status">
          <span>{deshacer.activo.estado_curaduria === "aprobado" ? "Aprobado" : "Descartado"}: <b>{titulo(deshacer.activo)}</b></span>
          <button className="boton chico" onClick={deshacerDecision}>Deshacer <kbd>U</kbd></button>
        </div>
      )}

      {!activos.length ? (
        <Vacio titulo={redactando ? "Redactando los primeros borradores" : "Este lote no dejó borradores"}>
          {redactando ? "Aparecen aquí en unos segundos." : "Ningún mensaje superó el umbral de su tipo."}
        </Vacio>
      ) : (
        <div className="estudio">
          <nav className="hoja borradores" aria-label="Borradores" ref={lista}>
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
                      <span className="sc">
                        {conCambios.includes(a) && <span className="sin-guardar" title="Cambios sin guardar" role="img"
                          aria-label="Cambios sin guardar" />}
                        {a.origen.score.toFixed(2)}
                      </span>
                      <span className="meta">{a.origen.autor || "Miembro"} en #{a.origen.channel || "sin canal"}</span>
                    </button>
                  ))}
                </div>
              );
            })}
            {!visibles.length && <p className="vacio">Ningún borrador {ESTADOS[filtro as "borrador"]?.toLowerCase()}.</p>}
          </nav>
          {activo && (
            <Editor key={activo.activo_id} activo={activo} alGuardar={reemplazar}
              contenido={pendientes[activo.activo_id] ?? activo.contenido}
              alEditar={(c) => editar(activo.activo_id, c && !mismoContenido(c, activo.contenido) ? c : null)} />
          )}
        </div>
      )}
    </>
  );
}

interface PropsEditor {
  activo: Activo;
  /** Lo que muestran los campos: la edición pendiente si la hay, o el contenido guardado. */
  contenido: Contenido;
  /** Con null se descarta la edición pendiente (ya se guardó o se reemplazó por el texto del servidor). */
  alEditar: (contenido: Contenido | null) => void;
  alGuardar: (a: Activo) => void;
}

function Editor({ activo, contenido, alEditar, alGuardar }: PropsEditor) {
  const [indicaciones, setIndicaciones] = useState("");
  const [ocupado, setOcupado] = useState<string | null>(null);
  const [error, setError] = useState("");
  // Las ediciones viven en Curaduria (ver borradores.ts): cambiar de borrador o de etapa ya no las pierde
  const setContenido = alEditar;
  const editado = !mismoContenido(contenido, activo.contenido);

  async function guardar(estado?: string) {
    setOcupado(estado ?? "guardar");
    setError("");
    try {
      const nuevo = await api.patch<Activo>(`/activos/${activo.activo_id}`, { contenido, ...(estado ? { estado } : {}) });
      alGuardar(nuevo);
      alEditar(null); // lo guardado ya es el contenido del servidor: no queda nada pendiente
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
      const nuevo = await api.post<Activo>(`/activos/${activo.activo_id}/regenerar`, { indicaciones });
      alGuardar(nuevo);
      alEditar(null); // el texto regenerado reemplaza a la edición pendiente
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
                  <>
                    <textarea id={`campo-${c.clave}`} className="area" rows={activo.formato === "sugerencia_faq" ? 9 : 8}
                      value={contenido[c.clave] ?? ""} onChange={(e) => setContenido({ ...contenido, [c.clave]: e.target.value })} />
                    {activo.formato === "post_linkedin" && c.clave === "copy" && (
                      <ContadorLinkedin texto={textoPublicable(activo.formato, contenido)} />
                    )}
                  </>
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

/** Cuántos caracteres lleva el post tal como se publicará (texto + hashtags) frente al límite de LinkedIn. */
function ContadorLinkedin({ texto }: { texto: string }) {
  const n = [...texto].length; // por caracteres, no por unidades UTF-16 (los emojis cuentan como uno)
  const resto = LIMITE_LINKEDIN - n;
  const nivel = resto < 0 ? "excedido" : resto <= LIMITE_LINKEDIN * 0.1 ? "cerca" : "";
  const aviso = nivel === "excedido" ? `Te pasas por ${-resto} caracteres: LinkedIn lo cortará o no lo dejará publicar.`
    : nivel === "cerca" ? `Quedan ${resto} caracteres.` : "";
  return (
    <p className={`contador ${nivel}`}>
      <span className="num">{n.toLocaleString("es")} / {LIMITE_LINKEDIN.toLocaleString("es")} caracteres</span>
      <span className="tenue"> · con hashtags</span>
      {aviso && <span className="contador-aviso" role="status"> {aviso}</span>}
    </p>
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
  // La sesión viaja en una cookie HttpOnly; `v` solo fuerza a recargar cuando la imagen cambia
  return `/api/activos/${activo.activo_id}/imagen?v=${encodeURIComponent(activo.imagen?.ruta ?? "")}`;
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
