# Estado actual del proyecto

Snapshot canónico: **2026-08-10 Europe/Madrid**
Ámbito: repositorio local y una captura read-only de QLab 5.5.10.

## Estado Git de cierre

```text
branch: validation/group-edge-runtime
HEAD: commit final de cierre, resuelto por Git en la verificación final
worktree: limpio tras la verificación final
```

El SHA no se duplica aquí: el commit final y su estado exacto son la fuente de
verdad de Git y de la PR.

## Verificación local

La suite completa queda en:

```text
2559 passed, 41 subtests passed
```

El Reader queda en:

```text
196 passed, 37 subtests passed
```

La corrección de `fileTarget` mantiene la separación entre capacidad y
presencia:

- `fileTarget` se lee internamente en los perfiles seguros que necesitan
  derivar presencia.
- `fileTargetPresent` es `true` para un target no vacío, `false` para un target
  vacío y `unknown` cuando la lectura no permite determinarlo.
- `hasFileTargets` no se usa como prueba de que exista un archivo.
- `auto`, `editable`, `health`, `targets`, `inspector_safe` y `full` no exponen
  rutas.
- `technical` y `full_sensitive` conservan la ruta solo por ser perfiles
  explícitamente sensibles; las lecturas internas no se almacenan en caché.
- Los tests comprueban también las claves enviadas realmente a
  `valuesForKeys`, la redacción, los estados `true/false/unknown` y la ausencia
  de caché para lecturas internas.

## Evidencia runtime de `fileTarget`

Captura read-only realizada tras reiniciar MCP, sin setters, Create, Delete,
playback, `/live` ni raw OSC.

```text
QLab: 5.5.10
workspace: mcp_prueba.qlab5
workspace UUID: 95F0A03D-140E-4673-974A-E76748EBB023
connection: ready
read access: confirmed
show mode: Edit
connect scopes: view, edit, control
```

Para el cue Audio `AUDIO_VALID` (#2), los perfiles `auto`, `editable`,
`health`, `targets`, `inspector_safe` y `full` devolvieron
`fileTargetPresent=true` sin incluir `fileTarget`. Los perfiles `technical` y
`full_sensitive` devolvieron la ruta, como permite su contrato sensible.

Para el cue Audio `AUDIO_MISSING_FILE` (#1), los perfiles seguros devolvieron
`fileTargetPresent=false`, sin ruta, aunque `hasFileTargets=true`.

Una consulta `hasFileTargets=true` con perfil `auto` devolvió una mezcla real de
`fileTargetPresent=true` y `false`, sin rutas en los resultados.

Esta evidencia valida el contrato Reader en el workspace y versión indicados;
no convierte el show completo en GO-ready ni valida escrituras de rutas.

## Alcance de la PR

La PR conserva sus cambios de Create secuencial y Delete recursivo, pero este
cierre no los amplía ni añade nuevas afirmaciones runtime sobre ellos. La
distinción operativa sigue siendo:

```text
estructura programada
≠
show runtime-validado
≠
show listo para GO
```

## Reproducción final

```bash
cd <repo-root>
PYTHONDONTWRITEBYTECODE=1 .venv/bin/pytest -q -p no:cacheprovider
git diff --check
git status --short --branch
```

La revisión final debe confirmar que solo cambian Reader, sus tests y este
snapshot; después se actualiza la descripción de la PR y se mergea únicamente
si no aparecen nuevos hallazgos.
