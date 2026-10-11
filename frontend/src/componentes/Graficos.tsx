// Gráficos del Resumen, en HTML y CSS (sin librerías). Reglas: marcas finas con punta redondeada sobre una sola
// línea base, 2 px de separación entre segmentos, texto siempre en tinta (nunca del color del dato), cada marca con
// su tooltip al pasar el mouse o al enfocarla con el teclado, y una tabla con los datos para leerlos sin el gráfico.

const NUM = new Intl.NumberFormat("es-PE");
const pct = (v: number, total: number) => (total ? `${Math.round((v / total) * 100)}%` : "0%");

function techo(max: number) {
  if (max <= 5) return 5;
  const paso = 10 ** Math.floor(Math.log10(max));
  return Math.ceil(max / paso) * paso;
}

export function Tarjeta({ titulo, bajada, children, tabla, ancho }: {
  titulo: string; bajada?: string; children: React.ReactNode; ancho?: boolean;
  tabla?: { columnas: string[]; filas: (string | number)[][] };
}) {
  return (
    <section className={`hoja grafico ${ancho ? "grafico-ancho" : ""}`}>
      <header className="grafico-cabeza">
        <h2>{titulo}</h2>
        {bajada && <p className="sec">{bajada}</p>}
      </header>
      {children}
      {tabla && (
        <details className="grafico-tabla">
          <summary>Ver los datos</summary>
          <div className="tabla-envoltura">
            <table>
              <thead><tr>{tabla.columnas.map((c) => <th key={c} scope="col">{c}</th>)}</tr></thead>
              <tbody>{tabla.filas.map((f, i) => (
                <tr key={i}>{f.map((v, j) => <td key={j} className={typeof v === "number" ? "num" : ""}>
                  {typeof v === "number" ? NUM.format(v) : v}</td>)}</tr>
              ))}</tbody>
            </table>
          </div>
        </details>
      )}
    </section>
  );
}

export function Leyenda({ items }: { items: { color: string; texto: string }[] }) {
  return (
    <ul className="leyenda">
      {items.map((i) => <li key={i.texto}><span style={{ background: i.color }} aria-hidden="true" />{i.texto}</li>)}
    </ul>
  );
}

/** Columnas apiladas por fecha: la parte destacada abajo (acento) y el resto encima (gris). */
export function ColumnasApiladas({ datos, etiquetaDestacada, etiquetaResto }: {
  datos: { etiqueta: string; destacado: number; total: number }[];
  etiquetaDestacada: string; etiquetaResto: string;
}) {
  const max = techo(Math.max(1, ...datos.map((d) => d.total)));
  const ticks = [max, max / 2, 0];
  const mayor = Math.max(...datos.map((d) => d.total));
  const rotular = (d: { total: number }, i: number) => datos.length <= 12 || d.total === mayor || i === datos.length - 1;
  return (
    <>
      <Leyenda items={[{ color: "var(--dato)", texto: etiquetaDestacada }, { color: "var(--dato-tenue)", texto: etiquetaResto }]} />
      <div className="columnas">
        <div className="columnas-eje" aria-hidden="true">
          {ticks.map((t) => <span key={t} className="num">{NUM.format(t)}</span>)}
        </div>
        <div className="columnas-cuerpo">
          <div className="columnas-area" role="list">
            {ticks.map((t) => <i key={t} className="columnas-grilla" style={{ bottom: `${(t / max) * 100}%` }} aria-hidden="true" />)}
            {datos.map((d, i) => {
              const texto = `${d.etiqueta}: ${d.total} mensajes, ${d.destacado} ${etiquetaDestacada.toLowerCase()}`;
              return (
                <div key={d.etiqueta} className="columna" role="listitem" tabIndex={0} data-tip={texto} aria-label={texto}>
                  {rotular(d, i) && <span className="columna-valor num">{d.total}</span>}
                  <div className="columna-pila" style={{ height: `${(d.total / max) * 100}%` }}>
                    {d.total - d.destacado > 0 && <span className="seg resto" style={{ flexGrow: d.total - d.destacado }} />}
                    {d.destacado > 0 && <span className="seg destacado" style={{ flexGrow: d.destacado }} />}
                  </div>
                </div>
              );
            })}
          </div>
          <div className="columnas-etiquetas" aria-hidden="true">
            {datos.map((d) => <span key={d.etiqueta}>{d.etiqueta}</span>)}
          </div>
        </div>
      </div>
    </>
  );
}

