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

Dos servidores MCP por casa, ambos corriendo en el VPS:

| Servidor | Qué es | Token (usuario de HA) |
|---|---|---|
| `ha-<casa>` | MCP oficial de HA (API Assist): estado y control de las entidades **expuestas a Assist** | `domotica-agente` (no admin) |
| `hacfg-<casa>` | [ha-mcp](https://github.com/homeassistant-ai/ha-mcp) `8.6.0`: configuración completa | `domotica-admin` (admin) |

**Qué recibe el modelo**
- La descripción de la tarea y las reglas de la fase (ver `prompt_trabajo` / `prompt_aplicar`).
- La copia de trabajo de este repositorio.
- Estado, historial, registros y configuración de la casa de la tarea, a través de esos servidores.

**Qué puede hacer (aprobación mixta)**
- *Fase trabajo* (sin aprobación previa):
  - **Controlar dispositivos directamente** con `ha-<casa>` (solo entidades expuestas a Assist).
  - **Leer** toda la configuración con `hacfg-<casa>`: ha-mcp corre con `READ_ONLY_MODE`
    (oculta y bloquea escrituras) y además solo se habilitan las herramientas de
    `HAMCP_TOOLS_LECTURA` (lista explícita).
  - Leer/editar archivos de la copia de trabajo. Los cambios de configuración se proponen en
    `tareas/<id>/plan_aplicar.md` dentro del PR.
- *Fase aplicar* (solo tras el merge del PR por el dueño): ejecutar el `plan_aplicar.md`
  **mergeado** (se lee de la rama principal) con ha-mcp sin restricciones, incluida la edición
  de YAML (requiere el componente `ha_mcp_tools` en la casa).

**Límites**
- Claude corre sin Bash y con `--permission-mode dontAsk`; Codex con sandbox y un shell que no
  ve variables `HA_*`, `HOMEASSISTANT_*`, `*TOKEN*`, `*KEY*`, `*SECRET*`.
- Los tokens viajan por entorno: nunca en la línea de comandos, en archivos ni en Git.
- No recibe el token de GitHub (el push y los PR los hace el servicio) ni los de la otra casa.
- `ha_report_issue` (reportes para un servicio externo) queda deshabilitada.
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
| `HA_<CASA>_TOKEN_AGENTE` | Token del usuario `domotica-agente` (no admin) para Assist |
| `HA_<CASA>_TOKEN_ADMIN` | Token del usuario `domotica-admin` (admin) para ha-mcp |
| `CLAUDE_TOKEN_GMAIL`, `CLAUDE_TOKEN_BRAVOSM`, `CLAUDE_CUENTA_DEFAULT` | `claude setup-token` por cuenta |
| `GH_TOKEN_HASSIO` | Token de alcance fino solo para este repo (Contents, Issues, Pull requests) |
| `DOMOTICA_CLAVE_HASH` | Hash de la clave de consentimiento (`python -m domotica_hub clave`) |
| `DOMOTICA_URL_PUBLICA` | URL pública (p. ej. `https://domotica.grupoaislar.com`) |
| `DOMOTICA_PORT`, `DOMOTICA_TIMEOUT_TAREA_MIN` | Opcionales |

## Instalación (VPS)

```bash
python3 -m venv ~/domotica/venv
python3 -m venv ~/domotica/venv-hamcp && ~/domotica/venv-hamcp/bin/pip install 'ha-mcp==8.6.0'
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
