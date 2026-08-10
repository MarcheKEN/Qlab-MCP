---
name: qlab-5-5-10-osc
description: "Navegación exacta del QLab 5 OSC Dictionary para buscar direcciones, argumentos, tipos, permisos view/edit/control/query, replies, update notifications, workspace prefixes, selected cues, /live y +/-; úsala para cualquier pregunta OSC de QLab 5.5.10 y nunca inventes una ruta no encontrada."
---

# QLab 5.5.10 OSC Dictionary

Usa el diccionario suministrado para localizar y citar sintaxis exacta. El contenido es técnico: conserva slashes, mayúsculas, nombres de propiedades, orden de argumentos, `live`, `+`, `-`, wildcards y JSON.

## Fuentes

- Fuente oficial: [QLab's OSC Dictionary](https://reference.qlab.app/docs/v5/scripting/osc-dictionary-v5/).
- Copia del repositorio: [`docs/references/qlab_osc_dictionary.md`](../../docs/references/qlab_osc_dictionary.md).
- Copia portable de esta skill: [`references/qlab_osc_dictionary.md`](references/qlab_osc_dictionary.md).
- Procedencia: [`references/source-manifest.json`](references/source-manifest.json).

La página oficial es la autoridad. El manifest del repositorio identifica la copia importada como `QLab 5; exact patch unknown`; por tanto, el nombre de la skill no debe ocultar esa incertidumbre del patch. Para afirmaciones específicamente nuevas de 5.5.10, comprueba la página oficial y el change log.

## Búsqueda determinista

1. Busca primero el literal (`rg -n '^### /cue/.*/preWait|/preWait' references/qlab_osc_dictionary.md`).
2. Confirma la línea de sintaxis, la tabla `view | edit | control | query | +/-? | Live`, descripción y ejemplos.
3. Distingue acción, lectura, escritura, query, reply y notification.
4. Comprueba el target: `cue_number`, `cue_id`, `selected`, playhead, wildcard o `/workspace/{id}`.
5. Si no hay entrada, responde literalmente: `Not found in the supplied QLab OSC Dictionary.` No generes una ruta por analogía.

## Reglas críticas

- `Live` va siempre al final: `/cue/x/opacity/+/live`, no `/cue/x/opacity/live/+`.
- `+/-` acepta forma de argumento y, desde QLab 5.5, forma incluida en la dirección cuando la entrada lo permite.
- `/selected` y cue number no son equivalentes a unique cue ID.
- Los mensajes sin workspace prefix pueden llegar a todos los workspaces que escuchen ese puerto; usa UUID exacto cuando el aislamiento importe.
- Reply y update no son lo mismo: replies responden a un mensaje; `/update/...` notifica cambios solicitados.
- Revisa permisos y passcode antes de cualquier escritura. Esta skill no autoriza envío OSC ni conexión runtime.

## Índice por intención

| Intención | Referencia |
|---|---|
| transporte, updates, replies, booleans, live, +/- | [Navigation](chapters/navigation.md) |
| aplicación, workspace, cue, Group, Audio, Video, Camera, Text, Light, Fade, Network, MIDI, Timecode, Script | copia exacta del [Dictionary](references/qlab_osc_dictionary.md) |
| muestras auditables | [Samples](chapters/samples.md) |
| conceptos generales de QLab | [qlab-5-5-10-reference](../qlab-5-5-10-reference/SKILL.md) |
