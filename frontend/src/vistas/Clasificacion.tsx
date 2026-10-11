import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import { plural } from "../etiquetas";
import { FilaClasificada } from "../componentes/Mensaje";
import { Salud } from "../componentes/Salud";
import { Portada, Vacio } from "../componentes/Marca";
import type { Analisis, Dataset, Mensaje, Sistema } from "../tipos";

const FILTROS: { id: string; nombre: string; filtra: (m: Mensaje) => boolean }[] = [
  { id: "oportunidades", nombre: "Oportunidades", filtra: (m) => m.es_oportunidad },
  { id: "apoyo", nombre: "Necesitan apoyo", filtra: (m) => m.necesita_apoyo },
  { id: "feedback", nombre: "Feedback", filtra: (m) => m.opportunity.type === "FEEDBACK" },
  { id: "descartados", nombre: "Descartados", filtra: (m) => !m.es_oportunidad },
  { id: "todos", nombre: "Todos", filtra: () => true },
];

interface Props {
  dataset: Dataset | null;
  analisis: Analisis | null;
  sistema: Sistema | null;
  alActualizar: () => void;
  alCurar: () => void;
  alElegirFuente: () => void;
}

export function Clasificacion({ dataset, analisis, sistema, alActualizar, alCurar, alElegirFuente }: Props) {
  const total = dataset?.total ?? 0;
  const [cantidad, setCantidad] = useState(total);
  const [simulado, setSimulado] = useState(false);
  const [omitir, setOmitir] = useState(true);
  const [filtro, setFiltro] = useState("oportunidades");
  const [aviso, setAviso] = useState<{ tipo: string; texto: string } | null>(null);
  const [enviando, setEnviando] = useState(false);
  const vistos = useRef(new Set<string>());

  useEffect(() => setCantidad(total), [total]);
  // Recuerda qué mensajes ya se mostraron, para resaltar solo los que llegan con cada lote
  useEffect(() => { analisis?.mensajes.forEach((m) => vistos.current.add(m.tracking.message_id)); });

  async function analizar() {
    setEnviando(true);
    setAviso(null);
    vistos.current = new Set();
    try {
      const r = await api.post<{ mensajes: number; repetidos: number; quedan: number }>("/analisis",
        { cantidad, simulado, omitir_repetidos: omitir });
      const partes = [`Se ${r.mensajes === 1 ? "analiza 1 mensaje" : `analizan ${r.mensajes} mensajes`}`];
      if (r.repetidos) partes.push(`se omite${r.repetidos === 1 ? "" : "n"} ${plural(r.repetidos, "ya analizado", "ya analizados")}`);
      if (r.quedan) partes.push(`${plural(r.quedan, "queda pendiente", "quedan pendientes")} para la próxima vez`);
      setAviso({ tipo: "", texto: partes.join(", ") + "." });
      setFiltro("oportunidades");
      alActualizar();
    } catch (err) {
      setAviso({ tipo: "error", texto: (err as Error).message });
    } finally {
      setEnviando(false);
    }
  }

  if (!total) {
    return (
      <>
        <Portada titulo="Qué vale la pena publicar" bajada="Primero carga los mensajes de la comunidad." />
        <Vacio titulo="No hay mensajes cargados"
          acciones={<button className="boton primario" onClick={alElegirFuente}>Elegir el origen de los mensajes</button>}>
          Elige un lote de ejemplo, Discord en vivo o un archivo JSON.
        </Vacio>
      </>
    );
  }

  const fase = analisis?.fase ?? "inactivo";
  const trabajando = fase === "clasificando";
  const mensajes = analisis?.mensajes ?? [];
  const resumen = analisis?.resumen;
  const filtroActual = FILTROS.find((f) => f.id === filtro)!;
  const mostrados = resumen ? mensajes.filter(filtroActual.filtra) : mensajes;
  const nuevos = new Set(mensajes.map((m) => m.tracking.message_id).filter((id) => !vistos.current.has(id)));
  const pendientes = analisis ? Object.values(analisis.avisos).reduce((s, n) => s + n, 0) : 0;

  return (
    <>
      <Portada
        titulo="Qué vale la pena publicar"
        bajada="El motor lee cada mensaje, detecta su sentimiento y sus temas, y le da un score según su tipo. Los que superan el umbral pasan a redacción."
        accion={resumen && analisis?.paquete?.activos
          ? <button className="boton primario" onClick={alCurar}>Revisar {plural(analisis.paquete.activos, "borrador", "borradores")}</button>
          : undefined}
        cifras={resumen && analisis ? [
          { valor: resumen.total_interacciones_procesadas, texto: "analizados" },
          { valor: resumen.oportunidades_detectadas, texto: "oportunidades" },
          { valor: analisis.paquete?.activos ?? 0, texto: "borradores" },
          { valor: resumen.consultas_operativas + resumen.feedback_recibido, texto: "para el equipo" },
        ] : undefined}
      />

      <section className="hoja">
        <div className="mando">
          <div className="campo">
            <label htmlFor="cantidad">Mensajes a analizar</label>
            <span className="tenue" style={{ fontSize: 12.5 }}>
              {omitir && !simulado ? "Se toman los más recientes que todavía no se analizaron." : "Se toman los más recientes del lote."}
            </span>
            <div className="cantidad">
              <input type="range" min={1} max={total} value={cantidad} aria-label="Mensajes a analizar"
                onChange={(e) => setCantidad(Number(e.target.value))} />
              <input id="cantidad" className="entrada num" type="number" min={1} max={total} value={cantidad}
                onChange={(e) => setCantidad(Math.min(total, Math.max(1, Number(e.target.value) || 1)))} />
              <span className="tenue">de {total}</span>
            </div>
          </div>
          <div className="opciones">
            <label className="interruptor">
              <input type="checkbox" checked={simulado} onChange={(e) => setSimulado(e.target.checked)} />
              Modo simulado (sin IA, no gasta cuota)
            </label>
            <label className="interruptor">
              <input type="checkbox" checked={omitir && !simulado} disabled={simulado}
                onChange={(e) => setOmitir(e.target.checked)} />
              Omitir los ya procesados{sistema ? ` (${sistema.base})` : ""}
            </label>
          </div>
          <span style={{ flex: 1 }} />
          <button className="boton primario" onClick={analizar} disabled={enviando || trabajando}>
            {enviando || trabajando ? <span className="cargando" /> : null}
            Analizar {plural(cantidad, "mensaje", "mensajes")}
          </button>
        </div>
        {trabajando && analisis && (
          <div className="progreso" aria-live="polite">
            <div className="pista"><i style={{ width: `${(mensajes.length / Math.max(analisis.total, 1)) * 100}%` }} /></div>
            <span className="sec num">
              Clasificando {mensajes.length} de {analisis.total} ({Math.round(analisis.transcurrido)} s). Los mensajes
              aparecen a medida que responde cada lote.
            </span>
          </div>
        )}
        {analisis?.redaccion && (
          <div className="progreso" aria-live="polite">
            {analisis.redaccion.terminado ? (
              <span className="sec num">
                Clasificado en {analisis.segundos_clasificacion?.toFixed(1)} s y{" "}
                {plural(analisis.redaccion.listos, "borrador redactado", "borradores redactados")} en{" "}
                {analisis.segundos_redaccion?.toFixed(1)} s más{analisis.simulado ? " (modo simulado)" : ""}.
                {typeof analisis.guardados_en_base === "number" &&
                  ` ${plural(analisis.guardados_en_base, "mensaje nuevo guardado", "mensajes nuevos guardados")} en la base.`}
              </span>
            ) : (
              <>
                <div className="pista">
                  <i style={{ width: `${(analisis.redaccion.lotes_listos / Math.max(analisis.redaccion.lotes, 1)) * 100}%` }} />
                </div>
                <span className="sec num">
                  Redactando borradores: {analisis.redaccion.listos} de {analisis.redaccion.total} listos. Ya puedes
                  revisarlos en Curaduría.
                </span>
              </>
            )}
          </div>
        )}
      </section>

      {aviso && <p className={`nota ${aviso.tipo}`} role="status">{aviso.texto}</p>}
      {analisis?.error && <p className="nota error" role="alert">{analisis.error}</p>}
      {pendientes > 0 && analisis?.redaccion?.terminado && (
        <p className="nota aviso">
          El paquete quedó parcial: {analisis.avisos.sin_analisis ?? 0} sin análisis,{" "}
          {analisis.avisos.sin_clasificacion ?? 0} sin clasificar y {analisis.avisos.piezas_pendientes ?? 0} piezas
          sin redactar. Revisa las cuotas de la IA.
        </p>
      )}

      {resumen && analisis && (
        <>
          <Salud analisis={analisis} alVerApoyo={() => setFiltro("apoyo")} />
          {resumen.tendencias_detectadas.length > 0 && (
            <details className="hoja">
              <summary className="hoja-cuerpo" style={{ cursor: "pointer", fontWeight: 600 }}>
                {plural(resumen.tendencias_detectadas.length, "tendencia detectada", "tendencias detectadas")}
              </summary>
              <ul className="hoja-cuerpo" style={{ paddingTop: 0, margin: 0, display: "grid", gap: 6 }}>
                {resumen.tendencias_detectadas.map((t) => (
                  <li key={t.tema}><b>{t.tema.replace(/_/g, " ")}</b>: <span className="sec">{t.descripcion}</span></li>
                ))}
              </ul>
            </details>
          )}
        </>
      )}

      {mensajes.length > 0 && (
        <section className="seccion">
          {resumen ? (
            <div className="seccion-cabeza">
              <div className="segmentos" role="group" aria-label="Filtrar mensajes">
                {FILTROS.map((f) => (
                  <button key={f.id} aria-pressed={filtro === f.id} onClick={() => setFiltro(f.id)}>
                    {f.nombre}<span className="n">{mensajes.filter(f.filtra).length}</span>
                  </button>
                ))}
              </div>
            </div>
          ) : <h2>Mensajes clasificados</h2>}
          {mostrados.length ? (
            <div className="hoja lista">
              {mostrados.map((m) => (
                <FilaClasificada key={m.tracking.message_id} m={m} umbrales={sistema?.umbrales ?? {}}
                  nuevo={trabajando && nuevos.has(m.tracking.message_id)} />
              ))}
            </div>
          ) : <p className="nota">Ningún mensaje coincide con «{filtroActual.nombre}».</p>}
        </section>
      )}
    </>
  );
}
