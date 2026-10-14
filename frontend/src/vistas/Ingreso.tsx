import { useState } from "react";
import { api } from "../api";
import escena from "../recursos/login-escena.webp";
import marca from "../recursos/login-marca.png";
import type { Sesion } from "../tipos";

// Pantalla de ingreso según el diseño de marca de CommunityLab AI: fondo claro con trazos violeta y verde azulado,
// botón con el degradado de la marca y la escena de la comunidad a la derecha.

const Icono = {
  usuario: (
    <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="8" r="4" /><path d="M4 20c1.5-3.5 4.5-5 8-5s6.5 1.5 8 5" /></svg>
  ),
  candado: (
    <svg viewBox="0 0 24 24" aria-hidden="true"><rect x="5" y="10" width="14" height="10" rx="2" /><path d="M8 10V7a4 4 0 0 1 8 0v3" /><path d="M12 14v2" /></svg>
  ),
  ojo: (
    <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z" /><circle cx="12" cy="12" r="3" /></svg>
  ),
  ojoTachado: (
    <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M2 12s3.5-7 10-7c2 0 3.7.6 5.1 1.5M22 12s-3.5 7-10 7c-2 0-3.7-.6-5.1-1.5" /><path d="M9.9 9.9a3 3 0 0 0 4.2 4.2" /><path d="M3 3l18 18" /></svg>
  ),
  flecha: (
    <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12h14M13 6l6 6-6 6" /></svg>
  ),
};

/** Trazos curvos del fondo (violeta y verde azulado), como en la pieza de marca. */
function Trazos() {
  return (
    <svg className="login-trazos" viewBox="0 0 760 320" preserveAspectRatio="xMinYMax slice" aria-hidden="true">
      <path d="M0 40 C180 40 300 140 330 320" fill="none" stroke="#7b5cf0" strokeWidth="1.4" opacity="0.7" />
      <path d="M0 90 C150 100 230 200 250 320" fill="none" stroke="#0db5d3" strokeWidth="1.2" opacity="0.6" />
      <path d="M90 320 C200 170 420 140 560 320" fill="none" stroke="#02b7ae" strokeWidth="1.2" opacity="0.55" />
      <path d="M0 150 C120 170 220 250 240 320 L0 320 Z" fill="#e9e6fd" opacity="0.55" />
    </svg>
  );
}

export function Ingreso({ alIngresar }: { alIngresar: (s: Sesion) => void }) {
  const [usuario, setUsuario] = useState("");
  const [clave, setClave] = useState("");
  const [verClave, setVerClave] = useState(false);
  const [ayuda, setAyuda] = useState(false);
  const [error, setError] = useState("");
  const [enviando, setEnviando] = useState(false);

  async function ingresar(e: React.FormEvent) {
    e.preventDefault();
    setEnviando(true);
    setError("");
    try {
      alIngresar(await api.post<Sesion>("/login", { usuario, clave }));
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setEnviando(false);
    }
  }

  return (
    <div className="login">
      <section className="login-panel">
        <Trazos />
        <div className="login-columna">
          <div className="login-marca">
            <img src={marca} alt="" width={110} height={118} />
            <div>
              <p className="login-nombre">CommunityLab <span>AI</span></p>
              <p className="login-lema">Personas <i>+</i> Conversaciones <i>+</i> Oportunidades</p>
            </div>
          </div>

          <form className="login-form" onSubmit={ingresar}>
            <div className="login-titulo">
              <h1>Bienvenido/a</h1>
              <p>El conocimiento de la comunidad, potenciado por la inteligencia artificial.</p>
            </div>

            <label className="login-campo">
              <span className="login-icono">{Icono.usuario}</span>
              <input placeholder="Usuario" aria-label="Usuario" autoComplete="username" value={usuario}
                onChange={(e) => setUsuario(e.target.value)} required autoFocus />
            </label>
            <label className="login-campo">
              <span className="login-icono">{Icono.candado}</span>
              <input type={verClave ? "text" : "password"} placeholder="Contraseña" aria-label="Contraseña"
                autoComplete="current-password" value={clave} onChange={(e) => setClave(e.target.value)} required />
              <button type="button" className="login-ver" onClick={() => setVerClave(!verClave)}
                aria-label={verClave ? "Ocultar contraseña" : "Mostrar contraseña"} aria-pressed={verClave}>
                {verClave ? Icono.ojo : Icono.ojoTachado}
              </button>
            </label>

            {error && <p className="login-error" role="alert">{error}</p>}

            <button className="login-boton" disabled={enviando}>
              {enviando ? <span className="cargando" /> : <>Ingresar {Icono.flecha}</>}
            </button>

            <button type="button" className="login-enlace" onClick={() => setAyuda(!ayuda)} aria-expanded={ayuda}>
              ¿Olvidaste tu contraseña?
            </button>
            {ayuda && (
              <p className="login-ayuda" role="status">
                Pídele a un administrador del equipo que te asigne una nueva desde «Usuarios».
              </p>
            )}
          </form>
        </div>
      </section>

      <section className="login-escena"
        aria-label="Conversaciones reales. Datos con sentido. Mejores decisiones. Comunidad, conversaciones, IA y oportunidades.">
        <img src={escena} alt="" />
      </section>
    </div>
  );
}
