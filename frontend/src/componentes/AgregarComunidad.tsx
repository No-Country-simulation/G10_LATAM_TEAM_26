import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import type { ComunidadDiscord } from "../tipos";

interface Identidad { aplicacion: string; servidores: { id: string; nombre: string }[] }

/** Alta de una comunidad de Discord: nombre + token de su aplicación; se verifica el token y se elige el servidor. */
export function AgregarComunidad({ alCerrar, alAgregar }: {
  alCerrar: () => void; alAgregar: (c: ComunidadDiscord) => void;
}) {
  const dialogo = useRef<HTMLDialogElement>(null);
  const [nombre, setNombre] = useState("");
  const [token, setToken] = useState("");
  const [identidad, setIdentidad] = useState<Identidad | null>(null);
  const [servidor, setServidor] = useState("");
  const [ocupado, setOcupado] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => { dialogo.current?.showModal(); }, []);

  async function verificar() {
    setOcupado(true);
    setError("");
    try {
      const datos = await api.post<Identidad>("/discord/verificar", { token });
      setIdentidad(datos);
      setServidor(datos.servidores[0]?.id ?? "");
      if (!nombre) setNombre(datos.servidores[0]?.nombre ?? "");
    } catch (err) {
      setIdentidad(null);
      setError((err as Error).message);
    } finally {
      setOcupado(false);
    }
  }

  async function guardar(e: React.FormEvent) {
    e.preventDefault();
    if (!identidad) return verificar();
    setOcupado(true);
    setError("");
    try {
      alAgregar(await api.post<ComunidadDiscord>("/discord/comunidades", { nombre, token, servidor_id: servidor }));
      dialogo.current?.close();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setOcupado(false);
    }
  }

  return (
    <dialog ref={dialogo} onClose={alCerrar} className="dialogo-ancho">
      <form onSubmit={guardar}>
        <h2>Agregar una comunidad de Discord</h2>
        <p className="sec" style={{ fontSize: 14 }}>
          Usa el token de la aplicación de Discord de esa comunidad (Developer Portal, sección Bot). La aplicación debe
          estar en el servidor, con permiso para leer el historial y el intent MESSAGE CONTENT activo.
        </p>
        <div className="campo">
          <label htmlFor="com-token">Token de la aplicación</label>
          <div style={{ display: "flex", gap: 8 }}>
            <input id="com-token" className="entrada" type="password" autoComplete="off" value={token} required
              onChange={(e) => { setToken(e.target.value); setIdentidad(null); }} />
            <button type="button" className="boton" onClick={verificar} disabled={!token || ocupado}>
              {ocupado && !identidad && <span className="cargando" />} Verificar
            </button>
          </div>
          <span className="tenue" style={{ fontSize: 12.5 }}>Se guarda solo en el servidor; el panel nunca lo vuelve a mostrar.</span>
        </div>

        {identidad && (
          <>
            <p className="nota bien">Token válido: aplicación «{identidad.aplicacion}», con acceso a{" "}
              {identidad.servidores.length === 1 ? "1 servidor" : `${identidad.servidores.length} servidores`}.</p>
            <div className="campo">
              <label htmlFor="com-servidor">Servidor</label>
              <select id="com-servidor" className="entrada" value={servidor} onChange={(e) => setServidor(e.target.value)}>
                {identidad.servidores.map((s) => <option key={s.id} value={s.id}>{s.nombre}</option>)}
              </select>
            </div>
            <div className="campo">
              <label htmlFor="com-nombre">Nombre de la comunidad</label>
              <input id="com-nombre" className="entrada" value={nombre} maxLength={60} required
                onChange={(e) => setNombre(e.target.value)} />
            </div>
          </>
        )}

        {error && <p className="nota error" role="alert">{error}</p>}
        <div style={{ display: "flex", gap: 10, justifyContent: "flex-end" }}>
          <button type="button" className="boton fantasma" onClick={() => dialogo.current?.close()}>Cancelar</button>
          <button className="boton primario" disabled={!identidad || !nombre.trim() || ocupado}>Agregar comunidad</button>
        </div>
      </form>
    </dialog>
  );
}
