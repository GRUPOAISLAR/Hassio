# Costa 204 — guía para agentes

Solo Costa 204. Lo común (repo, domotica-hub, integración `hpa4911`, reglas) está en el
[`AGENTS.md` de la raíz](../../AGENTS.md). Nada de este archivo aplica a Lote 101.

## Identidad

| | |
|---|---|
| Id en domotica-hub | `costa204` (servidores `ha-costa204`, `hacfg-costa204`) |
| Ubicación en HA | Costa 204 |
| Home Assistant | Core 2026.11.1 (actualizado 11/11/2026 07:14, tras backup completo 6beeb1fd); OS 18.5 (actualizado 11/11/2026 07:24) |
| Escala | ~1100 entidades, ~96 automatizaciones, ~17 scripts, 17 áreas |
| Áreas | estar, comedor, cocina, galería, baño galería, habitación principal, habitación de servicio, chicas, hall dormitorios, baño dormitorios, hall planta baja, toilette, lavadero, subsuelo, accesos, exterior, cooperativa |

## Subsistemas

- **Calefacción eléctrica por zonas**: 9 termostatos (dormitorios 1 y 2, galería, habitación
  principal, baños, hall dormitorios, estar, cocina-comedor) con fase, muestras, runtime y kWh
  por zona, y estado previo para restaurar.
- **Termotanques eléctricos** (habitación principal y lavadero) con limitador de potencia. El
  termotanque eléctrico existe solo en esta casa.
- **Solar**: inversor y pronóstico de producción; automatización "Corte – evaluar margen solar".
- **Cortes de luz**: bloqueo de dispositivos durante el corte y restauración de estado previo.
- **Aire York del estar** ("AC Estar"): único aire de la casa, trifásico. **No** tiene entidad
  `climate`: solo medición de consumo (`sensor.ac_estar_consumo`, `sensor.ac_estar_energy`).
  En las habitaciones hay ventiladores.
  **Medición inferida, no directa**: el powermeter mide toda la casa; `binary_sensor.ac_estar_prendido`
  se deducía de "fase T > 1500 W" y `sensor.ac_estar_consumo` restaba bases a las tres fases.
  Eso da falsos positivos con calefacción/termotanques en la fase T.
  **Desde el 11/11/2026 el York está desconectado** (controlador retirado, placa en
  reparación): el binario quedó fijo en `false` (la fórmula original está comentada dentro del
  helper). Al volver el equipo, detectarlo como carga trifásica (subida simultánea y pareja en
  R, S y T), no por una sola fase. Ver la página de Notion del York (receptor IR,
  extensión de cable y opción de módulo ESPHome si es fabricación Midea).
- **Pileta**: filtrado programado, protección del filtro sin agua en el skimmer, llenado con
  verificación, ionizador.
- **Riego** con suspensión por lluvia reciente y alerta de bomba sin consumo.
- **Accesos**: cerradura principal Tuya vía Xtend Tuya (desde 20/10/2026; la TTLock
  "Puerta Principal" vieja está rota y deshabilitada). TTLock "Puerta Lateral" con gateway.
  Script "Huésped: generar acceso (puertas y app)" y datos de inquilino.
  **Bienvenida hablada** (11/11/2026): generar el acceso del huésped deja
  `input_boolean.bienvenida_inquilino_pendiente` en on; la primera apertura con clave
  temporal (`event.puerta_principal_unlock_user_temporary`) dispara, 10 s después,
  `script.bienvenida_inquilino` en todos los parlantes disponibles (lista `parlantes` dentro
  del script; sumar ahí los nuevos), con el nombre de `input_text.inquilino_nombre`. Así no salta cuando entra la inmobiliaria a revisar
  (a menos que use una clave temporal).
  Huella n.º 2 de la cerradura principal = el dueño (sirve para distinguir su llegada de la
  de un inquilino).
- **Seguridad**: Alarmo (sirena), 5 cámaras (Foscam: Frente_Patio_Interno, Frente_izquierda,
  Fondo_Izquierdo, Lateral_Derecho; más Camara Entrada), modo casa (Presente/Ausente) con sugerencia
  automática si todos están fuera más de 1 h.
