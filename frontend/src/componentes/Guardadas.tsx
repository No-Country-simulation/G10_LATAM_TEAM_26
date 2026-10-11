import { useEffect, useState } from "react";
import { api, tokenActual } from "../api";
import { FORMATOS, plural } from "../etiquetas";
import { Vacio } from "./Marca";
import type { Formato, Guardadas as DatosGuardadas, PublicacionGuardada } from "../tipos";

const FECHA = new Intl.DateTimeFormat("es-PE", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });

/** Publicaciones que ya están en el bucket de OCI, incluidas las guardadas con la versión anterior del panel. */
export function Guardadas({ recarga, alCargar }: { recarga: number; alCargar?: (lista: PublicacionGuardada[]) => void }) {
  const [datos, setDatos] = useState<DatosGuardadas | null>(null);
  const [cargando, setCargando] = useState(true);
  const [formato, setFormato] = useState<string>("todos");

  async function cargar(refrescar = false) {
    setCargando(true);
    try {
      const nuevos = await api.get<DatosGuardadas>(`/publicaciones${refrescar ? "?refrescar=true" : ""}`);
      setDatos(nuevos);
      alCargar?.(nuevos.publicaciones);
    } catch (err) {
      setDatos({ conectado: true, bucket: "", publicaciones: [], error: (err as Error).message });
    } finally {
      setCargando(false);
    }
  }
  useEffect(() => { cargar(recarga > 0); }, [recarga]);

  const lista = datos?.publicaciones ?? [];
  const formatos = [...new Set(lista.map((p) => p.formato))];
  const visibles = lista.filter((p) => formato === "todos" || p.formato === formato);

  return (
    <section className="seccion" aria-busy={cargando}>
      <div className="seccion-cabeza">
        <div>
          <h2>Guardadas en OCI</h2>
          {datos?.conectado && !datos.error && (
            <p className="sec" style={{ fontSize: 14 }}>
              {plural(lista.length, "publicación", "publicaciones")} en el bucket {datos.bucket}
            </p>
          )}
        </div>
        <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
          {formatos.length > 1 && (
            <div className="segmentos" role="group" aria-label="Filtrar por formato">
              <button aria-pressed={formato === "todos"} onClick={() => setFormato("todos")}>
                Todas<span className="n">{lista.length}</span>
              </button>
              {formatos.map((f) => (
                <button key={f} aria-pressed={formato === f} onClick={() => setFormato(f)}>
                  {FORMATOS[f as Formato] ?? f}<span className="n">{lista.filter((p) => p.formato === f).length}</span>
                </button>
              ))}
            </div>
          )}
          <button className="boton chico" onClick={() => cargar(true)} disabled={cargando}>
            {cargando && <span className="cargando" />} Actualizar
          </button>
        </div>
      </div>

      {datos && !datos.conectado && (
        <p className="nota aviso">
          Sin conexión con OCI: faltan las credenciales del bucket en el .env del servidor.
        </p>
      )}
      {datos?.error && <p className="nota error" role="alert">No se pudo leer el bucket ({datos.error}).</p>}
      {!cargando && datos?.conectado && !datos.error && !lista.length && (
        <Vacio titulo="Todavía no hay publicaciones en el bucket">
          Cuando guardes un paquete, sus publicaciones aparecen aquí.
        </Vacio>
      )}
      {cargando && !datos && <p className="sec"><span className="cargando" /> Leyendo el bucket…</p>}

      {visibles.length > 0 && (
        <div className="guardadas">
          {visibles.map((p) => <Tarjeta key={`${p.id}-${p.objeto}`} p={p} />)}
        </div>
      )}
    </section>
  );
}

function Tarjeta({ p }: { p: PublicacionGuardada }) {
  const [abierta, setAbierta] = useState(false);
  const [copiado, setCopiado] = useState(false);
  const largo = p.texto.length > 260;
  const texto = [p.titulo, p.texto, p.hashtags?.join(" ")].filter(Boolean).join("\n\n");

  async function copiar() {
    try {
      await navigator.clipboard.writeText(texto);
      setCopiado(true);
      setTimeout(() => setCopiado(false), 2000);
    } catch {
      /* sin portapapeles: el texto se puede seleccionar a mano */
    }
  }

  return (
    <article className="guardada hoja">
      {p.imagen && (
        <img src={`/api/publicaciones/imagen?ruta=${encodeURIComponent(p.imagen)}&token=${encodeURIComponent(tokenActual())}`}
          alt="" loading="lazy" />
      )}
      <div className="guardada-cuerpo">
        <div className="guardada-meta">
          <span className={`chip formato-${p.formato}`}>
            {FORMATOS[p.formato as Formato] ?? p.formato}
          </span>
          {p.estado && p.estado !== "aprobado" && <span className="tenue">{p.estado}</span>}
        </div>
        {p.titulo && <h3>{p.titulo}</h3>}
        <p className={`cita guardada-texto ${largo && !abierta ? "recortado" : ""}`}>{p.texto}</p>
        {largo && (
          <button className="boton fantasma chico guardada-mas" onClick={() => setAbierta(!abierta)} aria-expanded={abierta}>
            {abierta ? "Ver menos" : "Ver completo"}
          </button>
        )}
        {p.hashtags?.length > 0 && <p className="guardada-tags">{p.hashtags.join(" ")}</p>}
        <footer className="guardada-pie">
          <span className="sec">
            {p.autor ? `De ${p.autor}` : "Autor sin registrar"}
            {p.mensaje_id ? ` (${p.mensaje_id})` : ""}
          </span>
          <span className="tenue num">
            <time dateTime={p.fecha}>{FECHA.format(new Date(p.fecha))}</time>
            {p.veces_guardado > 1 ? `, guardada ${p.veces_guardado} veces` : ""}
          </span>
          <button className="boton chico" onClick={copiar}>{copiado ? "Texto copiado" : "Copiar texto"}</button>
        </footer>
      </div>
    </article>
  );
}
