# PLAN LUCES Phase 5 — flags guardados de Light Cue

## Alcance

Phase 5 habilita en `qlab_update_cues` la escritura real de una sola propiedad booleana guardada —`alwaysCollate` o `subcontroller`— sobre una sola cue de tipo exacto `Light`, con `profile="light_basic"` y modo `saved`.

No habilita acciones live, Dashboard, playback, raw OSC, Light Patch, `lightCommandText` combinado ni ninguna otra operación Light.

## Contrato y preflight

Un dry-run confirmable devuelve `real_write_possible=true`, `requires_confirm_token=true`, `phase5_light_behavior_candidate=true`, `real_write_enabled=false`, `planned_only_reason="light_behavior_requires_confirm_token"` y token `confirm:lightBehavior:v1:...`.

La escritura real exige write mode habilitado, passcode, `/connect` con edit scope, QLab Edit Mode, workspace UUID explícito, una cue, una property, token exacto, baseline fresh booleano y cue tipo `Light`. Batch, propiedades mezcladas y modo live se bloquean antes de cualquier setter.

El token HMAC liga versión, `operation_kind="phase5_light_behavior_flag_write"`, workspace, cue ref/UUID, profile, property, path, mode, baseline, requested, risk y capability gate. Es válido durante la vida del proceso y no es single-use. Rollback requiere nuevo dry-run y token nuevo.

Tras el setter se limpia cache y se exige readback booleano exacto. Un baseline cambiado devuelve `stale_light_behavior_baseline`; un readback distinto devuelve `verification_failed`.

## Operaciones bloqueadas

- `alwaysCollate` y `subcontroller` juntos.
- Cualquiera de ellos junto a `lightCommandText` u otra property.
- `collateAndStart`, `setLight`, `replaceLightCommand`, `removeLightCommandsMatching`, `safeSort`, `prune` y aliases.
- Dashboard, playback, GO, start, stop, panic, audition, preview, raw OSC y ediciones de patch/DMX.

## Matriz de tests

Fake-client cubre ambos sentidos de ambos flags, token/contexto, rollback, baseline stale, cue no Light o ausente, batch, mezclas, modo live, readiness, readback mismatch y ausencia de direcciones prohibidas. Phase 4 permanece como regresión obligatoria.

## Protocolo runtime Phase 5B

Solo en `<TEST_WORKSPACE_NAME>`, con workspace UUID explícito y sin ejecutar cues:

1. Confirmar readiness y baseline fresh.
2. L1: `alwaysCollate false → true`; readback; nuevo dry-run/token; rollback `true → false`; readback final.
3. L2: `subcontroller true → false`; readback; nuevo dry-run/token; rollback `false → true`; readback final.
4. Abortar ante baseline inesperado, preflight fallido o mismatch. No continuar después de un fallo.
