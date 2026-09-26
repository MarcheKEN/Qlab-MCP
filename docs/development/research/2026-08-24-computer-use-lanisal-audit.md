# Investigación QLab mediante Computer Use — Memoria de la nisal

**Fecha:** 2026-08-24

**Estado:** snapshot de inspección GUI; no se modificó código ni configuración de QLab.

**Método:** Computer Use con `@oai/sky` (`get_app_state`, clics, desplazamiento y lectura de controles). No se usaron OSC, AppleScript ni llamadas MCP para obtener estos datos.

## 1. Identidad confirmada

El nombre que QLab muestra en Launcher/Window es:

```text
Memoria de la nisal - Filarmónica.qlab5
file:///Users/filarmonica/Documents/Qlab/5.5/Memoria%20de%20la%20nisal%20-%20Filarmónica/Memoria%20de%20la%20nisal%20-%20Filarmónica.qlab5
Workspace UUID: 2BE85FBF-91A8-49AE-9617-C58B3332BF92
```

Ésta es la coincidencia encontrada para la petición aproximada “Memoria de LANISAL”. El workspace muestra **311 cues en 5 listas**. No se guardó el Machine ID que aparece en la pestaña Info.

La ventana principal se abrió en `Master`, con el standby `0.5 · start PASADA`. El workspace tiene GO, toolbox, lista central, sidebar, inspector, Warnings, Settings y los controles globales Reset/Pause/Resume/Panic.

## 2. Inventario de listas

| Lista | Hijos observados | Contenido |
|---|---:|---|
| `Master` | 151 | Secuencia principal con Memo, Start, Audio y Fade. |
| `Música` | 13 | FX1–FX13, Audio de duración larga y un Fade. |
| `Lluces` | 68 | Cues Light por escena, Memo de separación y transiciones. |
| `sfx bombilla` | 13 | SFX cortos en WAV, FLAC, OGG y MP3. |
| `sfx whoosh` | 2 | Audio `whoosh_01.mp3` y Memo con una URL de YouTube. |

El sidebar indica `5 Cue Lists`, `0 Active Cues`, `New Cart` y `New List`. No se dejó ningún cart persistente: `New Cart` se probó de forma reversible y se deshizo; el workspace volvió a `5 Cue Lists`.

Capturas principales:

- [`main-lights.jpeg`](assets/lanisal-2026-08-24/main-lights.jpeg): lista `Lluces` y su inspector Light.
- [`music-list.jpeg`](assets/lanisal-2026-08-24/music-list.jpeg): lista de música.
- [`master-list.jpeg`](assets/lanisal-2026-08-24/master-list.jpeg): secuencia `Master`.
- [`sfx-bombilla.jpeg`](assets/lanisal-2026-08-24/sfx-bombilla.jpeg) y [`sfx-whoosh.jpeg`](assets/lanisal-2026-08-24/sfx-whoosh.jpeg): listas de efectos.
- [`show-mode.jpeg`](assets/lanisal-2026-08-24/show-mode.jpeg): misma lista en Show Mode.

## 3. Cues e inspector

### Lluces / Light

La lista `Lluces` alterna estados de iluminación y Memos de escena. Se observan números `LX1`, `LX1.5`, `LX2`, `LX10.5`, `LX37.1`, `LX37.2`, etc.; el número de cue puede ser decimal.

El cue `kabuki on` muestra:

- duración `00:05.000`, sin target, `Do not continue`;
- pestaña Levels en modo Text con el comando `35 kabuki=100`;
- pestaña Curve con `Custom Curve` y duración 5 s;
- hotkey `6` activo;
- MIDI, Wall Clock y Timecode triggers desactivados;
- segundo trigger al soltar desactivado y, si corre, segunda activación configurada como `does nothing`;
- `Fade & stop` y ducking de audio desactivados.

Capturas: [`light-levels.jpeg`](assets/lanisal-2026-08-24/light-levels.jpeg), [`light-curve.jpeg`](assets/lanisal-2026-08-24/light-curve.jpeg) y [`light-triggers.jpeg`](assets/lanisal-2026-08-24/light-triggers.jpeg).

