"""
CommunityLab AI - Adaptador de proveedores de IA
Llamadas estructuradas por una cadena de modelos (Gemini titular → modelos alternos de Gemini → Groq), cada uno con
su propia cuota. En clasificación, si un eslabón se demora se lanza el siguiente en paralelo (cobertura escalonada);
ante un error se pasa al siguiente de inmediato. Solo el último eslabón reintenta con espera ante cuota.
"""
import os
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from functools import lru_cache
from typing import Any, Dict, List, Tuple

from src import config
from src.utils.logger import setup_logger

logger = setup_logger("proveedores_llm")

Eslabon = Tuple[str, str]  # (proveedor, modelo)


def modelo(proveedor: str, rol: str) -> str:
    """Modelo principal de un proveedor para un rol. LLM_MODEL_<ROL> solo aplica al proveedor titular."""
    if proveedor == config.PROVEEDOR:
        return os.getenv(f"LLM_MODEL_{rol.upper()}", config.PROVEEDORES[proveedor][rol])
    return config.PROVEEDORES[proveedor][rol]


def _disponible(proveedor: str) -> bool:
    return bool(os.getenv(config.PROVEEDORES[proveedor]["key"]))


def cadena(rol: str) -> List[Eslabon]:
    """Orden de modelos para un rol: el titular y, si es Gemini, sus alternos (misma key, cuota propia por modelo);
    luego el otro proveedor. Solo entran los proveedores con API key."""
    eslabones: List[Eslabon] = []
    for proveedor in (config.PROVEEDOR, config.RESPALDO):
        if not _disponible(proveedor):
            continue
        principal = modelo(proveedor, rol)
        eslabones.append((proveedor, principal))
        if proveedor == "gemini":
            eslabones += [("gemini", m) for m in config.ALTERNOS_GEMINI if m != principal]
    return eslabones


@lru_cache(maxsize=None)
def _llm(proveedor: str, nombre: str, rol: str, temperature: float, reintentos: int):
    if proveedor == "groq":
        from langchain_groq import ChatGroq
        # gpt-oss razona antes de responder: con el límite por defecto se corta el JSON
        extra = {"reasoning_effort": config.RAZONAMIENTO_GROQ} \
            if rol == "analisis" and "gpt-oss" in nombre and config.RAZONAMIENTO_GROQ else {}
        return ChatGroq(model=nombre, temperature=temperature, max_retries=reintentos, max_tokens=16384, **extra)
    from langchain_google_genai import ChatGoogleGenerativeAI
    return ChatGoogleGenerativeAI(model=nombre, temperature=temperature, max_retries=reintentos)


def _es_limite_de_cuota(error: Exception) -> bool:
    nombre = type(error).__name__
    return "RateLimit" in nombre or "ResourceExhausted" in nombre \
        or getattr(error, "status_code", None) in (429, 503)


def _invocar_en(eslabon: Eslabon, prompt, esquema, rol: str, temperature: float, entrada: Dict[str, Any],
                ultimo: bool = True):
    """Una llamada estructurada a un modelo. Si no es el último eslabón falla rápido (sin reintentos) para que la
    cadena pase al siguiente; el último reintenta con espera ante cuota. Si falla, propaga el error."""
    proveedor, nombre = eslabon
    # En Groq, gpt-oss necesita json_schema para analizar (el modo por defecto rompe el parseo),
    # pero en redacción el modo por defecto es más estable con JSON largo
    usa_schema = proveedor == "groq" and rol == "analisis" and "gpt-oss" in nombre
    opciones = {"method": "json_schema"} if usa_schema else {}
    llm = _llm(proveedor, nombre, rol, temperature, 3 if ultimo else 0)
    ejecutable = prompt | llm.with_structured_output(esquema, **opciones)
    intentos = config.MAX_REINTENTOS_CUOTA if ultimo else 0
    for intento in range(intentos + 1):
        try:
            return ejecutable.invoke(entrada)
        except Exception as error:
            if not _es_limite_de_cuota(error) or intento == intentos:
                raise
            espera = config.ESPERA_BASE_S * (intento + 1)
            logger.warning(f"Cuota de {nombre} agotada, reintento en {espera}s")
            time.sleep(espera)


def _nombre(eslabon: Eslabon) -> str:
    return eslabon[1]


# Hilos propios para las llamadas con cobertura: la llamada que pierde la carrera termina sola en segundo plano
_EJECUTOR_COBERTURA = ThreadPoolExecutor(max_workers=32, thread_name_prefix="cobertura")


