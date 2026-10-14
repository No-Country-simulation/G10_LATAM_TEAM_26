// Cliente de la API: agrega el token de la sesión y convierte los errores en mensajes legibles.

const CLAVE_SESION = "communitylab.sesion";

export class ErrorApi extends Error {
  constructor(public estado: number, mensaje: string) {
    super(mensaje);
  }
}

export function sesionGuardada() {
  try {
    const texto = sessionStorage.getItem(CLAVE_SESION);
    return texto ? JSON.parse(texto) : null;
  } catch {
    return null;
  }
}

export function guardarSesion(sesion: unknown) {
  try {
    if (sesion) sessionStorage.setItem(CLAVE_SESION, JSON.stringify(sesion));
    else sessionStorage.removeItem(CLAVE_SESION);
  } catch {
    /* sin almacenamiento: la sesión dura lo que la pestaña */
  }
}

let token = sesionGuardada()?.token ?? "";
let alExpirar: () => void = () => {};

export function usarToken(nuevo: string, expirar: () => void) {
  token = nuevo;
  alExpirar = expirar;
}

export const tokenActual = () => token;

async function pedir<T>(metodo: string, ruta: string, cuerpo?: unknown): Promise<T> {
  const r = await fetch(`/api${ruta}`, {
    method: metodo,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: cuerpo === undefined ? undefined : JSON.stringify(cuerpo),
  });
  if (r.status === 401 && ruta !== "/login") alExpirar();
  if (!r.ok) {
    let detalle = `El servidor respondió ${r.status}.`;
    try {
      detalle = (await r.json()).detail ?? detalle;
    } catch {
      /* respuesta sin JSON */
    }
    throw new ErrorApi(r.status, detalle);
  }
  return r.json() as Promise<T>;
}

export const api = {
  get: <T>(ruta: string) => pedir<T>("GET", ruta),
  post: <T>(ruta: string, cuerpo: unknown = {}) => pedir<T>("POST", ruta, cuerpo),
  patch: <T>(ruta: string, cuerpo: unknown) => pedir<T>("PATCH", ruta, cuerpo),
  borrar: <T>(ruta: string) => pedir<T>("DELETE", ruta),
};

/** Descarga un archivo de la API (media kit, paquete JSON) con el token de la sesión. */
export async function descargar(ruta: string, nombre: string) {
  const r = await fetch(`/api${ruta}`, { headers: { Authorization: `Bearer ${token}` } });
  if (!r.ok) throw new ErrorApi(r.status, "No se pudo descargar el archivo.");
  const url = URL.createObjectURL(await r.blob());
  const enlace = Object.assign(document.createElement("a"), { href: url, download: nombre });
  enlace.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
