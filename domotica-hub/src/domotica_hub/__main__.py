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


def main() -> None:
    cfg = Config.cargar()
    if sys.argv[1:] == ["clave"]:
        guardar_clave(cfg)
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
