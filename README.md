# Local BGH Smart + cortinas Solidmation

Versión propia de la integración **Local BGH Smart** ([arpena/hpa4911](https://github.com/arpena/hpa4911), licencia MIT) para Home Assistant, con soporte agregado para el **comando Wi-Fi para cortina Solidmation HPA-4202**. Todo funciona en red local, sin la nube de Solidmation (la app MyHabeetat ya no funciona).

Mantiene el mismo dominio (`hpa4911`), así que reemplaza a la original sin tocar los aires BGH ya configurados: las entradas existentes siguen funcionando como aire acondicionado.

## Qué agrega

- **Tipo de equipo** al agregar un dispositivo: *Aire acondicionado (HPA-4911 / BGH)* o *Cortina (HPA-4202)*.
- **Entidad cortina** para el HPA-4202: subir, bajar y parar. Muestra *subiendo* / *bajando* según lo que informa el equipo.
- **Invertir sentido del motor**: si al conectar el motor la cortina baja cuando debería subir, se marca esta opción al agregar el equipo.

El HPA-4202 informa el estado del motor (parado, subiendo, bajando), pero **no la posición**: Home Assistant no sabe si la cortina quedó abierta o cerrada, por eso la entidad tiene ambos botones siempre disponibles.

## Protocolo del HPA-4202 (verificado el 26/10/2026, firmware 1.0.1.0)

Mismo protocolo UDP local que los BGH: se envía al puerto 20910 del equipo y se escucha en el 20911. Cabecera de 17 bytes (versión 0x00, MAC origen en ceros, MAC destino, secuencia, endpoint origen 0, endpoint destino, ID de comando).

| Comando | ID | Endpoint | Payload |
|---|---|---|---|
| Subir | `0x28` | 1 | — |
| Bajar | `0x29` | 1 | — |
| Parar | `0x22` | 1 | — |
| Ir a posición (no probado, no usado) | `0x27` | 1 | 1 byte |

Estado: comando `0xFD` desde el endpoint 1 con payload `04 XX FF`, donde `XX` = `00` parado, `01` subiendo, `02` bajando. Mientras el motor se mueve lo repite cada ~2 s. Los IDs provienen de la app "Hunter Douglas Smart Shades" 2.2.4 de Solidmation (clase `HACommand_Constants`).

## Instalación

1. Copiar `custom_components/hpa4911` a `/config/custom_components/hpa4911` (reemplazando la versión de HACS de arpena, o quitándola de HACS primero).
2. Reiniciar Home Assistant.
3. Ajustes → Dispositivos y servicios → Agregar integración → **Local BGH Smart** → completar nombre, MAC, IP y elegir **Cortina (HPA-4202)**.
