"""Lanzamiento de Claude Code y Codex en modo no interactivo.

Qué recibe el modelo:
  - El prompt armado por el ejecutor (descripción de la tarea + reglas de la fase).
  - El contenido de la copia de trabajo de la tarea (repo GRUPOAISLAR/Hassio).
  - Lo que devuelvan las herramientas MCP de Home Assistant de la casa de la tarea.
Qué puede hacer (aprobación mixta):
  - Fase "trabajo" (sin aprobación previa):
      · ha-<casa>: estado y CONTROL DIRECTO de las entidades expuestas a Assist (token agente).
      · hacfg-<casa>: lectura de toda la configuración con ha-mcp en READ_ONLY_MODE y solo las
        herramientas de HAMCP_TOOLS_LECTURA (token admin). Cambios de configuración → plan + PR.
      · Leer/editar archivos de la copia de trabajo. Sin Bash en Claude; Codex con sandbox
        workspace-write y un shell que no ve variables HA_*, HOMEASSISTANT_*, *TOKEN*, *KEY*, *SECRET*.
  - Fase "aplicar" (solo después de que el dueño mergea el PR): ha-mcp sin restricciones
    (incluye edición de YAML) + Assist. Sin edición de archivos.
Límites:
  - No recibe tokens de GitHub ni de la otra casa; no hace push (lo hace el ejecutor).
  - Los tokens viajan por entorno, nunca en la línea de comandos ni en archivos.
  - Tiempo máximo por corrida: Config.timeout_tarea_s.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import tempfile
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from .config import HAMCP_TOOLS_LECTURA, Config

TRABAJO = "trabajo"
APLICAR = "aplicar"


@dataclass
class Resultado:
    ok: bool
    sesion_id: str | None
    texto: str
    error: str = ""
    limite_uso: bool = False
    extra: dict = field(default_factory=dict)


class Cancelada(Exception):
    pass


def _env_base() -> dict[str, str]:
    return {
        "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
        "HOME": str(Path.home()),
        "LANG": "C.UTF-8",
        "TERM": "dumb",
    }


def _ha_env(cfg: Config, casa: str) -> dict[str, str]:
    """URL y tokens de la casa. HA_TOKEN: usuario agente (Assist). HOMEASSISTANT_*: ha-mcp (admin)."""
    C = casa.upper()
    claves = (f"HA_{C}_URL", f"HA_{C}_TOKEN_AGENTE", f"HA_{C}_TOKEN_ADMIN")
    url, agente, admin = (cfg.secreto(k) for k in claves)
    faltan = [k for k, v in zip(claves, (url, agente, admin)) if not v]
    if faltan:
        raise RuntimeError(f"Falta {', '.join(faltan)} en el archivo env")
    url = url.rstrip("/")
    return {"HA_URL": url, "HA_TOKEN": agente, "HOMEASSISTANT_URL": url, "HOMEASSISTANT_TOKEN": admin}


def _hamcp_opciones(fase: str) -> dict[str, str]:
    """Opciones no secretas de ha-mcp según la fase."""
    trabajo = fase == TRABAJO
    return {
        "READ_ONLY_MODE": "true" if trabajo else "false",
        "ENABLE_YAML_CONFIG_EDITING": "false" if trabajo else "true",
        "HA_MCP_DISABLE_SETTINGS_UI": "true",
        "LOG_LEVEL": "WARNING",
    }


def _comando_claude(cfg: Config, casa: str, fase: str, cuenta: str, sesion: str | None, prompt: str,
                    mcp_cfg: Path) -> tuple[list[str], dict[str, str]]:
    token = cfg.secreto(f"CLAUDE_TOKEN_{cuenta.upper()}")
    if not token:
        raise RuntimeError(f"Falta CLAUDE_TOKEN_{cuenta.upper()} en el archivo env")
    # Placeholders ${VAR}: Claude Code los expande desde su entorno; el archivo no tiene secretos.
    mcp_cfg.write_text(json.dumps({"mcpServers": {
        f"ha-{casa}": {
            "type": "http",
            "url": "${HA_URL}/api/mcp",
            "headers": {"Authorization": "Bearer ${HA_TOKEN}"},
        },
        f"hacfg-{casa}": {
            "type": "stdio",
            "command": str(cfg.hamcp_bin),
            "args": [],
            "env": {"HOMEASSISTANT_URL": "${HOMEASSISTANT_URL}", "HOMEASSISTANT_TOKEN": "${HOMEASSISTANT_TOKEN}",
                    **_hamcp_opciones(fase)},
        },
    }}))
    if fase == TRABAJO:
        herramientas = "Read,Edit,Write,Glob,Grep"
        permitidas = ["Read", "Edit", "Write", "Glob", "Grep", f"mcp__ha-{casa}",
                      *[f"mcp__hacfg-{casa}__{t}" for t in HAMCP_TOOLS_LECTURA]]
    else:
        herramientas = "Read"
        permitidas = ["Read", f"mcp__ha-{casa}", f"mcp__hacfg-{casa}"]
    cmd = ["claude", "-p", prompt, "--output-format", "json", "--strict-mcp-config",
           "--mcp-config", str(mcp_cfg), "--tools", herramientas,
           "--permission-mode", "dontAsk", "--allowedTools", *permitidas]
    if sesion:
        cmd += ["--resume", sesion]
    env = {**_env_base(), **_ha_env(cfg, casa),
           "CLAUDE_CONFIG_DIR": str(cfg.agentes_dir / f"claude-{cuenta}"),
           "CLAUDE_CODE_OAUTH_TOKEN": token}
    return cmd, env


def _toml_lista(valores) -> str:
    return "[" + ",".join(json.dumps(v) for v in valores) + "]"


def _comando_codex(cfg: Config, casa: str, fase: str, sesion: str | None, prompt: str) -> tuple[list[str], dict[str, str]]:
    ha = _ha_env(cfg, casa)
    opciones = "{" + ",".join(f"{k}={json.dumps(v)}" for k, v in _hamcp_opciones(fase).items()) + "}"
    a, c = f"mcp_servers.ha-{casa}", f"mcp_servers.hacfg-{casa}"
    over = [
        # Sin conectores de la cuenta de ChatGPT (codex_apps): esquivarían estos permisos.
        "-c", "features.apps=false",
        "-c", 'approval_policy="never"',
        "-c", 'sandbox_mode="workspace-write"' if fase == TRABAJO else 'sandbox_mode="read-only"',
        "-c", 'shell_environment_policy.exclude=["HA_*","HOMEASSISTANT_*","*TOKEN*","*KEY*","*SECRET*"]',
        # Assist (HTTP): el token se lee de HA_TOKEN en el entorno.
        "-c", f'{a}.url="{ha["HA_URL"]}/api/mcp"',
        "-c", f'{a}.bearer_token_env_var="HA_TOKEN"',
        "-c", f'{a}.default_tools_approval_mode="approve"',
        # ha-mcp (stdio): URL y token se reenvían desde el entorno (env_vars), no van en la línea.
        "-c", f'{c}.command="{cfg.hamcp_bin}"',
        "-c", f'{c}.env_vars={_toml_lista(["HOMEASSISTANT_URL", "HOMEASSISTANT_TOKEN"])}',
        "-c", f"{c}.env={opciones}",
        "-c", f"{c}.startup_timeout_sec=60",
        # "approve" = aprobado de antemano (en exec no hay a quién preguntar); el límite real es
        # enabled_tools + READ_ONLY_MODE. Requiere Codex >= 0.163 (en 0.159 se colgaba).
        "-c", f'{c}.default_tools_approval_mode="approve"',
    ]
    if fase == TRABAJO:
        over += ["-c", f"{c}.enabled_tools={_toml_lista(HAMCP_TOOLS_LECTURA)}"]
    if sesion:
        cmd = [str(cfg.codex_bin), "exec", "resume", "--json", "--skip-git-repo-check", *over, sesion, prompt]
    else:
        cmd = [str(cfg.codex_bin), "exec", "--json", "--skip-git-repo-check", *over, prompt]
    env = {**_env_base(), **ha, "CODEX_HOME": str(cfg.agentes_dir / "codex-gmail")}
    return cmd, env


def _parsear_claude(salida: str) -> Resultado:
    try:
        d = json.loads(salida.strip().splitlines()[-1])
    except (json.JSONDecodeError, IndexError):
        return Resultado(False, None, "", error=f"salida no JSON de claude: {salida[-300:]}")
    texto = str(d.get("result") or "")
    limite = d.get("api_error_status") == 429 or (bool(d.get("is_error")) and "limit" in texto.lower())
    return Resultado(not d.get("is_error"), d.get("session_id"), texto,
                     error=texto if d.get("is_error") else "", limite_uso=bool(limite),
                     extra={"denegadas": d.get("permission_denials") or []})


def _parsear_codex(salida: str) -> Resultado:
    sesion, textos, error = None, [], ""
    for linea in salida.splitlines():
        try:
            e = json.loads(linea)
        except json.JSONDecodeError:
            continue
        tipo = e.get("type")
        if tipo == "thread.started":
            sesion = e.get("thread_id")
        elif tipo == "item.completed" and (e.get("item") or {}).get("type") == "agent_message":
            textos.append(e["item"].get("text", ""))
        elif tipo in ("error", "turn.failed"):
            error = json.dumps(e.get("error") or e.get("message") or e)[:500]
    limite = "limit" in error.lower() or "429" in error
    return Resultado(not error and bool(textos), sesion, textos[-1] if textos else "", error=error, limite_uso=limite)


def ejecutar(
    cfg: Config,
    *,
    agente: str,
    casa: str,
    fase: str,
    cuenta: str | None,
    sesion: str | None,
    prompt: str,
    cwd: Path,
    log_path: Path,
    cancelar: threading.Event,
    avance: Callable[[float], None] | None = None,
    comando_override: list[str] | None = None,
) -> Resultado:
    """Corre el agente y devuelve su resultado. Lanza Cancelada si se pidió cancelar."""
    with tempfile.TemporaryDirectory(prefix="domotica-") as tmp:
        if agente == "claude":
            cmd, env = _comando_claude(cfg, casa, fase, cuenta or "gmail", sesion, prompt, Path(tmp) / "mcp.json")
        else:
            cmd, env = _comando_codex(cfg, casa, fase, sesion, prompt)
        if comando_override is not None:  # pruebas
            cmd = comando_override

        inicio = time.time()
        ultimo_aviso = inicio
        with open(log_path, "a", encoding="utf-8") as log:
            os.chmod(log_path, 0o600)
            log.write(f"\n=== {time.strftime('%F %T')} {agente} fase={fase} sesion={sesion or 'nueva'} ===\n")
            log.flush()
            salida_path = Path(tmp) / "salida"
            with open(salida_path, "w+", encoding="utf-8") as salida:
                proc = subprocess.Popen(cmd, cwd=cwd, env=env, stdout=salida, stderr=log,
                                        stdin=subprocess.DEVNULL, start_new_session=True, text=True)
                try:
                    while True:
                        try:
                            proc.wait(timeout=5)
                            break
                        except subprocess.TimeoutExpired:
                            pass
                        ahora = time.time()
                        if cancelar.is_set():
                            _matar(proc)
                            raise Cancelada()
                        if ahora - inicio > cfg.timeout_tarea_s:
                            _matar(proc)
                            return Resultado(False, sesion, "", error=f"tiempo agotado ({cfg.timeout_tarea_s // 60} min)")
                        if avance and ahora - ultimo_aviso >= cfg.intervalo_avance_s:
                            ultimo_aviso = ahora
                            avance(ahora - inicio)
                finally:
                    if proc.poll() is None:
                        _matar(proc)
                salida.seek(0)
                texto = salida.read()
            log.write(texto)
            log.write(f"\n=== fin código={proc.returncode} duración={time.time() - inicio:.0f}s ===\n")

    r = _parsear_claude(texto) if agente == "claude" else _parsear_codex(texto)
    if proc.returncode != 0 and r.ok:
        r.ok, r.error = False, f"código de salida {proc.returncode}"
    if not r.sesion_id:
        r.sesion_id = sesion
    return r


def _matar(proc: subprocess.Popen) -> None:
    try:
        os.killpg(proc.pid, signal.SIGTERM)
        proc.wait(timeout=15)
    except (ProcessLookupError, subprocess.TimeoutExpired):
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
