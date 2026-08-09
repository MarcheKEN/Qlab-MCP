# Estado actual del proyecto

Snapshot canónico: **2026-08-09 22:30 Europe/Madrid**  
Ámbito: repositorio local (raíz del proyecto).  
Este informe se capturó sin commit, reset, limpieza del worktree ni mutaciones QLab.

## Resumen ejecutivo

- `HEAD`: `8ece792bcd64844988d9cae1d15e648997cb7fce` en `validation/group-edge-runtime`.
- El worktree contiene cambios funcionales, tests y documentación todavía no incluidos en `HEAD`.
- Suite completa: `2553 passed, 3 failed, 41 subtests passed`.
- Las tres fallas son las conocidas de `fileTarget` en `tests/test_qlab_reader.py`.
- Suite focalizada Create/Delete/server: `2236 passed`.
- Runtime QLab: **no verificable en esta captura**. El MCP devolvió `qlab_unreachable` y `[Errno 61] Connection refused`.

La distinción operativa es deliberada:

```text
estructura programada
≠
show runtime-validado
≠
show listo para GO
```

## 1. Estado Git

### HEAD

```text
branch: validation/group-edge-runtime
HEAD: 8ece792bcd64844988d9cae1d15e648997cb7fce
commit: feat(create): support first cue in empty containers
HEAD date: 2026-08-09T02:18:13+02:00
snapshot date: 2026-08-09 22:30:06 CEST (+0200)
```

La historia inmediatamente relevante es:

```text
8ece792  feat(create): support first cue in empty containers
1858924  feat(create): support empty container placement routes
4beac77  docs(security): define threat model and security policy
8a5a92c  fix(security): harden input limits, OSC validation, and cue profiles
81ed136  Document safe anchored cue creation lifecycle
2c95c02  Require anchored, token-gated cue creation
b4f1953  Harden cue creation identity and cleanup reporting
```

### Worktree

Estado capturado antes de crear este informe:

```text
 M README.md
 M docs/development/runtime-validation/create-cues.md
 M docs/development/runtime-validation/edit-cues.md
 M docs/status/roadmap.md
 M docs/user/README.md
 M docs/user/tools.md
 M skills/README.md
 M src/qlab_mcp/models.py
 M src/qlab_mcp/server.py
 M src/qlab_mcp/write/allowlist.py
 M src/qlab_mcp/write/deletes.py
 M src/qlab_mcp/write/operations.py
 M src/qlab_mcp/write/registry.py
 M tests/test_delete_mode.py
 M tests/test_server_tools.py
 M tests/test_write_mode.py
?? skills/qclass-research/
```

Al finalizar la captura se añadió también este informe:

```text
?? docs/status/current-state.md
```

Resumen del diff previo al informe: `16 files changed, 1675 insertions(+), 220 deletions(-)`.

Separación de alcance:

- **Funcional:** `src/qlab_mcp/models.py`, `server.py`, `write/allowlist.py`, `write/deletes.py`, `write/operations.py`, `write/registry.py`.
- **Tests:** `tests/test_delete_mode.py`, `tests/test_server_tools.py`, `tests/test_write_mode.py`.
- **Documentación/skills:** `README.md`, `docs/development/runtime-validation/create-cues.md`, `docs/development/runtime-validation/edit-cues.md`, `docs/status/roadmap.md`, `docs/user/README.md`, `docs/user/tools.md`, `skills/README.md`, `skills/qclass-research/`.

**HEAD contiene** la ruta Create segura y las rutas de colocación de la primera cue en contenedores vacíos. **El worktree añade** la API/secuencia `qlab_create_cues`, la expansión recursiva de Delete, sus modelos, tests y documentación asociada, además de cambios de lectura existentes. Por tanto, esos cambios están implementados y probados localmente, pero todavía no pertenecen al commit actual.

## 2. Tests reproducibles

Los siguientes resultados son salidas reales de esta captura; no son estimaciones.

### Suite completa normal

Comando:

```bash
.venv/bin/pytest -q
```

Resultado literal:

```text
2553 passed, 3 failed, 41 subtests passed in 10.68s
```

### Reader aislado

Comando:

```bash
.venv/bin/pytest -q tests/test_qlab_reader.py
```

Resultado literal:

```text
3 failed, 190 passed, 37 subtests passed in 1.15s
```

Las tres fallas son exactamente:

1. `test_exhaustive_profile_includes_sensitive_heavy_and_deep_allowlisted_keys`: diferencia sobre `fileTarget` en `inspector_safe`.
2. `test_query_cues_health_redacts_file_target_but_reports_presence`: falta el indicador esperado `fileTargetPresent`.
3. `test_query_cues_targets_profile_redacts_file_target_but_reports_presence`: falta el indicador esperado `fileTargetPresent`.

**Clasificación:** fallos conocidos de `fileTarget` (test local, no corregidos en este informe). No se ocultaron filtrando la suite completa.

### Suites focalizadas

Comando:

```bash
.venv/bin/pytest -q tests/test_write_mode.py tests/test_delete_mode.py tests/test_server_tools.py
```

Resultado literal:

```text
2236 passed in 7.55s
```

Esto cubre la implementación local de Create, Create secuencial, Delete explícito/recursivo y el contrato FastMCP. Es evidencia de **test local**, no sustituto de una prueba QLab conectada.

## 3. Snapshot runtime QLab

### Captura actual

```text
Runtime snapshot:
2026-08-09 22:30 Europe/Madrid
QLab version: unknown (MCP no conectado)
workspace UUID: no verificado
workspace name: no verificado
MCP status: unverified / qlab_unreachable
```

