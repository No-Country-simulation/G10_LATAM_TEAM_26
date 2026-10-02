"""
CommunityLab AI - Clasificación y redacción en segundo plano
La clasificación corre en un hilo y publica los mensajes lote por lote, para que el panel los muestre apenas
llegan. Después, la redacción corre en otro hilo y agrega las piezas al paquete a medida que cada lote termina, y un
tercer hilo genera las imágenes de esas piezas (de mayor a menor score) sin bloquear nada.
"""
import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from src import config
from src.adapters import imagenes
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
        # Los activos nacen con la imagen pendiente solo si después la va a generar ImagenesEnSegundoPlano
        self.con_imagenes = config.GENERAR_IMAGENES and not modo_simulado
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
                futuros = {ejecutor.submit(redactar_lote, lote, self.modo_simulado, i): lote
                           for i, lote in enumerate(self.lotes)}
                for futuro in as_completed(futuros):
                    por_id = futuro.result()
                    for pieza in futuros[futuro]:
                        borrador = por_id.get(pieza["pieza_id"])
                        if borrador:
                            self.activos.append(construir_activo(pieza, borrador, con_imagen=self.con_imagenes))
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


class ImagenesEnSegundoPlano:
    """Genera en un hilo las imágenes pendientes del paquete, de mayor a menor score, a medida que la redacción
    agrega activos y al ritmo que permite el servicio. No bloquea el paquete: el panel muestra cada imagen cuando
    su estado pasa a 'lista'. Termina al acabar la redacción y la cola, o con detener() (p. ej. al cargar otro lote)."""

    def __init__(self, paquete: Dict[str, Any], generacion: Optional["GeneracionEnSegundoPlano"] = None,
                 generar: Optional[Callable[..., Any]] = None, intervalo: Optional[float] = None,
                 maximo: Optional[int] = None):
        self.paquete = paquete
        self.generacion = generacion
        self._generar = generar or imagenes.generar
        self.intervalo = config.IMAGENES_INTERVALO_S if intervalo is None else intervalo
        self.maximo = config.IMAGENES_MAX if maximo is None else maximo
        self.generadas = 0
        self.fallidas = 0
        self.terminado = False
        self._detener = threading.Event()
        self._hilo = threading.Thread(target=self._correr, name="imagenes", daemon=True)
        destino = Path(paquete["almacenamiento_oci"]["ruta_objeto"]).parent / "img" / paquete["paquete_id"]
        self.carpeta = config.RAIZ / "data" / "processed" / destino

    def iniciar(self) -> "ImagenesEnSegundoPlano":
        self._hilo.start()
        return self

    def detener(self) -> None:
        self._detener.set()

    def esperar(self, timeout: float | None = None) -> None:
        if self._hilo.is_alive():
            self._hilo.join(timeout)

    def pendientes(self) -> List[Dict[str, Any]]:
        return [a for a in list(self.paquete["activos"]) if (a.get("imagen") or {}).get("estado") == "pendiente"]

    def _redaccion_terminada(self) -> bool:
        return self.generacion is None or self.generacion.terminado

    def _correr(self) -> None:
        try:
            while not self._detener.is_set():
                if self.maximo and self.generadas + self.fallidas >= self.maximo:
                    for activo in self.pendientes():  # superado el máximo, el resto no queda esperando
                        activo["imagen"]["estado"] = "omitida"
                    if self._redaccion_terminada():
                        break
                    self._detener.wait(1)
                    continue
                pendientes = self.pendientes()
                if not pendientes:
                    if self._redaccion_terminada():
                        break
                    self._detener.wait(1)  # todavía se están redactando piezas
                    continue
                self._procesar(max(pendientes, key=lambda a: a["origen"]["score"]))
                self._detener.wait(self.intervalo)  # ritmo del servicio (15 s sin cuenta, 5 s con token)
        finally:
            self.terminado = True

    def _procesar(self, activo: Dict[str, Any]) -> None:
        imagen = activo["imagen"]
        imagen["estado"] = "generando"
        try:
            datos, extension = self._generar(imagen["prompt"], activo["formato"], semilla=random.randint(1, 10 ** 6))
            self.carpeta.mkdir(parents=True, exist_ok=True)
            ruta = self.carpeta / f"{activo['activo_id']}.{extension}"
            ruta.write_bytes(datos)
            imagen.update(estado="lista", ruta=str(ruta), proveedor="pollinations")
            imagen.pop("detalle", None)
            self.generadas += 1
        except Exception as error:
            codigo = getattr(getattr(error, "response", None), "status_code", None)
            imagen["intentos"] = imagen.get("intentos", 0) + 1
            if codigo in (402, 429) and imagen["intentos"] < config.IMAGENES_INTENTOS:
                # límite del servicio: la imagen vuelve a la cola y el hilo espera el intervalo antes de seguir
                logger.info(f"Límite de Pollinations ({codigo}) en {activo['activo_id']}; vuelve a la cola")
                imagen["estado"] = "pendiente"
                return
            logger.warning(f"No se pudo generar la imagen de {activo['activo_id']} ({type(error).__name__}: {error})")
            imagen.update(estado="error", detalle=f"{type(error).__name__}{f' {codigo}' if codigo else ''}")
            self.fallidas += 1
