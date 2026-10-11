import { SENTIMIENTOS, plural, tema } from "../etiquetas";
import type { Analisis, Sentimiento } from "../tipos";

const ORDEN: Sentimiento[] = ["positive", "neutral", "negative"];

/** Sentimiento del lote, temas principales y cuántos mensajes necesitan apoyo. */
export function Salud({ analisis, alVerApoyo }: { analisis: Analisis; alVerApoyo?: () => void }) {
  const { resumen, salud } = analisis;
  if (!resumen || !salud) return null;
  const dist = resumen.distribucion_sentimiento;
  const total = ORDEN.reduce((s, k) => s + (dist[k] || 0), 0) || 1;
  const apoyo = analisis.mensajes.filter((m) => m.necesita_apoyo).length;
  return (
    <section className="hoja hoja-cuerpo seccion">
      <div className="salud">
        <div>
          <span className="etiqueta-campo">Salud de la comunidad</span>
          <p className="salud-estado">{salud.emoji} {salud.etiqueta}</p>
          <div className="salud-leyenda">
            {ORDEN.map((s) => (
              <span key={s} className={`sent ${s}`}>
                <span className="num">{dist[s] || 0}</span> {SENTIMIENTOS[s].toLowerCase()}
              </span>
            ))}
          </div>
        </div>
        <div>
          <span className="etiqueta-campo">Distribución del sentimiento</span>
          <div className="barra-sent" role="img"
            aria-label={ORDEN.map((s) => `${dist[s] || 0} ${SENTIMIENTOS[s]}`).join(", ")}>
            {ORDEN.filter((s) => dist[s]).map((s) => (
              <span key={s} className={s} style={{ flexGrow: dist[s] / total }} />
            ))}
          </div>
          <span className="etiqueta-campo" style={{ display: "block", marginTop: 18 }}>Temas principales</span>
          <div className="temas">
            {resumen.temas_principales.length
              ? resumen.temas_principales.map((t) => <span key={t} className="tema">{tema(t)}</span>)
              : <span className="tenue">Sin temas repetidos en este lote.</span>}
          </div>
        </div>
      </div>
      {apoyo > 0 && (
        <div className="nota aviso" style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
          <span style={{ flex: 1 }}>
            <b>{plural(apoyo, "mensaje necesita", "mensajes necesitan")} apoyo</b>: tienen sentimiento negativo o son
            feedback sobre el programa.
          </span>
          {alVerApoyo && <button className="boton chico" onClick={alVerApoyo}>Ver esos mensajes</button>}
        </div>
      )}
    </section>
  );
}