### Audio

`Música` contiene Audio con targets dentro del propio proyecto. `FX1` apunta a `audio/1.- Obertura.mp3`, dura `02:38.824` y está configurado como `Auto-continue`.

Su inspector mostró:

- I/O: patch `Main - UMC202HD 192k - (2 Out) - (disconnected)`;
- archivo MP3, 2 canales a 44100 Hz; salida mostrada como `2 out @ (null) Hz`;
- Time & Loops: media sliced, play count 1, loop infinito off, integrated fade off, rate 1 y preserve pitch off;
- Levels: crosspoint `main=0`, canales de salida 1–12 a `1`, gangs off;
- Objects: audio map `(no map)`, lista vacía, `Add Audio Object` disponible;
- Trim: ajuste global que no puede ser cambiado por Fade cues, con mute/solo por canal;
- Audio FX: ningún efecto.

Capturas: [`audio-io.jpeg`](assets/lanisal-2026-08-24/audio-io.jpeg), [`audio-time-loops.jpeg`](assets/lanisal-2026-08-24/audio-time-loops.jpeg), [`audio-levels.jpeg`](assets/lanisal-2026-08-24/audio-levels.jpeg), [`audio-objects.jpeg`](assets/lanisal-2026-08-24/audio-objects.jpeg), [`audio-trim.jpeg`](assets/lanisal-2026-08-24/audio-trim.jpeg) y [`audio-fx.jpeg`](assets/lanisal-2026-08-24/audio-fx.jpeg).

### Fade

`FX2` (`fade 1.- Obertura.mp3`) tiene duración 5 s y target `FX1` por modo `Cue`. La pestaña Curve usa `S-Curve`, dominio `Slider`, y `Stop target when done` está off. La pestaña Levels usa modo `Absolute`, `main=1`, canales 1–12 a `0`, y `Stop target when done` off.

Capturas: [`fade-curve.jpeg`](assets/lanisal-2026-08-24/fade-curve.jpeg) y [`fade-levels.jpeg`](assets/lanisal-2026-08-24/fade-levels.jpeg).

### Memo y Start

- `ESCENA 01` es un Memo sin número, sin target, duración 0 y `Do not continue`.
- En `sfx whoosh`, un Memo usa como nombre `https://www.youtube.com/watch?v=4zRbWNtd05w`; no es un cue de reproducción web.
- El Start `0.5 · start PASADA` tiene target `LX1 / PASADA`, target mode `Cue`, duración 0 y `Do not continue`.

Capturas: [`memo-scene.jpeg`](assets/lanisal-2026-08-24/memo-scene.jpeg), [`memo-youtube.jpeg`](assets/lanisal-2026-08-24/memo-youtube.jpeg) y [`start-cue.jpeg`](assets/lanisal-2026-08-24/start-cue.jpeg).

### Master

`Master` es una timeline de 151 hijos. El comienzo visible es:

```text
SC0 Memo ESCENAS
SFX0 Memo EFECTOS SONIDO
0 Memo MÚSICA
LX0 Memo MEMORIAS LUCES
0.5 Start PASADA
0.7 Start PASADA SALA
SC1 Memo ESCENA 01 - Inicio
1 Audio Pista 01 (02:01.533)
Fade Pista 01 (1.5 s)
0.6 Start OSCURO SALA
Start VA SUBIENDO LUZ
2 Audio Pista 02 (34.853 s)
Fade Pista 02 (2 s)
Start APARICIÓN DE BEA (pre-wait 14 s)
```

El patrón es una secuencia de Memos de escena seguida de Start/Audio/Fade, con pre-waits y post-waits que forman el timing. El Group raíz `Master` aparece como lista con 151 hijos; su inspector expone Basics, Triggers y Timecode.

### Tipos no presentes en las listas observadas

El toolbox y el menú `Cues` exponen Group, Audio, Mic, Video, Camera, Text, Light, Fade, Network, MIDI, MIDI File, Timecode, Start, Stop, Pause, Load, Reset, Devamp, GoTo, Target, Arm, Disarm, Wait, Memo y Script. En este workspace no se observó ningún cue Video, Camera, Text, Network, MIDI, MIDI File, Timecode o Script en las cinco listas; sí están disponibles como tipos de creación.

