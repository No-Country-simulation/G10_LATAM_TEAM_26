"""
CommunityLab AI - Clasificación y redacción en segundo plano
La clasificación corre en un hilo y publica los mensajes lote por lote, para que el panel los muestre apenas
llegan. Después, la redacción corre en otro hilo y agrega las piezas al paquete a medida que cada lote termina.
"""
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable, Dict, List, Optional

from src import config
from src.core.agents.strategist import construir_activo, lotes_de_piezas, planificar_piezas, redactar_lote
from src.core.packager import avisos, fila_p
from src.utils.logger import setup_logger

logger = setup_logger("generacion")


class ClasificacionEnSegundoPlano:
    """Estado observable de la clasificación: `parciales` crece (en Formato P) a medida que responde cada lote,
    y `detalle` queda con el resultado completo de clasificar() al terminar."""

    def __init__(self, clasificar: Callable[..., Dict[str, Any]], interacciones: List[Dict[str, Any]],
                 metadatos: Optional[Dict[str, Any]], simulado: bool, total: int):
        self._clasificar = clasificar
        self._args = (interacciones, metadatos, simulado)
        self.total = total
        self.parciales: List[Dict[str, Any]] = []
        self.detalle: Optional[Dict[str, Any]] = None
        self.error: Optional[Exception] = None
        self.terminado = False
        self.segundos: Optional[float] = None
        self._inicio = 0.0
        self._bloqueo = threading.Lock()
        self._hilo = threading.Thread(target=self._correr, name="clasificacion", daemon=True)

    @property
    def transcurrido(self) -> float:
        return self.segundos if self.segundos is not None else time.perf_counter() - self._inicio

    def iniciar(self) -> "ClasificacionEnSegundoPlano":
        self._inicio = time.perf_counter()
        self._hilo.start()
        return self

    def esperar(self, timeout: float | None = None) -> None:
        if self._hilo.is_alive():
            self._hilo.join(timeout)

    def _al_avanzar(self, filas: list) -> None:
        nuevas = [fila_p({**mensaje, **analisis}, clasificacion) for mensaje, analisis, clasificacion in filas]
        with self._bloqueo:
            self.parciales = self.parciales + nuevas  # lista nueva: el panel puede leer la anterior sin bloqueo

    def _correr(self) -> None:
        try:
            self.detalle = self._clasificar(*self._args, al_avanzar=self._al_avanzar)
        except Exception as error:
            logger.error(f"La clasificación en segundo plano se detuvo ({type(error).__name__}: {error})")
            self.error = error
        finally:
            self.segundos = time.perf_counter() - self._inicio
            self.terminado = True


class GeneracionEnSegundoPlano:
    """Estado observable de la redacción: el panel lo consulta mientras el hilo trabaja.
    Los activos se agregan a paquete['activos'] (la misma lista), así el panel los ve apenas existen."""

    def __init__(self, estado: Dict[str, Any], paquete: Dict[str, Any], modo_simulado: bool = False):
        self.estado = estado
        self.paquete = paquete
        self.modo_simulado = modo_simulado
        self.piezas = planificar_piezas(estado.get("oportunidades", []))
        self.lotes = lotes_de_piezas(self.piezas)
        self.activos = paquete["activos"]
        self.pendientes: list = []
        self.lotes_listos = 0
        self.terminado = not self.lotes
        self._hilo = threading.Thread(target=self._correr, name="redaccion", daemon=True)

    @property
    def total_piezas(self) -> int:
        return len(self.piezas)

    def iniciar(self) -> "GeneracionEnSegundoPlano":
        if self.lotes:
            self.paquete["status"] = "parcial"  # hasta que terminen todas las piezas
            self._hilo.start()
        return self

    def esperar(self, timeout: float | None = None) -> None:
        if self._hilo.is_alive():
            self._hilo.join(timeout)

    def _correr(self) -> None:
        try:
            with ThreadPoolExecutor(max_workers=max(1, min(config.MAX_CONCURRENCIA, len(self.lotes)))) as ejecutor:
                futuros = {ejecutor.submit(redactar_lote, lote, self.modo_simulado): lote for lote in self.lotes}
                for futuro in as_completed(futuros):
                    por_id = futuro.result()
                    for pieza in futuros[futuro]:
                        borrador = por_id.get(pieza["pieza_id"])
                        if borrador:
                            self.activos.append(construir_activo(pieza, borrador))
                        else:
                            self.pendientes.append(pieza["pieza_id"])
                    self.lotes_listos += 1
            orden = {p["activo_id"]: p["orden"] for p in self.piezas}
            # Reemplazo en un paso: list.sort() deja la lista vacía para otros hilos mientras ordena
            self.activos[:] = sorted(self.activos, key=lambda a: orden.get(a["activo_id"], len(orden)))
        except Exception as error:
            logger.error(f"La redacción en segundo plano se detuvo ({type(error).__name__}: {error})")
            self.pendientes.extend(p["pieza_id"] for p in self.piezas
                                   if p["activo_id"] not in {a["activo_id"] for a in self.activos}
                                   and p["pieza_id"] not in self.pendientes)
        finally:
            self.estado["activos_generados"] = list(self.activos)
            self.estado["piezas_pendientes"] = list(self.pendientes)
            self.paquete["status"] = "parcial" if any(avisos(self.estado).values()) else "exito"
            self.terminado = True