La comprobación MCP usada fue `qlab_check_connection(require_read_access=true)`. Resultado relevante:

```text
status: qlab_unreachable
message: QLab did not respond to /workspaces over OSC.
error: [Errno 61] Connection refused
workspace_count: 0
```

La comprobación de escritura para el UUID histórico también terminó en `workspace_unavailable`; no se enviaron comandos mutantes. Por ello, en esta captura no se puede afirmar el modo Edit, readiness, actividad, patches, stages, rutas, conteos broken/warning ni la estructura actual de `PRUEBA List`.

### Referencia histórica no vigente

En una captura runtime anterior se observó QLab 5.5.10 con `mcp_prueba.qlab5`, workspace UUID `95F0A03D-140E-4673-974A-E76748EBB023` y `PRUEBA List` UUID `BE16789A-25E1-45DE-9E11-0EAA71015B14`. Esa referencia sirve para reanudar la investigación, pero **no es el snapshot actual** y debe volver a leerse después de reconectar MCP.

El estado histórico de `PRUEBA List` incluía un grupo principal, una escena Timeline y cues Text, Light, Audio, Wait, Video, Fade, Devamp, Mic, MIDI y Timecode. Audio/Video/Devamp/MIDI/Timecode aparecían broken por targets, archivos o patches ausentes; Fade, Text y algunas Light aparecían sanas/inactivas tras cambios MCP. Es evidencia `runtime probado` de aquella captura, no una garantía permanente del workspace.

## 4. Estado del show

### Estructura programada

La implementación local permite construir estructura sin setters iniciales: QLab aplica sus Cue Templates y Create devuelve `properties={}`. La estructura se verifica por UUID, tipo, parent, índice o coordenadas de Cart. Esto es **documentado** y **test local**.

La secuencia `qlab_create_cues` encadena el UUID confirmado de cada cue como anchor de la siguiente, usa un token por operación, se detiene ante la primera ambigüedad y no hace rollback. Esto está en el **worktree** y tiene **test local**.

Delete explícito mantiene la ruta de hojas; Delete recursivo planifica hojas primero, conserva la raíz solicitada, usa token/readback y no hace rollback. Esto está en el **worktree** y tiene **test local**.

### Runtime validado

No hay runtime validado nuevo en esta captura. La referencia histórica solo demuestra pruebas acotadas de QLab 5.5.10, no reproducción completa del show.

### Preparación para GO

No se puede declarar `PRUEBA List` lista para GO. Faltan, como mínimo, una lectura runtime fresca, la validación de archivos/targets, patches, stages, permisos y el comportamiento completo de Audio, Video, MIDI, Timecode y demás cues dependientes. Una cue `created + broken` sigue siendo una creación estructural válida, pero no una cue lista para ejecución.

## 5. Contrato y arquitectura actual

| Área | Estado | Evidencia |
|---|---|---|
| `qlab_create_cue` singular | exacto `after_cue_id` o `parent_container_id`; sin properties/setters; máximo un `/new` | documentado + test local; Wait anclado probado en QLab 5.5.10 |
| Lista vacía | `currentCueListID` + `/new` sin anchor | documentado; prueba raw-OSC histórica, requiere nueva lectura MCP |
| Group vacío | `/new` con Group + un `/move` a índice 0 | documentado; prueba histórica |
| Cue Cart vacío | `/new` con Cart y request `0,0`; readback `1,1` | documentado; prueba histórica |
| Salud Create | healthy/broken/warning/unknown informativo; estados activos son fallo de seguridad | documentado + test local |
| `qlab_create_cues` | secuencial, UUID encadenado, sin rollback | worktree + test local |
| Edit | perfiles por tipo, referencias UUID concretas y confirm gates para operaciones de riesgo | documentado + test local |
| Delete explícito | hojas UUID, secuencial, convergencia fresca, sin rollback | documentado + test local/runtime histórico |
| Delete recursivo | expansión post-order, raíz preservada, contenedor vacío como no-op | worktree + test local; runtime pendiente |
| Raw OSC/playback/GO | fuera del MCP público | documentado |

Las etiquetas usadas aquí significan: **documentado** = contrato o decisión escrita; **test local** = prueba automatizada sin QLab; **runtime probado** = evidencia de una sesión QLab concreta; **inferido** = interpretación no contractual; **pendiente** = falta de prueba o decisión.

## 6. Bloqueos y siguiente captura

1. Reconectar/reiniciar MCP de forma segura y repetir el snapshot con UUID, versión, modo, readiness, actividad, settings, overview y detalles de `PRUEBA List`.
2. Reproducir la secuencia Create/Delete únicamente en un workspace controlado, con una cue por operación y limpieza explícita de las cues creadas.
3. Resolver o reclasificar los tres fallos de `fileTarget` sin ocultarlos en la suite completa.
4. Registrar qué cambios del worktree se incorporan posteriormente a commits; no asumir que el diff local ya forma parte de `HEAD`.
5. Antes de declarar GO, validar targets/archivos, patches, stages, warnings y reproducción real del show. Mantener separadas estructura programada, runtime validado y preparación para GO.

## 7. Reproducción mínima

```bash
cd <repo-root>
.venv/bin/pytest -q
.venv/bin/pytest -q tests/test_qlab_reader.py
.venv/bin/pytest -q tests/test_write_mode.py tests/test_delete_mode.py tests/test_server_tools.py
git status --short
git diff --check
```

Después de que MCP vuelva a conectar, repetir primero `qlab_check_connection`, luego overview/status/settings/readiness y solo después cualquier operación de escritura con dry-run y token fresco.
