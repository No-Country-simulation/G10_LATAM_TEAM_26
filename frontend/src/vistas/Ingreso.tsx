import { useState } from "react";
import { api } from "../api";
import { EscenaIngreso } from "../componentes/EscenaIngreso";
import logo from "../recursos/logo.svg";
import type { Sesion } from "../tipos";

// Pantalla de ingreso según la propuesta del equipo de diseño: fondo cálido, azul marino y verde azulado, el logo de
// CommunityLab AI y la escena de la red de conversaciones a la derecha.

const Icono = {
  usuario: (
    <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="8" r="4" /><path d="M4 20c1.5-3.5 4.5-5 8-5s6.5 1.5 8 5" /></svg>
  ),
  candado: (
    <svg viewBox="0 0 24 24" aria-hidden="true"><rect x="5" y="11" width="14" height="10" rx="2" /><path d="M8 11V8a4 4 0 0 1 8 0v3" /><circle cx="12" cy="16" r=".8" fill="currentColor" /></svg>
  ),
  ojo: (
    <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M2.5 12c1-2 4.5-6 9.5-6s8.5 4 9.5 6c-1 2-4.5 6-9.5 6s-8.5-4-9.5-6z" /><circle cx="12" cy="12" r="3" /></svg>
  ),
  ojoTachado: (
    <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 3l18 18" /><path d="M10.6 6.2A9.8 9.8 0 0 1 12 6c5 0 8.5 4 9.5 6-.4.8-1.2 2-2.4 3.2M6.5 7.6C4.6 9 3.4 10.8 2.5 12c1 2 4.5 6 9.5 6 1.5 0 2.8-.4 4-.9" /><path d="M9.9 9.9a3 3 0 0 0 4.2 4.2" /></svg>
  ),
  flecha: (
    <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 12h16M14 6l6 6-6 6" /></svg>
  ),
};

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
        <div className="login-columna">
          <div className="login-marca">
            <img src={logo} alt="" width={88} height={88} />
            <div>
              <p className="login-nombre">CommunityLab <span>AI</span></p>
              <p className="login-lema">Personas. Conversaciones. Oportunidades.</p>
            </div>
          </div>

          <form className="login-form" onSubmit={ingresar}>
            <div className="login-titulo">
              <h1>Iniciar sesión</h1>
              <p>Accede a tu cuenta para continuar</p>
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
              {enviando ? <span className="cargando" /> : <>Ingresar <span className="login-flecha">{Icono.flecha}</span></>}
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

          <p className="login-pie" aria-label="Comunidad más IA igual a impacto">
            <span>Comunidad</span><i>+</i><span>IA</span><i>=</i><span>Impacto</span>
          </p>
        </div>
      </section>

      <EscenaIngreso />
    </div>
  );
}
