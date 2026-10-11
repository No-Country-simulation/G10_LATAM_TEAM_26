import { SENTIMIENTOS, TIPOS, fecha, tema } from "../etiquetas";
import type { Interaccion, Mensaje as MensajeP } from "../tipos";

/** Score con la marca del umbral de su tipo: se ve de un vistazo si pasa o no. */
export function Medidor({ score, umbral }: { score: number; umbral?: number }) {
  const alto = umbral !== undefined && score >= umbral;
  return (
    <div className="medidor" aria-label={`Score ${score.toFixed(2)}${umbral ? `, umbral ${umbral}` : ""}`}>
      <span className={`valor ${alto ? "" : "bajo"}`}>{score.toFixed(2)}</span>
      <span className="barra-score">
        <i className={alto ? "alto" : ""} style={{ width: `${score * 100}%` }} />
        {umbral !== undefined && <b style={{ left: `calc(${umbral * 100}% - 1px)` }} />}
      </span>
      <small>{umbral !== undefined ? `umbral ${umbral}` : "no genera contenido"}</small>
    </div>
  );
}

export function FilaClasificada({ m, umbrales, nuevo }: { m: MensajeP; umbrales: Record<string, number>; nuevo?: boolean }) {
  const tipo = m.opportunity.type;
  return (
    <article className={`mensaje ${nuevo ? "nuevo" : ""}`}>
      <Medidor score={m.opportunity.opportunity_score} umbral={umbrales[tipo]} />
      <div>
        <div className="mensaje-cabeza">
          <span className="autor">{m.autor}</span>
          <span className="canal">#{m.tracking.channel || "sin canal"}</span>
          <span className="marcas">
            <span className={`sent ${m.analysis.sentiment}`}>{SENTIMIENTOS[m.analysis.sentiment]}</span>
            <span className={`chip ${tipo}`}>{TIPOS[tipo]}</span>
          </span>
        </div>
        <p className="cita burbuja">{m.texto}</p>
        <p className="razon">{m.opportunity.reason}</p>
        {m.analysis.topics.length > 0 && (
          <div className="temas">{m.analysis.topics.map((t) => <span key={t} className="tema">{tema(t)}</span>)}</div>
        )}
      </div>
    </article>
  );
}

export function FilaOriginal({ m }: { m: Interaccion }) {
  return (
    <article className="mensaje" style={{ gridTemplateColumns: "minmax(0, 1fr)" }}>
      <div>
        <div className="mensaje-cabeza">
          <span className="autor">{m.autor}</span>
          <span className="canal">#{m.channel}</span>
          <span className="marcas tenue num">{fecha(m.timestamp)}</span>
        </div>
        <p className="cita">{m.texto}</p>
      </div>
    </article>
  );
}