- **Cortinas** (8, incluida blackout de la habitación principal) y ventiladores de techo.
- **Integraciones/complementos**: eWeLink y Sonoff LAN, Shelly, Tuya, Node-RED, Mosquitto,
  Google AI (conversación/TTS/STT), Telegram.

## Conocido / pendientes

- **Luz blanca de las cámaras Foscam: apagada a propósito.** La de `Frente_Patio_Interno`
  (frente, da al garage) estaba siempre prendida: no cumple función, queda fea y consume de
  la alimentación PoE. Se apagó el 11/11/2026 (`switch.frente_patio_interno_white_light` en
  `off`). La visión nocturna infrarroja (`*_infrared_mode`) queda activa. No volver a
  encenderla; si la cámara la reenciende sola, agregar una automatización que la apague.
- **Extractores con apagado automático a los 15 min**: toilette, baños de dormitorios y (desde
  11/11/2026) baño principal (`automation.extractor_bano_principal_auto_off_15_min`). El del
  baño de la galería (`switch.sonoff_10013afde4_1`) todavía no tiene.
- **Sensor de temperatura del baño principal NO funciona (verificado 11/11/2026)**: es un
  Shelly H&T gen1 (`sensor.sensor_temperatura_bano_habitacion_principal_temperatura`) que no
  reporta; HA solo restaura 15,25 °C al reiniciar y a los ~20 min lo marca no disponible.
  `climate.termostato_bano_principal` (YAML) queda en `idle` con ese valor viejo: el baño no
  se está climatizando. Hay además un sensor ZHA viejo del mismo nombre, no disponible.
- **NSPanel (firmware de fábrica)**: solo maneja equipos de la cuenta eWeLink (Sonoff) y su
  propia calefacción. El complemento **eWeLink Smart Home** (CoolKit, legado) que subía
  entidades de HA a eWeLink —así aparecían las luces Shelly en el panel— fallaba (archivo de
  datos dañado) y el 11/11/2026 se **desinstaló para reinstalarlo, pero ya no compila**: el
  repo `CoolKit-Technologies/ha-addon` está archivado desde el 24/02/2026. El complemento
  nuevo (`iHost-Open-Source-Project/hassio-ihost-addon`) no sube equipos de HA a eWeLink.
  Las entidades plantilla `ewelink_virtual_*` quedaron sin uso. Camino elegido para manejar
  todo desde los paneles: **NSPanel Easy (ESPHome)**, piloto en el panel de la galería (plan y
  riesgos en [`nspanel.md`](nspanel.md)). El
  repositorio de ESPHome ya está en la tienda de complementos.
- **Guía para huéspedes con IA (11/11/2026)**: agente `conversation.guia_costa_204` (Gemini,
  subentrada de Google Generative AI) con el manual como instrucciones y **sin control de
  dispositivos** (`llm_hass_api` vacío: no abre cerraduras ni toca la alarma). Pipeline de
  Assist "Guía Costa 204 (huéspedes)" (STT/TTS Home Assistant Cloud es-AR) y
  `script.guia_responder_en_parlantes` (pregunta → respuesta hablada en los parlantes).
  Acceso del huésped: botón **"Preguntale a la casa"** en el panel `huespedes-costa` (vista Casa),
  que abre Assist con ese pipeline y empieza a escuchar (usuario `inquilino`, app de HA).
  Con Google: `script.guia_de_la_casa` expuesto a Google Assistant (HA Cloud): "Ok Google,
  activá Guía de la casa" → resumen hablado en todos los parlantes. "Ok Google" no puede
  hacer preguntas libres a la guía (va al asistente de Google); solo frases armadas.
  Al cambiar `manual-uso.md`, actualizar también el prompt del agente.
  Probada el 11/11/2026 (tras cargar crédito prepago en Google AI Studio): responde bien
  ubicación de teclas, se niega a dar claves/alarma y dice "no lo sé" ante lo que no está en
  el manual. Si vuelve el error 402, es falta de crédito en AI Studio (afecta también al
  pipeline "Google IA", el preferido de la casa).
