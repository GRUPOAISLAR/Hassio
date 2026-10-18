"""Lanzamiento de Claude Code y Codex en modo no interactivo.

Qué recibe el modelo:
  - El prompt armado por el ejecutor (descripción de la tarea + reglas de la fase).
  - El contenido de la copia de trabajo de la tarea (repo GRUPOAISLAR/Hassio).
  - Lo que devuelvan las herramientas MCP de Home Assistant de la casa de la tarea.
Qué puede hacer:
  - Fase "trabajo": leer/editar archivos dentro de la copia de trabajo y consultar HA solo con
    HA_TOOLS_LECTURA (token de lectura). Sin Bash en Claude; Codex con sandbox workspace-write
    (sin red para comandos) y sin variables con TOKEN/KEY/SECRET en su shell.
  - Fase "aplicar" (solo después de que el dueño mergea el PR): todas las herramientas MCP de HA
    de esa casa, con el token de escritura. Sin edición de archivos.
Límites:
  - No recibe tokens de GitHub ni de la otra casa; no hace push (lo hace el ejecutor).
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

from .config import HA_TOOLS_LECTURA, Config

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


def _ha_env(cfg: Config, casa: str, fase: str) -> dict[str, str]:
    C = casa.upper()
    url = cfg.secreto(f"HA_{C}_URL").rstrip("/")
    clave_token = f"HA_{C}_TOKEN_{'ESCRITURA' if fase == APLICAR else 'LECTURA'}"
    token = cfg.secreto(clave_token)
    if not url or not token:
        raise RuntimeError(f"Falta HA_{C}_URL o {clave_token} en el archivo env")
    return {f"HA_{C}_URL": url, f"HA_{C}_TOKEN": token}


def _comando_claude(cfg: Config, casa: str, fase: str, cuenta: str, sesion: str | None, prompt: str,
                    mcp_cfg: Path) -> tuple[list[str], dict[str, str]]:
    token = cfg.secreto(f"CLAUDE_TOKEN_{cuenta.upper()}")
    if not token:
        raise RuntimeError(f"Falta CLAUDE_TOKEN_{cuenta.upper()} en el archivo env")
    C = casa.upper()
    # Placeholders: Claude Code los expande desde el entorno; el archivo no tiene secretos.
    mcp_cfg.write_text(json.dumps({"mcpServers": {f"ha-{casa}": {
        "type": "http",
        "url": f"${{HA_{C}_URL}}/api/mcp",
        "headers": {"Authorization": f"Bearer ${{HA_{C}_TOKEN}}"},
    }}}))
    if fase == TRABAJO:
        herramientas = "Read,Edit,Write,Glob,Grep"
        permitidas = ["Read", "Edit", "Write", "Glob", "Grep",
                      *[f"mcp__ha-{casa}__{t}" for t in HA_TOOLS_LECTURA]]
    else:
        herramientas = "Read"
        permitidas = ["Read", f"mcp__ha-{casa}"]
    cmd = ["claude", "-p", prompt, "--output-format", "json", "--strict-mcp-config",
           "--mcp-config", str(mcp_cfg), "--tools", herramientas,
           "--permission-mode", "dontAsk", "--allowedTools", *permitidas]
    if sesion:
        cmd += ["--resume", sesion]
    env = {**_env_base(), **_ha_env(cfg, casa, fase),
           "CLAUDE_CONFIG_DIR": str(cfg.agentes_dir / f"claude-{cuenta}"),
           "CLAUDE_CODE_OAUTH_TOKEN": token}
    return cmd, env


def _comando_codex(cfg: Config, casa: str, fase: str, sesion: str | None, prompt: str) -> tuple[list[str], dict[str, str]]:
    C = casa.upper()
    ha = _ha_env(cfg, casa, fase)
    over = [
        "-c", 'approval_policy="never"',
        "-c", 'sandbox_mode="workspace-write"' if fase == TRABAJO else 'sandbox_mode="read-only"',
        "-c", 'shell_environment_policy.exclude=["HA_*","*TOKEN*","*KEY*","*SECRET*"]',
        "-c", f'mcp_servers.ha-{casa}.url="{ha[f"HA_{C}_URL"]}/api/mcp"',
        "-c", f'mcp_servers.ha-{casa}.bearer_token_env_var="HA_{C}_TOKEN"',
        # Sin aprobación interactiva en exec: lo que se habilita (enabled_tools) se aprueba solo.
        "-c", f'mcp_servers.ha-{casa}.default_tools_approval_mode="approve"',
    ]
    if fase == TRABAJO:
        tools = ",".join(f'"{t}"' for t in HA_TOOLS_LECTURA)
        over += ["-c", f"mcp_servers.ha-{casa}.enabled_tools=[{tools}]"]
    if sesion:
        cmd = ["codex", "exec", "resume", "--json", "--skip-git-repo-check", *over, sesion, prompt]
    else:
        cmd = ["codex", "exec", "--json", "--skip-git-repo-check", *over, prompt]
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