def _con_cobertura(eslabones: List[Eslabon], args: tuple):
    """Cobertura escalonada: arranca el primer eslabón y, cada COBERTURA_S sin respuesta (o ante un error), lanza el
    siguiente en paralelo. Gana la primera respuesta válida; las llamadas más lentas terminan solas."""
    en_curso: Dict[Any, Eslabon] = {}
    siguiente, ultimo_error = 0, None

    def lanzar():
        nonlocal siguiente
        eslabon = eslabones[siguiente]
        es_ultimo = siguiente == len(eslabones) - 1
        en_curso[_EJECUTOR_COBERTURA.submit(_invocar_en, eslabon, *args, ultimo=es_ultimo)] = eslabon
        siguiente += 1

    lanzar()
    while en_curso:
        listos, _ = wait(en_curso, timeout=config.COBERTURA_S if siguiente < len(eslabones) else None,
                         return_when=FIRST_COMPLETED)
        if not listos:
            logger.warning(f"'{_nombre(eslabones[siguiente - 1])}' no respondió en {config.COBERTURA_S:g} s; "
                           f"lanzando cobertura en '{_nombre(eslabones[siguiente])}'")
            lanzar()
            continue
        for futuro in listos:
            eslabon = en_curso.pop(futuro)
            try:
                resultado = futuro.result()
                if eslabon != eslabones[0]:
                    logger.info(f"Respuesta de '{_nombre(eslabon)}' (cobertura)")
                return resultado
            except Exception as error:
                ultimo_error = error
                if siguiente < len(eslabones):
                    logger.warning(f"'{_nombre(eslabon)}' falló ({type(error).__name__}); "
                                   f"conmutando a '{_nombre(eslabones[siguiente])}'")
                    lanzar()
                else:
                    logger.warning(f"'{_nombre(eslabon)}' falló ({type(error).__name__})")
    raise ultimo_error


def invocar(prompt, esquema, rol: str, temperature: float, entrada: Dict[str, Any]):
    """Una llamada estructurada por la cadena de modelos del rol. En los roles con cobertura, además de conmutar
    ante errores, lanza el siguiente eslabón en paralelo cuando el actual se demora."""
    eslabones = cadena(rol)
    if not eslabones:
        raise RuntimeError("Ningún proveedor disponible (revisa las API keys del .env).")
    args = (prompt, esquema, rol, temperature, entrada)
    if len(eslabones) > 1 and rol in config.ROLES_CON_COBERTURA and config.COBERTURA_S > 0:
        return _con_cobertura(eslabones, args)
    for i, eslabon in enumerate(eslabones):
        ultimo = i == len(eslabones) - 1
        try:
            return _invocar_en(eslabon, *args, ultimo=ultimo)
        except Exception as error:
            if ultimo:
                raise
            logger.warning(f"'{_nombre(eslabon)}' falló ({type(error).__name__}); "
                           f"conmutando a '{_nombre(eslabones[i + 1])}'")


def invocar_lotes(prompt, esquema, rol: str, temperature: float, entradas: List[Dict[str, Any]],
                  al_completar=None) -> List[Any]:
    """Una llamada por lote, en paralelo, con los resultados en el orden de entrada.
    `prompt` puede ser uno solo o una lista con uno por entrada. Un lote que falla devuelve None
    (el nodo lo rellena o lo reporta) en lugar de abortar la corrida completa.
    `al_completar(indice, resultado)`, si se pasa, se llama apenas termina cada lote (para mostrar avance)."""
    prompts = prompt if isinstance(prompt, list) else [prompt] * len(entradas)

    def uno(indice_par):
        indice, (p, entrada) = indice_par
        try:
            resultado = invocar(p, esquema, rol, temperature, entrada)
        except Exception as error:
            logger.error(f"Un lote de {rol} falló ({type(error).__name__}); se marca como pendiente")
            resultado = None
        if al_completar:
            al_completar(indice, resultado)
        return resultado

    pares = list(enumerate(zip(prompts, entradas)))
    if len(pares) <= 1 or config.MAX_CONCURRENCIA <= 1:
        return [uno(p) for p in pares]
    with ThreadPoolExecutor(max_workers=min(config.MAX_CONCURRENCIA, len(pares))) as ejecutor:
        return list(ejecutor.map(uno, pares))
