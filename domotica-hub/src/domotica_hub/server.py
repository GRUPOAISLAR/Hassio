"""Servidor MCP de domotica-hub (streamable HTTP, OAuth 2.1, solo 127.0.0.1)."""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlparse

from mcp.server.auth.settings import AuthSettings, ClientRegistrationOptions, RevocationOptions
from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from . import db as D
from .auth import SCOPE, Proveedor
from .config import AGENTES, CASAS, CUENTAS_CLAUDE, Config
from .db import DB
from .ejecutor import Ejecutor

log = logging.getLogger("domotica_hub")

INSTRUCCIONES = """Cola de tareas para los agentes de domótica (Claude Code y Codex) sobre las casas
lote101 y costa204 (Home Assistant). Cada tarea queda registrada en GitHub con issue, rama y PR.
Los agentes trabajan en solo lectura; los cambios en Home Assistant se aplican recién cuando el
dueño mergea el PR con el plan. Usá estado(id) y resultado(id) para seguir una tarea."""

LECTURA = ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False)


def _resumen(t: dict[str, Any], repo: str) -> dict[str, Any]:
    return {
        "id": t["id"],
        "casa": t["casa"],
        "agente": t["agente"],
        "cuenta": t["cuenta"],
        "estado": t["estado"],
        "descripcion": t["descripcion"][:200],
        "continuar_de": t["continuar_de"],
        "issue": f"https://github.com/{repo}/issues/{t['issue']}" if t["issue"] else None,
        "pr": f"https://github.com/{repo}/pull/{t['pr']}" if t["pr"] else None,
        "rama": t["rama"],
        "requiere_aplicar": bool(t["requiere_aplicar"]),
        "error": t["error"],
    }


