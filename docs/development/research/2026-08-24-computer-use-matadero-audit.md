# Investigación QLab mediante Computer Use — MATADERO

**Fecha:** 2026-08-24
**Estado:** snapshot de inspección GUI; no se modificó código ni configuración de QLab.
**Método:** Computer Use con `@oai/sky` (`get_app_state`, clics, desplazamiento y lectura de controles). No se usaron OSC, AppleScript ni llamadas MCP para obtener estos datos.

## Resultado corto

La petición `Matadero` quedó resuelta en QLab como el workspace:

```text
MATADERO - FILAR.qlab5
file:///Users/filarmonica/Documents/Qlab/5.5/MATADERO%20-%20FILAR.qlab5
Workspace UUID: A192C068-0974-4624-90BD-56D68BF0286B
```

La ventana muestra **1802 cues en 8 listas**. La inspección encontró **205 Broken Cues and Warnings**. El proyecto es un show teatral completo: grupos anidados, cues temporizados de iluminación, vídeo, sonido, texto, fades, Start/Stop y una lista pequeña de pruebas.

No se hizo GO, Preview, Send, Panic, creación, borrado ni edición de cues. La única interacción fue navegar por listas, pestañas y diagnósticos para leerlos y guardar capturas. Las vistas Network/OSC Access no se guardaron porque muestran passcodes; sus valores quedan deliberadamente fuera de este informe.

## Capturas

Todas las capturas se guardaron en [`assets/matadero-2026-08-24`](assets/matadero-2026-08-24/). Las más representativas son:

- [`main-workspace.jpeg`](assets/matadero-2026-08-24/main-workspace.jpeg): ventana principal y las ocho listas.
- [`full-show.jpeg`](assets/matadero-2026-08-24/full-show.jpeg): secuencia anidada del show.
- [`workspace-status.jpeg`](assets/matadero-2026-08-24/workspace-status.jpeg): 205 warnings/broken cues.
- [`settings-general.jpeg`](assets/matadero-2026-08-24/settings-general.jpeg): reglas de GO, panic y auto-numbering.
- [`settings-video-outputs.jpeg`](assets/matadero-2026-08-24/settings-video-outputs.jpeg): stages de vídeo offline.
- [`settings-light-patch.jpeg`](assets/matadero-2026-08-24/settings-light-patch.jpeg): patch Art-Net e instrumentos.
- [`lx-warmup-levels.jpeg`](assets/matadero-2026-08-24/lx-warmup-levels.jpeg): valores de un cue Light.
- [`pruebas-intro.jpeg`](assets/matadero-2026-08-24/pruebas-intro.jpeg): lista de pruebas de iluminación.
- [`mcp-fixtures.jpeg`](assets/matadero-2026-08-24/mcp-fixtures.jpeg): fixtures internos de grupos y Wait.
- [`main-test-fixtures.jpeg`](assets/matadero-2026-08-24/main-test-fixtures.jpeg): comprobación posterior del workspace y de la lista `__MCP GROUP TEST FIXTURES`.
- [`status-warnings-refresh.jpeg`](assets/matadero-2026-08-24/status-warnings-refresh.jpeg): comprobación posterior de la pestaña Warnings.
- [`scripts.jpeg`](assets/matadero-2026-08-24/scripts.jpeg): los dos Network cues de `Scripts`.
- [`video-av4-io.jpeg`](assets/matadero-2026-08-24/video-av4-io.jpeg), [`audio-sfx4-io.jpeg`](assets/matadero-2026-08-24/audio-sfx4-io.jpeg) y [`text-txt1.jpeg`](assets/matadero-2026-08-24/text-txt1.jpeg): inspector de vídeo, audio y texto.

También se capturaron las pestañas de estado, controles, auditoría, plantillas, audio, vídeo, luz y MIDI; los nombres exactos están en el directorio de assets.

## Inventario de listas

| Lista | Hijos observados | Señal principal |
|---|---:|---|
| `Full show` | 22 | Timeline teatral con grupos y acciones de transporte. |
| `Videos` | 4 | `AV1`–`AV4`, cues Video de transporte. |
| `Sonido` | 25 | SFX Audio y Fades de 2–3 s. |
| `Texto` | 47 | Text, Start, Stop y Fade; grupos de textos y glitches. |
| `LX` | 83 | Light cues y grupos/chases temporizados. |
| `Scripts` | 2 | Network `+1dB` y `-1dB`. |
| `Pruebas intro` | 27 | Pruebas Light con pre-waits y comandos por instrumento. |
| `__MCP GROUP TEST FIXTURES` | 3 | Fixtures de Group/Wait, incluyendo un grupo de 378 hijos. |

