"""
CommunityLab AI - Redacción en segundo plano
Después de clasificar, redacta las piezas en un hilo aparte y las agrega al paquete a medida que cada
lote termina, para que el panel muestre la clasificación sin esperar los textos.
"""
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict

from src import config
from src.core.agents.strategist import construir_activo, lotes_de_piezas, planificar_piezas, redactar_lote
from src.core.packager import avisos
from src.utils.logger import setup_logger

logger = setup_logger("generacion")


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
