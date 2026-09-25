"""
CommunityLab AI - Adaptador de proveedores de IA
Llamadas estructuradas a Gemini o Groq con reintentos ante cuota, respaldo automático
entre proveedores y lotes en paralelo.
"""
import os
import time
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from typing import Any, Dict, List

from src import config
from src.utils.logger import setup_logger

logger = setup_logger("proveedores_llm")


def modelo(proveedor: str, rol: str) -> str:
    """Modelo para un rol ('analisis' o 'redaccion'). LLM_MODEL_<ROL> solo aplica al proveedor titular."""
    if proveedor == config.PROVEEDOR:
        return os.getenv(f"LLM_MODEL_{rol.upper()}", config.PROVEEDORES[proveedor][rol])
    return config.PROVEEDORES[proveedor][rol]


@lru_cache(maxsize=None)
def _llm(proveedor: str, rol: str, temperature: float):
    variable_key = config.PROVEEDORES[proveedor]["key"]
    if not os.getenv(variable_key):
        raise RuntimeError(f"Falta {variable_key} para el proveedor '{proveedor}'.")
    nombre = modelo(proveedor, rol)
    if proveedor == "groq":
        from langchain_groq import ChatGroq
        # gpt-oss razona antes de responder: con el límite por defecto se corta el JSON
        return ChatGroq(model=nombre, temperature=temperature, max_retries=3, max_tokens=16384)
    from langchain_google_genai import ChatGoogleGenerativeAI
    return ChatGoogleGenerativeAI(model=nombre, temperature=temperature, max_retries=3)


def _es_limite_de_cuota(error: Exception) -> bool:
    nombre = type(error).__name__
    return "RateLimit" in nombre or "ResourceExhausted" in nombre \
        or getattr(error, "status_code", None) in (429, 503)


def invocar(prompt, esquema, rol: str, temperature: float, entrada: Dict[str, Any]):
    """Una llamada estructurada. Si el titular agota los reintentos, conmuta al respaldo."""
    for proveedor in (config.PROVEEDOR, config.RESPALDO):
        if not os.getenv(config.PROVEEDORES[proveedor]["key"]):
            continue
        # En Groq, gpt-oss necesita json_schema para analizar (el modo por defecto rompe el parseo),
        # pero en redacción el modo por defecto es más estable con JSON largo
        usa_schema = proveedor == "groq" and rol == "analisis" and "gpt-oss" in modelo(proveedor, rol)
        opciones = {"method": "json_schema"} if usa_schema else {}
        cadena = prompt | _llm(proveedor, rol, temperature).with_structured_output(esquema, **opciones)
        for intento in range(config.MAX_REINTENTOS_CUOTA + 1):
            try:
                return cadena.invoke(entrada)
            except Exception as error:
                if not _es_limite_de_cuota(error) or intento == config.MAX_REINTENTOS_CUOTA:
                    if proveedor != config.RESPALDO:
                        logger.warning(f"'{proveedor}' falló ({type(error).__name__}); "
                                       f"conmutando a '{config.RESPALDO}'")
                        break
                    raise
                espera = config.ESPERA_BASE_S * (intento + 1)
                logger.warning(f"Cuota de {proveedor} agotada, reintento en {espera}s")
                time.sleep(espera)
    raise RuntimeError("Ningún proveedor disponible (revisa las API keys del .env).")


def invocar_lotes(prompt, esquema, rol: str, temperature: float, entradas: List[Dict[str, Any]]) -> List[Any]:
    """Una llamada por lote, en paralelo, con los resultados en el orden de entrada.
    `prompt` puede ser uno solo o una lista con uno por entrada. Un lote que falla devuelve None
    (el nodo lo rellena o lo reporta) en lugar de abortar la corrida completa."""
    prompts = prompt if isinstance(prompt, list) else [prompt] * len(entradas)

    def uno(par):
        try:
            return invocar(par[0], esquema, rol, temperature, par[1])
        except Exception as error:
            logger.error(f"Un lote de {rol} falló ({type(error).__name__}); se marca como pendiente")
            return None

    pares = list(zip(prompts, entradas))
    if len(pares) <= 1 or config.MAX_CONCURRENCIA <= 1:
        return [uno(p) for p in pares]
    with ThreadPoolExecutor(max_workers=min(config.MAX_CONCURRENCIA, len(pares))) as ejecutor:
        return list(ejecutor.map(uno, pares))
