"""
CommunityLab AI - Utilidades de texto y lotes
"""
import html
import json
import re
from typing import Any, Dict, Iterator, List, Optional

from src import config


def texto_llm(valor: Optional[str]) -> str:
    """Normaliza texto devuelto por el LLM: entidades HTML (Groq devuelve &eacute; a veces) y espacios."""
    return html.unescape(valor or "").strip()


_PASO = re.compile(r"\s+(?=(\d{1,2})[.)]\s)")


def pasos_en_lineas(texto: str) -> str:
    """Pone cada paso numerado en su propia línea: el modelo casi siempre los escribe seguidos ('... 1. x 2. y').
    Solo actúa si los números forman la secuencia 1, 2, 3... para no tocar cifras sueltas."""
    numeros = [int(m.group(1)) for m in _PASO.finditer(texto)]
    if len(numeros) < 2 or numeros != list(range(1, len(numeros) + 1)):
        return texto
    return _PASO.sub("\n", texto)


def hashtags(crudos: List[str]) -> List[str]:
    """Separa hashtags que el modelo devuelve pegados ('#Uno#Dos') y agrega '#' si falta."""
    partes = [p for h in map(texto_llm, crudos) for p in re.split(r"[#\s,]+", h) if p]
    return list(dict.fromkeys(f"#{p}" for p in partes))


def lotes(items: List[Any], n: Optional[int] = None) -> Iterator[List[Any]]:
    n = n or config.TAMANO_LOTE
    for i in range(0, len(items), n):
        yield items[i:i + n]


def json_mensajes(mensajes: List[Dict[str, Any]], campos: List[str]) -> str:
    return json.dumps([{c: m.get(c) for c in campos} for m in mensajes], ensure_ascii=False)
