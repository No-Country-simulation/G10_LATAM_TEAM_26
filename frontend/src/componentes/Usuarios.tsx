import { useEffect, useRef, useState } from "react";
import { api } from "../api";

/** Alta de usuarios del panel (solo administradores). */
export function Usuarios({ alCerrar }: { alCerrar: () => void }) {
  const dialogo = useRef<HTMLDialogElement>(null);
  const [usuario, setUsuario] = useState("");
  const [clave, setClave] = useState("");
  const [rol, setRol] = useState("CURATOR");
  const [mensaje, setMensaje] = useState<{ tipo: "bien" | "error"; texto: string } | null>(null);

  useEffect(() => { dialogo.current?.showModal(); }, []);

  async function crear(e: React.FormEvent) {
    e.preventDefault();
    try {
      await api.post("/usuarios", { usuario, clave, rol });
      setMensaje({ tipo: "bien", texto: `Usuario «${usuario}» creado.` });
      setUsuario("");
      setClave("");
    } catch (err) {
      setMensaje({ tipo: "error", texto: (err as Error).message });
    }
  }

  return (
    <dialog ref={dialogo} onClose={alCerrar}>
      <form onSubmit={crear}>
        <h2>Crear usuario</h2>
        <div className="campo">
          <label htmlFor="nu-usuario">Usuario</label>
          <input id="nu-usuario" className="entrada" value={usuario} onChange={(e) => setUsuario(e.target.value)} required />
        </div>
        <div className="campo">
          <label htmlFor="nu-clave">Contraseña</label>
          <input id="nu-clave" className="entrada" type="password" autoComplete="new-password" value={clave}
            onChange={(e) => setClave(e.target.value)} required />
        </div>
        <div className="campo">
          <span className="etiqueta-campo">Rol</span>
          <div className="segmentos" role="group" aria-label="Rol">
            {[["CURATOR", "Curador"], ["VIEWER", "Lector"], ["ADMIN", "Administrador"]].map(([valor, nombre]) => (
              <button type="button" key={valor} aria-pressed={rol === valor} onClick={() => setRol(valor)}>{nombre}</button>
            ))}
          </div>
        </div>
        {mensaje && <p className={`nota ${mensaje.tipo}`} role="status">{mensaje.texto}</p>}
        <div style={{ display: "flex", gap: 10, justifyContent: "flex-end" }}>
          <button type="button" className="boton fantasma" onClick={() => dialogo.current?.close()}>Cerrar</button>
          <button className="boton primario">Crear usuario</button>
        </div>
      </form>
    </dialog>
  );
}
