"""
CommunityLab AI - Salidas locales
Escribe el paquete (Formato B) y un cuadro CSV por mensaje en la carpeta salidas/ del proyecto.
"""
import csv
import json
from typing import Any, Dict, List, Optional

from src import config


def cuadro_resumen(estado: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Una fila por mensaje procesado con su clasificación y los activos que generó."""
    activos_por_mensaje: Dict[str, Dict[str, List[str]]] = {}
    for a in estado.get("activos_generados", []):
        activos_por_mensaje.setdefault(a["origen"]["message_id"], {}).setdefault(a["formato"], []).append(a["activo_id"])
    filas = []
    for m in estado["mensajes_analizados"]:
        c = estado.get("clasificaciones", {}).get(m["message_id"], {})
        activos = activos_por_mensaje.get(m["message_id"], {})
        filas.append({
            "message_id": m["message_id"],
            "canal": m.get("canal") or "",
            "texto": m["texto"],
            "sentimiento": m["sentiment"],
            "tipo": c.get("type", ""),
            "score": c.get("score", ""),
            "contenido_exito": ", ".join(activos.get("post_linkedin", [])),
            "newsletter": ", ".join(activos.get("destaque_newsletter", [])),
            "pregunta_faq": ", ".join(activos.get("sugerencia_faq", [])),
            "reason": c.get("reason", ""),
        })
    return filas


def guardar_salidas(paquete: Dict[str, Any], estado: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
    """Escribe <paquete_id>.json y, si se pasa el estado completo, <paquete_id>_cuadro.csv."""
    config.DIRECTORIO_SALIDAS.mkdir(parents=True, exist_ok=True)
    ruta_paquete = config.DIRECTORIO_SALIDAS / f"{paquete['paquete_id']}.json"
    ruta_paquete.write_text(json.dumps(paquete, indent=2, ensure_ascii=False), encoding="utf-8")
    rutas = {"paquete": str(ruta_paquete)}
    if estado:
        ruta_cuadro = config.DIRECTORIO_SALIDAS / f"{paquete['paquete_id']}_cuadro.csv"
        filas = cuadro_resumen(estado)
        with open(ruta_cuadro, "w", encoding="utf-8-sig", newline="") as f:
            escritor = csv.DictWriter(f, fieldnames=list(filas[0].keys()) if filas else ["message_id"])
            escritor.writeheader()
            escritor.writerows(filas)
        rutas["cuadro"] = str(ruta_cuadro)
    return rutas