- TTLock Puerta Lateral: pilas cambiadas (100 % al 11/11/2026). **Webhook registrado el 11/11**
  (callback URL de Nabu Casa en la app "Costa Esmeralda" de euopen.ttlock.com): los eventos llegan
  al instante (`sensor.puerta_lateral_last_operator` / `_last_trigger`). Avisa por Telegram
  quién abrió y cómo, en la misma automatización que la principal. Auto Lock activo.
- Tecla del acceso (pared de madera junto al pasillo exterior) = Sonoff dual
  `switch.sonoff_10013b00fb_1` → `light.exterior_semi_cubierto_lateral_placard` ("Pasillo Acceso
  Principal Exterior"); el canal 2 es el techo del semicubierto lateral. El 11/11 respondió de
  forma irregular: el primer toque no se registró, el segundo sí.
- Cuenta Tuya compartida con Lote 101: aquí están deshabilitados los equipos de la otra casa.
- Reparaciones abiertas en HA (11/2026): migración de `chat_id` de Telegram en varias
  automatizaciones (rompía en 2026.9) y configuración `http` en YAML pendiente de quitar
  (rompe en 2027.2).
- Tras actualizar a 2026.11.1: 126/130 integraciones cargadas; en `setup_retry` las mismas que
  ya estaban caídas (Shelly spots comedor, 2 Android TV remote, Foscam Frente_izquierda).
  Ninguna automatización usa `climate.turn_on`. Repairs nuevos: `ssl_profile_outdated` (http) y
  un aviso de marketplace (`removed`).
- **Panel "Cocina"** (`panel-cocina`, 480×480 para el NSPanel Pro 86 de la cocina): luces de
  cocina/comedor/galería/pileta, calefacción cocina-comedor, música del estar, "Preguntale a
  la casa" y "Apagar luces". El usuario `panel-cocina` se crea a mano (la API no permite
  crear usuarios).

## Notion (estado vivo)

- [🌊 Costa 204 — Base de conocimiento](https://app.notion.com/p/415825a110c381de8b6ac6b246dcc3e7)
- [Costa 204 · Aire York — receptor IR y extensión de cable](https://app.notion.com/p/404825a110c3810d9499dd32bb883997)
- [Estado conocido y diagnóstico — Home Assistant](https://app.notion.com/p/403825a110c3819988bce5eefcd1c6d2)
  → sección "Costa 204 — conocido".

## Mantenimiento

Registro de reparaciones (colector solar, etc.): [`mantenimiento.md`](mantenimiento.md).

## Manuales, glosario y fotos

- [`glosario.md`](glosario.md): nombre fijo de cada ambiente y equipo, dónde está y su foto.
  Usar esos nombres en todo (manuales, HA, guía con IA, mensajes).
- [`manual-interno.md`](manual-interno.md): propietarios. Tableros y térmicas, medidor de
  tensión, inversores y baterías, tablero solar, sensor de corte, termotanque, ablandador.
- [`fotos/README.md`](fotos/README.md): índice de todas las fotos por lugar. Al sumar una foto,
  agregarla ahí.
- Cocina (verificado 11/11 en el registro): spots de la mesada y del pasillo son la misma luz
  `light.luz_spots_cocina`; junto al vajillero, medio-abajo = colgante del comedor de la galería; medio-arriba
  llega a la entrada 2 del Shelly "Comedor Galería" sin efecto; la derecha y la de arriba de la
  galería no llegan a HA (probar de noche). Las tres quedaron pendientes de electricista
  (¿cable suelto?). Los spots del comedor de la galería (`light.shellydimmer2_409151588222`)
  hoy no tienen tecla.

### Manual de uso

Borrador del manual para huéspedes: [`manual-uso.md`](manual-uso.md), con fotos en `fotos/`
(siempre sin metadatos EXIF/GPS, máx. 1600 px). Espejo en Notion: [📖 Manual de uso](https://app.notion.com/p/415825a110c3817a9abdcc4e998142be).

## Configuración versionada

Los archivos de configuración de esta casa que se versionen van en `casas/costa204/`
(nunca `secrets.yaml` ni credenciales).
