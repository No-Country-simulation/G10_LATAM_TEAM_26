// Escena de la pantalla de ingreso, según el diseño del equipo de diseño (atardecer sobre la ciudad con la red de
// conversaciones). Todo es CSS y SVG: no hay imágenes que descargar y escala sin perder nitidez.

type Silueta = "mujer" | "rulos" | "hombre" | "cola" | "calvo";

/** Siluetas de los avatares (se definen una vez y cada burbuja las reutiliza con <use>). */
function Siluetas() {
  return (
    <svg width="0" height="0" className="escena-defs" aria-hidden="true">
      <defs>
        <g id="silueta-mujer">
          <path d="M14 64c0-14 8-20 18-20s18 6 18 20z" fill="#14213d" /><circle cx="32" cy="27" r="11" fill="#14213d" />
          <path d="M19 30c-3-14 5-22 14-22s17 8 12 24c-2-8-6-12-13-12s-11 4-13 10z" fill="#0b132b" />
        </g>
        <g id="silueta-rulos">
          <path d="M12 64c0-13 8-19 20-19s20 6 20 19z" fill="#15183a" /><circle cx="33" cy="30" r="10" fill="#15183a" />
          <circle cx="24" cy="20" r="6" fill="#0b0d26" /><circle cx="33" cy="16" r="7" fill="#0b0d26" />
          <circle cx="42" cy="21" r="6" fill="#0b0d26" />
        </g>
        <g id="silueta-hombre">
          <path d="M10 64c0-14 9-20 22-20s22 6 22 20z" fill="#12284f" /><circle cx="32" cy="28" r="11" fill="#12284f" />
          <path d="M21 24c1-9 8-13 15-11 6 2 8 7 6 11-3-4-9-5-21 0z" fill="#0a1a38" />
        </g>
        <g id="silueta-cola">
          <path d="M12 64c0-13 8-19 20-19s20 6 20 19z" fill="#1d3a3a" /><circle cx="31" cy="29" r="10" fill="#1d3a3a" />
          <path d="M20 27c0-10 7-15 14-14 7 1 10 8 9 14-3-6-8-8-14-7s-8 3-9 7z" fill="#0f2222" />
          <path d="M44 22c8 2 10 12 4 20-1-8-3-12-7-14z" fill="#0f2222" />
        </g>
        <g id="silueta-calvo">
          <path d="M10 64c0-14 9-20 22-20s22 6 22 20z" fill="#10305a" /><circle cx="32" cy="28" r="11" fill="#10305a" />
        </g>
      </defs>
    </svg>
  );
}

function Burbuja({ clase, silueta, tono, lineas = 3, grande = false }: {
  clase: string; silueta: Silueta; tono: string; lineas?: 2 | 3; grande?: boolean;
}) {
  return (
    <div className={`escena-burbuja ${clase}${grande ? " grande" : ""}`}>
      <span className={`escena-avatar ${tono}`}>
        <svg viewBox="0 0 64 64"><use href={`#silueta-${silueta}`} /></svg>
      </span>
      <span className="escena-lineas"><i /><i />{lineas === 3 && <i className="corta" />}</span>
    </div>
  );
}

const iconos = {
  grupo: <><circle cx="12" cy="8" r="2.6" /><circle cx="5.5" cy="10" r="2" /><circle cx="18.5" cy="10" r="2" />
    <path d="M7.5 18c0-2.8 2-4.5 4.5-4.5s4.5 1.7 4.5 4.5M2.5 17c0-2 1.3-3.3 3-3.5M21.5 17c0-2-1.3-3.3-3-3.5" /></>,
  documento: <><path d="M6 3h9l4 4v14H6z" /><path d="M9 11h7M9 14h7M9 17h4" /></>,
  idea: <path d="M9 18h6M10 21h4M12 3a6 6 0 0 0-3.5 10.9c.6.5 1 1.2 1 2.1h5c0-.9.4-1.6 1-2.1A6 6 0 0 0 12 3z" />,
  grafico: <path d="M3 20h18M4 20v-5h3v5M10 20v-8h3v8M16 20v-11h3v11M4 11l5-4 4 3 7-6M16 4h4v4" />,
};

