"""OAuth 2.1 de un solo usuario para el conector MCP.

Flujo: el cliente (ChatGPT) se registra solo (DCR) → /authorize redirige a /consentimiento →
el dueño escribe su clave → se emite un código de un solo uso (PKCE lo valida el SDK) →
/token entrega access token (1 h) + refresh token (30 días, rotativo).

La clave del dueño se guarda como hash scrypt en DOMOTICA_CLAVE_HASH (archivo env).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import html
import json
import secrets
import time
import uuid

from mcp.server.auth.provider import (
    AccessToken,
    AuthorizationCode,
    AuthorizationParams,
    RefreshToken,
    construct_redirect_uri,
)
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken
from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse, Response

from .config import Config
from .db import DB

SCOPE = "domotica"
ACCESS_TTL_S = 3600
REFRESH_TTL_S = 30 * 24 * 3600
CODIGO_TTL_S = 300
PENDIENTE_TTL_S = 600
MAX_FALLOS = 5
BLOQUEO_S = 15 * 60
SUJETO = "dueno"


def _hash(valor: str) -> str:
    return hashlib.sha256(valor.encode()).hexdigest()


def hash_clave(clave: str) -> str:
    sal = secrets.token_bytes(16)
    h = hashlib.scrypt(clave.encode(), salt=sal, n=2**14, r=8, p=1, dklen=32)
    return "scrypt$" + base64.b64encode(sal).decode() + "$" + base64.b64encode(h).decode()


def verificar_clave(clave: str, guardado: str) -> bool:
    try:
        tipo, sal_b64, h_b64 = guardado.split("$")
    except ValueError:
        return False
    if tipo != "scrypt":
        return False
    h = hashlib.scrypt(clave.encode(), salt=base64.b64decode(sal_b64), n=2**14, r=8, p=1, dklen=32)
    return hmac.compare_digest(h, base64.b64decode(h_b64))


class Proveedor:
    """Implementa OAuthAuthorizationServerProvider del SDK de MCP sobre SQLite."""

    def __init__(self, db: DB, cfg: Config):
        self.db = db
        self.cfg = cfg
        self._fallos = 0
        self._bloqueado_hasta = 0.0

    # --- clientes -----------------------------------------------------------------------

    async def get_client(self, client_id: str) -> OAuthClientInformationFull | None:
        fila = self.db.uno("SELECT info_json FROM oauth_clientes WHERE client_id = ?", (client_id,))
        return OAuthClientInformationFull.model_validate_json(fila["info_json"]) if fila else None

    async def register_client(self, client_info: OAuthClientInformationFull) -> None:
        self.db.ejecutar(
            "INSERT OR REPLACE INTO oauth_clientes (client_id, info_json, creado) VALUES (?, ?, ?)",
            (client_info.client_id, client_info.model_dump_json(), time.time()),
        )

    # --- autorización -------------------------------------------------------------------

    async def authorize(self, client: OAuthClientInformationFull, params: AuthorizationParams) -> str:
        pendiente = secrets.token_urlsafe(24)
        self.db.ejecutar("DELETE FROM oauth_pendientes WHERE expira < ?", (time.time(),))
        self.db.ejecutar(
            "INSERT INTO oauth_pendientes (id, client_id, params_json, expira) VALUES (?, ?, ?, ?)",
            (pendiente, client.client_id, params.model_dump_json(), time.time() + PENDIENTE_TTL_S),
        )
        return f"{self.cfg.url_publica}/consentimiento?id={pendiente}"

    def _pendiente(self, pendiente: str) -> tuple[dict, AuthorizationParams] | None:
        fila = self.db.uno(
            "SELECT * FROM oauth_pendientes WHERE id = ? AND expira >= ?", (pendiente, time.time())
        )
        if not fila:
            return None
        return fila, AuthorizationParams.model_validate_json(fila["params_json"])

    async def pagina_consentimiento(self, request: Request) -> Response:
        if request.method == "GET":
            pendiente = request.query_params.get("id", "")
            datos = self._pendiente(pendiente)
            if not datos:
                return HTMLResponse(_pagina("Solicitud vencida o inválida. Volvé a conectar desde ChatGPT."), 400)
            fila, params = datos
            cliente = await self.get_client(fila["client_id"])
            nombre = (cliente.client_name if cliente else None) or fila["client_id"]
            return HTMLResponse(_formulario(pendiente, nombre, params.redirect_uri.host or ""))

        form = await request.form()
        pendiente = str(form.get("id", ""))
        datos = self._pendiente(pendiente)
        if not datos:
            return HTMLResponse(_pagina("Solicitud vencida o inválida. Volvé a conectar desde ChatGPT."), 400)
        fila, params = datos

        if form.get("accion") == "rechazar":
            self.db.ejecutar("DELETE FROM oauth_pendientes WHERE id = ?", (pendiente,))
            destino = construct_redirect_uri(str(params.redirect_uri), error="access_denied", state=params.state)
            return RedirectResponse(destino, status_code=302)

        if time.time() < self._bloqueado_hasta:
            return HTMLResponse(_pagina("Demasiados intentos fallidos. Probá en 15 minutos."), 429)
        guardado = self.cfg.secreto("DOMOTICA_CLAVE_HASH")
        if not guardado or not verificar_clave(str(form.get("clave", "")), guardado):
            self._fallos += 1
            if self._fallos >= MAX_FALLOS:
                self._fallos = 0
                self._bloqueado_hasta = time.time() + BLOQUEO_S
            return HTMLResponse(_formulario(pendiente, "", "", error="Clave incorrecta."), 401)
        self._fallos = 0

        self.db.ejecutar("DELETE FROM oauth_pendientes WHERE id = ?", (pendiente,))
        codigo = secrets.token_urlsafe(32)
        ac = AuthorizationCode(
            code=codigo,
            scopes=params.scopes or [SCOPE],
            expires_at=time.time() + CODIGO_TTL_S,
            client_id=fila["client_id"],
            code_challenge=params.code_challenge,
            redirect_uri=params.redirect_uri,
            redirect_uri_provided_explicitly=params.redirect_uri_provided_explicitly,
            resource=params.resource,
            subject=SUJETO,
        )
        self.db.ejecutar(
            "INSERT INTO oauth_codigos (code_hash, datos_json, expira) VALUES (?, ?, ?)",
            (_hash(codigo), ac.model_dump_json(exclude={"code"}), ac.expires_at),
        )
        destino = construct_redirect_uri(str(params.redirect_uri), code=codigo, state=params.state)
        return RedirectResponse(destino, status_code=302)

    async def load_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: str
    ) -> AuthorizationCode | None:
        fila = self.db.uno(
            "SELECT datos_json FROM oauth_codigos WHERE code_hash = ? AND expira >= ?",
            (_hash(authorization_code), time.time()),
        )
        if not fila:
            return None
        datos = json.loads(fila["datos_json"])
        if datos["client_id"] != client.client_id:
            return None
        return AuthorizationCode(code=authorization_code, **datos)

    async def exchange_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: AuthorizationCode
    ) -> OAuthToken:
        self.db.ejecutar("DELETE FROM oauth_codigos WHERE code_hash = ?", (_hash(authorization_code.code),))
        return self._emitir(client.client_id, authorization_code.scopes, authorization_code.resource)

    # --- tokens -------------------------------------------------------------------------

    def _emitir(self, client_id: str, scopes: list[str], resource: str | None) -> OAuthToken:
        grupo = uuid.uuid4().hex
        access, refresh = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        ahora = time.time()
        for token, tipo, ttl in ((access, "access", ACCESS_TTL_S), (refresh, "refresh", REFRESH_TTL_S)):
            self.db.ejecutar(
                "INSERT INTO oauth_tokens (token_hash, tipo, client_id, scopes, resource, expira, grupo)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (_hash(token), tipo, client_id, " ".join(scopes), resource, ahora + ttl, grupo),
            )
        self.db.ejecutar("DELETE FROM oauth_tokens WHERE expira < ?", (ahora,))
        return OAuthToken(
            access_token=access, expires_in=ACCESS_TTL_S, scope=" ".join(scopes), refresh_token=refresh
        )

    def _token(self, token: str, tipo: str) -> dict | None:
        return self.db.uno(
            "SELECT * FROM oauth_tokens WHERE token_hash = ? AND tipo = ? AND expira >= ?",
            (_hash(token), tipo, time.time()),
        )

    async def load_refresh_token(self, client: OAuthClientInformationFull, refresh_token: str) -> RefreshToken | None:
        fila = self._token(refresh_token, "refresh")
        if not fila or fila["client_id"] != client.client_id:
            return None
        return RefreshToken(
            token=refresh_token,
            client_id=fila["client_id"],
            scopes=fila["scopes"].split(),
            expires_at=int(fila["expira"]),
            resource=fila["resource"],
            subject=SUJETO,
        )

    async def exchange_refresh_token(
        self, client: OAuthClientInformationFull, refresh_token: RefreshToken, scopes: list[str]
    ) -> OAuthToken:
        # Rotación: el refresh usado y su access asociado dejan de valer.
        await self.revoke_token(refresh_token)
        return self._emitir(client.client_id, scopes or refresh_token.scopes, refresh_token.resource)

    async def load_access_token(self, token: str) -> AccessToken | None:
        fila = self._token(token, "access")
        if not fila:
            return None
        return AccessToken(
            token=token,
            client_id=fila["client_id"],
            scopes=fila["scopes"].split(),
            expires_at=int(fila["expira"]),
            resource=fila["resource"],
            subject=SUJETO,
        )

    async def revoke_token(self, token: AccessToken | RefreshToken) -> None:
        fila = self.db.uno("SELECT grupo FROM oauth_tokens WHERE token_hash = ?", (_hash(token.token),))
        if fila:
            self.db.ejecutar("DELETE FROM oauth_tokens WHERE grupo = ?", (fila["grupo"],))


# --- HTML mínimo --------------------------------------------------------------------------

_ESTILO = (
    "body{font-family:system-ui,sans-serif;max-width:420px;margin:48px auto;padding:0 16px}"
    "input,button{font-size:16px;padding:8px;margin:4px 0;width:100%;box-sizing:border-box}"
    ".err{color:#b00}"
)


def _pagina(cuerpo: str) -> str:
    return (
        "<!doctype html><html lang=es><meta charset=utf-8>"
        "<meta name=viewport content='width=device-width,initial-scale=1'>"
        f"<title>Domótica</title><style>{_ESTILO}</style><body><h1>Domótica</h1><p>{cuerpo}</p></body></html>"
    )


def _formulario(pendiente: str, cliente: str, destino: str, error: str = "") -> str:
    quien = f"<p><b>{html.escape(cliente)}</b> pide acceso a domotica-hub" + (
        f" (vuelve a {html.escape(destino)})." if destino else "."
    ) + "</p>" if cliente else ""
    err = f"<p class=err>{html.escape(error)}</p>" if error else ""
    return _pagina(
        f"</p>{quien}{err}<form method=post action=/consentimiento>"
        f"<input type=hidden name=id value='{html.escape(pendiente, quote=True)}'>"
        "<input type=password name=clave placeholder='Clave del dueño' autocomplete=current-password autofocus>"
        "<button name=accion value=aprobar>Autorizar</button>"
        "<button name=accion value=rechazar>Rechazar</button></form><p>"
    )
