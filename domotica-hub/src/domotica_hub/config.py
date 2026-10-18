"""Configuración de domotica-hub.

Los secretos viven en ~/.config/domotica/env (permisos 600) y se leen bajo demanda con
`secreto()`, así un token actualizado se usa sin reiniciar el servicio. Nunca se exportan
al entorno del proceso ni se registran en logs.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

CASAS = ("lote101", "costa204")
AGENTES = ("claude", "codex")
CUENTAS_CLAUDE = ("gmail", "bravosm")

# Herramientas MCP de Home Assistant permitidas en las fases de solo lectura.
HA_TOOLS_LECTURA = ("GetLiveContext", "GetDateTime")


def leer_env(path: Path) -> dict[str, str]:
    """Parsea un archivo KEY=VALUE. Ignora comentarios y líneas vacías; no interpreta comillas."""
    datos: dict[str, str] = {}
    if not path.exists():
        return datos
    for linea in path.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        clave, valor = linea.split("=", 1)
        datos[clave.strip()] = valor.strip()
    return datos


@dataclass(frozen=True)
class Config:
    env_file: Path
    base: Path
    agentes_dir: Path
    host: str = "127.0.0.1"
    port: int = 8770
    url_publica: str = "http://127.0.0.1:8770"
    repo_github: str = "GRUPOAISLAR/Hassio"
    timeout_tarea_s: int = 45 * 60
    intervalo_avance_s: int = 10 * 60
    intervalo_pr_s: int = 120

    @property
    def repo(self) -> Path:
        return self.base / "repo"

    @property
    def db_path(self) -> Path:
        return self.base / "datos" / "hub.sqlite3"

    @property
    def worktrees(self) -> Path:
        return self.base / "worktrees"

    @property
    def locks(self) -> Path:
        return self.base / "locks"

    @property
    def logs(self) -> Path:
        return self.base / "logs"

    @property
    def estado(self) -> Path:
        return self.base / "estado"

    def secreto(self, nombre: str) -> str:
        """Devuelve el valor de una clave del archivo env, o "" si no está."""
        return leer_env(self.env_file).get(nombre, "")

    def preparar_directorios(self) -> None:
        for d in (self.db_path.parent, self.worktrees, self.locks, self.logs, self.estado):
            d.mkdir(parents=True, exist_ok=True)
            os.chmod(d, 0o700)

    @classmethod
    def cargar(cls) -> "Config":
        home = Path.home()
        env_file = Path(os.environ.get("DOMOTICA_ENV", home / ".config/domotica/env"))
        env = leer_env(env_file)
        port = int(env.get("DOMOTICA_PORT") or 8770)
        return cls(
            env_file=env_file,
            base=Path(os.environ.get("DOMOTICA_BASE", home / "domotica")),
            agentes_dir=Path(os.environ.get("DOMOTICA_AGENTES", home / ".config/domotica/agentes")),
            port=port,
            url_publica=(env.get("DOMOTICA_URL_PUBLICA") or f"http://127.0.0.1:{port}").rstrip("/"),
            timeout_tarea_s=int(env.get("DOMOTICA_TIMEOUT_TAREA_MIN") or 45) * 60,
        )
