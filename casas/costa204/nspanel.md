# Costa 204 — NSPanel: estado y plan (relevado 11/11/2026)

Hay 4 NSPanel originales (EU) en la casa: habitación principal, dormitorio 1, dormitorio 2 y
galería. Hacen de termostato de la calefacción eléctrica: cada uno tiene 2 relés (zonas) y su
propio sensor de temperatura. Ver el mapa de canales en `manual-uso.md`.

## Por qué el firmware de fábrica no alcanza

Solo maneja equipos de la cuenta eWeLink. El puente que subía entidades de HA a eWeLink (el
complemento legado eWeLink Smart Home) está archivado y ya no compila. El complemento nuevo no
hace ese puente. Detalle en `AGENTS.md`.

## Opción elegida: NSPanel Easy (ESPHome)

Proyecto: <https://github.com/edwardtfn/NSPanel-Easy> (sucesor de NSPanel_HA_Blueprint).

### Qué hace falta

- **ESPHome**: el repositorio ya está en la tienda de complementos. Para compilar, el proyecto
  recomienda 4 GB de RAM si ESPHome corre como complemento; si el equipo de HA no los tiene,
  se compila en una PC con ESPHome.
- **Versiones**: HA y ESPHome publicados como mucho un mes antes del release de NSPanel Easy
  que se use. Antes de empezar, actualizar HA (hoy 2026.10.2) a 2026.11.x.
- **Hardware**: adaptador USB-TTL de **3,3 V** (más voltaje daña el panel), cables dupont y un
  destornillador.
- **Una vez por panel**: desenchufarlo, abrirlo, conectar 3V3, GND, TX↔RX cruzados e IO0 a GND,
  y grabar desde ESPHome Web. Después todo se actualiza por Wi-Fi, incluida la pantalla (TFT
  de Nextion, entre 10 y 20 min).
- **Antes de grabar**: copiar el firmware original de **ese** panel con
  `esptool read-flash 0 0x400000 nspanel_<lugar>.bin` y `verify-flash`, y guardarlo. Es la
  única forma de volver atrás, porque cada copia tiene credenciales únicas de ese panel. La
  pantalla original no se puede respaldar.

### Qué ofrece (según la documentación)

- Página de inicio, 4 páginas de botones y 4 de entidades: cualquier entidad de HA (luces
  Shelly, cortinas, escenas, scripts).
- Páginas de clima, alarma, pronóstico, reproductor y ventilador, y un **QR del Wi-Fi para
  huéspedes**.
- Termostato embebido con los relés y el sensor del propio panel, que según la documentación
  regula aunque no haya Wi-Fi ni HA.
- Teclas físicas configurables, con respaldo local del relé.

### Riesgos abiertos al 11/11/2026 (por eso se arranca con un piloto)

- **#636**: con 3 o más paneles, el event loop de HA se traba entre 20 y 55 s. Lo reportaron
  con HA 2026.10.4 y HAOS. Los arreglos de v2026.11.6 todavía no están confirmados. Con 4
  paneles nos afecta.
- **#735**: si el panel arranca sin HA, no se llega a la pantalla del termostato (sigue
  regulando). El arreglo está anunciado para el próximo release.
- **#577**: reporte de control local de relés que no funciona sin HA (marcado stale).
- No hay una lista oficial de "probado/estable". Usar el canal `main`.

### Plan

1. Piloto **solo en el panel de la galería** (tiene un canal libre): backup → flasheo →
   termostato embebido + página de luces Shelly de la galería.
2. Probar sin internet y con HA reiniciado: que la calefacción siga regulando y que las teclas
   conmuten.
3. Pasar a los paneles de los dormitorios solo cuando #636 y #735 estén confirmados como
   resueltos.

## NSPanel Pro (si se compra o se usa)

- Desde el firmware V4.0.0 (09/2025) se instala la **app oficial de Home Assistant desde
  F-Droid, sin root**. Las funciones originales siguen andando.
- Versiones posteriores: menú de apps, puente Matter para entidades de HA (V4.3.0) y portal
  web local con autorización de la conexión con HA (V4.6.0, 06/2026).
- **Pro 86 y Pro 120 originales**: no está confirmado que tengan relés. No reemplazan a un
  NSPanel termostato.
- **NSPanel Pro Gen2** (04/2026): doble relé, Matter y soporte de HA.
- Para una pantalla de pared que muestre el panel de HA, es la opción más simple: no hay que
  abrir nada.

Fuentes: documentación de NSPanel Easy (install, backup_stock_firmware, version_compatibility,
blueprint), issues #636, #735 y #577 de NSPanel-Easy, esphome#16472, notas de versión del
NSPanel Pro en sonoff.tech.
