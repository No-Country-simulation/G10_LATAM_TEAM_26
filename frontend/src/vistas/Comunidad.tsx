import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api";
import { SENTIMIENTOS, TIPOS, plural, tema } from "../etiquetas";
import { Salud } from "../componentes/Salud";
import { Portada, Vacio } from "../componentes/Marca";
import { AgregarComunidad } from "../componentes/AgregarComunidad";
import type { ComunidadDiscord } from "../tipos";
import type { Analisis, Dataset, Historico, Interaccion, Sentimiento, Sistema, TipoOportunidad } from "../tipos";

type Fuente = Dataset["fuente"];

interface Props {
  dataset: Dataset | null;
  analisis: Analisis | null;
  sistema: Sistema | null;
  alCambiarDataset: (d: Dataset) => void;
  alAnalizar: () => void;
}

const VISIBLES = 8;

export function Comunidad({ dataset, analisis, sistema, alCambiarDataset, alAnalizar }: Props) {
  const [seleccion, setSeleccion] = useState<Fuente>(dataset?.fuente ?? "estandar");
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState("");
  const [historico, setHistorico] = useState<Historico | null>(null);
  const archivo = useRef<HTMLInputElement>(null);
  const [comunidades, setComunidades] = useState<ComunidadDiscord[]>([]);
  const [agregando, setAgregando] = useState(false);
  const [quitando, setQuitando] = useState(false);
  const comunidadActual = dataset?.comunidad_discord ?? "principal";
  const esAdmin = sistema?.rol === "ADMIN";

  useEffect(() => { api.get<ComunidadDiscord[]>("/discord/comunidades").then(setComunidades).catch(() => {}); }, []);

  async function quitarComunidad(id: string) {
    setError("");
    try {
      await api.borrar(`/discord/comunidades/${encodeURIComponent(id)}`);
      setComunidades((lista) => lista.filter((c) => c.id !== id));
      setQuitando(false);
      leerDiscord("principal");
    } catch (err) {
      setError((err as Error).message);
    }
  }

  function leerDiscord(comunidad: string, refrescar = false) {
    cargar(api.post<Dataset>("/dataset/fuente", { fuente: "discord", comunidad, refrescar }));
  }
  const ahora = useReloj();

  useEffect(() => { if (dataset) setSeleccion(dataset.fuente); }, [dataset?.fuente]);
  useEffect(() => { api.get<Historico>("/historico").then(setHistorico).catch(() => {}); }, [analisis?.fase]);

  async function cargar(peticion: Promise<Dataset>) {
    setCargando(true);
    setError("");
    try {
      alCambiarDataset(await peticion);
    } catch (err) {
      setError((err as Error).message);
      if (dataset) setSeleccion(dataset.fuente);
    } finally {
      setCargando(false);
    }
  }

  function elegir(fuente: Fuente) {
    setSeleccion(fuente);
    if (fuente === "archivo") return; // se carga recién al elegir el archivo
    if (fuente !== dataset?.fuente) cargar(api.post<Dataset>("/dataset/fuente", { fuente, comunidad: comunidadActual }));
  }

  async function subir(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0];
    e.target.value = "";
    if (f) cargar(api.post<Dataset>("/dataset/archivo", { nombre: f.name, contenido: await f.text() }));
  }

  const mensajes = dataset?.interacciones ?? [];
  const rango = rangoDeFechas(mensajes);
  const canales = contar(mensajes.map((m) => m.channel));
  // Lo analizado en esta sesión (si es de este mismo origen) y lo que ya estaba analizado en la base
  const sesionDelLote = analisis && analisis.comunidad === dataset?.origen_comunidad ? analisis : null;
  const saludDelLote = sesionDelLote?.resumen ? sesionDelLote : null;
  const resultados = new Map(sesionDelLote?.mensajes.map((m) => [m.tracking.message_id, m.opportunity.type]) ?? []);
  const enBase = new Set(dataset?.analizados ?? []);
  const estadoDe = (id: string): EstadoMensaje => resultados.get(id) ?? (enBase.has(id) ? "analizado" : null);
  const analizados = mensajes.filter((m) => estadoDe(m.message_id)).length;
  const pendientes = mensajes.length - analizados;
  const analizando = analisis?.fase === "clasificando";

  const lote = !mensajes.length ? null
    : analizando ? {
      estado: { texto: "Analizando", tono: "en-curso" as const },
      texto: `El motor está analizando el lote: ${analisis!.mensajes.length} de ${analisis!.total} mensajes listos.`,
      boton: "Ver el avance",
    } : pendientes === mensajes.length ? {
      estado: { texto: "Sin analizar", tono: "pendiente" as const },
      texto: "Todavía no se analizaron: analízalos para saber qué vale la pena publicar.",
      boton: `Analizar ${plural(mensajes.length, "mensaje", "mensajes")}`,
    } : pendientes > 0 ? {
      estado: { texto: `${pendientes} sin analizar`, tono: "pendiente" as const },
      texto: sesionDelLote?.simulado
        ? `${plural(analizados, "se analizó", "se analizaron")} en modo simulado, que no se guarda en la base, y ${plural(pendientes, "queda pendiente", "quedan pendientes")}.`
        : `${plural(analizados, "ya se analizó", "ya se analizaron")} y ${plural(pendientes, "queda pendiente", "quedan pendientes")}. Al analizar se procesan solo los nuevos.`,
      boton: sesionDelLote?.simulado ? "Analizar los mensajes" : `Analizar ${plural(pendientes, "mensaje nuevo", "mensajes nuevos")}`,
    } : {
      estado: { texto: "Analizado", tono: "listo" as const },
      texto: "Todos ya se analizaron. Revisa los resultados y los borradores.",
      boton: "Ver los resultados",
    };

  return (
    <>
      <Portada
        titulo={dataset?.fuente === "discord" && comunidadActual !== "principal"
          ? comunidades.find((c) => c.id === comunidadActual)?.nombre ?? "Comunidad de Discord"
          : nombreComunidad(dataset)}
        estado={lote?.estado}
        bajada={mensajes.length > 0
          ? <>{plural(mensajes.length, "mensaje cargado", "mensajes cargados")} de {plural(canales.length, "canal", "canales")}{rango && <> ({rango})</>}. {lote?.texto}</>
          : "Elige de dónde vienen los mensajes para empezar."}
        accion={lote && (
          <button className="boton primario" onClick={alAnalizar} disabled={cargando}>{lote.boton}</button>
        )}
        cifras={mensajes.length ? [
          { valor: mensajes.length, texto: "cargados" },
          { valor: pendientes, texto: "sin analizar" },
          { valor: new Set(mensajes.map((m) => m.autor)).size, texto: "personas" },
          { valor: canales.length, texto: canales.length === 1 ? "canal" : "canales" },
        ] : undefined}
      />

      <div className="com-cuerpo">
        <aside className="com-lateral">
          <fieldset className="com-origen" aria-busy={cargando}>
            <legend>De dónde vienen los mensajes</legend>

            <Opcion valor="estandar" actual={seleccion} alElegir={elegir} titulo="Lote de ejemplo"
              detalle="30 mensajes reales de la comunidad ONE G10, semana 04." />

            <Opcion valor="discord" actual={seleccion} alElegir={elegir} titulo="Discord en vivo"
              detalle={sistema && !sistema.discord_configurado
                ? "Falta el token del bot en el servidor: solo se leen capturas guardadas."
                : "Lee los canales y sus hilos. Cada actualización trae solo lo nuevo."}>
              {seleccion === "discord" && (
                <div className="com-comunidad">
                  <label htmlFor="com-discord" className="etiqueta-campo">Comunidad</label>
                  <div className="com-comunidad-fila">
                    <select id="com-discord" className="entrada" value={comunidadActual} disabled={cargando}
                      onChange={(e) => { setQuitando(false); leerDiscord(e.target.value); }}>
                      {comunidades.map((c) => (
                        <option key={c.id} value={c.id}>{c.nombre}{c.servidor ? ` (${c.servidor})` : ""}</option>
                      ))}
                    </select>
                    {(() => {
                      const actual = comunidades.find((c) => c.id === comunidadActual);
                      if (!actual || actual.principal) return null;
                      return <span className="tenue com-token">{actual.servidor} (token {actual.token_final ?? "guardado"})</span>;
                    })()}
                    {esAdmin && (
                      <div className="com-acciones">
                        <button className="boton fantasma chico com-agregar" onClick={() => setAgregando(true)}>
                          + Agregar una comunidad
                        </button>
                        {comunidadActual !== "principal" && !quitando && (
                          <button className="boton fantasma chico peligro" onClick={() => setQuitando(true)}>Quitar</button>
                        )}
                      </div>
                    )}
                    {quitando && (() => {
                      const actual = comunidades.find((c) => c.id === comunidadActual);
                      return actual && (
                        <div className="com-confirmar" role="group" aria-label="Confirmar que quieres quitar la comunidad">
                          <p>¿Quitar «{actual.nombre}» de la lista? Se borra su token; los mensajes ya leídos y analizados se conservan.</p>
                          <div className="com-acciones">
                            <button className="boton chico peligro" onClick={() => quitarComunidad(actual.id)}>Quitar comunidad</button>
                            <button className="boton fantasma chico" onClick={() => setQuitando(false)}>Cancelar</button>
                          </div>
                        </div>
                      );
                    })()}
                  </div>
                </div>
              )}
              {dataset?.fuente === "discord" && (
                <div className="com-estado">
                  <span className="sec">
                    {dataset.consultado
                      ? `Actualizado ${haceCuanto(dataset.consultado, ahora)}${dataset.nuevos ? `, ${plural(dataset.nuevos, "mensaje nuevo", "mensajes nuevos")}` : ", sin mensajes nuevos"}`
                      : "Mensajes guardados"}
                  </span>
                  <button className="boton chico" disabled={cargando}
                    onClick={() => leerDiscord(comunidadActual, true)}>
                    Actualizar
                  </button>
                </div>
              )}
            </Opcion>

            <Opcion valor="archivo" actual={seleccion} alElegir={elegir} titulo="Archivo JSON"
              detalle="Un lote exportado en Formato A (spec.md).">
              {seleccion === "archivo" && (
                <div className="com-estado">
                  <span className="sec com-archivo">
                    {dataset?.fuente === "archivo" ? dataset.archivo : "Ningún archivo elegido"}
                  </span>
                  <button className="boton chico" disabled={cargando} onClick={() => archivo.current?.click()}>
                    {dataset?.fuente === "archivo" ? "Cambiar archivo" : "Elegir archivo"}
                  </button>
                </div>
              )}
            </Opcion>
            <input ref={archivo} type="file" accept="application/json,.json" hidden onChange={subir} />
            {agregando && (
              <AgregarComunidad alCerrar={() => setAgregando(false)} alAgregar={(c) => {
                setComunidades((lista) => [...lista, c]);
                setSeleccion("discord");
                leerDiscord(c.id, true);
              }} />
            )}

            {cargando && <p className="sec com-cargando" role="status"><span className="cargando" /> Cargando mensajes…</p>}
            {error && <p className="nota error" role="alert">{error}</p>}
            {dataset?.aviso && <p className="nota aviso">{dataset.aviso}</p>}
          </fieldset>

          {canales.length > 0 && (
            <section className="com-bloque">
              <h2>Por canal</h2>
              <ul className="com-canales">
                {canales.slice(0, 6).map(([canal, n]) => (
                  <li key={canal}>
                    <span className="com-canal-nombre">#{canal}</span>
                    <span className="num sec">{n}</span>
                    <span className="com-canal-barra" aria-hidden="true">
                      <i style={{ width: `${(n / canales[0][1]) * 100}%` }} />
                    </span>
                  </li>
                ))}
              </ul>
              {canales.length > 6 && <p className="tenue com-nota">y {plural(canales.length - 6, "canal más", "canales más")}</p>}
            </section>
          )}

          {!saludDelLote && mensajes.length > 0 && (
            <p className="com-pista">
              Al analizar el lote verás aquí el sentimiento de la comunidad, los temas que más se repiten y quién
              necesita apoyo.
            </p>
          )}
        </aside>

        <section className="com-principal" aria-label="Vista previa de los mensajes">
          {saludDelLote && (
            <div className="seccion">
              <div className="seccion-cabeza">
                <h2>Resultado del último análisis</h2>
                <span className="sec" style={{ fontSize: 13.5 }}>
                  {plural(saludDelLote.mensajes.length, "mensaje analizado", "mensajes analizados")}
                  {saludDelLote.simulado ? " en modo simulado" : ""}
                </span>
              </div>
              <Salud analisis={saludDelLote} />
            </div>
          )}
          <Conversacion mensajes={mensajes} cargando={cargando} estadoDe={estadoDe} />
          {historico && historico.mensajes > 0 && <HistoricoBase historico={historico} />}
        </section>
      </div>
    </>
  );
}

