# PLAN LUCES Phase 3 — análisis LCL en dry-run

Fecha: 2026-06-19

## 1. Resumen ejecutivo

Phase 3 integra el helper interno `analyze_light_command_text(command_text, light_patch)` en la planificación `dry_run` de `qlab_update_cues` para actualizaciones `profile=light_basic` de `lightCommandText`.

La planificación lee la cue, confirma que es Light, obtiene el Light Patch `safe`, analiza el texto nuevo y adjunta resultados y resumen de instrumentos/parámetros afectados. No se envían setters. Toda actualización `lightCommandText` queda bloqueada en modo real durante esta fase, incluso con `confirm_token`.

Referencias oficiales: [Light Cues](https://qlab.app/docs/v5/lighting/light-cues/), [Lighting Command Language](https://qlab.app/docs/v5/lighting/lighting-command-language/) y [OSC Dictionary](https://qlab.app/docs/v5/scripting/osc-dictionary-v5/).

## 2. Flujo actual de actualización

`QLabReader.update_cues`:

1. Normaliza lote, perfil, propiedades y operaciones permitidas.
2. Vincula tokens de confirmación.
3. En `dry_run`, resuelve `workspace_id` y lee valores actuales mediante `update_safe`.
4. Valida que `light_basic` solo se aplique a una cue Light.
5. Construye `before`, `after`, `diff` y `planned_operations`.
6. Devuelve siempre `executed_operations=[]`.

El registry ya incluye `lightCommandText` en `light_basic` como setter planificable, con `read_key=lightCommandText`, riesgo alto y escritura real deshabilitada.

## 3. Punto exacto de análisis

El helper se llama solo en la rama `dry_run`, después de `_try_read_update_values` y `_validate_profile_for_before`, y antes de `_batch_item_result`.

Condiciones:

- La operación normalizada contiene `property=lightCommandText`.
- La lectura de cue no produjo errores.
- El perfil confirmó cue tipo Light.

El Light Patch se obtiene con `_get_workspace_setting_details_single(..., section="light", kind="light_patch", profile="safe")`, usando el `workspace_id` explícito ya resuelto. Se carga de forma lazy una vez por lote y se reutiliza para todas las operaciones LCL. Otros setters `light_basic` no leen el patch.

## 4. Respuesta propuesta e implementada

El setter planificado conserva `before`, `after` y `diff` existentes, y añade:

```json
{
  "operation": "set_property",
  "property": "lightCommandText",
  "risk_tier": "high",
  "real_write_enabled": false,
  "real_write_possible": true,
  "requires_confirm_token": true,
  "planned_only_reason": "light_command_real_write_not_enabled",
  "confirm_token": "...",
  "light_command_analysis": {
    "availability": "available",
    "overall_status": "valid",
    "line_count": 1,
    "analyzed_count": 1,
    "status_counts": {
      "valid": 1,
      "warning": 0,
      "invalid": 0,
      "unsupported": 0
    },
    "affected_instruments": ["Front"],
    "affected_parameters": ["intensity"],
    "affected_pair_count": 1,
    "skipped_member_count": 0,
    "results": []
  }
}
```

`results` contiene la salida completa por línea del helper. El resumen deduplica pares instrumento/parámetro y no calcula look, fade, collation, Dashboard ni DMX.

## 5. Riesgo y gates

| Resultado global | Dry-run | `real_write_possible` | Motivo |
| --- | --- | ---: | --- |
| `valid` | OK | `true` | `light_command_real_write_not_enabled` |
| `warning` | OK con warning | `true` | `light_command_real_write_not_enabled` |
| `invalid` | OK con warning | `false` | `light_command_analysis_failed` |
| `unsupported` | OK con warning | `false` | `unsupported_light_command_syntax` |
| `unavailable` | OK con warning | `false` | `light_command_analysis_unavailable` |

Decisión: warnings no añaden un gate distinto. El resultado por línea y el resumen deben revisarse, pero un futuro write usaría gates normales y `confirm_token`. Evitar un segundo mecanismo reduce estados y mantiene contrato actual.

Durante Phase 3, `real_write_possible=true` expresa únicamente que el análisis no detectó bloqueo semántico. No habilita escritura. `real_write_enabled` permanece `false` y preflight real rechaza siempre `lightCommandText`, incluso si recibe el token emitido por dry-run.

Para `invalid`, `unsupported` o `unavailable`, se omite `confirm_token`.

## 6. Manejo de errores

- Fallo de lectura/normalización del patch: análisis `unavailable`, código `light_patch_read_failed`.
- Excepción interna del helper: análisis `unavailable`, código `light_command_analyzer_failed`.
- Cue inexistente, lectura fallida o tipo no Light: conserva preflight existente; no lee patch ni ejecuta helper.
- Patch vacío: el helper devuelve targets inválidos; dry-run sigue siendo inspeccionable.
- Lotes: una lectura de patch como máximo; fallo compartido se representa por operación.

Los fallos de análisis no hacen crash ni se convierten en setters. `executed_operations` permanece vacío.

## 7. Tests

Cobertura implementada:

- Análisis válido adjunto con `before`/`after`/`diff`, riesgo alto y token.
- Resultado warning mantiene posibilidad futura y token.
- Invalid y unsupported bloquean posibilidad futura, cambian motivo y omiten token.
- Lectura de patch una sola vez para varias cues del lote.
- Fallo de patch y excepción del helper son no fatales.
- Setter Light distinto de `lightCommandText` no lee patch.
- Perfil/tipo inválido no llega al análisis.
- Intento real con token falla en preflight antes de cualquier OSC.
- Suite unitaria pura del helper cubre gramática MVP y casos no soportados.

## 8. Fuera de alcance

- Herramienta MCP pública para analizar LCL.
- Integración en `qlab_get_cue_details`.
- Ampliar gramática LCL.
- Ejecutar setters de `lightCommandText`.
- `safeSort`, `prune`, `replace` u otras operaciones reales.
- Dashboard, live lighting, raw OSC, GO, playback, start, stop, panic, audition o preview.
- Modificar patch, instrumentos, grupos, definiciones o direcciones DMX.

## 9. Pasos recomendados posteriores

1. Mantener Phase 3 en dry-run hasta validar respuestas contra patches reales variados.
2. Revisar warnings y sintaxis unsupported observada antes de ampliar gramática.
3. Diseñar verificación post-write determinista para `lightCommandText`.
4. Solo después, decidir si habilitar escritura real tras gates normales y token.