function Ficha({ clase, tono, icono }: { clase: string; tono: string; icono: keyof typeof iconos }) {
  return (
    <span className={`escena-ficha ${tono} ${clase}`}>
      <svg viewBox="0 0 24 24">{iconos[icono]}</svg>
    </span>
  );
}

export function EscenaIngreso() {
  return (
    <section className="escena" aria-label="Conversaciones reales. Datos con sentido. Mejores decisiones.">
      <div className="escena-cielo" />
      <div className="escena-brillo" />
      <div className="escena-ciudad" />
      {[1, 2, 3, 4, 5].map((n) => <div key={n} className={`escena-bokeh k${n}`} />)}

      <div className="escena-texto" aria-hidden="true">
        <p>Conversaciones reales.<br />Datos con sentido.<br />Mejores decisiones.</p>
        <hr />
      </div>

      <div className="escena-red" aria-hidden="true">
        <svg className="escena-lineas-red" viewBox="0 0 700 760" preserveAspectRatio="none">
          <g fill="none" stroke="rgba(255,255,255,.55)" strokeWidth="1.2">
            <path d="M170 150 C 260 60, 380 40, 480 90" /><path d="M170 150 C 150 250, 120 330, 90 400" />
            <path d="M170 150 C 240 230, 330 230, 400 260" /><path d="M480 90 C 600 60, 680 70, 760 130" />
            <path d="M400 260 C 470 300, 540 300, 600 350" /><path d="M90 400 C 200 420, 330 450, 470 470" />
            <path d="M470 470 C 540 420, 590 400, 600 350" /><path d="M470 470 C 420 560, 370 600, 340 640" />
            <path d="M600 350 C 660 380, 700 430, 720 480" /><path d="M90 400 C 80 470, 60 520, 50 570" />
          </g>
          <g fill="#fff">
            <circle cx="480" cy="90" r="5" /><circle cx="400" cy="260" r="6" fill="#5ec9ae" />
            <circle cx="470" cy="470" r="6" fill="#c7b8ff" /><circle cx="600" cy="350" r="5" />
          </g>
        </svg>

        <Ficha clase="f-grupo" tono="verde" icono="grupo" />
        <Ficha clase="f-documento" tono="violeta" icono="documento" />
        <Ficha clase="f-idea" tono="violeta" icono="idea" />
        <Ficha clase="f-grafico" tono="azul" icono="grafico" />

        <Burbuja clase="b-a" silueta="mujer" tono="violeta" grande />
        <Burbuja clase="b-b" silueta="rulos" tono="indigo" grande />
        <Burbuja clase="b-c" silueta="hombre" tono="azul" />
        <Burbuja clase="b-d" silueta="cola" tono="verde" lineas={2} grande />
        <Burbuja clase="b-e" silueta="calvo" tono="cielo" />
      </div>

      <svg className="escena-planta" viewBox="0 0 300 300" aria-hidden="true">
        <g fill="none" stroke="#3c5a2c" strokeWidth="3" strokeLinecap="round">
          <path d="M280 300C250 220 230 160 150 90" /><path d="M270 260C230 250 200 230 170 190" />
          <path d="M250 200C290 180 300 140 290 100" />
        </g>
        <g fill="#6e9a3c">
          <ellipse cx="190" cy="140" rx="14" ry="6" transform="rotate(-40 190 140)" />
          <ellipse cx="160" cy="105" rx="12" ry="5" transform="rotate(-60 160 105)" />
          <ellipse cx="215" cy="190" rx="14" ry="6" transform="rotate(20 215 190)" />
          <ellipse cx="240" cy="230" rx="15" ry="6" transform="rotate(30 240 230)" />
          <ellipse cx="285" cy="130" rx="12" ry="5" transform="rotate(70 285 130)" />
          <ellipse cx="270" cy="170" rx="13" ry="5" transform="rotate(-30 270 170)" />
        </g>
      </svg>
      <div className="escena-roca" />
      <Siluetas />
    </section>
  );
}
