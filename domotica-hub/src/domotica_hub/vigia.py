"""Vigía de salud de domotica-hub, separado de los avisos de AISLAR.

Corre cada 5 minutos (domotica-vigia.timer). Si el hub falla dos veces seguidas, abre un
issue con la etiqueta de título "[salud]" en el repo de registro; GitHub le avisa al dueño.
Cuando se recupera, comenta y cierra ese issue. Nunca abre más de uno a la vez.
"""

from __future__ import annotations

import json
import time
import urllib.request
from pathlib import Path

from .config import Config
from .github import GitHub

MAX_EDAD_S = 180
FALLOS_PARA_AVISAR = 2


def salud_local(archivo: Path) -> tuple[bool, str]:
    try:
        edad = time.time() - archivo.stat().st_mtime
        datos = json.loads(archivo.read_text())
    except (OSError, ValueError) as e:
        return False, f"sin estado ({type(e).__name__})"
    if edad > MAX_EDAD_S:
        return False, f"estado viejo ({int(edad)} s): ¿servicio caído?"
    if not datos.get("ok"):
        return False, f"no ok; último error: {datos.get('ultimo_error') or '-'}"
    return True, (f"ok (cola {datos.get('en_cola', 0)}, en curso {datos.get('en_curso', 0)}, "
                  f"esperando aprobación {datos.get('esperando_aprobacion', 0)})")


def salud_publica(url: str) -> tuple[bool, str]:
    if not url.startswith("https://"):
        return True, "sin URL pública"
    try:
        with urllib.request.urlopen(f"{url}/salud", timeout=15) as r:
            return r.status == 200, f"{url}/salud → {r.status}"
    except Exception as e:  # DNS, TLS, proxy, 503...
        return False, f"{url}/salud → {type(e).__name__}: {str(e)[:120]}"


def revisar(cfg: Config, gh: GitHub | None = None) -> int:
    estado_path = cfg.estado / "vigia.json"
    try:
        estado = json.loads(estado_path.read_text())
    except (OSError, ValueError):
        estado = {"issue": None, "fallos": 0}

    ok_l, msg_l = salud_local(cfg.estado / "salud.json")
    ok_p, msg_p = salud_publica(cfg.url_publica)
    ok = ok_l and ok_p
    detalle = f"- Local: {msg_l}\n- Público: {msg_p}"
    print(("OK" if ok else "FALLA") + " | " + detalle.replace("\n", " "))

    gh = gh or GitHub(cfg)
    if ok:
        if estado.get("issue"):
            gh.comentar(estado["issue"], f"✅ domotica-hub se recuperó ({time.strftime('%F %T')}).\n\n{detalle}")
            gh.cerrar_issue(estado["issue"])
        estado = {"issue": None, "fallos": 0}
    else:
        estado["fallos"] = estado.get("fallos", 0) + 1
        if estado["fallos"] >= FALLOS_PARA_AVISAR and not estado.get("issue"):
            estado["issue"] = gh.crear_issue(
                "[salud] domotica-hub no responde",
                f"Detectado {time.strftime('%F %T')} por domotica-vigia ({estado['fallos']} chequeos seguidos).\n\n"
                f"{detalle}\n\nRevisar: `systemctl status domotica-hub` y `journalctl -u domotica-hub -n 50`.\n"
                "Este issue se cierra solo cuando el servicio se recupera.",
            )

    tmp = estado_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(estado))
    tmp.replace(estado_path)
    return 0 if ok else 1
