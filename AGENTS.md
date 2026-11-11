# Hassio — guía para agentes (Codex, Claude Code y otros)

Este archivo es la entrada común a todo el conocimiento del repo. Lo leen automáticamente
Codex (`AGENTS.md`) y Claude Code (vía `CLAUDE.md`, que lo importa). Lo específico de cada casa
está **separado** en `casas/<casa>/AGENTS.md`: Lote 101 y Costa 204 comparten herramientas,
pero son dos desarrollos distintos y no se mezclan.

## Mapa

| Qué | Dónde | Alcance |
|---|---|---|
| Integración **Local BGH Smart** (`hpa4911`) para Home Assistant | `custom_components/hpa4911/`, `README.md`, `hacs.json` | Común (se instala en cada casa que tenga kits BGH/Solidmation) |
| **domotica-hub**: servicio MCP que encola tareas para Claude Code / Codex | `domotica-hub/` (ver `domotica-hub/README.md`) | Común (atiende a las dos casas) |
| Conocimiento y configuración versionada de **Lote 101** | `casas/lote101/` | Solo Lote 101 |
| Conocimiento y configuración versionada de **Costa 204** | `casas/costa204/` | Solo Costa 204 |
| Informes y planes de tareas del hub | `tareas/<id>/` (lo crea el hub) | Por tarea |

## Las dos casas

| | Lote 101 | Costa 204 |
|---|---|---|
| Id en el hub | `lote101` | `costa204` |
| Ubicación en HA | Adrogué | Costa 204 |
| Escala aprox. (11/2026) | ~2400 entidades, ~196 automatizaciones, 18 áreas | ~1100 entidades, ~96 automatizaciones, 17 áreas |
| Guía | [`casas/lote101/AGENTS.md`](casas/lote101/AGENTS.md) | [`casas/costa204/AGENTS.md`](casas/costa204/AGENTS.md) |

Regla: antes de tocar algo de una casa, leé su guía. No asumas que un equipo, una entidad o
una automatización de una casa existe en la otra (comparten la cuenta Tuya, pero cada HA tiene
deshabilitados los equipos de la otra casa desde el 22/10/2026).

## Fuentes de conocimiento

1. **Este repo** (fuente de verdad para código, protocolo y decisiones de diseño).
2. **Notion** — estado operativo vivo (lo que cambia día a día):
   - [🏠 Hassio — Base de conocimiento](https://app.notion.com/p/415825a110c3819c9650fcd0b6fbe83a):
     índice con lo común, y subpáginas
     [🌳 Lote 101](https://app.notion.com/p/415825a110c3812bb7a0cd6303b8560d) y
     [🌊 Costa 204](https://app.notion.com/p/415825a110c381de8b6ac6b246dcc3e7).
   - [Estado conocido y diagnóstico — Home Assistant](https://app.notion.com/p/403825a110c3819988bce5eefcd1c6d2):
     la lee y actualiza la rutina diaria de reporte. Tiene secciones separadas por casa.
3. **Home Assistant en vivo**, a través de los servidores MCP (ver `domotica-hub/README.md`).

Lo durable (cómo funciona algo, por qué se decidió así, recetas de reparación) va al repo.
Lo efímero (qué está caído hoy, seguimiento día a día) va a Notion.

### Usar este conocimiento desde ChatGPT / Codex

- **Codex CLI / Codex en la nube**: clona el repo y lee este archivo solo. Para sumar Notion,
  agregá el servidor MCP oficial: `codex mcp add notion --url https://mcp.notion.com/mcp` y
  `codex mcp login notion`.
- **ChatGPT**: activá el conector de Notion (y el de GitHub para el repo) en Configuración →
  Conectores.
- **Excepción**: el Codex que lanza `domotica-hub` corre **sin** conectores de la cuenta de
  ChatGPT (`features.apps=false`) a propósito; esas tareas ven el repo y la casa, no Notion.

## Integración `hpa4911` — lo esencial

- Fork de [arpena/hpa4911](https://github.com/arpena/hpa4911) (MIT). Mismo dominio `hpa4911`
  para reemplazar a la original sin romper entradas existentes.
- Equipos: aire acondicionado BGH con kit **HPA-4911** (`climate`, sensor *Vibration*, binario
  *Running*) y comando de cortina **Solidmation HPA-4202** (`cover`, sin posición).
- Protocolo UDP local: se envía al puerto 20910, se escucha en 20911. Detalle verificado de
  comandos y estados en `README.md`. Constantes en `custom_components/hpa4911/const.py`.
- Los kits se identifican por **MAC** (no por IP): si cambian de IP por DHCP se reaprenden solos.
- Opción *Ignorar el modo que informa el kit* + servicio `hpa4911.set_assumed_hvac_mode` para
  kits que informan mal el modo.
- Cualquier dato nuevo del protocolo se documenta en `README.md` con fecha y firmware en que
  se verificó.

## domotica-hub — lo esencial

- Herramientas MCP: `crear_tarea`, `listar_tareas`, `estado`, `resultado`, `cancelar`.
- Cada tarea: issue + rama (`claude/<id>` o `codex/<id>`) + PR en este repo. Cambios de
  configuración de HA se proponen en `tareas/<id>/plan_aplicar.md` y solo se aplican después
  de que el dueño mergea el PR.
- Servidores por casa: `ha-<casa>` (Assist, control de dispositivos, usuario no admin) y
  `hacfg-<casa>` (ha-mcp, configuración; solo lectura en la fase de trabajo).
- Código en `domotica-hub/src/domotica_hub/`: `server.py` (MCP + OAuth), `ejecutor.py`
  (cola, fases, prompts), `agentes.py` (lanzamiento de Claude/Codex), `github.py`, `vigia.py`
  (salud), `config.py` (casas, herramientas habilitadas).

## Reglas para trabajar en el repo

- **Secretos**: nunca escribir tokens, contraseñas, URLs de acceso remoto, IPs públicas ni
  contenido de `secrets.yaml` en archivos, commits, issues o PRs. Los secretos viven solo en
  `~/.config/domotica/env` en el VPS.
- **Datos personales**: no incluir más de lo necesario (nombres de personas, teléfonos,
  ubicaciones exactas).
- **Separación por casa**: lo de una casa va en `casas/<casa>/`; lo común, en la raíz o en
  `domotica-hub/` / `custom_components/`.
- **Idioma**: documentación en español rioplatense. Código e identificadores en inglés en
  `custom_components/` (sigue el upstream); en español en `domotica-hub/`.
- **Commits**: en `domotica-hub/` con prefijo `domotica-hub: …` en español; en la integración,
  mensaje en inglés en imperativo ("Add …", "Follow …").
- **Pruebas** de domotica-hub antes de subir cambios:
  ```bash
  pip install -e 'domotica-hub[test]' && python -m pytest -q domotica-hub
  ```
- Al aprender algo durable, actualizá la guía que corresponda (esta o la de la casa) en el
  mismo PR.
