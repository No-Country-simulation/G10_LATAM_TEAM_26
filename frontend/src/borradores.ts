import { useCallback, useEffect, useState } from "react";

export type Contenido = Record<string, any>;

const clave = (paqueteId: string) => `communitylab.ediciones.${paqueteId}`;

/** ¿Dos contenidos son iguales? Los textos del borrador son planos, así que comparar el JSON basta. */
export const mismoContenido = (a: Contenido, b: Contenido) => JSON.stringify(a) === JSON.stringify(b);

function leer(paqueteId: string): Record<string, Contenido> {
  try {
    const texto = sessionStorage.getItem(clave(paqueteId));
    return texto ? JSON.parse(texto) : {};
  } catch {
    return {};
  }
}

function escribir(paqueteId: string, datos: Record<string, Contenido>) {
  try {
    if (Object.keys(datos).length) sessionStorage.setItem(clave(paqueteId), JSON.stringify(datos));
    else sessionStorage.removeItem(clave(paqueteId));
  } catch {
    /* sin almacenamiento: las ediciones sobreviven al cambio de borrador, pero no a recargar la página */
  }
}

/**
 * Ediciones de los borradores que todavía no se guardaron en el servidor, por activo.
 * Viven fuera del editor para que no se pierdan al elegir otro borrador ni al cambiar de etapa del flujo
 * (la vista se desmonta); se guardan en sessionStorage para sobrevivir también a recargar la página.
 */
export function useEdicionesPendientes(paqueteId: string | undefined) {
  const [pendientes, setPendientes] = useState<Record<string, Contenido>>({});

  useEffect(() => {
    setPendientes(paqueteId ? leer(paqueteId) : {});
  }, [paqueteId]);

  /** `contenido` null descarta la edición pendiente de ese activo (ya se guardó o volvió al original). */
  const editar = useCallback((activoId: string, contenido: Contenido | null) => {
    setPendientes((previo) => {
      const siguiente = { ...previo };
      if (contenido) siguiente[activoId] = contenido;
      else delete siguiente[activoId];
      if (paqueteId) escribir(paqueteId, siguiente);
      return siguiente;
    });
  }, [paqueteId]);

  return { pendientes, editar };
}
