---
name: qclass-research
description: "Use when researching QLab topics covered by the imported Figure 53 QClass 5.5 transcripts in docs/qclass/. Load the local index first, search the relevant transcript, and report timestamped evidence without consulting other sources."
---

# QClass Research

Usa esta skill para investigar únicamente los transcriptos Markdown de las
clases QClass 5.5 de Figure 53 almacenados en `docs/qclass/`. Son registros de
clases en directo sobre QLab, no un manual normativo ni una prueba de
comportamiento runtime.

## Alcance y fuentes

La única fuente permitida es esta carpeta:

- `docs/qclass/README.md`, índice de días, temas y timestamps.
- `docs/qclass/September 2025 QClass 5.5 at the Voxel - Day 1.md`.
- `docs/qclass/September 2025 QClass 5.5 at the Voxel - Day 2.md`.
- `docs/qclass/September 2025 QClass 5.5 at the Voxel - Day 3.md`.

Los nombres `.txt` mencionados dentro de los Markdown son metadatos del
transcripto importado; no los trates como archivos disponibles. No consultes
otras carpetas del repositorio, documentación web, código, ni fuentes externas
para completar una respuesta QClass.

## Flujo obligatorio

1. Lee primero `docs/qclass/README.md`. Identifica el día y el tema más cercano
   a la pregunta; conserva el timestamp mostrado en el índice.
2. Busca términos concretos en el Markdown correspondiente. Por ejemplo:

   ```sh
   rg -n -i "geometry|camera|video fx" "docs/qclass/September 2025 QClass 5.5 at the Voxel - Day 2.md"
   ```

3. Lee el contexto alrededor de cada coincidencia con `sed -n` u otra lectura
   acotada. Si el tema cruza días, repite la búsqueda en cada transcripto y
   separa las evidencias por día.
4. Responde separando:
   - **Evidencia**: lo que el transcripto dice, con día, sección y timestamp.
   - **Interpretación**: síntesis o conexión razonable derivada del texto.
   - **Límites**: lo que no aparece o no puede confirmarse en estos transcriptos.
5. Si no encuentras evidencia suficiente, dilo explícitamente. No rellenes
   huecos con conocimiento general de QLab ni conviertas una explicación oral
   en una afirmación normativa.

## Reglas de lectura

- Conserva literalmente nombres de controles, cue types, comandos y términos
  técnicos cuando aparezcan en el texto; explica en español cuando convenga.
- No edites los transcriptos. Añade navegación solo al índice si el usuario lo
  solicita expresamente y mantiene intacto el texto importado.
- Esta skill es de investigación documental: no ejecuta QLab, no envía OSC o
  AppleScript y no autoriza cambios en workspaces, cues ni archivos de show.
- Si la pregunta necesita una fuente fuera de `docs/qclass/`, informa que está
  fuera del alcance de QClass en vez de consultarla automáticamente.

## Formato recomendado

```text
Fuente: Day N — <tema/sección> — <timestamp>
Evidencia: <paráfrasis breve o cita corta del transcripto>
Interpretación: <síntesis, si procede>
Límites: <qué no confirma el transcripto>
```
