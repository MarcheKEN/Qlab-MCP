# PLAN LUCES Phase 4A — escritura limitada de `lightCommandText`

## 1. Alcance

Phase 4A habilita una sola mutación: actualizar `lightCommandText` de un único cue de tipo exacto `Light` mediante `qlab_update_cues` y `profile="light_basic"`.

El diccionario OSC incluido en el repositorio documenta `/cue/{cue_number}/lightCommandText {string}` como lectura/escritura. La implementación usa su variante estable y cualificada por workspace: `/workspace/{workspace_id}/cue_id/{cue_unique_id}/lightCommandText`.

No añade tools MCP. No habilita Dashboard, playback, raw OSC, Light Patch ni otros setters Light.

## 2. Dry-run confirmable

Un dry-run produce candidato Phase 4 solo cuando:

- `light_command_analysis.overall_status == "valid"`;
- texto solicitado no vacío;
- baseline actual es string;
- cue tiene `uniqueID` resuelto.

Operación resultante:

```json
{
  "property": "lightCommandText",
  "risk_tier": "high",
  "real_write_enabled": false,
  "real_write_possible": true,
  "requires_confirm_token": true,
  "phase4_real_write_candidate": true,
  "planned_only_reason": "light_command_requires_valid_analysis_and_confirm_token",
  "confirm_token": "confirm:lightCommandText:v1:..."
}
```

`real_write_enabled=false` impide bypass del registry general. Solo flujo especializado Phase 4 acepta token.

Texto vacío puede analizar como `valid`, pero no es confirmable: `phase4_real_write_candidate=false`, `real_write_possible=false`, sin token y motivo `empty_light_command_text_not_writeable`.

Estados `warning`, `invalid`, `unsupported` y `unavailable` tampoco generan token ni ruta real.

## 3. Preflight real exacto

Si cualquier item menciona `lightCommandText`, toda llamada queda bajo reglas Phase 4:

1. Workspace explícito y resoluble.
2. Un solo item.
3. `profile="light_basic"`.
4. Una sola property/operation: `lightCommandText`, path idéntico y modo `saved`.
5. Exactamente un `confirm_token` revisado.
6. Readiness normal: writes habilitados, passcode, scope `edit` vía `/connect` y QLab Edit Mode (`showMode=false`).
7. Cache de lectura limpia; lectura fresh de tipo, `uniqueID` y baseline.
8. Tipo exacto `Light`.
9. Light Patch safe leído fresh; texto solicitado reanalizado y aún `valid`.
10. Firma y contexto del token válidos.
11. Hash del baseline fresh igual al firmado. Si cambia: `stale_light_command_baseline`; cero setters.
12. Un único setter por `cue_id`.
13. Cache limpia y readback fresh. Éxito solo con igualdad exacta del string solicitado.

Mismatch de readback devuelve `verification_failed`, incluyendo `requested` y `after`. Todo fallo anterior al setter deja `executed_operations=[]` por item.

## 4. Token

Token autocontenido HMAC-SHA256, secreto aleatorio por proceso. Payload:

- `version=1`;
- `operation_kind="phase4_light_command_text_write"`;
- `workspace_id`, `cue_ref`, `cue_id`;
- `profile`, `property`, `path`, `mode`;
- SHA-256 de baseline y requested;
- `risk_tier`, `capability_gate`, `analysis_status="valid"`.

No contiene texto LCL en claro. Reiniciar MCP cambia secreto e invalida tokens anteriores. Tokens no son single-use dentro del mismo proceso. Rollback exige siempre leer baseline actual, ejecutar nuevo dry-run y usar token nuevo.

## 5. Operaciones bloqueadas

- `alwaysCollate`, `subcontroller`, `collateAndStart`;
- `setLight`, `replaceLightCommand`, `removeLightCommandsMatching`;
- `safeSort`, `safeSortCommands`, `prune`, `pruneCommands`;
- batch o mezcla con propiedades adicionales;
- Dashboard/live lighting;
- GO, playback, start, stop, panic, audition, preview;
- raw OSC;
- cambios de Light Patch, instrumentos, grupos, definiciones o DMX.

## 6. Matriz de tests fake-client

| Caso | Resultado esperado |
|---|---|
| Dry-run válido/no vacío | Candidato high-risk y token |
| Write válido | Un setter; readback exacto |
| Rollback | Nuevo dry-run y token; restaura baseline |
| Vacío/warning/invalid/unsupported/unavailable | Sin token ni ruta real |
| Cue no-Light, ausente, patch/read failure | Preflight bloqueado; cero setters |
| Dos items o property adicional | Llamada completa bloqueada antes de OSC |
| Setter Light distinto | Sigue dry-run only |
| Token malformado, firma o versión inválida | Bloqueado |
| Workspace/ref/cue/request/context distinto | Bloqueado |
| Baseline stale | `stale_light_command_baseline`; cero setters |
| Readback distinto | `verification_failed` con requested/after |
| Sin edit scope o Show Mode | Bloqueado antes de setter |
| Direcciones observadas | Sin Dashboard, playback ni OSC sin workspace |

## 7. Protocolo runtime Phase 4B — no ejecutado

Usar exclusivamente `<TEST_WORKSPACE_NAME>`, tras identificar su UUID explícito. Elegir un Light Cue desarmado y aislado. No usar cues de show, Dashboard ni playback.

1. Confirmar conexión, workspace UUID, Edit Mode y scope `edit`.
2. Leer cue y guardar `uniqueID`, tipo y `lightCommandText` original.
3. Leer Light Patch safe. Abortar si patch vacío, lectura parcial o target de prueba inexistente.
4. Ejecutar dry-run con cambio mínimo válido y no vacío.
5. Revisar analysis, diff, baseline, `phase4_real_write_candidate` y token.
6. Ejecutar una sola llamada real con mismo workspace/cue/property/value y token.
7. Verificar `updated`, un setter y readback exacto.
8. Para rollback, ejecutar nuevo dry-run desde valor actual hacia texto original. Revisar token nuevo.
9. Ejecutar rollback único y verificar readback original exacto.
10. Ante cualquier mismatch, no reintentar write; registrar respuesta y parar.

Prompt exacto para Phase 4B:

```text
Usa solo tools MCP read-only salvo las dos llamadas qlab_update_cues expresamente descritas. Trabaja únicamente en <TEST_WORKSPACE_NAME> usando su workspace_id UUID explícito. No uses GO, playback, start, stop, panic, audition, preview, Dashboard ni raw OSC. Identifica un Light Cue desarmado y aislado; lee y conserva su lightCommandText original. Lee Light Patch safe y aborta si está vacío/parcial o no ofrece un target simple válido. Ejecuta dry_run=true para cambiar solo lightCommandText a un comando mínimo válido no vacío. Revisa overall_status=valid, phase4_real_write_candidate=true, diff, baseline y confirm_token. Si todo coincide, ejecuta exactamente una llamada real qlab_update_cues con un item, profile=light_basic, solo lightCommandText y ese token. Verifica un único setter y readback exacto. Después crea un nuevo dry-run desde el valor actual hacia el texto original, obtiene token nuevo y ejecuta un único rollback. Verifica readback original exacto. Ante cualquier error, stale baseline, análisis no válido o mismatch, no hagas más writes y reporta. No cambies ningún otro cue, patch, instrumento, grupo, definición ni dirección DMX.
```

Phase 4B no forma parte de esta entrega y no se ha ejecutado.