La barra lateral expone `8 Cue Lists`, `0 Active Cues`, `New Cart` y `New List`. En este workspace no se observó ningún cart existente; no se creó ninguno.

## Comportamiento observado

### Full show

El show está construido como una secuencia de grupos anidados. Aparecen, entre otros:

- `LX0 · OSCURO`, `LXP · PASADA` y cues Light con duraciones de 2–5 s.
- Grupos `ENTRADA DE PÚBLICO`, `INICIO SHOW`, `SECUENCIA INICIO Y CASA`, `Secuencia musica intro` y numerosas secuencias de escena.
- Audio, Fade, Start y Stop para cortinilla, texto de telón, actos, playlists y SFX.
- Pre-waits fraccionarios y largos (por ejemplo 7.303 s, 16.719 s y 28.824 s), lo que confirma que el timing está distribuido entre cue y grupo, no sólo en el nombre.

El patrón útil para el MCP es `Group → hijos temporizados → acciones de transporte`, con números alfanuméricos, decimales y nombres operativos.

### Vídeo

`Videos` contiene:

- `AV1` → `ENTRE-ACTOS.mp4`, stage `FULL NO WARP (Output 1)`.
- `AV2` → `sulfataton teatro.mp4`, stage `Cortina (Output 1)`.
- `AV3` → `PROYECTO_GLITCH.mp4`, stage `FULL NO WARP (Output 1)`.
- `AV4` → `Matadero Intro final.mp4`, stage `FULL NO WARP (Output 1)`.

Los cuatro cues tienen duración 0 y actúan como transporte. Sus targets apuntan a rutas absolutas bajo `/Users/david/Documents/QLab/Norbayu/Matadero/MATADERO/...`; esto es un riesgo directo de portabilidad.

### Audio

`Sonido` separa Audio y Fade. Por ejemplo, `SFX4` apunta a `03. LOOP.mp3`; el inspector muestra `Patch 1`, dispositivo `External Headphones - (2 Out) - (disconnected)` y formato sin frecuencia válida. Los Audio cues observados tienen duración 0; los Fades duran 2–3 s.

### Texto

`Texto` combina textos completos, grupos de palabras/sílabas, Start/Stop y Fades. `TXT1` contiene el texto de telón en cuatro líneas, centrado, con tamaño 1370×352. Hay grupos para `PLAYLIST EMILIO`, `SILABAS`, `TEXTOS PRIMERA PARTE CHASE`, glitches, personajes y el texto final temporizado.

### Iluminación

`LX` contiene 83 hijos. Los primeros cues (`LX1`–`LX17`) son estados de sala, frontales, sombras, pares y contras; después aparecen grupos como `GL1`, `GL2`, `RND1`, `GL3`, `GL4`, `GL5`, `GL6`, `GL7` y `GL10` para glitches, chases, flicker y pulsos.

El cue `LX · Warm up` muestra comandos por instrumento (`48 Cabina`, `49 Cabina`, `all`, `47 Sombras`) en la pestaña Levels. `Pruebas intro` muestra el modelo más explícito: una Light cue con 36 instrumentos y valores como `home` o `80`.

El Light Patch usa Art-Net Universe 1 / Net 0 / Sub-Net 0, con grupos como `Boca`, `CalleDCHA`, `CalleIZQ`, `FrontalCalido`, `FrontalFrio`, `PUENTEFRONTAL`, `V1Calido`, `V1Frio`, `V2Calido`, `V2Frio` y `VARA3`. Varias filas aparecen sobreescritas y las definiciones locales incluyen `Generic → Dimmer`.

### Scripts y fixtures MCP

`Scripts` contiene dos Network cues:

- `+1dB`: mensaje OSC visible `/cue/selected/level/0/0/+ 1`.
- `-1dB`: cue equivalente para decremento.

La lista `__MCP GROUP TEST FIXTURES` confirma tres estructuras de prueba:

- cue `4`, Group timeline, 2 hijos, duración 5 s: Wait de 2 s con post-wait 2 s y Wait de 5 s con post-wait 5 s;
- cue `7`, Group timeline, 2 hijos, duración 3 s: Wait 0 s y Wait 3 s con post-wait 3 s;
- cue `8`, Group timeline, 378 hijos, duración 1 s, colapsado.

El inspector de Group expone los modos `Timeline`, `Start first and enter`, `Start first`, `Start random` y `Playlist`. En los fixtures observados, el modo activo es `Timeline`: inicia todos los hijos simultáneamente y avanza el playhead al siguiente cue/secuencia.

## Estado, settings y dependencias

### Warnings

Workspace Status reporta **205 Broken Cues and Warnings**. Las causas visibles incluyen:

