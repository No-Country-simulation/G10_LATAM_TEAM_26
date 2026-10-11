"""
CommunityLab AI - Espacio de trabajo de cada sesión de la API web
Hace lo que en Streamlit hacía st.session_state: el lote cargado, la clasificación, la redacción y las imágenes en
segundo plano, y el paquete que se cura. Un hilo de seguimiento encadena las etapas (clasificar -> guardar en la base
-> redactar -> imágenes), así el navegador solo consulta el estado.
"""
import threading
import time
from typing import Any, Dict, List, Optional

from src import config
from src.adapters.db import repository
from src.adapters.ingestion.loaders import interacciones_desde_payload, load_fixture_data
from src.core.orchestrator import clasificar_en_segundo_plano, generar_contenido, generar_imagenes
from src.domain.schemas import BatchInputPayload
from src.core.salud import estado_general, necesita_apoyo
from src.utils.logger import setup_logger

logger = setup_logger("api_espacio")


def es_oportunidad(p: Dict[str, Any]) -> bool:
    umbral = config.UMBRALES_POR_TIPO.get(p["opportunity"]["type"])
    return umbral is not None and p["opportunity"]["opportunity_score"] >= umbral


class Espacio:
    def __init__(self, usuario: str, rol: str):
        self.usuario, self.rol = usuario, rol
        self.fuente = "estandar"
        self.discord_comunidad = "principal"
        self.dataset: Optional[BatchInputPayload] = load_fixture_data()
        self.nombre_archivo: Optional[str] = None
        self._bloqueo = threading.Lock()
        self._limpiar()

    def _limpiar(self) -> None:
        self.clasificacion = None
        self.generacion = None
        self.imagenes = None
        self.paquete: Optional[Dict[str, Any]] = None
        self.procesados: List[Dict[str, Any]] = []
        self.avisos: Dict[str, list] = {}
        self.textos: Dict[str, Dict[str, Any]] = {}
        self.comunidad = ""
        self.simulado = False
        self.repetidos = 0
        self.error: Optional[str] = None
        self.segundos_clasificacion: Optional[float] = None
        self.segundos_redaccion: Optional[float] = None
        self.guardados_en_base: Any = None
        self.resultado_oci: Optional[Dict[str, Any]] = None

    # ─── Análisis ─────────────────────────────────────────────────────────────

    def analizar(self, cantidad: int, simulado: bool, omitir_repetidos: bool) -> Dict[str, Any]:
        """Arranca la clasificación del lote. Devuelve cuántos mensajes van y cuántos se omitieron por repetidos."""
        if not self.dataset:
            raise ValueError("No hay un lote cargado.")
        # Primero se descartan los ya analizados y recién después se toman N: así "analizar 10" son los 10 siguientes
        # pendientes (los más recientes), aunque los primeros del lote ya se hayan procesado antes
        interacciones, metadatos = interacciones_desde_payload(self.dataset)
        repetidos = 0
        if omitir_repetidos and not simulado:
            interacciones, repetidos = repository.separar_nuevos(interacciones, self.dataset.origen_comunidad)
            if not interacciones:
                raise ValueError("Todos los mensajes ya fueron procesados. Desactiva «Omitir mensajes ya "
                                 "procesados» para analizarlos de nuevo.")
        pendientes = len(interacciones)
        interacciones = interacciones[:cantidad]
        with self._bloqueo:
            if self.imagenes:  # un lote nuevo: no se siguen generando imágenes del anterior
                self.imagenes.detener()
            self._limpiar()
            self.simulado, self.repetidos = simulado, repetidos
            self.comunidad = self.dataset.origen_comunidad
            self.textos = {m["message_id"]: m for m in interacciones}
            self.clasificacion = clasificar_en_segundo_plano(interacciones, metadatos, simulado=simulado)
            threading.Thread(target=self._seguir, args=(self.clasificacion,), name="seguimiento", daemon=True).start()
        return {"mensajes": len(interacciones), "repetidos": repetidos, "quedan": pendientes - len(interacciones)}

    def _seguir(self, clasificacion) -> None:
        """Encadena las etapas en el servidor, como hacían los fragmentos del panel de Streamlit."""
        clasificacion.esperar()
        if clasificacion is not self.clasificacion:
            return  # llegó otro lote mientras tanto
        if clasificacion.error:
            self.error = (f"No se pudo clasificar el lote ({type(clasificacion.error).__name__}). Revisa las API "
                          f"keys y las cuotas de la IA, o prueba el modo simulado.")
            return
        detalle = clasificacion.detalle
        self.procesados, self.avisos = detalle["procesados"], detalle["avisos"]
        self.segundos_clasificacion = clasificacion.segundos
        if not self.simulado:  # los análisis reales quedan en la base para no reprocesar esos mensajes
            try:
                self.guardados_en_base = repository.guardar_mensajes(detalle["procesados"], self.textos, self.comunidad)
            except Exception as error:
                self.guardados_en_base = f"no se pudo guardar ({type(error).__name__})"
        inicio = time.perf_counter()
        self.generacion = generar_contenido(detalle, simulado=self.simulado)
        if not self.simulado:
            self.imagenes = generar_imagenes(detalle["paquete"], self.generacion)
        self.paquete = detalle["paquete"]
        self.generacion.esperar()
        if clasificacion is self.clasificacion:
            self.segundos_redaccion = time.perf_counter() - inicio
            self.avisos["piezas_pendientes"] = list(self.generacion.pendientes)

    def relanzar_imagenes(self) -> None:
        if self.paquete and (not self.imagenes or self.imagenes.terminado):
            self.imagenes = generar_imagenes(self.paquete)

    # ─── Lectura del estado ───────────────────────────────────────────────────

    def fase(self) -> str:
        if self.error:
            return "error"
        if not self.clasificacion:
            return "inactivo"
        if not self.paquete:
            return "clasificando"
        if self.generacion and not self.generacion.terminado:
            return "redactando"
        return "listo"

    def _fila(self, p: Dict[str, Any]) -> Dict[str, Any]:
        original = self.textos.get(p["tracking"]["message_id"], {})
        return {**p, "texto": original.get("texto", ""), "autor": original.get("autor") or "Miembro",
                "es_oportunidad": es_oportunidad(p), "necesita_apoyo": necesita_apoyo(p)}

    def estado(self) -> Dict[str, Any]:
        clasificacion, generacion, imagenes, paquete = self.clasificacion, self.generacion, self.imagenes, self.paquete
        orden = {mid: i for i, mid in enumerate(self.textos)}
        filas = self.procesados if paquete else (clasificacion.parciales if clasificacion else [])
        filas = sorted(filas, key=lambda p: orden.get(p["tracking"]["message_id"], 0))
        resumen = paquete["resumen_comunidad"] if paquete else None
        activos = list(paquete["activos"]) if paquete else []
        return {
            "fase": self.fase(),
            "error": self.error,
            "simulado": self.simulado,
            "comunidad": self.comunidad,
            "repetidos": self.repetidos,
            "total": clasificacion.total if clasificacion else 0,
            "transcurrido": round(clasificacion.transcurrido, 1) if clasificacion else 0,
            "segundos_clasificacion": self.segundos_clasificacion,
            "segundos_redaccion": self.segundos_redaccion,
            "guardados_en_base": self.guardados_en_base,
            "mensajes": [self._fila(p) for p in filas],
            "resumen": resumen,
            "salud": dict(zip(("emoji", "etiqueta"), estado_general(resumen["distribucion_sentimiento"])))
            if resumen else None,
            "avisos": {k: len(v) for k, v in self.avisos.items()},
            "redaccion": {
                "listos": len(generacion.activos), "total": generacion.total_piezas,
                "lotes_listos": generacion.lotes_listos, "lotes": len(generacion.lotes),
                "terminado": generacion.terminado,
            } if generacion else None,
            "imagenes": {
                "generadas": imagenes.generadas, "fallidas": imagenes.fallidas,
                "pendientes": sum(1 for a in activos if (a.get("imagen") or {}).get("estado") in ("pendiente", "generando")),
                "terminado": imagenes.terminado,
            } if imagenes else None,
            "paquete": {
                "paquete_id": paquete["paquete_id"], "status": paquete["status"],
                "periodo_referencia": paquete["periodo_referencia"],
                "ruta_objeto": paquete["almacenamiento_oci"]["ruta_objeto"],
                "activos": len(activos),
                "curaduria": {e: sum(1 for a in activos if a["estado_curaduria"] == e)
                              for e in ("borrador", "aprobado", "descartado")},
            } if paquete else None,
            "resultado_oci": self.resultado_oci,
        }
