# Costa 204 — relevamiento de teclas: diseño vs. lo verificado

Cruce entre la planilla de diseño de la domótica (Google Sheets "EJEMPLO DOMOTICA COSTA 204",
hoja ILUMINACION, 06/2024: circuito, ambiente, artefacto, caja, ubicación de tecla, equipo y
MAC) y lo verificado tecla por tecla en el registro de Home Assistant el 11/11/2026.
La planilla es el **diseño original**: algunos equipos se reemplazaron o se reasignaron después
(ej. el Sonoff `1001d8d053` de "acceso peatonal / reserva vehicular" hoy maneja llenado de
pileta y estacas del frente; el dimmer de "galería techo comedor" `349454707815` se reemplazó
por `409151588222`). Las IP de la planilla no se copian acá.

## Teclas que no hacen nada: qué deberían manejar según el diseño

| Tecla (ubicación verificada) | Qué debería manejar (planilla) | Equipo | Estado / hipótesis |
|---|---|---|---|
| Pasillo de servicio, tecla del medio (caja 11, "GALERIA 3 TECLAS") | Circuito **a**: perímetro fondo, 6 apliques negros bidireccionales | Sonoff Dual R3 `10013aec78` canal 1 (`switch.sonoff_10013aec78_1`) | Desde HA funciona; la tecla no llega al Sonoff → cable de la entrada S1 suelto o sin conectar |
| Galería junto a los jarrones, tecla de arriba (caja 7) | Circuito **T**: spots del techo del comedor de la galería | Shelly Dimmer 2 (hoy `409151588222`) | El reemplazo del dimmer no tiene esa tecla cableada (la entrada 1 la usa el pasillo de la galería) |
| Junto al vajillero, tecla sola de la derecha | Probable circuito **J** (caja 18, "COCINA 1 TECLA"): luz de la isla (tubo LED de madera) | Shelly Dimmer 2 `34945471BC58` | No llega a HA. La entrada 2 de ese Shelly recibe en cambio la placa del medio entre hall y estar |
| Hall de entrada, derecha abajo (caja 2) | Circuito **C**: spots del techo de la reserva vehicular | Diseño: Sonoff `1001d8d053` (reasignado) | Hoy sin equipo para ese circuito; hay una automatización "Luz Acceso y Reserva con Sensor" (apagada) |
| Placa del medio entre hall y estar (2 teclas) | Diseño: caja 5 (repite spots y centro del estar) o caja 6 (estar techo ventanal + galería living) | — | Llegan a la entrada 2 del Shelly de la isla (`34945471BC58`): cable cruzado o reasignado |

Resueltas con automatización (entradas 2 sueltas de los Shelly): estar junto a la salamandra,
arriba → R techo ventanal (`34945471BCDE`) y abajo → P spots estar (`34945471CAED`).
También: vajillero, media tecla de arriba de la placa del medio →
circuito **T** (spots del comedor de la galería) por la entrada 2 de `409151588222`.

## SW2 de los Shelly Dimmer 2: corregido el 11/11/2026

Causa: varios Shelly Dimmer 2 tenían `btn_type = one_button` (el dimmer ignora SW2). Los que
andaban tenían `dual_button` (SW1 y SW2 conmutan; mantener apretado SW1 sube y SW2 baja el
brillo). El 11/11/2026 se cambiaron a `dual_button` (vía Node-RED, abierto temporalmente y
vuelto a cerrar):

| IP final | Shelly | Luz |
|---|---|---|
| .31 | `34945471be06` | Barra galería (colgante de la barra de la parrilla) |
| .37 | `c45bbe5638bf` | Estar pared |
| .41 | `34945471caed` | Spots estar |
| .54 | `ec64c9c4db9d` | Pasillo galería (spots parrilla–horno) |
| .55 | `3494547290bb` | Spots dormitorio 2 |
| .139 | `244cab40220a` | Galería living |
| .144 | `c45bbe6a84ef` | Techo toilette |
| .201 | `3494547227d7` | Mesa de luz izquierda (habitación principal) |
| .220 | `409151588222` | Spots comedor galería |
| .232 | `349454723b28` | Mesada cocina (colgantes) |
| .235 | `34945471bcde` | Estar techo ventanal |

**Sin cambiar a propósito:** `.234` `34945471bc58` (luz de la isla): su SW2 recibe las dos
teclas del medio entre hall y estar; decidir antes qué deben manejar. `.145`
`349454729610` (spots comedor) está desconectado: revisar al volver.
Ya estaban en `dual_button`: .36, .38, .43, .83, .148, .165, .181, .188, .189, .233, .248.

Las automatizaciones puente (`automation.estar_teclas_junto_a_la_salamandra_entradas_2_sueltas`
y `automation.cocina_tecla_del_vajillero_medio_arriba_prende_spots_del_comedor_de_la_galeria`)
quedaron **desactivadas**; borrarlas cuando se confirme a la vista que las teclas andan.
Teclas que podrían empezar a andar por este cambio: galería junto a los jarrones (arriba,
SW2 de galería living) y otras segundas teclas de la planilla de diseño. Volver a probarlas.

## Posibles nombres cruzados en HA (verificar de noche, a la vista)

- Sonoff Dual R3 `10013b0bb7` (diseño: canal D = estacas del patio interno, canal E = apliques
  del acceso peatonal y perímetro del frente). En HA `_1` se llama "Patio interno" y `_2`
  "Perímetro frente". La tecla del hall de entrada (diseño: circuito E) prende `_1` y el dueño
  ve que maneja el perímetro: los nombres de los canales pueden estar invertidos.
- `light.luz_spots_estar` (`34945471caed`, diseño: circuito P, spots AR111 del techo del estar):
  el dueño vio que la tecla de la derecha del medio prende los "spots del comedor". El dimmer de
  los spots del comedor (circuito L, `349454729610`) figura como `light.luz_spots_comedor`, **no
  disponible**.

## Circuitos del diseño útiles para seguir el relevamiento

- Hall PB: A spots hall (`34945471bc6c`, cajas 1 y 3), Ñ tira LED placard (sin domótica).
- Estar: O pared (`c45bbe5638bf`), P spots (`34945471caed`), Q centro (`244cab402272`),
  R techo ventanal (`34945471bcde`, cajas 6 y 19).
- Comedor: L spots (`349454729610`), M colgante centro (`34945472469d`).
- Cocina: I pasillo (cajas 17 y 19), J barra/isla (`34945471bc58`), K apliques mesada
  (`349454723b28`).
- Galería: S living (`244cab40220a`), T spots comedor, U colgante comedor, W barra
  (`34945471be06`), X pasillo (reemplazado por `ec64c9c4db9d`), Y parrilla
  (`10013b0692` canal 1), ventilador (Sonoff iFan `1001589E84`, control remoto).
- Exterior: a perímetro fondo y H lavadero (`10013aec78`), D/E patio interno y perímetro frente
  (`10013b0bb7`), F semicubierto y G placard (`10013b00fb`), reflectores (`10013b1377`).
