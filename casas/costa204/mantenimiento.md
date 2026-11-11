# Costa 204: registro de mantenimiento

## Colector solar de la pileta (techo)

Paños de manguera de polipropileno negro sobre el techo. La bomba del filtro
(`switch.psw_4ch_cbu_switch_1`) hace circular el agua de la pileta por los paños. Lo controlan
`automation.colector_solar_encendido` (diferencia > `input_number.diferencial_encendido`) y
`automation.colector_solar_apagado` (diferencia baja durante 30 min, o puesta del sol).

![Vista general del colector](fotos/colector-vista-general.jpg)

Estado general (11/11/2026): varios paños están deformados y separados, con tubos ondulados y
huecos entre paños, sobre todo hacia los extremos. Es el desgaste típico por calor y edad.
Ahí es más probable que aparezcan fisuras.

### 11/11/2026: prueba de pérdidas

- Para probar, se pausó `automation.colector_solar_apagado` y se prendió la bomba a mano.
  **Reactivar la automatización al terminar.**
- Pérdida encontrada: un tubo rajado. Salía agua en chorrito.

  ![Pérdida](fotos/colector-perdida-2026-11-11.jpg)

- Reparación provisoria: **cinta autosoldable** sobre la rajadura. Está en la última fila de
  paños antes del caño colector, en el paño del medio, junto a la unión entre paños.

  ![Ubicación de la reparación](fotos/colector-reparacion-ubicacion-2026-11-11.jpg)
  ![Cinta autosoldable](fotos/colector-reparacion-cinta-2026-11-11.jpg)

- Revisar en la próxima visita: que la cinta siga sellando con el colector caliente, y una
  posible marca o agujero en un tubo del borde derecho de la foto de la cinta, a la altura del
  final del parche.