El menú `Cues` confirma los 25 tipos y usa la acción `buildCueFromMenuSelection`. Al elegir `Memo` se creó inmediatamente un `(Untitled Memo Cue)` y el contador pasó temporalmente a `312 cues in 5 lists`; se deshizo desde `Edit → Deshacer Create 1 Memo Cue`, quedando de nuevo en `311 cues`. Esto documenta el comportamiento de `New Cue` sin dejar una mutación.

## 4. Workspace Status

Workspace Status reporta **131 Broken Cues and Warnings**.

Lo más importante:

- Patch de audio `Main - UMC202HD 192k - (2 Out) - (disconnected)`; causa 70 warnings y detalle “Audio output device missing”.
- Al expandir esa causa aparece `1 · Pista 01` con “Issue with audio output patch”.
- Varios `fade fx viento 2` aparecen flagged.
- `start COCINA NOCHE` está flagged y contiene la nota `Termina el B.O. ¿cuando entro?`.
- Muchos cues Light (`B.O.`, `LX1`, `LX1.5`, `LX2`, etc.) reportan `Missing USB DMX device` para `ENTTEC DMX USB PRO - EN429755`.
- `Light Patch` reporta problemas y causa dos warnings adicionales.

Pestañas:

- Logs: Cue triggers, OSC input/output y MIDI input están off; área vacía.
- Triggers: hotkeys locales `6 → kabuki on`, `7 → kabuki off`, `Ñ → B.O. · B.O.`, `0 → whoosh_01.mp3`; controles workspace Space/V/⌥Space/⌥V/L/S/P/[ /]/N/Q/O/T/⌥T/E/D/W/C/F.
- Art-Net: tabla vacía, ningún nodo encontrado.
- Video Metrics: tabla vacía, sin métricas activas.
- Info: UUID confirmado; Machine ID omitido.

Capturas: [`status-warnings.jpeg`](assets/lanisal-2026-08-24/status-warnings.jpeg), [`status-warning-expanded.jpeg`](assets/lanisal-2026-08-24/status-warning-expanded.jpeg), [`status-logs.jpeg`](assets/lanisal-2026-08-24/status-logs.jpeg), [`status-triggers.jpeg`](assets/lanisal-2026-08-24/status-triggers.jpeg), [`status-artnet.jpeg`](assets/lanisal-2026-08-24/status-artnet.jpeg), [`status-video-metrics.jpeg`](assets/lanisal-2026-08-24/status-video-metrics.jpeg), [`status-warnings-second-pass.jpeg`](assets/lanisal-2026-08-24/status-warnings-second-pass.jpeg), [`status-logs-second-pass.jpeg`](assets/lanisal-2026-08-24/status-logs-second-pass.jpeg), [`status-triggers-second-pass.jpeg`](assets/lanisal-2026-08-24/status-triggers-second-pass.jpeg), [`status-artnet-second-pass.jpeg`](assets/lanisal-2026-08-24/status-artnet-second-pass.jpeg) y [`status-video-metrics-second-pass.jpeg`](assets/lanisal-2026-08-24/status-video-metrics-second-pass.jpeg).

## 5. Edit Mode y Show Mode

En Edit Mode están visibles toolbox, inspector, sidebar y controles de edición. Al cambiar a Show Mode:

- el toolbox queda deshabilitado/oculto;
- el inspector queda deshabilitado;
- la lista y el GO permanecen visibles;
- los controles globales Reset/Pause/Resume/Panic siguen presentes;
- el workspace continúa mostrando `311 cues in 5 lists`.

No se pulsó GO, Preview, Send, Panic ni ningún botón de salida. Se guardaron capturas adicionales de ambos modos: [`mode-edit-second-pass.jpeg`](assets/lanisal-2026-08-24/mode-edit-second-pass.jpeg) y [`mode-show-second-pass.jpeg`](assets/lanisal-2026-08-24/mode-show-second-pass.jpeg).

## 6. Workspace Settings

### General, File Management y Display

