# Costa 204 — manual de la casa para huéspedes (borrador)

Manual para huéspedes de **Home Exchange** y **Airbnb**. Es la base del instructivo impreso,
del mensaje de bienvenida de las plataformas y del asistente que responde preguntas.
Solo Costa 204. Espejo en Notion: [📖 Manual de uso](https://app.notion.com/p/415825a110c3817a9abdcc4e998142be).

Reglas de este documento:
- **Nada de claves en el repo** (Wi-Fi, alarma, cerraduras): se ponen como `‹se entrega aparte›`
  y se envían por la plataforma o por mensaje.
- Fotos en `fotos/`, sin datos de ubicación (EXIF/GPS) y con un máximo de 1600 px.
- Estado: ✅ completo · 🟡 parcial · ⬜ pendiente.

## Índice para el huésped

| # | Sección | Estado |
|---|---|---|
| 1 | Llegada y acceso (cerradura, horario, estacionamiento) | ⬜ |
| 2 | Wi-Fi, TV y parlantes | 🟡 |
| 3 | Luces y teclas, por ambiente | 🟡 (habitación principal) |
| 4 | Climatización: calefacción, ventiladores, aire del estar | ⬜ |
| 5 | Agua caliente (termotanques) y consumo eléctrico (limitador) | ⬜ |
| 6 | Cortinas | 🟡 |
| 7 | Pileta y jardín (riego automático) | ⬜ |
| 8 | Cocina y electrodomésticos | ⬜ |
| 9 | Basura y reciclaje | ⬜ |
| 10 | Seguridad: alarma, cámaras exteriores, qué hacer si suena | ⬜ |
| 11 | Reglas de la casa (Airbnb) / acuerdos del intercambio (Home Exchange) | ⬜ |
| 12 | Salida (check-out): checklist | ⬜ |
| 13 | Emergencias y contactos útiles (zona) | ⬜ |
| 14 | Recomendaciones de la zona | ⬜ |

## Diferencias por plataforma

- **Airbnb**: reglas, horario de llegada y salida, y check-out en el formato de la app.
  Las instrucciones de llegada se cargan en *Guía de llegada*.
- **Home Exchange**: tono de intercambio entre dueños; agregar qué se puede usar (bicis,
  despensa, etc.), cuidados de plantas y animales y cómo dejar la casa.
- Los dos usan la misma base técnica (secciones 2 a 10).

---

## 2. Wi-Fi, TV y parlantes 🟡

- Wi-Fi: red `‹se entrega aparte›` · clave `‹se entrega aparte›`.
- Al abrir la puerta por primera vez con su código, la casa los saluda por los parlantes.
- TV de la habitación principal: control TCL (ver más abajo).

## 3. Luces y teclas

### Cómo funcionan las teclas (toda la casa)

- Son teclas **de pulsar (push)**: se aprietan y vuelven solas. No quedan "arriba" o "abajo".
- **Pulsación corta**: prende o apaga.
- **Medias teclas dimerizables**: dejándolas **apretadas** sube o baja el brillo. Si se
  mantiene mucho tiempo, el brillo puede quedar casi en cero y parecer apagada: soltar y
  volver a mantener para subirlo, o revisar en la app.

### Habitación principal

#### Botonera junto a la cama, lado derecho (sobre la mesa de luz)

![Teclas junto a la cama, lado derecho](fotos/habitacion-principal-teclas-cama-derecha.jpg)

Dos placas, de izquierda a derecha:

| Placa | Posición | Qué maneja | Tipo |
|---|---|---|---|
| Izquierda (doble) | Media tecla de arriba | Velador derecho | Push, dimerizable |
| Izquierda (doble) | Media tecla de abajo | Luz del centro de la habitación | Push, dimerizable |
| Derecha | Tecla grande | Cortina | Push |

#### Controles remotos (en la mesa de luz)

**Control del televisor** (TCL, Google TV): encendido arriba a la derecha, volumen +/− en
el centro, accesos directos a Netflix, Prime Video, Disney+ y YouTube; botón de Google
Assistant para buscar por voz.

![Control del TV](fotos/habitacion-principal-control-tv.jpg)

**Control del ventilador de techo** (Sonoff, por radio, 8 botones): luz y ventilador,
encendido/apagado y velocidades. Funciona sin internet. *Pendiente confirmar qué hace cada
botón.*

![Control del ventilador](fotos/habitacion-principal-control-ventilador.jpg)

> Nota interna (no va al huésped): lo que se hace con este control **no** queda registrado
> como acción de Home Assistant. El encendido del ventilador del 10/11 22:23 sin autor
> visible probablemente vino de acá.

Fotos: 10/11/2026.

---

## Pendientes para completar

- Fotos y mapa de teclas del resto de los ambientes (estar, cocina, comedor, galería,
  dormitorios 1 y 2, baños, hall, exterior).
- Botones del control del ventilador; cómo se usa la tecla de la cortina (toque o mantener).
- Secciones ⬜ del índice: datos que tiene que pasar el dueño.
