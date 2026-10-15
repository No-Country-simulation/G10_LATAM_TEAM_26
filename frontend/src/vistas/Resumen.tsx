import { useEffect, useState } from "react";
import { api } from "../api";
import { TIPOS, plural, tema } from "../etiquetas";
import { Barras, BarraSentimiento, ColumnasApiladas, Embudo, TasaAprobacion, Tarjeta } from "../componentes/Graficos";
import { Portada, Vacio } from "../componentes/Marca";
import type { Guardadas, TipoOportunidad } from "../tipos";

interface DatosResumen {
  base: string;
  mensajes: number;
  oportunidades?: number;
  demo?: boolean;
  por_dia?: { fecha: string; mensajes: number; oportunidades: number }[];
  tipos?: Record<string, number>;
  sentimientos?: Record<string, number>;
  canales?: Record<string, number>;
  temas?: Record<string, number>;
  activos?: Record<string, number>;
  aprobacion?: Aprobacion;
  ultima_actividad?: string | null;
  error?: string;
}

interface Conteo { aprobados: number; descartados: number; pendientes: number }
interface Aprobacion {
  total: Conteo;
  por_tipo: Record<string, Conteo>;
  por_rango: (Conteo & { desde: number; hasta: number })[];
}

const SCORE = new Intl.NumberFormat("es-PE", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const etiquetaRango = (desde: number, hasta: number) =>
  desde === 0 ? `Menos de ${SCORE.format(hasta)}` : hasta >= 1 ? `${SCORE.format(desde)} o más` : `${SCORE.format(desde)} a ${SCORE.format(hasta - 0.01)}`;

const DIA = new Intl.DateTimeFormat("es-PE", { day: "numeric", month: "short" });
const FECHA = new Intl.DateTimeFormat("es-PE", { day: "numeric", month: "long", hour: "2-digit", minute: "2-digit" });
const CON_CONTENIDO = new Set(["SUCCESS_STORY", "MILESTONE", "FAQ"]);

export function Resumen({ alAnalizar, umbrales = {} }: { alAnalizar: () => void; umbrales?: Record<string, number> }) {
  const [datos, setDatos] = useState<DatosResumen | null>(null);
  const [guardadas, setGuardadas] = useState<number | null>(null);

  useEffect(() => {
    api.get<DatosResumen>("/resumen").then(setDatos).catch(() => setDatos({ base: "", mensajes: 0, error: "sin conexión" }));
    api.get<Guardadas>("/publicaciones").then((g) => setGuardadas(g.publicaciones.length)).catch(() => setGuardadas(null));
  }, []);

  if (!datos) {
    return <Portada titulo="Resumen de la comunidad" bajada="Cargando las métricas…" />;
  }
  if (!datos.mensajes) { // sin análisis guardados ni lote de ejemplo
    return (
      <>
        <Portada titulo="Resumen de la comunidad" bajada="Todavía no hay mensajes analizados guardados en la base." />
        <Vacio titulo={datos.error ? "No se pudo leer la base" : "Aún no hay métricas"}
          acciones={<button className="boton primario" onClick={alAnalizar}>Analizar un lote</button>}>
          {datos.error ? `La base no respondió (${datos.error}).` : "Cuando analices mensajes con IA, el resumen aparece aquí."}
        </Vacio>
      </>
    );
  }

  const tipos = Object.entries(datos.tipos ?? {}).sort((a, b) => b[1] - a[1]);
  const sent = datos.sentimientos ?? {};
  const activos = datos.activos ?? {};
  const borradores = Object.values(activos).reduce((s, n) => s + n, 0);
  const aprobados = (activos.aprobado ?? 0) + (activos.publicado ?? 0);
  const porDia = (datos.por_dia ?? []).map((d) => ({
    etiqueta: DIA.format(new Date(`${d.fecha}T12:00:00`)), destacado: d.oportunidades, total: d.mensajes,
  }));
  const canales = Object.entries(datos.canales ?? {});
  const temas = Object.entries(datos.temas ?? {});
  const oportunidades = datos.oportunidades ?? 0;
  const ap = datos.aprobacion;
  const gruposTipo = Object.entries(ap?.por_tipo ?? {})
    .filter(([t]) => CON_CONTENIDO.has(t))
    .map(([t, c]) => ({ etiqueta: TIPOS[t as TipoOportunidad] ?? t, ...c }));
  const gruposRango = (ap?.por_rango ?? [])
    .filter((r) => r.aprobados + r.descartados + r.pendientes > 0)
    .map((r) => ({ etiqueta: etiquetaRango(r.desde, r.hasta), aprobados: r.aprobados, descartados: r.descartados, pendientes: r.pendientes }));
  const decididos = (ap?.total.aprobados ?? 0) + (ap?.total.descartados ?? 0);
  const textoUmbrales = Object.entries(umbrales)
    .map(([t, u]) => `${TIPOS[t as TipoOportunidad] ?? t} ${SCORE.format(u)}`).join(", ");

  return (
    <>
      <Portada
        titulo="Resumen de la comunidad"
        bajada={datos.demo
          ? "Así se ve el Resumen con el lote de ejemplo de la semana 04. Con tus propios análisis, aquí aparecen los tuyos."
          : <>Todo lo que se analizó y se curó, guardado en {datos.base}.
            {datos.ultima_actividad && <> Último análisis: {FECHA.format(new Date(datos.ultima_actividad))}</>}</>}
        cifras={[
          { valor: datos.mensajes, texto: "mensajes analizados" },
          { valor: oportunidades, texto: `oportunidades (${Math.round((oportunidades / datos.mensajes) * 100)}%)` },
          { valor: guardadas ?? "—", texto: "publicaciones en OCI" },
          { valor: aprobados, texto: "borradores aprobados" },
        ]}
      />

      {datos.demo && (
        <div className="nota aviso aviso-cambios" role="note">
          <span><b>Datos de ejemplo.</b> Todavía no hay análisis guardados en la base, así que se muestra el lote de ejemplo
            (30 mensajes, sin borradores ni aprobaciones). Analiza un lote con IA y guarda un paquete para ver los tuyos.</span>
          <button className="boton chico primario" onClick={alAnalizar}>Analizar un lote</button>
        </div>
      )}

      <div className="resumen">
        <Tarjeta ancho titulo="Actividad por día"
          bajada={`Mensajes analizados cada día y cuántos fueron oportunidades de contenido (${plural(porDia.length, "día", "días")} con actividad).`}
          tabla={{ columnas: ["Día", "Mensajes", "Oportunidades"], filas: (datos.por_dia ?? []).map((d) => [d.fecha, d.mensajes, d.oportunidades]) }}>
          <ColumnasApiladas datos={porDia} etiquetaDestacada="Oportunidades" etiquetaResto="Otros mensajes" />
        </Tarjeta>

        <Tarjeta titulo="Qué tipo de mensajes llegan"
          bajada="En color, los tipos que pueden convertirse en publicaciones; en gris, los que no generan contenido."
          tabla={{ columnas: ["Tipo", "Mensajes"], filas: tipos.map(([t, n]) => [TIPOS[t as TipoOportunidad] ?? t, n]) }}>
          <Barras total={datos.mensajes}
            datos={tipos.map(([t, n]) => ({ etiqueta: TIPOS[t as TipoOportunidad] ?? t, valor: n, destacar: CON_CONTENIDO.has(t) }))} />
        </Tarjeta>

        <div className="resumen-columna">
          <Tarjeta titulo="Sentimiento de la comunidad" bajada="Cómo se sienten los mensajes analizados."
            tabla={{ columnas: ["Sentimiento", "Mensajes"], filas: [["Positivo", sent.positive ?? 0], ["Neutral", sent.neutral ?? 0], ["Negativo", sent.negative ?? 0]] }}>
            <BarraSentimiento positivo={sent.positive ?? 0} neutral={sent.neutral ?? 0} negativo={sent.negative ?? 0} />
          </Tarjeta>

          <Tarjeta titulo="Del mensaje a la publicación" bajada="Cuánto avanza cada etapa respecto de la anterior."
            tabla={{ columnas: ["Etapa", "Cantidad"], filas: [["Analizados", datos.mensajes], ["Oportunidades", oportunidades], ["Borradores guardados", borradores], ["Aprobados", aprobados]] }}>
            <Embudo etapas={[
              { etiqueta: "Analizados", valor: datos.mensajes },
              { etiqueta: "Oportunidades", valor: oportunidades },
              { etiqueta: "Borradores guardados", valor: borradores },
              { etiqueta: "Aprobados", valor: aprobados },
            ]} />
            {!borradores && <p className="tenue grafico-nota">Los borradores cuentan desde que se guarda un paquete en Publicación.</p>}
          </Tarjeta>
        </div>

        {ap && decididos > 0 && (
          <Tarjeta ancho titulo="Qué aprueban los curadores"
            bajada={`De ${plural(decididos, "borrador decidido", "borradores decididos")}, ${Math.round((ap.total.aprobados / decididos) * 100)} % se aprobó. Sirve para ver si los umbrales de score${textoUmbrales ? ` (${textoUmbrales})` : ""} están bien puestos: un rango con casi todo descartado pide un umbral más alto.`}
            tabla={{ columnas: ["Grupo", "Aprobados", "Descartados", "Por revisar"],
              filas: [...gruposTipo, ...gruposRango].map((g) => [g.etiqueta, g.aprobados, g.descartados, g.pendientes]) }}>
            <div className="aprobacion-dos">
              <div><h3 className="aprobacion-sub">Por tipo de mensaje</h3><TasaAprobacion grupos={gruposTipo} /></div>
              <div><h3 className="aprobacion-sub">Por score del mensaje</h3><TasaAprobacion grupos={gruposRango} /></div>
            </div>
            <p className="tenue grafico-nota">Las barras claras tienen menos de 5 decisiones: todavía no son confiables.</p>
          </Tarjeta>
        )}

        <Tarjeta titulo="Canales más activos" bajada="Dónde se concentra la conversación."
          tabla={{ columnas: ["Canal", "Mensajes"], filas: canales.map(([c, n]) => [`#${c}`, n]) }}>
          <Barras total={datos.mensajes} datos={canales.map(([c, n]) => ({ etiqueta: `#${c}`, valor: n }))} />
        </Tarjeta>

        <Tarjeta titulo="Temas más mencionados" bajada="Los temas que la IA detectó con más frecuencia."
          tabla={{ columnas: ["Tema", "Menciones"], filas: temas.map(([t, n]) => [tema(t), n]) }}>
          <Barras unidad="menciones" datos={temas.map(([t, n]) => ({ etiqueta: tema(t), valor: n }))} />
        </Tarjeta>
      </div>
    </>
  );
}