def crear_servidor(cfg: Config, db: DB, ejecutor: Ejecutor) -> MCPServer:
    proveedor = Proveedor(db, cfg)
    servidor = MCPServer(
        name="domotica-hub",
        instructions=INSTRUCCIONES,
        version="0.1.0",
        auth_server_provider=proveedor,
        auth=AuthSettings(
            issuer_url=cfg.url_publica,
            resource_server_url=f"{cfg.url_publica}/mcp",
            client_registration_options=ClientRegistrationOptions(
                enabled=True, valid_scopes=[SCOPE], default_scopes=[SCOPE]
            ),
            revocation_options=RevocationOptions(enabled=True),
            required_scopes=[SCOPE],
            validate_token_resource=False,
        ),
    )

    @servidor.custom_route("/consentimiento", methods=["GET", "POST"])
    async def consentimiento(request: Request) -> Response:
        r = await proveedor.pagina_consentimiento(request)
        r.headers["X-Frame-Options"] = "DENY"
        r.headers["Content-Security-Policy"] = "default-src 'none'; style-src 'unsafe-inline'; form-action 'self' https:"
        r.headers["Cache-Control"] = "no-store"
        return r

    @servidor.custom_route("/salud", methods=["GET"])
    async def salud(_: Request) -> Response:
        s = ejecutor.salud()
        return JSONResponse({"ok": s["ok"]}, status_code=200 if s["ok"] else 503)

    @servidor.tool(description="Crea una tarea para un agente. casa: lote101|costa204. agente: claude|codex. "
                               "cuenta (opcional, solo claude): gmail|bravosm. continuar_de (opcional): id de una "
                               "tarea anterior cuya sesión, rama y PR se reutilizan.")
    def crear_tarea(casa: str, agente: str, descripcion: str, cuenta: str | None = None,
                    continuar_de: int | None = None) -> dict[str, Any]:
        casa, agente = casa.strip().lower(), agente.strip().lower()
        if casa not in CASAS:
            raise ValueError(f"casa inválida; opciones: {', '.join(CASAS)}")
        if agente not in AGENTES:
            raise ValueError(f"agente inválido; opciones: {', '.join(AGENTES)}")
        descripcion = descripcion.strip()
        if not 10 <= len(descripcion) <= 4000:
            raise ValueError("la descripción debe tener entre 10 y 4000 caracteres")
        if agente == "codex":
            if cuenta not in (None, "", "gmail"):
                raise ValueError("codex solo tiene la cuenta gmail")
            cuenta, explicita = "gmail", False
        else:
            explicita = bool(cuenta)
            cuenta = (cuenta or cfg.secreto("CLAUDE_CUENTA_DEFAULT") or "gmail").strip().lower()
            if cuenta not in CUENTAS_CLAUDE:
                raise ValueError(f"cuenta inválida; opciones: {', '.join(CUENTAS_CLAUDE)}")
        if continuar_de is not None:
            p = db.tarea(continuar_de)
            if not p:
                raise ValueError(f"no existe la tarea #{continuar_de}")
            if (p["casa"], p["agente"]) != (casa, agente):
                raise ValueError("para continuar, casa y agente deben ser los de la tarea original")
            if p["estado"] not in (D.TERMINADA, D.ESPERANDO_APROBACION, D.ERROR, D.INTERRUMPIDA) or not p["sesion_id"]:
                raise ValueError(f"la tarea #{continuar_de} no se puede continuar (estado {p['estado']})")
        tid = db.crear_tarea(casa, agente, descripcion, cuenta, explicita, continuar_de)
        ejecutor.despertar()
        en_cola = db.uno("SELECT COUNT(*) n FROM tareas WHERE estado = ? AND id < ?", (D.EN_COLA, tid))["n"]
        return {"id": tid, "estado": D.EN_COLA, "tareas_antes": en_cola,
                "mensaje": "Tarea en cola. Consultá estado(id) para seguirla."}

    @servidor.tool(description="Lista las tareas más recientes, opcionalmente filtradas por estado.",
                   annotations=LECTURA)
    def listar_tareas(estado: str | None = None, limite: int = 20) -> list[dict[str, Any]]:
        limite = max(1, min(limite, 100))
        if estado:
            filas = db.todos("SELECT * FROM tareas WHERE estado = ? ORDER BY id DESC LIMIT ?", (estado, limite))
        else:
            filas = db.todos("SELECT * FROM tareas ORDER BY id DESC LIMIT ?", (limite,))
        return [_resumen(t, cfg.repo_github) for t in filas]

    @servidor.tool(description="Estado de una tarea y sus últimos eventos.", annotations=LECTURA)
    def estado(id: int) -> dict[str, Any]:
        t = db.tarea(id)
        if not t:
            raise ValueError(f"no existe la tarea #{id}")
        eventos = db.eventos(id)[-15:]
        return {**_resumen(t, cfg.repo_github),
                "eventos": [{"tipo": e["tipo"], "detalle": e["detalle"]} for e in eventos]}

    @servidor.tool(description="Resultado (resumen del agente) de una tarea terminada.", annotations=LECTURA)
    def resultado(id: int) -> dict[str, Any]:
        t = db.tarea(id)
        if not t:
            raise ValueError(f"no existe la tarea #{id}")
        return {"id": id, "estado": t["estado"], "resultado": t["resultado"], "error": t["error"],
                "pr": _resumen(t, cfg.repo_github)["pr"]}

    @servidor.tool(description="Cancela una tarea en cola, en curso o esperando aprobación.",
                   annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, openWorldHint=False))
    def cancelar(id: int) -> dict[str, Any]:
        return {"id": id, "resultado": ejecutor.cancelar(id)}

    return servidor


def transporte(cfg: Config) -> TransportSecuritySettings:
    host_publico = urlparse(cfg.url_publica).netloc
    hosts = ["127.0.0.1:*", "localhost:*"] + ([host_publico] if host_publico else [])
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=hosts,
        allowed_origins=["https://chatgpt.com", "https://chat.openai.com", f"{cfg.url_publica}"],
    )