- General: no hay cue de apertura/cierre; mínimo entre GO `0` s; key-up requerido; panic `1` s; auto-numbering on con incremento `1`; auto-load off; playhead bloqueado a selección.
- File Management: backups automáticos, backup antes de guardar y rotación activados; tamaño mostrado `17 MB`; **Copy files into project folder when adding: on**.
- Display: filas de lista y botones de cart en Medium; Active Cues ordenados por “Most recently started last”.

Capturas: [`settings-general.jpeg`](assets/lanisal-2026-08-24/settings-general.jpeg), [`settings-file-management.jpeg`](assets/lanisal-2026-08-24/settings-file-management.jpeg) y [`settings-display.jpeg`](assets/lanisal-2026-08-24/settings-display.jpeg).

### Controls

- Keyboard conserva los shortcuts de GO, Preview, Audition, Load, Panic, Pause/Resume y edición de propiedades.
- Workspace MIDI: Musical Voice Messages off; canal Any; MSC on; Device ID 0; comandos GO/STOP/RESUME/LOAD/ALL_OFF/STANDBY/SEQUENCE/RESET disponibles; todos los mappings `None` y Capture off.
- OSC: comandos custom vacíos y Capture off; QLab responde sólo cuando OSC Access permite conexiones; botones OSC Access y OSC dictionary disponibles.

Capturas: [`settings-controls-keyboard.jpeg`](assets/lanisal-2026-08-24/settings-controls-keyboard.jpeg), [`settings-workspace-midi.jpeg`](assets/lanisal-2026-08-24/settings-workspace-midi.jpeg).

### Audition y Collaboration

- Audition: Audio deja la salida sin cambios; Video redirige a ventana Audition; MIDI, MTC, LTC y Network sin salida; Light redirige a Audition tab; cues con patch no se ejecutan.
- Collaboration: conexiones on en `192.168.1.32`; preguntar antes de un colaborador nuevo; Show Mode view-only; permisos por defecto Connect & View on, Edit/Control off; no hay clientes conectados.

Capturas: [`settings-audition.jpeg`](assets/lanisal-2026-08-24/settings-audition.jpeg) y [`settings-collaboration.jpeg`](assets/lanisal-2026-08-24/settings-collaboration.jpeg).

### Templates

Cue Templates lista todas las familias de cue. Defaults observados:

- Group, Mic, Video, Camera, MIDI, MIDI File, Start, Stop, Pause, Load,
  Reset, Devamp, GoTo, Target, Arm, Disarm, Memo y Script mantienen nombre
  editable, pre-wait/post-wait en `00:00.000`, `Do not continue`, notas y
  controles de armed/color; sus campos de target o duración dependen del tipo.
- Timecode tiene duración por defecto `01:00:03.600` y placeholder de nombre
  `1:00:00:00`.
- Light: duración 5 s, `Do not continue`.
- Audio: sin target y duración 0 hasta arrastrar un archivo.
- Fade: duración 3 s, target mode `Cue`, sin target.
- Network: nombre `1 · Patch 1 - {custom}`, duración 0.
- Wait: duración 1 s y post-wait 1 s.

El gestor de Workspace Templates muestra `Blank (default)` y `Default`. No se renombró, borró ni estableció ningún template.

Capturas: [`template-audio.jpeg`](assets/lanisal-2026-08-24/template-audio.jpeg), [`template-light.jpeg`](assets/lanisal-2026-08-24/template-light.jpeg), [`template-fade.jpeg`](assets/lanisal-2026-08-24/template-fade.jpeg), [`template-network.jpeg`](assets/lanisal-2026-08-24/template-network.jpeg), [`template-wait.jpeg`](assets/lanisal-2026-08-24/template-wait.jpeg), [`template-timecode.jpeg`](assets/lanisal-2026-08-24/template-timecode.jpeg), [`template-script.jpeg`](assets/lanisal-2026-08-24/template-script.jpeg) y [`template-manager.jpeg`](assets/lanisal-2026-08-24/template-manager.jpeg).

### Audio

