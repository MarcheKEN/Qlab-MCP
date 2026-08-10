# Lighting, networking, MIDI y timecode

La documentación agrupa `Light Cues`, `Light Dashboard`, `Light Patch Editor`, `Network cues`, `MIDI cues`, `MIDI File cues`, `Timecode cues`, `Using MIDI & MSC`, `Using Timecode` y `Show control broadcast`.

## Fade cues

Un **Absolute Fade** (predeterminado) lleva cada parámetro activo a su nivel final, independientemente del valor inicial. Un **Relative Fade** suma/resta o multiplica/divide respecto al valor activo; por eso el punto de partida importa y repetirlo puede acumular cambios. En QLab 5 los absolute fades supersede relative fades. Fuente: [Fading Video and Video Effects](https://reference.qlab.app/docs/v5/video/fading-video/) y [Fading Audio and Audio Effects](https://reference.qlab.app/docs/v5/audio/fading-audio/).

En `Workspace Settings`, los tabs `Network`, `MIDI` y `OSC` son configuración del workspace. Los permisos de OSC se gestionan en `Network → OSC Access`; la página conceptual de OSC explica el flujo y la skill OSC separada contiene el diccionario exacto.

Fuentes oficiales:

- [Lighting](https://reference.qlab.app/docs/v5/lighting/)
- [Using MIDI and MSC](https://reference.qlab.app/docs/v5/networking/using-midi-and-msc/)
- [Using Timecode](https://reference.qlab.app/docs/v5/networking/using-timecode/)
- [Workspace Settings](https://reference.qlab.app/docs/v5/fundamentals/workspace-settings/)
- [QLab 5 Manual](https://reference.qlab.app/docs/v5/)

No uses esta página para inventar comandos de control. La reproducción, Audition, Stop/Panic y show control requieren una fuente específica y una validación separada.
