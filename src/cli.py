"""
CommunityLab AI - Línea de comandos

    python -m src.cli lote.json              JSON con la lista "interacciones" (Formato A)
    python -m src.cli comentarios.csv        CSV o export de Discord
    python -m src.cli lote.json --simulado   sin IA: heurísticas, sin gastar cuota

Escribe el paquete y el cuadro por mensaje en salidas/.
"""
import json
import sys

from src.adapters.ingestion.loaders import cargar_entrada
from src.adapters.salidas import guardar_salidas
from src.core.orchestrator import procesar_detalle

EJEMPLO = [
    {"message_id": "csv-comentarios-0001",
     "texto": "Comunidad, quedé seleccionada para el puesto de Desarrolladora Junior de IA!"},
    {"message_id": "csv-comentarios-0002",
     "texto": "Tengo una duda: ¿cómo despliego un grafo de LangGraph en OCI Functions?"},
    {"message_id": "csv-comentarios-0003", "texto": "Buenas noches a todos"},
]


def main() -> None:
    # Las consolas de Windows usan cp1252 y fallan con los emojis de los mensajes
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

    simulado = "--simulado" in sys.argv
    argumentos = [a for a in sys.argv[1:] if not a.startswith("--")]
    interacciones, metadatos = cargar_entrada(argumentos[0]) if argumentos else (EJEMPLO, {})
    if simulado:
        print("MODO SIMULADO: sin llamadas a la IA (heurísticas de desarrollo).", file=sys.stderr)

    detalle = procesar_detalle(interacciones, metadatos, simulado=simulado)
    rutas = guardar_salidas(detalle["paquete"], detalle["estado"])
    print(json.dumps(detalle["paquete"], indent=2, ensure_ascii=False))
    print(f"\nPaquete: {rutas['paquete']}\nCuadro:  {rutas.get('cuadro', '')}", file=sys.stderr)


if __name__ == "__main__":
    main()
