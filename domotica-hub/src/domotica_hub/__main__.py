"""Punto de entrada: `python -m domotica_hub` (servicio) o `python -m domotica_hub clave`."""

from __future__ import annotations

import getpass
import logging
import os
import sys

from .config import Config


def guardar_clave(cfg: Config) -> None:
    """Pide la clave del dueño y guarda su hash scrypt en DOMOTICA_CLAVE_HASH (archivo env)."""
    from .auth import hash_clave

    clave = getpass.getpass("Nueva clave para autorizar conectores (mín. 12 caracteres): ")
    if len(clave) < 12 or clave != getpass.getpass("Repetila: "):
        sys.exit("No coinciden o es demasiado corta. No se guardó nada.")
    lineas = cfg.env_file.read_text(encoding="utf-8").splitlines() if cfg.env_file.exists() else []
    nueva = f"DOMOTICA_CLAVE_HASH={hash_clave(clave)}"
    lineas = [nueva if l.startswith("DOMOTICA_CLAVE_HASH=") else l for l in lineas]
    if nueva not in lineas:
        lineas.append(nueva)
    tmp = cfg.env_file.with_suffix(".tmp")
    tmp.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    os.chmod(tmp, 0o600)
    tmp.replace(cfg.env_file)
    print("Clave guardada (solo el hash).")


def probar(cfg: Config, agente: str, casa: str, pedido: str, cuenta: str = "gmail") -> None:
    """Corre un agente con los mismos permisos de la fase de trabajo, sin issue/PR. Para pruebas manuales."""
    import tempfile
    import threading
    from pathlib import Path

    from . import agentes

    with tempfile.TemporaryDirectory(prefix="domotica-prueba-") as tmp:
        r = agentes.ejecutar(cfg, agente=agente, casa=casa, fase=agentes.TRABAJO, cuenta=cuenta, sesion=None,
                             prompt=pedido, cwd=Path(tmp), log_path=Path(tmp) / "log",
                             cancelar=threading.Event())
        print(r.texto if r.ok else f"ERROR: {r.error}")
        if r.extra.get("denegadas"):
            print("Denegadas:", ", ".join(d.get("tool_name", "?") for d in r.extra["denegadas"]))


def main() -> None:
    cfg = Config.cargar()
    if sys.argv[1:] == ["clave"]:
        guardar_clave(cfg)
        return
    if sys.argv[1:] == ["vigia"]:
        from .vigia import revisar

        cfg.preparar_directorios()
        sys.exit(revisar(cfg))
    if sys.argv[1:2] == ["probar"] and len(sys.argv) in (5, 6):
        probar(cfg, *sys.argv[2:])
        return

    import uvicorn

    from .db import DB
    from .ejecutor import Ejecutor
    from .github import GitHub
    from .server import crear_servidor, transporte

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    os.umask(0o077)
    cfg.preparar_directorios()
    db = DB(cfg.db_path)
    ejecutor = Ejecutor(cfg, db, GitHub(cfg))
    ejecutor.iniciar()
    app = crear_servidor(cfg, db, ejecutor).streamable_http_app(
        host=cfg.host, transport_security=transporte(cfg))
    try:
        # access_log=False: las URLs de OAuth llevan parámetros que no deben quedar en logs.
        uvicorn.run(app, host=cfg.host, port=cfg.port, access_log=False, proxy_headers=True,
                    forwarded_allow_ips="127.0.0.1")
    finally:
        ejecutor.detener()


if __name__ == "__main__":
    main()