function Opcion({ valor, actual, alElegir, titulo, detalle, children }: {
  valor: Fuente; actual: Fuente; alElegir: (f: Fuente) => void; titulo: string; detalle: string; children?: React.ReactNode;
}) {
  const marcada = valor === actual;
  return (
    <div className={`com-opcion ${marcada ? "marcada" : ""}`}>
      <label>
        <input type="radio" name="origen" value={valor} checked={marcada} onChange={() => alElegir(valor)} />
        <span>
          <b>{titulo}</b>
          <span className="sec">{detalle}</span>
        </span>
      </label>
      {children}
    </div>
  );
}

/** Vista previa con forma de conversación: por día, con quién habla y en qué canal. */
function Conversacion({ mensajes, cargando, estadoDe }: {
  mensajes: Interaccion[]; cargando: boolean; estadoDe: (id: string) => EstadoMensaje;
}) {
  const [canal, setCanal] = useState<string | null>(null);
  const [vista, setVista] = useState<"todos" | "pendientes" | "analizados">("todos");
  const [todos, setTodos] = useState(false);
  useEffect(() => { setCanal(null); setTodos(false); setVista("todos"); }, [mensajes]);

  const canales = useMemo(() => contar(mensajes.map((m) => m.channel)), [mensajes]);
  const pendientes = mensajes.filter((m) => !estadoDe(m.message_id)).length;
  const filtrados = [...mensajes]
    .filter((m) => !canal || m.channel === canal)
    .filter((m) => vista === "todos" || (vista === "pendientes") === !estadoDe(m.message_id))
    .sort((a, b) => b.timestamp.localeCompare(a.timestamp));
  const visibles = todos ? filtrados : filtrados.slice(0, VISIBLES);
  const dias = agruparPorDia(visibles);

  if (!mensajes.length) {
    return (
      <Vacio titulo={cargando ? "Cargando mensajes…" : "Este origen no tiene mensajes"}>
        {cargando ? "En unos segundos verás la conversación." : "Prueba con otro origen o actualiza Discord."}
      </Vacio>
    );
  }

  return (
    <div className="hoja com-conversacion">
      <div className="com-conv-cabeza">
        <div>
          <h2>Mensajes cargados</h2>
          <p className="sec" style={{ fontSize: 13.5 }}>Cada mensaje indica si ya se analizó y qué resultado tuvo.</p>
        </div>
        <div className="segmentos" role="group" aria-label="Filtrar por estado">
          <button aria-pressed={vista === "todos"} onClick={() => setVista("todos")}>Todos<span className="n">{mensajes.length}</span></button>
          <button aria-pressed={vista === "pendientes"} onClick={() => setVista("pendientes")}>Sin analizar<span className="n">{pendientes}</span></button>
          <button aria-pressed={vista === "analizados"} onClick={() => setVista("analizados")}>Analizados<span className="n">{mensajes.length - pendientes}</span></button>
        </div>
      </div>
      {canales.length > 1 && (
        <div className="com-filtro-canal" role="group" aria-label="Filtrar por canal">
          <button aria-pressed={!canal} onClick={() => setCanal(null)}>Todos los canales</button>
          {canales.map(([c, n]) => (
            <button key={c} aria-pressed={canal === c} onClick={() => setCanal(canal === c ? null : c)}>#{c} <span className="num">{n}</span></button>
          ))}
        </div>
      )}
      {!filtrados.length && (
        <p className="sec" style={{ padding: "18px 22px" }}>
          {vista === "pendientes" ? "No quedan mensajes sin analizar." : "Ningún mensaje coincide con el filtro."}
        </p>
      )}
      {dias.map(([dia, grupo]) => (
        <section key={dia} className="com-dia" aria-label={dia}>
          <h3 className="com-dia-titulo"><span>{dia}</span></h3>
          <ol className="com-mensajes">
            {grupo.map((m, i) => {
              const seguido = i > 0 && grupo[i - 1].autor === m.autor && grupo[i - 1].channel === m.channel &&
                Math.abs(new Date(grupo[i - 1].timestamp).getTime() - new Date(m.timestamp).getTime()) < 10 * 60e3;
              return (
                <li key={m.message_id} className={`com-msg ${seguido ? "seguido" : ""}`}>
                  {seguido ? <span className="com-avatar vacio-av" aria-hidden="true" /> : (
                    <span className="com-avatar" style={colorDe(m.autor)} aria-hidden="true">{iniciales(m.autor)}</span>
                  )}
                  <div>
                    {!seguido && (
                      <p className="com-msg-cabeza">
                        <b>{m.autor}</b>
                        <span className="tenue">#{m.channel}</span>
                        <time className="tenue num" dateTime={m.timestamp}>{hora(m.timestamp)}</time>
                      </p>
                    )}
                    <div className="com-msg-cuerpo">
                      <p className="com-texto burbuja">{m.texto}</p>
                      <EstadoDelMensaje estado={estadoDe(m.message_id)} />
                    </div>
                  </div>
                </li>
              );
            })}
          </ol>
        </section>
      ))}
      {filtrados.length > VISIBLES && (
        <div className="com-mas">
          <button className="boton chico" onClick={() => setTodos(!todos)} aria-expanded={todos}>
            {todos ? "Ver menos" : `Ver los ${filtrados.length} mensajes`}
          </button>
        </div>
      )}
    </div>
  );
}