/** Barras horizontales de una sola serie; `destacar` pinta en acento las que son la historia y el resto en gris. */
export function Barras({ datos, total, unidad = "mensajes" }: {
  datos: { etiqueta: string; valor: number; destacar?: boolean }[]; total?: number; unidad?: string;
}) {
  const max = Math.max(1, ...datos.map((d) => d.valor));
  return (
    <ul className="barras">
      {datos.map((d) => {
        const texto = `${d.etiqueta}: ${NUM.format(d.valor)} ${unidad}${total ? ` (${pct(d.valor, total)})` : ""}`;
        return (
          <li key={d.etiqueta} tabIndex={0} data-tip={texto} aria-label={texto}>
            <span className="barra-etiqueta">{d.etiqueta}</span>
            <span className="barra-pista">
              <i className={d.destacar === false ? "tenue" : ""} style={{ width: `calc((100% - 76px) * ${d.valor / max})` }} />
              <b className="num">{NUM.format(d.valor)}{total ? <small> {pct(d.valor, total)}</small> : null}</b>
            </span>
          </li>
        );
      })}
    </ul>
  );
}

/** Escala ordenada negativo -> neutral -> positivo, en una sola barra al 100%. */
export function BarraSentimiento({ negativo, neutral, positivo }: { negativo: number; neutral: number; positivo: number }) {
  const total = negativo + neutral + positivo || 1;
  const partes = [
    { clave: "neg", texto: "Negativo", valor: negativo, color: "var(--dato-neg)" },
    { clave: "neu", texto: "Neutral", valor: neutral, color: "var(--dato-neutro)" },
    { clave: "pos", texto: "Positivo", valor: positivo, color: "var(--dato)" },
  ];
  return (
    <>
      <div className="sentimiento-barra" role="list">
        {partes.filter((p) => p.valor).map((p) => {
          const texto = `${p.texto}: ${p.valor} (${pct(p.valor, total)})`;
          return <span key={p.clave} role="listitem" tabIndex={0} data-tip={texto} aria-label={texto}
            style={{ flexGrow: p.valor, background: p.color }} />;
        })}
      </div>
      <ul className="sentimiento-cifras">
        {partes.map((p) => (
          <li key={p.clave}><span style={{ background: p.color }} aria-hidden="true" />
            <b className="num">{pct(p.valor, total)}</b> {p.texto.toLowerCase()} <span className="tenue num">({p.valor})</span></li>
        ))}
      </ul>
    </>
  );
}

/** Etapas ordenadas que se van reduciendo: cada una con su valor y el porcentaje respecto de la anterior. */
export function Embudo({ etapas }: { etapas: { etiqueta: string; valor: number }[] }) {
  const max = Math.max(1, etapas[0]?.valor ?? 1);
  return (
    <ol className="embudo">
      {etapas.map((e, i) => {
        const previo = i > 0 ? etapas[i - 1].valor : null;
        const texto = `${e.etiqueta}: ${NUM.format(e.valor)}${previo ? ` (${pct(e.valor, previo)} de la etapa anterior)` : ""}`;
        return (
          <li key={e.etiqueta} tabIndex={0} data-tip={texto} aria-label={texto}>
            <span className="embudo-etiqueta">{e.etiqueta}</span>
            <span className="barra-pista">
              <i style={{ width: `calc((100% - 76px) * ${e.valor / max})` }} />
              <b className="num">{NUM.format(e.valor)}{previo !== null ? <small> {pct(e.valor, previo)}</small> : null}</b>
            </span>
          </li>
        );
      })}
    </ol>
  );
}
