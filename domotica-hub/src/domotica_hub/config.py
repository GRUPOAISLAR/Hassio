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

# Servidores MCP por casa:
#   ha-<casa>     MCP oficial de HA (API Assist) con el token de `domotica-agente` (no admin):
#                 estado y control directo de las entidades expuestas a Assist.
#   hacfg-<casa>  ha-mcp (HAMCP_VERSION) con el token de `domotica-admin`: configuración completa.
#                 En la fase de trabajo corre con READ_ONLY_MODE y además solo se habilitan estas
#                 herramientas (lista explícita, no se confía en anotaciones). ha_report_issue queda
#                 afuera porque arma reportes para un servicio externo.
HAMCP_VERSION = "8.6.0"
HAMCP_TOOLS_LECTURA = (
    "ha_config_get_automation", "ha_config_get_calendar_events", "ha_config_get_category",
    "ha_config_get_dashboard", "ha_config_get_label", "ha_config_get_scene", "ha_config_get_script",
    "ha_config_list_dashboard_resources", "ha_config_list_groups", "ha_config_list_helpers",
    "ha_eval_template", "ha_get_app", "ha_get_automation_traces", "ha_get_camera_image", "ha_get_device",
    "ha_get_entity", "ha_get_entity_exposure", "ha_get_hacs_info", "ha_get_history", "ha_get_integration",
    "ha_get_logs", "ha_get_operation_status", "ha_get_overview", "ha_get_skill_guide", "ha_get_state",
    "ha_get_system_health", "ha_get_todo", "ha_get_zone", "ha_list_floors_areas", "ha_list_services",
    # Mixtas: en READ_ONLY_MODE ha-mcp permite sus lecturas y bloquea sus escrituras al llamarlas.
    "ha_manage_app", "ha_manage_backup", "ha_manage_blueprints", "ha_manage_energy_prefs",
    "ha_manage_pipeline", "ha_manage_radio", "ha_manage_theme", "ha_manage_updates",
    "ha_search",
)


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
    def codex_bin(self) -> Path:
        """Codex propio de domótica (npm local, versión fija); no se usa el global del VPS."""
        return self.base / "codex" / "node_modules" / ".bin" / "codex"

    @property
    def hamcp_bin(self) -> Path:
        return self.base / "venv-hamcp" / "bin" / "ha-mcp"

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