- targets de archivos ausentes;
- patch de audio desconectado;
- stages y rutas de vídeo sin destino/offline;
- `Video Outputs Settings` sin stage válido;
- instrumentos Light sin patch;
- `Light Patch` con problemas;
- cues flagged como `27 · SECUENCIA SHOCK`, `43.5 · TRANSFORMACION DOÑA EMILIA`, `LX51 · LUZ EMILIA CON NITO ARRIBA` y varios Start cues;
- falta de nodos Art-Net en la pestaña de diagnóstico.

Los warnings son evidencia de readiness incompleta, no una prueba de que todos sean fallos de producción: algunos cues están marcados intencionalmente.

### Settings de workspace

- General: mínimo entre GO `0` s, key-up requerido, panic `1` s, auto-numbering `+1`, auto-load off y playhead bloqueado a selección.
- File Management: backups automáticos, backup antes de guardar y rotación activados; **Copy files into project folder when adding: off**.
- Display: filas de lista y botones de cart en tamaño Medium; Active Cues ordenados por “Most recently started last”.
- Audition: audio sin cambio, vídeo redirigido a Audition, MIDI/timecode/network sin salida, Light redirigido a Audition y cues con patch sin efecto.
- Collaboration: activado en `192.168.1.32`, pedir aprobación a colaboradores nuevos y Show Mode view-only.
- Workspace MIDI: MSC activado, device ID 0, sin mappings; MIDI Voice Messages musical off.
- MSC Broadcast: activado para GO/Reset/Stop/Panic, pero sin destinos configurados.
- MIDI Outputs: sin patches.
- Video Inputs: cámara del Mac desconectada.
- Output Devices: sólo la pantalla Retina integrada (2940×1912, 60 fps).
- Output Routing: `Output 1` 3024×1964 hacia `EPSON PJ (missing)`.
- Video Outputs: seis stages (`TELON`, `Cortina`, `Cortina L`, `Cortina R`, `FULL NO WARP`, `CUADRADO A BOCA`) hacia `EPSON PJ [offline]`.

Las pantallas Network Outputs y OSC Access se inspeccionaron sólo para conocer la topología. Mostraban OSC en el puerto 53000 y una ruta UDP local a `localhost:53000`, pero los passcodes fueron omitidos y no se serializaron.

## Implicaciones para el MCP

1. Resolver siempre el UUID exacto antes de leer o escribir; `Matadero` es un alias humano y el archivo real contiene `MATADERO - FILAR`.
2. Convertir Workspace Status en readiness tipada: archivo, patch, stage, route, device, target, Light instrument, Art-Net, MIDI y MSC.
3. Validar la gráfica de infraestructura separada de las propiedades del cue. Un cue puede estar bien formado y seguir siendo no ejecutable por falta de stage, dispositivo o archivo.
4. Mantener tipos de cue explícitos: Group/Playlist, Light, Audio, Video, Text, Fade, Start/Stop, Wait y Network tienen propiedades y riesgos distintos.
5. Preservar números y nombres tal como aparecen (`LX0`, `AV4`, `SFX4`, `TXT1`, `LX51`, `43.5`); no asumir que todo cue number es un entero.
6. Tratar rutas absolutas de medios como un problema de portabilidad y ofrecer diagnóstico antes de cualquier mutación.
7. Separar inspección, Preview, Send y GO. Un read o readiness check del MCP no debe disparar outputs.
8. Redactar siempre passcodes de OSC/Network en logs, resultados, capturas y documentación.
9. Exponer diagnósticos con frescura y límites: Logs están vacíos con sus toggles off, Art-Net no descubre nodos y Video Metrics no tiene filas; ninguno de esos estados demuestra por sí solo que el show esté listo.

## Límites

- Es una fotografía del estado GUI del 24-08-2026; no sustituye una prueba actual de OSC, hardware o salida física.
- No se dispararon cues ni se modificó ningún setting.
- No se guardaron capturas de Network/OSC Access para no conservar credenciales.
- Las rutas y dispositivos offline explican parte de los warnings, pero la relación causal completa debe comprobarse con una prueba de readiness controlada.

## Referencias

- Manual local: [`docs/sources/qlab-5.5.10/reference/QLab_5_Reference_Manual.local-snapshot.pdf`](../../sources/qlab-5.5.10/reference/QLab_5_Reference_Manual.local-snapshot.pdf)
- Diccionario OSC local: [`docs/sources/qlab-5.5.10/osc/qlab_osc_dictionary.repository.md`](../../sources/qlab-5.5.10/osc/qlab_osc_dictionary.repository.md)
- [QLab 5 Workspace Settings](https://qlab.app/docs/v5/fundamentals/workspace-settings/)
- [QLab 5 OSC Dictionary](https://qlab.app/docs/v5/scripting/osc-dictionary-v5/)
