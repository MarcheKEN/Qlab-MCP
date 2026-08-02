---
name: qlab-5-applescript
description: "Consulta exacta del AppleScript Dictionary de QLab 5 para localizar comandos, clases, propiedades, elementos, enumeraciones, records, sintaxis y ejemplos."
---

# QLab 5 AppleScript Dictionary

Usa esta skill para responder preguntas sobre nombres y firmas AppleScript de
QLab 5. Conserva literalmente mayúsculas, espacios, identificadores, tipos,
parámetros y código.

## Fuente y autoridad

- Fuente oficial: [QLab AppleScript Dictionary](https://qlab.app/docs/v5/scripting/applescript-dictionary-v5/).
- Copia del repositorio: [`docs/references/qlab_applescript_dictionary.md`](../../docs/references/qlab_applescript_dictionary.md).
- Copia portable: [`references/qlab_applescript_dictionary.md`](references/qlab_applescript_dictionary.md).
- Procedencia y hashes: [`references/source-manifest.json`](references/source-manifest.json).

La página oficial sigue siendo la autoridad. El snapshot local documenta QLab 5,
pero no demuestra un patch concreto.

## Navegación exacta

1. Lee [`chapters/navigation.md`](chapters/navigation.md) para elegir la sección.
2. Busca primero el literal en la copia completa:
   `rg -n '^## go$|^## workspace$|fontName|com.figure53.QLab.5' references/qlab_applescript_dictionary.md`.
3. Para una entrada, conserva sus bloques `Syntax`, `Result`, `Parameters`,
   `Classes`, `Properties`, `Elements`, `Where Used` y `Examples`.
4. Distingue la **QLab Suite** de la **Standard Suite**. No atribuyas a QLab
   un comando estándar sin indicarlo.

## Reglas de seguridad y exactitud

- No inventes comandos, propiedades, tipos ni ejemplos por analogía.
- No confundas el nombre de una clase con un cue number o un unique ID.
- No ejecutes AppleScript ni modifiques QLab desde esta skill.
- Separa lo que confirma el diccionario de cualquier comportamiento runtime no
  verificado.
- Si la entrada no aparece, responde: `Not found in the supplied QLab AppleScript Dictionary.`
