# domotica-hub

Servicio MCP que recibe tareas (por ejemplo desde ChatGPT en modo desarrollador) y las ejecuta
con **Claude Code** o **Codex CLI** sobre las casas **lote101** y **costa204** (Home Assistant).
Este repositorio es el registro común: cada tarea deja issue, rama, PR y comentarios de avance.

## Herramientas MCP

| Herramienta | Qué hace |
|---|---|
| `crear_tarea(casa, agente, descripcion, cuenta?, continuar_de?)` | Encola una tarea. `cuenta` solo para claude (`gmail` por defecto, `bravosm` de respaldo). `continuar_de` reanuda la sesión, rama y PR de una tarea anterior. |
| `listar_tareas(estado?, limite?)` | Últimas tareas. |
| `estado(id)` | Estado, enlaces a issue/PR y últimos eventos. |
| `resultado(id)` | Resumen final del agente. |
| `cancelar(id)` | Cancela en cola, en curso o esperando aprobación. |

## Ciclo de una tarea

```
en_cola → en_curso → (PR) ─┬─ sin plan_aplicar.md ─────────────→ terminada
                           └─ con plan_aplicar.md → esperando_aprobacion
                                 ├─ dueño mergea el PR → aplicando → terminada
                                 └─ PR cerrado sin merge ─────────→ cancelada
```

- Una tarea por vez. Bloqueos `flock` por casa (`locks/casa-<casa>.lock`) y por sesión.
- Cada tarea trabaja en su propia copia (`git worktree`) en `~/domotica/worktrees/<id>`, rama
  `claude/<id>` o `codex/<id>`. Informe en `tareas/<id>/informe-<id>.md`.
- Al arrancar el servicio, lo que estaba `en_curso`/`aplicando` pasa a `interrumpida` y **no** se relanza.
- Si el repositorio de registro no es **privado**, la tarea falla sin publicar nada.

## Agentes de IA: datos, acciones y límites

**Qué recibe el modelo**
- La descripción de la tarea y las reglas de la fase (ver `prompt_trabajo` / `prompt_aplicar`).
- La copia de trabajo de este repositorio.
- El estado de la casa de la tarea, a través del servidor MCP de Home Assistant (`/api/mcp`).

**Qué puede hacer**
- *Fase trabajo* (siempre): leer/editar archivos de la copia de trabajo y consultar HA solo con
  `homeassistant__GetLiveContext`, `llm__GetDateTime`, `todo__get_items` y `media_player__search_media`, usando el token de **lectura**. Claude corre sin Bash, con
  `--permission-mode dontAsk` (todo lo no permitido se rechaza). Codex corre con sandbox
  `workspace-write` y su shell no ve variables con `TOKEN`/`KEY`/`SECRET`/`HA_`.
- *Fase aplicar* (solo tras el merge del PR por el dueño): ejecutar el `plan_aplicar.md`
  **mergeado** (se lee de la rama principal, no de la copia de trabajo) con todas las herramientas
  MCP de esa casa y el token de **escritura**. Sin edición de archivos.

**Límites**
- No recibe el token de GitHub (el push y los PR los hace el servicio) ni los de la otra casa.
- Tiempo máximo por corrida: `DOMOTICA_TIMEOUT_TAREA_MIN` (45 min por defecto).
- Respaldo de cuenta: si `gmail` llega a su límite de uso en una tarea nueva sin cuenta
  explícita, se reintenta una vez con `bravosm`. Una sesión iniciada nunca cambia de cuenta.

## Seguridad

- Escucha solo en `127.0.0.1:8770`; se publica a través del proxy existente.
- OAuth 2.1 de un solo usuario: registro dinámico de clientes, PKCE, consentimiento con clave del
  dueño (hash scrypt), access token 1 h, refresh token 30 días con rotación. Tokens guardados como
  SHA-256. Ninguna credencial viaja en la URL. Protección contra DNS rebinding (Host/Origin).
- Secretos solo en `~/.config/domotica/env` (600), leídos bajo demanda. Nunca en Git ni en logs.

## Variables del archivo env

| Clave | Uso |
|---|---|
| `HA_<CASA>_URL` | URL de Nabu Casa de la casa |
| `HA_<CASA>_TOKEN_LECTURA` / `HA_<CASA>_TOKEN_ESCRITURA` | Tokens de HA por fase |
| `CLAUDE_TOKEN_GMAIL`, `CLAUDE_TOKEN_BRAVOSM`, `CLAUDE_CUENTA_DEFAULT` | `claude setup-token` por cuenta |
| `GH_TOKEN_HASSIO` | Token de alcance fino solo para este repo (Contents, Issues, Pull requests) |
| `DOMOTICA_CLAVE_HASH` | Hash de la clave de consentimiento (`python -m domotica_hub clave`) |
| `DOMOTICA_URL_PUBLICA` | URL pública (p. ej. `https://domotica.grupoaislar.com`) |
| `DOMOTICA_PORT`, `DOMOTICA_TIMEOUT_TAREA_MIN` | Opcionales |

## Instalación (VPS)

```bash
python3 -m venv ~/domotica/venv
~/domotica/venv/bin/pip install -e ~/domotica/repo/domotica-hub     # mcp==2.3.0
~/domotica/venv/bin/python -m domotica_hub clave                      # define la clave del dueño
sudo cp ~/domotica/repo/domotica-hub/deploy/domotica-hub.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now domotica-hub
```

Salud: `deploy/check_salud.py` (sale 0/1) lee `~/domotica/estado/salud.json`, que el servicio
actualiza cada minuto. Pensado para sumarse a `aislar-healthcheck`.

## Pruebas

```bash
~/domotica/venv/bin/pip install -e '~/domotica/repo/domotica-hub[test]'
~/domotica/venv/bin/python -m pytest -q domotica-hub
```

Las pruebas usan un repositorio git local, GitHub y agentes simulados, y datos ficticios.