- Outputs: patch `Main`, dispositivo `UMC202HD 192k - (2 Out) - (disconnected)`, límites +12/-60 dB.
- Inputs: `Patch 1`, `System Input - Micrófono del MacBook Air - (1 In)`.
- Maps: un mapa `Stereo`, con Edit/Monitor/Delete. El editor usa tamaño 1000×1000, marcas `Left (-400,0)` y `Right (400,0)`, sin audio patch y sin map objects. Los map objects serían compartidos entre cues y ajustables por Fade.

Capturas: [`settings-audio-outputs.jpeg`](assets/lanisal-2026-08-24/settings-audio-outputs.jpeg), [`settings-audio-inputs.jpeg`](assets/lanisal-2026-08-24/settings-audio-inputs.jpeg), [`audio-map-editor.jpeg`](assets/lanisal-2026-08-24/audio-map-editor.jpeg) y [`audio-map-objects.jpeg`](assets/lanisal-2026-08-24/audio-map-objects.jpeg).

### Video

- Video Outputs: un solo stage `Stage 1`, 2880×1800, `Pantalla Retina integrada`.
- Output Routing: `Output 1`, 2880×1800 fill to 2940×1912, device Retina, guide `full`, Show off.
- Output Devices: `Pantalla Retina integrada`, 2940×1912, 60 fps.
- Video Inputs: `Patch 1`, `FaceTime HD Camera - (disconnected)`.

Capturas: [`settings-video-outputs.jpeg`](assets/lanisal-2026-08-24/settings-video-outputs.jpeg), [`settings-output-routing.jpeg`](assets/lanisal-2026-08-24/settings-output-routing.jpeg), [`settings-output-devices.jpeg`](assets/lanisal-2026-08-24/settings-output-devices.jpeg) y [`settings-video-inputs.jpeg`](assets/lanisal-2026-08-24/settings-video-inputs.jpeg).

### Light

- Light Patch tiene instrumentos Art-Net en Universe 1 y también entradas USB DMX Universe 0; se observan grupos y dispositivos con nombres teatrales (`kabuki`, `contra led`, `frontal`, `Sala 1`, `999`, `final casa`, etc.).
- El panel informa `43 Instruments`, `12 Instruments`, `4 Instruments` y `4 Instruments` en varios grupos.
- Light Definitions locales: `Generic` contiene `Dimmer` y `RGBWA+UV`. `Dimmer` tiene parámetro `intensity`, Home `0%`, Use % on y 16-bit off.
- Light Dashboard MIDI: `No MIDI device`, con subcontrollers, `selected`, `all`, grupos e instrumentos.

Capturas: [`settings-light-patch.jpeg`](assets/lanisal-2026-08-24/settings-light-patch.jpeg), [`settings-light-definitions.jpeg`](assets/lanisal-2026-08-24/settings-light-definitions.jpeg), [`light-dimmer.jpeg`](assets/lanisal-2026-08-24/light-dimmer.jpeg) y [`settings-light-dashboard-midi.jpeg`](assets/lanisal-2026-08-24/settings-light-dashboard-midi.jpeg).

### Network y MIDI

- Network Outputs: `Patch 1`, OSC Message, UDP, Automatic, destino `localhost:53000`, con passcode configurado.
- OSC Access: conexiones on, IP `192.168.1.32`, puerto OSC `53000` TCP/UDP, respuestas UDP por defecto `53001`, Plain Text `53535` UDP; existe un passcode con View/Edit/Control activados y No Passcode está desactivado.
- MIDI Outputs: tabla vacía; botón New MIDI Patch.
- MSC Broadcast: activado para GO numerado y Reset/Stop/Panic All, pero sin destinos.

Los valores numéricos de passcode no se guardaron en capturas ni en este documento.

Capturas: [`settings-midi-outputs.jpeg`](assets/lanisal-2026-08-24/settings-midi-outputs.jpeg) y [`settings-msc-broadcast.jpeg`](assets/lanisal-2026-08-24/settings-msc-broadcast.jpeg). Las vistas Network/OSC Access se inspeccionaron por accesibilidad, pero no se capturaron por contener credenciales.

## 7. Menús y ventanas auxiliares

### Menús superiores

