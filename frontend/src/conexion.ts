import { useCallback, useEffect, useRef, useState } from "react";
import { ErrorApi } from "./api";

const ESPERA_INICIAL_MS = 3000;
const ESPERA_MAXIMA_MS = 15000;

/**
 * Sigue qué consultas al servidor están fallando para avisarlo en pantalla y reintentarlas solas.
 * Antes los errores del sondeo se tragaban (`catch {}`): si el servidor se caía un momento, la consulta no se volvía
 * a programar y la pantalla se quedaba congelada sin decir nada.
 */
export function useConexion() {
  const [fallas, setFallas] = useState<ReadonlySet<string>>(new Set());
  const reintentos = useRef(new Map<string, { temporizador: number; intentos: number }>());

  useEffect(() => {
    const activos = reintentos.current;
    return () => activos.forEach((r) => window.clearTimeout(r.temporizador));
  }, []);

  const marcar = useCallback((fuente: string, falla: boolean) => {
    setFallas((previo) => {
      if (previo.has(fuente) === falla) return previo;
      const siguiente = new Set(previo);
      if (falla) siguiente.add(fuente);
      else siguiente.delete(fuente);
      return siguiente;
    });
  }, []);

  /** La consulta de `fuente` funcionó: se quita el aviso y se olvida el reintento pendiente. */
  const exito = useCallback((fuente: string) => {
    const pendiente = reintentos.current.get(fuente);
    if (pendiente) window.clearTimeout(pendiente.temporizador);
    reintentos.current.delete(fuente);
    marcar(fuente, false);
  }, [marcar]);

  /** La consulta de `fuente` falló: se avisa y se vuelve a llamar a `reintentar` con una espera creciente. */
  const falla = useCallback((fuente: string, error: unknown, reintentar: () => void) => {
    // Sesión vencida: api.ts ya devuelve al ingreso; reintentar con un token muerto solo repetiría el 401
    if (error instanceof ErrorApi && error.estado === 401) return;
    marcar(fuente, true);
    const previo = reintentos.current.get(fuente);
    if (previo) window.clearTimeout(previo.temporizador);
    const intentos = (previo?.intentos ?? 0) + 1;
    const espera = Math.min(ESPERA_INICIAL_MS * 1.5 ** (intentos - 1), ESPERA_MAXIMA_MS);
    reintentos.current.set(fuente, { intentos, temporizador: window.setTimeout(reintentar, espera) });
  }, [marcar]);

  return { sinConexion: fallas.size > 0, exito, falla };
}
