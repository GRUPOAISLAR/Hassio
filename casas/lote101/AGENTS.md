# Lote 101 — guía para agentes

Solo Lote 101. Lo común (repo, domotica-hub, integración `hpa4911`, reglas) está en el
[`AGENTS.md` de la raíz](../../AGENTS.md). Nada de este archivo aplica a Costa 204.

## Identidad

| | |
|---|---|
| Id en domotica-hub | `lote101` (servidores `ha-lote101`, `hacfg-lote101`) |
| Ubicación en HA | Adrogué |
| Home Assistant | 2026.11.1 sobre Raspberry Pi 4 (relevado 11/11/2026) |
| Escala | ~2400 entidades, ~196 automatizaciones, ~47 scripts, 18 áreas |
| Áreas | estar, comedor, cocina, SUM, galería, habitación principal (suite), chicas, Tomás, baño chicos, hall planta alta/baja, hall exterior, lavadero, subsuelo, exterior, Edesur, calefacción |

## Subsistemas

- **Aires BGH** con la integración propia `hpa4911` (este repo): Habitación Principal, Galería,
  SUM, Chicas, Tomás, Pasillo PA y el Termostato BGH (kit HPA-4412) de la habitación principal.
  Firmwares 1.0.0.8 a 1.0.0.17. El kit de Galería informa mal el modo (vuelve solo a *calor*
  ~57 s después de apagarlo) y no manda vibración: usa *Ignorar el modo que informa el kit*.
  El 01/11/2026 un corte de red cambió las IP de todos los kits; desde entonces se siguen por MAC.
- **Aire Estar**: SmartIR sobre Broadlink "IR Estar" (`climate.aire_estar`), con confirmación
  de la orden por consumo.
- **Z-Wave (Z-Wave JS)**: sensores Fibaro FGMS-001 (movimiento/temperatura/luz), KeyFob
  FGKF-601, controlador RGBW (cortinas estar/comedor), módulo de toldo (Sunscreen Estar
  Frente), Smart Implant como contactor del termostato Nest.
- **Zigbee**: ZHA/ConBee (hay complemento deCONZ instalado).
- **Tuya / LocalTuya**, Shelly, Sonoff: luces, teclas de escena, persianas.
- **Calefacción por losa** con caldera: válvulas por zona y contactor que se enciende si
  cualquier zona pide calor. Los termostatos usan `sensor.temperatura_*_combinada`: si el
  Fibaro no se ve hace más de 6 h, toman la temperatura del aire BGH.
- **Consumo**: powermeter por fase (R/S/T), detector de anomalías v5 por fase, runtime y kWh
  por equipo. Ojo: las pinzas están en la salida del C40 de Planta Baja (mide 45–61 % del total).
- **Cortes de luz (Edesur)**: sensor Wi-Fi de corte (Sonoff a pila), contador de cortes,
  "Restaurar estado previo tras recuperar energía". La bomba sumergible **no** se reactiva tras
  un corte (verificado en un corte real el 07/11/2026).
- **Pileta y riego**: placa con PCF8574 (riego y filtrado), llenado de pileta y tanque, riego
  semanal por días.
- **Cocina con recetas**: termostatos y timers para queso (Gruyere, Cremón) y yogur.
- **Cámaras**: Foscam y ONVIF, más visión con LLM (personas y autos).
- **Otros**: alarma "Alarma Lote 101", portón de garaje, Sonos y Chromecast, Nest, Grocy,
  lista de compras con pyscript (`lc_*`), bot de Telegram.

## Ruido conocido (no reportar como novedad)

- 350+ entidades `unavailable` son habituales. Importa solo un config entry entero en
  `setup_retry` (pasó con ZHA/ConBee en agosto de 2026).
- Errores de LocalTuya en `discovery.py` (decode / block length).
- Cámaras en `setup_retry` conocidas: Foscam Garage, Lateral, Bodega_Subsuelo, Caja_Fuerte;
  ONVIF Pileta, Bodega Subsuelo, Lateral; linkplay Subsuelo.
- Temperatura estable durante horas **no** es sensor congelado: para saber si un nodo Z-Wave
  está vivo, usar su `_last_seen`.

## Recetas de reparación

- **Sensor Z-Wave a pila sin verse >2 días**: cambiar pila (FGMS-001 → CR123A, KeyFob
  FGKF-601 → CR2450) y despertar con triple click en el botón B. Si no vuelve, acercarlo al
  controlador y repetir. Si tampoco, Z-Wave JS UI → Failed Nodes → **REPLACE (nunca REMOVE)**
  y reponer los parámetros.
- **Nodo Z-Wave a red en `dead`**: verificar alimentación → ping/heal y re-entrevista → si
  sigue, REPLACE.
- **Fibaro que no acepta parámetros**: re-entrevista y despertarlo.
- Parámetros de reporte de temperatura Fibaro (desde 21/10/2026): 60=3, 62=600, 64=3600.

## Pendientes estructurales

- Mover las pinzas del powermeter a la entrada general.
- Pasar a `secrets.yaml` la credencial de una cámara Foscam que está en `configuration.yaml`.
- Identificar la otra instancia que usa el bot de Telegram (error "Conflict: terminated by
  other getUpdates request").
- El sensor de Galería (nodo 23) no llega a la red desde la galería: necesita repetidor Z-Wave.

## Notion (estado vivo)

- [🌳 Lote 101 — Base de conocimiento](https://app.notion.com/p/415825a110c3812bb7a0cd6303b8560d)
- [Estado conocido y diagnóstico — Home Assistant](https://app.notion.com/p/403825a110c3819988bce5eefcd1c6d2)
  → secciones "Lote 101 — …" (seguimiento diario de nodos, cortes y pendientes).

## Configuración versionada

Los archivos de configuración de esta casa que se versionen van en `casas/lote101/`
(nunca `secrets.yaml` ni credenciales).