type EstadoMensaje = TipoOportunidad | "analizado" | null;

function EstadoDelMensaje({ estado }: { estado: EstadoMensaje }) {
  if (!estado) return <span className="estado-msg sin-analizar">Sin analizar</span>;
  if (estado === "analizado") return <span className="estado-msg chip">Analizado</span>;
  return <span className={`estado-msg chip ${estado}`}>{TIPOS[estado]}</span>;
}

function HistoricoBase({ historico }: { historico: Historico }) {
  const grupos: [string, Record<string, number> | undefined, (k: string) => string][] = [
    ["Por tipo", historico.tipos, (k) => TIPOS[k as TipoOportunidad] ?? k],
    ["Por sentimiento", historico.sentimientos, (k) => SENTIMIENTOS[k as Sentimiento] ?? k],
    ["Canales más activos", historico.canales, (k) => `#${k}`],
  ];
  return (
    <details className="hoja com-historico">
      <summary>
        Histórico guardado en la base: {plural(historico.mensajes, "mensaje analizado", "mensajes analizados")}
        <span className="tenue"> ({historico.base})</span>
      </summary>
      <div className="com-historico-cuerpo">
        {grupos.map(([titulo, datos, nombre]) => Object.keys(datos ?? {}).length > 0 && (
          <div key={titulo}>
            <span className="etiqueta-campo">{titulo}</span>
            <div className="temas">
              {Object.entries(datos!).sort((a, b) => b[1] - a[1]).map(([k, n]) => (
                <span key={k} className="tema"><span className="num">{n}</span> {tema(nombre(k))}</span>
              ))}
            </div>
          </div>
        ))}
      </div>
    </details>
  );
}

