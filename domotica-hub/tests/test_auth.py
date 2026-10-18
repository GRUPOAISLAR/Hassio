from __future__ import annotations

import base64
import hashlib
import secrets
from urllib.parse import parse_qs, urlparse

import pytest
from starlette.testclient import TestClient

from domotica_hub.auth import hash_clave, verificar_clave
from domotica_hub.ejecutor import Ejecutor
from domotica_hub.server import crear_servidor, transporte

CLAVE = "clave-de-prueba-larga"
REDIRECT = "https://chatgpt.com/connector_platform_oauth_redirect"
MCP_HEADERS = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}
INIT = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                   "clientInfo": {"name": "prueba", "version": "0"}}}


@pytest.fixture
def cliente(entorno):
    cfg = entorno["cfg"]
    with open(cfg.env_file, "a") as f:
        f.write(f"DOMOTICA_CLAVE_HASH={hash_clave(CLAVE)}\n")
    ej = Ejecutor(cfg, entorno["db"], entorno["gh"])
    app = crear_servidor(cfg, entorno["db"], ej).streamable_http_app(transport_security=transporte(cfg))
    with TestClient(app, base_url="http://127.0.0.1:8770", follow_redirects=False) as c:
        yield c


def _autorizar(c: TestClient, clave: str = CLAVE):
    reg = c.post("/register", json={"redirect_uris": [REDIRECT], "client_name": "ChatGPT",
                                    "token_endpoint_auth_method": "client_secret_post",
                                    "grant_types": ["authorization_code", "refresh_token"],
                                    "response_types": ["code"], "scope": "domotica"})
    assert reg.status_code == 201, reg.text
    cli = reg.json()
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    r = c.get("/authorize", params={"response_type": "code", "client_id": cli["client_id"], "redirect_uri": REDIRECT,
                                    "code_challenge": challenge, "code_challenge_method": "S256",
                                    "state": "xyz", "scope": "domotica"})
    assert r.status_code == 302, r.text
    consent = urlparse(r.headers["location"])
    assert consent.path == "/consentimiento"
    pendiente = parse_qs(consent.query)["id"][0]
    assert c.get(f"/consentimiento?id={pendiente}").status_code == 200
    r = c.post("/consentimiento", data={"id": pendiente, "clave": clave, "accion": "aprobar"})
    return cli, verifier, r


def test_flujo_oauth_completo_y_acceso_mcp(cliente):
    c = cliente
    assert c.post("/mcp", json=INIT, headers=MCP_HEADERS).status_code == 401

    cli, verifier, r = _autorizar(c)
    assert r.status_code == 302 and r.headers["X-Frame-Options"] == "DENY"
    destino = urlparse(r.headers["location"])
    qs = parse_qs(destino.query)
    assert destino.netloc == "chatgpt.com" and qs["state"] == ["xyz"]

    tok = c.post("/token", data={"grant_type": "authorization_code", "code": qs["code"][0], "redirect_uri": REDIRECT,
                                 "client_id": cli["client_id"], "client_secret": cli["client_secret"],
                                 "code_verifier": verifier})
    assert tok.status_code == 200, tok.text
    t = tok.json()
    # El código es de un solo uso.
    again = c.post("/token", data={"grant_type": "authorization_code", "code": qs["code"][0], "redirect_uri": REDIRECT,
                                   "client_id": cli["client_id"], "client_secret": cli["client_secret"],
                                   "code_verifier": verifier})
    assert again.status_code == 400

    r = c.post("/mcp", json=INIT, headers={**MCP_HEADERS, "Authorization": f"Bearer {t['access_token']}"})
    assert r.status_code == 200 and "domotica-hub" in r.text

    # Refresh con rotación: el access anterior deja de valer.
    nuevo = c.post("/token", data={"grant_type": "refresh_token", "refresh_token": t["refresh_token"],
                                   "client_id": cli["client_id"], "client_secret": cli["client_secret"]})
    assert nuevo.status_code == 200, nuevo.text
    viejo = c.post("/mcp", json=INIT, headers={**MCP_HEADERS, "Authorization": f"Bearer {t['access_token']}"})
    assert viejo.status_code == 401


def test_clave_incorrecta_no_emite_codigo(cliente):
    _, _, r = _autorizar(cliente, clave="otra-clave-cualquiera")
    assert r.status_code == 401 and "location" not in r.headers


def _token(c: TestClient) -> str:
    cli, verifier, r = _autorizar(c)
    code = parse_qs(urlparse(r.headers["location"]).query)["code"][0]
    return c.post("/token", data={"grant_type": "authorization_code", "code": code, "redirect_uri": REDIRECT,
                                  "client_id": cli["client_id"], "client_secret": cli["client_secret"],
                                  "code_verifier": verifier}).json()["access_token"]


def test_host_no_permitido_rechazado(cliente):
    token = _token(cliente)
    auth = {**MCP_HEADERS, "Authorization": f"Bearer {token}"}
    r = cliente.post("/mcp", json=INIT, headers={**auth, "Host": "atacante.example"})
    assert r.status_code == 421, r.status_code
    r = cliente.post("/mcp", json=INIT, headers={**auth, "Origin": "https://atacante.example"})
    assert r.status_code == 403, r.status_code


def test_hash_de_clave():
    h = hash_clave(CLAVE)
    assert verificar_clave(CLAVE, h) and not verificar_clave("x", h) and CLAVE not in h
