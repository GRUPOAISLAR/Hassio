# Costa 204 — guía para agentes

Solo Costa 204. Lo común (repo, domotica-hub, integración `hpa4911`, reglas) está en el
[`AGENTS.md` de la raíz](../../AGENTS.md). Nada de este archivo aplica a Lote 101.

## Identidad

| | |
|---|---|
| Id en domotica-hub | `costa204` (servidores `ha-costa204`, `hacfg-costa204`) |
| Ubicación en HA | Costa 204 |
| Home Assistant | 2026.10.2 (relevado 11/11/2026) |
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
  En las habitaciones hay ventiladores. Ver la página de Notion del York (receptor IR,
  extensión de cable y opción de módulo ESPHome si es fabricación Midea).
- **Pileta**: filtrado programado, protección del filtro sin agua en el skimmer, llenado con
  verificación, ionizador.
- **Riego** con suspensión por lluvia reciente y alerta de bomba sin consumo.
- **Accesos**: cerradura principal Tuya vía Xtend Tuya (desde 20/10/2026; la TTLock
  "Puerta Principal" vieja está rota y deshabilitada). TTLock "Puerta Lateral" con gateway.
  Script "Huésped: generar acceso (puertas y app)" y datos de inquilino.
- **Seguridad**: Alarmo (sirena), 5 cámaras, modo casa (Presente/Ausente) con sugerencia
  automática si todos están fuera más de 1 h.
- **Cortinas** (8, incluida blackout de la habitación principal) y ventiladores de techo.
- **Integraciones/complementos**: eWeLink y Sonoff LAN, Shelly, Tuya, Node-RED, Mosquitto,
  Google AI (conversación/TTS/STT), Telegram.

## Conocido / pendientes

- TTLock Puerta Lateral: pilas al 0 %, `unavailable` hasta cambiarlas. El gateway está online.
- Cuenta Tuya compartida con Lote 101: aquí están deshabilitados los equipos de la otra casa.
- Reparaciones abiertas en HA (11/2026): migración de `chat_id` de Telegram en varias
  automatizaciones (rompía en 2026.9) y configuración `http` en YAML pendiente de quitar
  (rompe en 2027.2).
- HA está una versión menor atrás de Lote 101.

## Notion (estado vivo)

- [🌊 Costa 204 — Base de conocimiento](https://app.notion.com/p/415825a110c381de8b6ac6b246dcc3e7)
- [Costa 204 · Aire York — receptor IR y extensión de cable](https://app.notion.com/p/404825a110c3810d9499dd32bb883997)
- [Estado conocido y diagnóstico — Home Assistant](https://app.notion.com/p/403825a110c3819988bce5eefcd1c6d2)
  → sección "Costa 204 — conocido".

## Configuración versionada

Los archivos de configuración de esta casa que se versionen van en `casas/costa204/`
(nunca `secrets.yaml` ni credenciales).
