from __future__ import annotations

import json
import sys
import threading
import time
from pathlib import Path

import pytest

from domotica_hub import agentes
from domotica_hub.agentes import APLICAR, TRABAJO, _comando_claude, _comando_codex, _parsear_codex


def test_claude_trabajo_control_directo_y_config_solo_lectura(entorno, tmp_path: Path):
    cfg = entorno["cfg"]
    cmd, env = _comando_claude(cfg, "lote101", TRABAJO, "gmail", None, "hola", tmp_path / "mcp.json")
    permitidas = cmd[cmd.index("--allowedTools") + 1:]
    assert "mcp__ha-lote101" in permitidas                        # control directo (Assist)
    assert "mcp__hacfg-lote101__ha_get_state" in permitidas
    assert "mcp__hacfg-lote101" not in permitidas                 # nunca el servidor de config entero
    assert not any(p.startswith("mcp__hacfg-lote101__ha_config_set") or "ha_restart" in p
                   or "ha_report_issue" in p for p in permitidas)
    assert "Bash" not in cmd[cmd.index("--tools") + 1]
    cfg_mcp = (tmp_path / "mcp.json").read_text()
    assert "ficticio" not in cfg_mcp                              # solo placeholders
    srv = json.loads(cfg_mcp)["mcpServers"]["hacfg-lote101"]
    assert srv["env"]["READ_ONLY_MODE"] == "true" and srv["env"]["ENABLE_YAML_CONFIG_EDITING"] == "false"
    assert env["HA_TOKEN"] == "ficticio-agente" and env["HOMEASSISTANT_TOKEN"] == "ficticio-admin"
    assert "GH_TOKEN" not in env and "GH_TOKEN_HASSIO" not in env


def test_claude_aplicar_habilita_config(entorno, tmp_path: Path):
    cmd, _ = _comando_claude(entorno["cfg"], "lote101", APLICAR, "gmail", "s1", "x", tmp_path / "mcp.json")
    assert "mcp__hacfg-lote101" in cmd and cmd[cmd.index("--resume") + 1] == "s1"
    srv = json.loads((tmp_path / "mcp.json").read_text())["mcpServers"]["hacfg-lote101"]
    assert srv["env"]["READ_ONLY_MODE"] == "false" and srv["env"]["ENABLE_YAML_CONFIG_EDITING"] == "true"


def test_codex_trabajo_limita_config_y_no_expone_tokens(entorno):
    cmd, env = _comando_codex(entorno["cfg"], "lote101", TRABAJO, None, "x")
    linea = " ".join(cmd)
    assert "ficticio" not in linea                                # tokens solo por entorno
    assert env["HOMEASSISTANT_TOKEN"] == "ficticio-admin"
    habil = next(c for c in cmd if c.startswith("mcp_servers.hacfg-lote101.enabled_tools="))
    assert "ha_get_state" in habil and "ha_config_set" not in habil and "ha_restart" not in habil
    assert any(c.startswith("mcp_servers.hacfg-lote101.env=") and 'READ_ONLY_MODE="true"' in c for c in cmd)
    assert not any(c.startswith("mcp_servers.ha-lote101.enabled_tools") for c in cmd)  # Assist completo
    assert 'sandbox_mode="workspace-write"' in cmd and "HOMEASSISTANT_*" in linea
    cmd, _ = _comando_codex(entorno["cfg"], "lote101", APLICAR, "abc", "x")
    assert cmd[:3] == ["codex", "exec", "resume"]
    assert not any("enabled_tools" in c for c in cmd) and any('READ_ONLY_MODE="false"' in c for c in cmd)


def test_falta_casa_configurada(entorno, tmp_path: Path):
    with pytest.raises(RuntimeError, match="HA_COSTA204_TOKEN_ADMIN"):
        _comando_claude(entorno["cfg"], "costa204", TRABAJO, "gmail", None, "x", tmp_path / "m.json")


def test_parsear_codex():
    salida = "\n".join(json.dumps(e) for e in [
        {"type": "thread.started", "thread_id": "t-1"},
        {"type": "item.completed", "item": {"type": "agent_message", "text": "listo"}},
        {"type": "turn.completed"},
    ])
    r = _parsear_codex(salida)
    assert r.ok and r.sesion_id == "t-1" and r.texto == "listo"


def _correr(entorno, tmp_path, script: str, cancelar=None):
    return agentes.ejecutar(
        entorno["cfg"], agente="claude", casa="lote101", fase=TRABAJO, cuenta="gmail", sesion=None,
        prompt="x", cwd=tmp_path, log_path=tmp_path / "log", cancelar=cancelar or threading.Event(),
        comando_override=[sys.executable, "-c", script])


def test_ejecutar_parsea_salida_y_registra_log(entorno, tmp_path: Path):
    r = _correr(entorno, tmp_path, 'import json;print(json.dumps({"result":"ok","session_id":"s9","is_error":False}))')
    assert r.ok and r.sesion_id == "s9" and r.texto == "ok"
    assert (tmp_path / "log").stat().st_mode & 0o777 == 0o600


def test_ejecutar_cancela(entorno, tmp_path: Path):
    ev = threading.Event()
    threading.Timer(0.5, ev.set).start()
    t0 = time.time()
    with pytest.raises(agentes.Cancelada):
        _correr(entorno, tmp_path, "import time; time.sleep(60)", cancelar=ev)
    assert time.time() - t0 < 20