// ─── Utilidades de presentación ──────────────────────────────────────────────

function nombreComunidad(d: Dataset | null) {
  if (!d) return "Comunidad";
  if (d.fuente === "discord") return "Servidor de Discord";
  return (d.origen_comunidad ?? "Comunidad").replace(/_/g, " ");
}

function contar(valores: string[]): [string, number][] {
  const conteo = new Map<string, number>();
  valores.forEach((v) => conteo.set(v, (conteo.get(v) ?? 0) + 1));
  return [...conteo.entries()].sort((a, b) => b[1] - a[1]);
}

const DIA = new Intl.DateTimeFormat("es-PE", { day: "numeric", month: "long" });
const DIA_CORTO = new Intl.DateTimeFormat("es-PE", { day: "numeric", month: "short" });

function rangoDeFechas(mensajes: Interaccion[]) {
  const t = mensajes.map((m) => new Date(m.timestamp).getTime()).filter((x) => !Number.isNaN(x));
  if (!t.length) return "";
  const [a, b] = [new Date(Math.min(...t)), new Date(Math.max(...t))];
  return a.toDateString() === b.toDateString() ? DIA.format(a) : `${DIA_CORTO.format(a)} al ${DIA_CORTO.format(b)}`;
}

function nombreDia(fecha: Date) {
  const hoy = new Date();
  const ayer = new Date(hoy.getTime() - 864e5);
  if (fecha.toDateString() === hoy.toDateString()) return "Hoy";
  if (fecha.toDateString() === ayer.toDateString()) return "Ayer";
  return DIA.format(fecha);
}