- **QLab:** About, Change Log, Updates, Preferences, Licenses, License Agreement, Demo Mode, Services, Hide/Show y Quit.
- **File:** New Workspace, New From Template, Open, Open Recent, Connect, Close, Save, Save As, Save As Template, Workspace Files, Workspace Settings por categorías, Import/Export Settings y Workspace Templates.
- **Edit:** Cut/Copy/Paste/Delete/Select All/Find, formato, spelling, speech, autofill y dictado.
- **Cues:** todos los tipos de cue del toolbox; elegir un tipo crea el cue inmediatamente. Se probó `Memo` y se revirtió mediante Undo.
- **Tools:** Load to time, Renumber, Delete numbers, Record cue sequence, Always audition, Live fade preview, Highlight related cues y fondos de escritorio.
- **View:** Full Screen, Inspector, Inspector for selected cue, GO/Standby/Toolbar, Toolbox, Lists/Carts/Active Cues, selección y navegación del playhead, movimiento de cues y Enter Show Mode.
- **Window:** Launcher Window, Workspace Status, Override Controls, Open All Audition Windows, Light Dashboard, Light Patch, Light Library, DMX Status, Timecode Status y Bring All to Front. `HID Info` no apareció en el menú ni en el árbol de accesibilidad de esta compilación QLab 5.5.10; el diagnóstico equivalente disponible es `Workspace Status > Info`, junto con las ventanas DMX y Timecode.
- **Help:** búsqueda, documentación QLab, tutoriales, soporte y updates.

### Launcher Window

El Launcher muestra QLab 5.5.10, Open Workspace, New Workspace, documentación, tutoriales, licencias y Recent Workspaces. La lista Recent Workspaces contiene `Memoria de la nisal - Filarmónica.qlab5` con su ruta completa, además de los workspaces inspeccionados anteriormente.

Captura: [`launcher-recent.jpeg`](assets/lanisal-2026-08-24/launcher-recent.jpeg).

### Override Controls

Todos los overrides globales estaban ON: Musical MIDI in/out, MSC in/out, SysEx in/out, Network External/Local in/out, Timecode input/output y DMX output.

Captura: [`override-controls.jpeg`](assets/lanisal-2026-08-24/override-controls.jpeg).

### Audition Output

`Open All Audition Windows` abrió `Audition Output: Stage 1`. La ventana es un monitor con `Clone this monitor window`, `Float off` y sin controles de salida; se cerró sin reproducir cues.

Captura: [`audition-output-stage1.jpeg`](assets/lanisal-2026-08-24/audition-output-stage1.jpeg).

### Light Dashboard

El dashboard abrió en `Live`, vista `Sliders`, selección `All`, sin cues Light ejecutados. Los botones `New Cue with Changes` y `Update` estaban deshabilitados; `New Cue with All` y `Record All` están disponibles; `Clear All` indica blackout a valores Home y no se pulsó. Se observaron grupos `00 Sala`, `999`, `contra led`, `final casa`, `frontal` e instrumentos como `1 Fake lámpara cocina`, `2 Lámpara`, `10 Cocina`, `16 bombilla`, `17 Cama` y `18 Puerta dormitorio`. La vista ofrece `Sliders` y `Tiles`, y la selección `All`/`Used`.

Captura: [`light-dashboard.jpeg`](assets/lanisal-2026-08-24/light-dashboard.jpeg).

### Light Library

La biblioteca muestra fabricantes y definiciones. Al abrir `American DJ` se observaron definiciones `15 Hex Bar IP - 12/14/17/30/33/38/41/6/60/9 channel` y `3 Sixty 2R`. La definición `15 Hex Bar IP - 12 channel` contiene parámetros red, green, blue, white, amber y uv en canales 1, 3, 5, 7, 9 y 11.

Captura: [`light-library.jpeg`](assets/lanisal-2026-08-24/light-library.jpeg).

### DMX y Timecode Status

- DMX Status abrió una ventana vacía, sin contenido de dispositivos.
- Timecode Status mostró tablas vacías de Incoming Timecode y Outgoing Timecode, botones Show y Float off.

