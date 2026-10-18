#!/usr/bin/env python3
"""Chequeo de salud de domotica-hub para integrar en aislar-healthcheck.

Sale con 0 si ~/domotica/estado/salud.json existe, tiene menos de 3 minutos y ok=true;
con 1 en otro caso, imprimiendo el motivo en una línea. No necesita red ni credenciales.
"""
import json
import sys
import time
from pathlib import Path

ARCHIVO = Path.home() / "domotica" / "estado" / "salud.json"
MAX_EDAD_S = 180


def main() -> int:
    try:
        edad = time.time() - ARCHIVO.stat().st_mtime
        datos = json.loads(ARCHIVO.read_text())
    except (OSError, ValueError) as e:
        print(f"domotica-hub: sin estado ({type(e).__name__})")
        return 1
    if edad > MAX_EDAD_S:
        print(f"domotica-hub: estado viejo ({int(edad)} s); ¿servicio caído?")
        return 1
    if not datos.get("ok"):
        print(f"domotica-hub: no ok; último error: {datos.get('ultimo_error') or '-'}")
        return 1
    print(f"domotica-hub: ok (cola {datos.get('en_cola', 0)}, en curso {datos.get('en_curso', 0)}, "
          f"esperando aprobación {datos.get('esperando_aprobacion', 0)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
