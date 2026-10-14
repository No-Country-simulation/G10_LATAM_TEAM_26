import { createContext, useContext } from "react";
import { createPortal } from "react-dom";
import marca from "../recursos/login-marca.png";

// Piezas de marca de CommunityLab AI: el símbolo, la red de conversaciones (el motivo de la pantalla de ingreso)
// y la portada de cada etapa, que se dibuja dentro de la franja azul marino del encabezado.

export function Simbolo({ tam = 30 }: { tam?: number }) {
  return <img src={marca} alt="" width={tam} height={tam} style={{ width: tam, height: "auto" }} />;
}

/** Burbujas de conversación unidas por una red: personas, mensajes e ideas conectadas. Decorativa. */
export function RedConversaciones({ className = "" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 520 280" preserveAspectRatio="xMaxYMid meet" aria-hidden="true" focusable="false">
      <g fill="none" strokeWidth="1.2" strokeLinecap="round">
        <path d="M30 210 C120 150 170 230 250 170 S390 90 500 120" stroke="var(--red-lavanda)" />
        <path d="M60 60 C140 110 210 40 300 90 S430 200 510 230" stroke="var(--red-menta)" />
        <path d="M150 260 C190 200 260 210 300 150 S360 40 440 30" stroke="var(--red-lavanda)" strokeDasharray="2 6" />
      </g>
      {[[60, 60, 4, "menta"], [250, 170, 5, "lavanda"], [300, 90, 3.5, "menta"], [440, 30, 4, "lavanda"],
        [500, 120, 3, "menta"], [150, 260, 3, "lavanda"], [380, 150, 6, "menta"]].map(([x, y, r, c], i) => (
        <g key={i}>
          <circle cx={x} cy={y} r={Number(r) * 3} fill={`var(--red-${c})`} opacity="0.18" />
          <circle cx={x} cy={y} r={r} fill={`var(--red-${c})`} />
        </g>
      ))}
      <Burbuja x={318} y={34} tono="lavanda" lineas={[64, 44]} />
      <Burbuja x={92} y={118} tono="menta" lineas={[72, 50, 36]} />
      <Burbuja x={300} y={186} tono="morado" lineas={[56, 40]} cola="derecha" />
      <g transform="translate(196 52)">
        <circle r="17" fill="var(--red-menta)" opacity="0.9" />
        <path d="M-7 5c1-4 4-6 7-6s6 2 7 6M0-3a3 3 0 1 0 0-.1M-9 3c.5-2.5 2-4 4-4.5M9 3c-.5-2.5-2-4-4-4.5"
          stroke="#0f2a3a" strokeWidth="1.6" fill="none" strokeLinecap="round" />
      </g>
      <g transform="translate(470 200)">
        <circle r="16" fill="var(--red-lavanda)" opacity="0.9" />
        <path d="M-4 6h8M-3 9h6M0-9a6 6 0 0 0-4 10.5c.8.8 1 1.5 1 2.5h6c0-1 .2-1.7 1-2.5A6 6 0 0 0 0-9z"
          stroke="#1b1f4b" strokeWidth="1.5" fill="none" strokeLinejoin="round" />
      </g>
    </svg>
  );
}

function Burbuja({ x, y, tono, lineas, cola = "izquierda" }: {
  x: number; y: number; tono: string; lineas: number[]; cola?: "izquierda" | "derecha";
}) {
  const ancho = Math.max(...lineas) + 64;
  const alto = 22 + lineas.length * 12;
  return (
    <g transform={`translate(${x} ${y})`}>
      <rect width={ancho} height={alto} rx="14" fill="var(--red-burbuja)" stroke="var(--red-borde)" />
      <path d={cola === "izquierda" ? `M14 ${alto} l-4 10 l14 -10` : `M${ancho - 24} ${alto} l14 10 l-4 -10`}
        fill="var(--red-burbuja)" stroke="var(--red-borde)" strokeLinejoin="round" />
      <circle cx="24" cy={alto / 2} r="12" fill={`var(--red-${tono})`} />
      <circle cx="24" cy={alto / 2 - 3} r="4" fill="#0f2238" opacity="0.75" />
      <path d={`M16 ${alto / 2 + 9} a8 6 0 0 1 16 0`} fill="#0f2238" opacity="0.75" />
      {lineas.map((l, i) => (
        <rect key={i} x="46" y={13 + i * 12} width={l} height="5" rx="2.5" fill="var(--red-linea)" />
      ))}
    </g>
  );
}

/** Lugar del encabezado donde cada etapa dibuja su portada. */
export const DestinoPortada = createContext<HTMLElement | null>(null);

/** Título, bajada, acción y cifras de la etapa, dentro de la franja de marca. */
export function Portada({ titulo, estado, bajada, accion, cifras }: {
  titulo: string;
  estado?: { texto: string; tono: "pendiente" | "en-curso" | "listo" };
  bajada?: React.ReactNode;
  accion?: React.ReactNode;
  cifras?: { valor: React.ReactNode; texto: string }[];
}) {
  const destino = useContext(DestinoPortada);
  if (!destino) return null;
  return createPortal(
    <div className="portada">
      <div className="portada-texto">
        {estado && (
          <span className={`portada-estado ${estado.tono}`} role="status">
            {estado.tono === "en-curso" && <span className="cargando" />}{estado.texto}
          </span>
        )}
        <h1>{titulo}</h1>
        {bajada && <p>{bajada}</p>}
        {accion && <div className="portada-accion">{accion}</div>}
      </div>
      {cifras && cifras.length > 0 && (
        <dl className="portada-cifras">
          {cifras.map((c) => (
            <div key={c.texto}><dt>{c.texto}</dt><dd className="num">{c.valor}</dd></div>
          ))}
        </dl>
      )}
    </div>,
    destino,
  );
}

/** Estado vacío con la ilustración de marca: dice qué falta y cómo seguir. */
export function Vacio({ titulo, children, acciones }: {
  titulo: string; children?: React.ReactNode; acciones?: React.ReactNode;
}) {
  return (
    <div className="hoja vacio-marca">
      <RedConversaciones className="vacio-ilustracion" />
      <div className="vacio-texto">
        <h2>{titulo}</h2>
        {children && <p className="sec">{children}</p>}
        {acciones && <div className="vacio-acciones">{acciones}</div>}
      </div>
    </div>
  );
}