Capturas: [`dmx-status.jpeg`](assets/lanisal-2026-08-24/dmx-status.jpeg) y [`timecode-status.jpeg`](assets/lanisal-2026-08-24/timecode-status.jpeg).

### Open in New Window

`Open in New Window` creó una ventana secundaria de `Master` sin sidebar ni inspector. Conserva GO, la lista central y un selector de lista con `Master`, `Música`, `Lluces`, `sfx bombilla` y `sfx whoosh`. Se cerró después de la inspección.

Capturas: [`master-secondary-window.jpeg`](assets/lanisal-2026-08-24/master-secondary-window.jpeg) y [`master-secondary-refresh.jpeg`](assets/lanisal-2026-08-24/master-secondary-refresh.jpeg).

### New List, New Cart y rollback

- `New List` creó directamente una lista vacía llamada `Cue List` y mostró temporalmente `6 Cue Lists`; se revirtió con Undo y el contador volvió a `311 cues in 5 lists`.
- `New Cart` creó directamente un cart vacío `Cue Cart`, cambió el sidebar a `5 Lists and 1 Cart` y mostró la cuadrícula de botones vacíos; también se revirtió con Undo.
- En ambos casos no se guardó el workspace ni se dejó contenido nuevo.

Capturas: [`new-list-created.jpeg`](assets/lanisal-2026-08-24/new-list-created.jpeg), [`new-cart-created.jpeg`](assets/lanisal-2026-08-24/new-cart-created.jpeg) y [`new-cue-memo-created.jpeg`](assets/lanisal-2026-08-24/new-cue-memo-created.jpeg).

## 8. Implicaciones para el MCP

1. Resolver el UUID exacto antes de cualquier operación; el alias “LANISAL” no es el nombre de archivo real.
2. Modelar readiness por dependencias: patch de audio, USB DMX, Art-Net, archivos, stages, rutas, cámara y destinos MSC.
3. Mantener separados Edit/Show, lectura, Preview, Send y GO. La navegación GUI no implica playback.
4. Preservar cue numbers decimales y alfanuméricos (`LX1.5`, `LX37.1`, `0.5`, `SC1`).
5. Tratar `Master` como timeline de transporte y no como simple lista plana: Memo → Start → Audio → Fade → pre/post-wait.
6. Exponer inspector por tipo: Light Levels/Curve/Triggers, Audio I/O/Loops/Levels/Objects/Trim/FX y Fade Curve/Levels.
7. El estado de `OSC Access` y Network Outputs demuestra que la autorización y los passcodes pertenecen a la capa de acceso, no al cue únicamente.
8. Redactar passcodes y Machine ID en resultados, logs, capturas y documentación.
9. Tratar logs vacíos, Art-Net vacío, Video Metrics vacío, DMX vacío y Timecode vacío como diagnósticos con límite, no como prueba global de funcionamiento.

## 9. Límites

- Snapshot del 24-08-2026; no valida hardware físico ni receptores de red.
- No se pulsaron GO, Preview, Send, Panic, Clear All, Record All, Delete, Save ni ningún control de salida. `New Cue`, `New List` y `New Cart` se probaron sólo con operaciones efímeras y se revirtieron mediante Undo.
- Network Outputs, OSC Access e Info fueron inspeccionados sin conservar passcodes ni Machine ID.
- El aviso USB DMX identifica un dispositivo ausente; no se concluye por ello que el patch lógico completo sea incorrecto.

## Referencias

- Manual local: [`docs/sources/qlab-5.5.10/reference/QLab_5_Reference_Manual.local-snapshot.pdf`](../../sources/qlab-5.5.10/reference/QLab_5_Reference_Manual.local-snapshot.pdf)
- Diccionario OSC local: [`docs/sources/qlab-5.5.10/osc/qlab_osc_dictionary.repository.md`](../../sources/qlab-5.5.10/osc/qlab_osc_dictionary.repository.md)
- [QLab 5 Workspace Settings](https://qlab.app/docs/v5/fundamentals/workspace-settings/)
- [QLab 5 OSC Dictionary](https://qlab.app/docs/v5/scripting/osc-dictionary-v5/)