function agruparPorDia(mensajes: Interaccion[]): [string, Interaccion[]][] {
  const dias = new Map<string, Interaccion[]>();
  mensajes.forEach((m) => {
    const clave = nombreDia(new Date(m.timestamp));
    dias.set(clave, [...(dias.get(clave) ?? []), m]);
  });
  return [...dias.entries()];
}

const hora = (iso: string) => new Date(iso).toLocaleTimeString("es-PE", { hour: "2-digit", minute: "2-digit" });

function iniciales(nombre: string) {
  const partes = nombre.replace(/[^\p{L}\p{N} ]/gu, "").trim().split(/\s+/);
  return ((partes[0]?.[0] ?? "?") + (partes[1]?.[0] ?? "")).toUpperCase();
}

const TONOS = [
  ["var(--acento-suave)", "var(--acento)"],
  ["var(--logro-f)", "var(--logro)"],
  ["var(--faq-f)", "var(--faq)"],
  ["var(--exito-f)", "var(--exito)"],
  ["var(--feedback-f)", "var(--feedback)"],
];

function colorDe(nombre: string): React.CSSProperties {
  let h = 2166136261; // FNV-1a: reparte bien nombres parecidos entre los tonos
  for (const c of nombre) h = Math.imul(h ^ c.charCodeAt(0), 16777619);
  h >>>= 0;
  const [fondo, tinta] = TONOS[h % TONOS.length];
  return { background: fondo, color: tinta };
}

function haceCuanto(iso: string, ahora: number) {
  const s = Math.max(0, Math.round((ahora - new Date(iso).getTime()) / 1000));
  if (s < 60) return "hace un momento";
  const m = Math.round(s / 60);
  if (m < 60) return `hace ${plural(m, "minuto", "minutos")}`;
  return `a las ${hora(iso)}`;
}

/** Re-dibuja cada 30 s para que «Actualizado hace…» no quede viejo. */
function useReloj() {
  const [ahora, setAhora] = useState(Date.now());
  useEffect(() => {
    const id = window.setInterval(() => setAhora(Date.now()), 30000);
    return () => window.clearInterval(id);
  }, []);
  return ahora;
}
