# PLAN LUCES — modelo de lectura y analizador LCL MVP

Snapshot: 2026-06-19

QLab verificado: 5.5.10

Alcance: análisis y planificación read-only. Este documento no autoriza cambios en QLab ni en el MCP.

## 1. Resumen ejecutivo

El MCP actual ya puede obtener las dos fuentes principales necesarias para entender iluminación:

- `/settings/light/patch`, mediante `qlab_get_workspace_setting_details`, contiene instrumentos, grupos, definiciones y parámetros.
- Los perfiles `auto` e `inspector_safe` de `qlab_get_cue_details` devuelven `lightCommandText`, `alwaysCollate`, `subcontroller`, duración y estado de cada Light Cue.

La brecha principal no es acceso OSC. Es normalización: el Light Patch seguro se presenta como `instrument_index` tabular, los parámetros profundos quedan omitidos y no existe análisis semántico de Lighting Command Language (LCL). La propuesta mínima mantiene las herramientas existentes, amplía la salida segura del Light Patch y añade después una sola herramienta read-only para analizar texto LCL.

No se propone leer ni controlar el estado Live del Light Dashboard. No se propone escribir cues, patch, niveles, grupos, instrumentos, definiciones ni direcciones DMX.

## 2. Fuentes y comportamiento oficial de QLab 5

Fuentes oficiales consultadas:

- [The Light Patch Editor](https://qlab.app/docs/v5/lighting/light-patch-editor/)
- [Light Cues](https://qlab.app/docs/v5/lighting/light-cues/)
- [The Light Dashboard](https://qlab.app/docs/v5/lighting/light-dashboard/)
- [The Lighting Command Language](https://qlab.app/docs/v5/lighting/lighting-command-language/)
- [QLab's OSC Dictionary](https://qlab.app/docs/v5/scripting/osc-dictionary-v5/)

### 2.1 Light Patch

El Light Patch pertenece a `Workspace Settings → Light`. El editor muestra instrumentos y grupos, parámetros por instrumento, definición asignada y estado de patch. Los nombres deben ser únicos dentro del workspace. Un instrumento puede estar sin patch o roto por conflicto de dirección; un instrumento sin patch no aparece en Light Dashboard.

El OSC Dictionary define `/workspace/{id}/settings/light/patch` como read-only para permisos view, edit y control. Devuelve un JSON con:

- `settingKeywords`: al menos `home`, `pass` y `cue`.
- `instruments[]`: `name`, `patched`, `conflicted`, `definition` y `parameters[]`.
- `groups[]`: nombre, miembros, instrumentos expandidos y parámetros de grupo.
- Definición: `name`, `manufacturer`, `definitionVersion`, `defaultParameter`, `isBroken` y mapa de parámetros.
- Parámetro: `name`, `type`, `homeValue`, `homeValueInDMX`, `valueIsPercentage`, `twoBytes`, `uniqueName` y `definitionParameter` cuando corresponda.

`twoBytes` permite distinguir parámetros de 8 y 16 bits. `valueIsPercentage` permite distinguir valores porcentuales de valores DMX crudos. El payload documentado no publica una lista normalizada de direcciones DMX ni el destino físico de cada parámetro; publica `patched` y `conflicted`.

Con varios workspaces abiertos debe usarse UUID explícito. Un mensaje sin `/workspace/{id}` puede llegar a todos los workspaces que escuchen el mismo puerto. Los nombres de los workspaces observados contienen espacios o diacríticos, por lo que el UUID también evita las restricciones de caracteres OSC aplicables al display name.

### 2.2 Light Cues

Una Light Cue contiene texto LCL, duración y curva. No tiene target de cue: puede afectar uno o varios parámetros del Light Patch. Sus comandos se interpretan secuencialmente, de arriba abajo.

Lecturas OSC específicas confirmadas:

| Campo | Mensaje | Lectura oficial |
| --- | --- | --- |
| `lightCommandText` | `/cue/{cue_number}/lightCommandText` | Texto completo de comandos |
| `alwaysCollate` | `/cue/{cue_number}/alwaysCollate` | Estado de “Collate effects of previous light cues” |
| `subcontroller` | `/cue/{cue_number}/subcontroller` | Estado de “Use as subcontroller in dashboard” |

Duración, identidad, armed/broken/warning y waits pertenecen a los mensajes comunes de cue y ya forman parte de los perfiles de detalle actuales.

QLab documenta cuatro causas principales de Light Cue rota:

1. Comando LCL inválido.
2. Ningún instrumento referido está correctamente patcheado.
3. Definición de instrumento rota.
4. Dispositivo USB DMX requerido desconectado.

El booleano `isBroken` no identifica por sí solo cuál de estas causas aplica.

### 2.3 Lighting Command Language

Formas básicas oficiales:

```text
instrument = value
instrument.parameter = value
group = value
group.parameter = value
```

Los espacios alrededor de `=` son opcionales. Si se omite el parámetro, QLab usa el parámetro por defecto definido para el instrumento. En un `group.parameter`, QLab aplica el valor solo a miembros que posean ese parámetro. `home` usa el valor home definido; `pass` excluye explícitamente el target del ajuste de la cue.

QLab soporta más sintaxis —rangos, grupos ad hoc, pull desde otra cue y valores compuestos—, pero queda fuera del MVP propuesto.

### 2.4 Light Dashboard

Light Dashboard representa niveles Live y Audition, permite control inmediato y puede grabar o actualizar Light Cues. Es deliberadamente ajeno a esta fase. Leer el patch o el texto de una cue no equivale a leer el look actual, determinar la cue “activa” de iluminación ni simular el resultado acumulado de cues previas.

## 3. Implementación actual del repositorio

### 3.1 Estado Git previo

Estado observado antes de crear este documento:

```text
 M README.md
?? docs/cue_detail_read_coverage_probe_report.md
?? docs/runtime_concurrency_probe_report.md
?? docs/runtime_tool_probe_report.md
```

Esos cambios son preexistentes y quedan fuera de alcance.

### 3.2 Herramientas MCP expuestas

Diez herramientas detectadas. Siete inspectoras read-only:

1. `qlab_check_connection`
2. `qlab_get_workspace_overview`
3. `qlab_get_workspace_status`
4. `qlab_get_workspace_settings`
5. `qlab_get_workspace_setting_details`
6. `qlab_query_cues`
7. `qlab_get_cue_details`

Tres herramientas orientadas al flujo de escritura, no usadas en este trabajo:

1. `qlab_check_write_readiness` — preflight sin mutación, pero perteneciente al flujo write.
2. `qlab_create_cue`
3. `qlab_update_cues`

El servidor no expone GO, stop, panic ni raw OSC como herramientas MCP.

### 3.3 Lectura actual del Light Patch

`src/qlab_mcp/settings/workspace.py` usa la dirección workspace-qualified `settings/light/patch`. Primero intenta UDP y usa TCP como fallback para payloads grandes.

Perfil `safe`:

- Devuelve `summary`, `groups`, `instrument_index` y `definition_counts`.
- `instrument_index` usa columnas `name`, `comment`, `patched`, `conflicted`, `definition`, `manufacturer`, `parameter_count` y `parameter_names`.
- Deduplica instrumentos presentes tanto arriba como dentro de grupos.
- Omite explícitamente `instrument.definition.parameters` e `instrument.parameters[].definitionParameter`.

Perfiles `technical` y `exhaustive`:

- Conservan el payload Light Patch bajo `details.patch` después de aplicar redacción general.
- Permiten inspeccionar definición y parámetros profundos, pero no ofrecen todavía un modelo normalizado estable.

La vista summary de settings no lee el Light Patch en perfil seguro; devuelve `patch_read: "skipped"` y anuncia el detail request disponible. Esto evita descargar involuntariamente un payload grande.

### 3.4 Lectura actual de Light Cues

`AUTO_LIGHT_KEYS` contiene exactamente:

```text
lightCommandText
alwaysCollate
subcontroller
```

`qlab_query_cues(primary_filter="type", primary_value="Light")` localiza cues y devuelve identidad/estado compacto. `qlab_get_cue_details(profile="auto"|"inspector_safe")` añade campos comunes, timing y los tres campos específicos de Light Cue. El MCP no analiza `lightCommandText`; solo lo devuelve.

La salud actual deriva una advertencia genérica cuando `isBroken=true`. No discrimina entre comando inválido, patch incompleto, definición rota o dispositivo ausente.

## 4. Hallazgos runtime reales

Todas las llamadas usaron UUID explícito. No se llamó ninguna herramienta write-facing, playback, Dashboard ni raw OSC.

### 4.1 Conexión y workspaces

`qlab_check_connection(require_read_access=true)` sin UUID devolvió:

```json
{
  "ok": false,
  "status": "workspace_ambiguous",
  "qlab_reachable": true,
  "workspace_count": 3,
  "message": "QLab is reachable, but multiple workspaces are open and no workspace_id was provided."
}
```

Workspaces detectados:

| Workspace | UUID | QLab | Cue lists leíbles |
| --- | --- | --- | ---: |
| `<TEST_WORKSPACE_NAME>` | `<TEST_WORKSPACE_UUID>` | 5.5.10 | 5 |
| `<TEST_WORKSPACE_NAME>` | `<TEST_WORKSPACE_UUID>` | 5.5.10 | 1 |
| `<TEST_WORKSPACE_NAME>` | `<TEST_WORKSPACE_UUID>` | 5.5.10 | 7 |

Las tres comprobaciones explícitas devolvieron `ok=true`, `status="ready"`, `workspace_readable=true` y `qlab_version="5.5.10"`.

### 4.2 Settings summary

En los tres UUID, esta llamada:

```json
{
  "mode": "summary",
  "sections": ["light"],
  "profile": "safe"
}
```

devolvió el mismo contrato Light:

```json
{
  "summary": {
    "details_available": true,
    "patch_read": "skipped",
    "message": "Use qlab_get_workspace_setting_details with section='light' and kind='light_patch' to inspect the light patch."
  }
}
```

Además anunció `{"section":"light","kind":"light_patch","ref":null}` en `available_detail_requests`.

### 4.3 Light Patch seguro

Llamada usada por workspace:

```json
{
  "section": "light",
  "kind": "light_patch",
  "profile": "safe",
  "workspace_id": "<UUID explícito>"
}
```

Resultados exactos relevantes:

| Workspace | `patch_present` | Instrumentos | Grupos | Transporte | Sin patch | Conflictos |
| --- | ---: | ---: | ---: | --- | ---: | ---: |
| `<TEST_WORKSPACE_NAME>` | true | 59 | 6 | `tcp_fallback` | 2 | 0 |
| `<TEST_WORKSPACE_NAME>` | true | 0 | 0 | `udp` | 0 | 0 |
| `<TEST_WORKSPACE_NAME>` | true | 60 | 13 | `tcp_fallback` | 12 | 0 |

`patch_present=true` con cero elementos representa un patch devuelto correctamente pero vacío; no significa que haya instrumentos.

El primer workspace de prueba devolvió:

```json
{
  "definition_counts": {
    "Generic Dimmer": 46,
    "Generic RGBWA+UV": 13
  },
  "technical_payloads_omitted": [
    "instrument.definition.parameters",
    "instrument.parameters[].definitionParameter"
  ]
}
```

Los instrumentos sin patch observados fueron `32 Cuna` y `104 FRONTAL`. Los RGBWA+UV publicaron siete nombres de parámetro: `color`, `red`, `green`, `blue`, `white`, `amber`, `uv`.

El tercer workspace de prueba devolvió `{"definition_counts":{"Generic Dimmer":60}}`. Instrumentos sin patch: `07 PC refuerzo 1`, `10 PC refuerzo 4`, `37 Contra L medio`, `38 Contra L arriba`, `40 Contra R centro`, `41 Contra R arriba`, `46 Sala 2`, `46 Sala 3`, `46 Sala 4`, `48 Cabina`, `49 Cabina` y `50 Puntual butaca`.

Los arrays completos de 59 y 60 instrumentos y las listas completas de miembros de grupo no se reproducen aquí. Las cifras, nombres excepcionales y claves anteriores proceden directamente de la respuesta; esta omisión evita convertir el documento en un dump runtime.

### 4.4 Consulta de Light Cues

Argumentos usados:

```json
{
  "primary_filter": "type",
  "primary_value": "Light",
  "profile": "basic_safe",
  "max_cues_scanned": 5000,
  "max_results": 10,
  "workspace_id": "<UUID explícito>"
}
```

| Workspace | Escaneadas | Light Cues | Devueltas | `query_completeness` | `truncated` | Motivo |
| --- | ---: | ---: | ---: | --- | --- | --- |
| `<TEST_WORKSPACE_NAME>` | 316 | 90 | 10 | `complete` | true | `max_results` |
| `<TEST_WORKSPACE_NAME>` | 30 | 1 | 1 | `complete` | false | — |
| `<TEST_WORKSPACE_NAME>` | 1424 | 933 | 10 | `complete` | true | `max_results` |

`status="partial"` en los workspaces primero y tercero indica límite de resultados, no escaneo incompleto: ambos devolvieron `scanned_all_cues=true` e `id_only_unscanned_count=0`.

### 4.5 Detalle de cues representativas

Perfil usado: `inspector_safe`.

Primer workspace, cue `<TEST_CUE_UUID>`:

```json
{
  "type_specific": {
    "lightCommandText": "20 Calle Arbol = 100\n21 Calle Arbol = 100",
    "alwaysCollate": false,
    "subcontroller": false
  },
  "timing": {
    "preWait": 0,
    "duration": 2.5,
    "postWait": 0,
    "continueMode": 0,
    "continueModeLabel": "do_not_continue"
  },
  "status": {
    "armed": true,
    "isBroken": false,
    "isWarning": false
  }
}
```

Segundo workspace, cue `<TEST_CUE_UUID>`:

```json
{
  "number": "12",
  "name": "LIGHT_DISARMED_BROKEN",
  "type_specific": {
    "lightCommandText": "all = home",
    "alwaysCollate": false,
    "subcontroller": false
  },
  "timing": {"duration": 5},
  "status": {
    "armed": false,
    "isBroken": true,
    "isWarning": false
  }
}
```

Tercer workspace, cue `<TEST_CUE_UUID>`:

```json
{
  "number": "LX0",
  "name": "OSCURO",
  "type_specific": {
    "lightCommandText": "all = home",
    "alwaysCollate": false,
    "subcontroller": false
  },
  "timing": {"duration": 5},
  "status": {
    "armed": true,
    "isBroken": false,
    "isWarning": false
  }
}
```

Los extractos reducen campos comunes no relacionados con iluminación; valores mostrados y nombres de claves no están reinterpretados.

## 5. Qué puede leerse por OSC

- Identidad de workspaces abiertos y sus UUID.
- Light Patch completo documentado mediante `/settings/light/patch`.
- Instrumentos y grupos, incluido membership.
- Estado `patched` y `conflicted` por instrumento.
- Definición embebida, fabricante, versión, `isBroken` y parámetro por defecto.
- Parámetros físicos y virtuales publicados por QLab, home, escala porcentaje/DMX y 8/16-bit.
- Listado y estado común de Light Cues.
- Texto íntegro `lightCommandText`.
- `alwaysCollate` y `subcontroller`.
- Duración, waits, continue mode, armed, broken y warning.

## 6. Qué no queda disponible mediante estas lecturas

- Direcciones DMX normalizadas por parámetro: no aparecen en el esquema oficial publicado para `/settings/light/patch`.
- Estado Live actual del Light Dashboard, modificaciones amarillas, niveles originadores o look acumulado.
- Confirmación de salida física real, luz visible en escenario o salud extremo a extremo de Art-Net, sACN o USB DMX.
- Causa exacta de `isBroken=true`; debe inferirse de patch/comando y puede exigir comprobación humana.
- Resultado final de ejecutar una secuencia de Light Cues, incluyendo collation, orden histórico, curvas y valores previos.
- Validación completa de toda la gramática LCL mediante un endpoint OSC read-only específico; QLab expone texto y estado broken, no un AST ni diagnóstico estructurado.

El OSC Dictionary sí contiene setters y comandos de Dashboard/cue. Su existencia no los convierte en lecturas ni los incluye en esta fase.

## 7. Modelo de lectura propuesto

El modelo se construirá componiendo settings, query y cue details existentes; no hace falta otro agregador MCP.

```json
{
  "workspace_id": "UUID",
  "instruments": [
    {
      "name": "string",
      "comment": "string|null",
      "patched": true,
      "conflicted": false,
      "definition": {
        "name": "string|null",
        "manufacturer": "string|null",
        "version": "number|string|null",
        "broken": false,
        "default_parameter_index": 0,
        "default_parameter_name": "intensity|null"
      },
      "parameter_names": ["intensity"]
    }
  ],
  "groups": [
    {
      "name": "string",
      "instrument_names": ["string"],
      "parameter_names": ["string"]
    }
  ],
  "parameters": [
    {
      "scope": "instrument|group",
      "owner_name": "string",
      "name": "string",
      "unique_name": "string|null",
      "type": "scalar|pantilt|rgbcolor|cmycolor|muxer|unknown",
      "broken": false,
      "home_value": null,
      "home_value_dmx": null,
      "value_is_percentage": null,
      "two_bytes": null
    }
  ],
  "light_cues": [
    {
      "unique_id": "UUID",
      "number": "string",
      "name": "string",
      "duration": 0,
      "armed": true,
      "broken": false,
      "warning": false,
      "always_collate": false,
      "subcontroller": false,
      "command_text": "string"
    }
  ],
  "warnings": [],
  "errors": [],
  "unsupported_or_unavailable_fields": []
}
```

Reglas del modelo:

- Conservar nombres y texto originales; añadir campos normalizados, no sustituir el payload fuente.
- Diferenciar `null`/unavailable de `false`, `0` y colección vacía.
- Derivar `default_parameter_name` desde `definition.defaultParameter` y el mapa de parámetros. Si falla, dejar `null` y añadir warning.
- Un patch vacío es éxito con arrays vacíos.
- Instrumento `patched=false`, `conflicted=true` o definición rota genera warning estructurado, no error de transporte.
- Mantener `instrument_index` durante compatibilidad; añadir `instruments[]` y `parameters[]` sin romper consumidores existentes.
- Declarar omisiones en `unsupported_or_unavailable_fields`; nunca inventar direcciones, niveles Live ni causa exacta de cue rota.

## 8. Analizador LCL read-only MVP

Herramienta futura mínima:

```text
qlab_analyze_light_command_text(workspace_id: string, command_text: string)
```

La herramienta leerá el Light Patch del UUID indicado y no enviará setters. Obtener texto desde una cue seguirá siendo responsabilidad de `qlab_get_cue_details`; no se añade un segundo modo por `cue_ref`.

### 8.1 Gramática admitida

Una asignación por línea:

```text
target [ "." parameter ] "=" value
value := number | "home" | "pass"
```

Se admiten espacios opcionales alrededor de `=` y extremos de línea. Líneas vacías se ignoran. El texto y número de línea originales se conservan.

### 8.2 Resolución

1. Buscar target exacto entre instrumentos y grupos.
2. Si no existe, probar coincidencia case-insensitive única y marcar `normalized_match=true`.
3. Más de una coincidencia normalizada produce `ambiguous_target`; ninguna produce `unknown_target`.
4. Target con parámetro explícito:
   - Instrumento: validar que lo posee.
   - Grupo: expandir solo miembros que lo poseen; miembros incompatibles quedan en `skipped_members`.
5. Target sin parámetro:
   - Instrumento: resolver su `defaultParameter`.
   - Grupo: resolver el default de cada miembro; el resultado puede contener parámetros distintos.
6. `all` no es keyword implícita del analizador. Es válido solo si existe como grupo en ese workspace.
7. `home` y `pass` se aceptan como valores simbólicos; el analizador no calcula el estado Live resultante.

Salida por línea:

```json
{
  "line": 1,
  "source": "Back.red = 50",
  "status": "valid|warning|invalid|unsupported",
  "target": {
    "input": "Back",
    "resolved_name": "back|null",
    "kind": "instrument|group|null",
    "exists": true,
    "normalized_match": true
  },
  "parameter": {
    "input": "red|null",
    "exists": true,
    "defaulted": false
  },
  "value": {"kind": "number|home|pass", "raw": "50"},
  "affected": [
    {"instrument": "110 CONTRA", "parameter": "red"}
  ],
  "skipped_members": [],
  "warnings": [],
  "errors": []
}
```

### 8.3 Sintaxis fuera del MVP

Debe devolverse `status="unsupported"`, nunca una interpretación parcial, para:

- Rangos y listas: `1 - 3 = 50`, `1, 2 = 50`.
- Grupos ad hoc: `[1 - 3] = 50`.
- Pull desde cue: `10 = cue A`.
- Valores compuestos o funciones: color, pan/tilt, muxers y formas equivalentes.
- Operadores, expresiones, múltiples asignaciones en una línea o texto no reconocido.
- Cualquier forma válida de LCL que no esté incluida explícitamente en la gramática MVP.

El analizador no reordena, poda ni reemplaza comandos. Tampoco simula comandos duplicados, secuencia histórica, fade, `alwaysCollate`, subcontroller, Dashboard o DMX.

### 8.4 Ejemplos mínimos esperados

| Entrada | Resultado esperado |
| --- | --- |
| `Front = 100` | Target resuelto; default por instrumento; afectados enumerados |
| `Back.red = 50` | Grupo válido; solo miembros con `red` |
| `All = 0` | Válido solo si grupo `all` existe; posible normalized match |
| `Front = home` | Defaults resueltos; valores home disponibles como metadatos |
| `Back = pass` | Afectados identificados; sin simulación de look |

## 9. Cambios MCP requeridos en fases posteriores

1. Ampliar normalización segura de Light Patch:
   - Añadir `instruments[]`, `groups[].parameter_names` y `parameters[]`.
   - Resolver definición rota y parámetro por defecto.
   - Conservar `instrument_index` y `definition_counts` durante compatibilidad.
2. Añadir warnings estructurados:
   - Instrumentos sin patch, conflicto, definición/parámetro roto y metadata incompleta.
   - Diferenciar datos no expuestos, omitidos por perfil y fallos de transporte.
3. Añadir `qlab_analyze_light_command_text` con la gramática anterior.
4. Reutilizar `qlab_query_cues` y `qlab_get_cue_details`; no crear `qlab_get_light_model` ni otro agregador hasta demostrar necesidad.
5. Mantener TCP fallback para payloads grandes y UUID obligatorio en toda herramienta nueva.

## 10. Reglas de seguridad

- Solo OSC read-only documentado y herramientas inspectoras MCP.
- UUID explícito siempre que haya varios workspaces.
- Prohibidos GO, playback, start, stop, panic, audition y preview.
- Prohibidos raw OSC y control Live del Dashboard.
- Prohibidos `dashboard/setLight`, `dashboard/clear`, `newCueWithAll`, `newCueWithChanges`, `recordAllToLatest`, `updateSelectedCues`, `collateAndStart`, setters y operaciones de orden/prune/replace.
- Prohibido modificar Light Patch, instrumentos, grupos, definiciones, direcciones DMX y Light Cues.
- `lightCommandText` se trata como datos no confiables: límites de tamaño/líneas, sin ejecución ni reenvío a QLab.
- Un análisis `valid` significa “admitido y resoluble por este MVP”, no garantía de salida física ni equivalencia completa con el parser interno de QLab.
- Nunca ocultar sintaxis desconocida: devolver `unsupported` con línea y texto originales.

## 11. Plan de pruebas para el futuro probe runtime

### 11.1 Unitarias

- Normalizar patch vacío, instrumento simple, RGBWA+UV, grupo mixto y definición rota.
- Resolver `defaultParameter` válido, ausente y fuera del mapa.
- Preservar 8/16-bit, porcentaje/DMX, home y tipo de parámetro.
- Detectar unpatched/conflicted sin convertirlos en error de transporte.
- Probar los cinco ejemplos MVP.
- Probar target desconocido, parámetro desconocido y target ambiguo por normalización.
- Probar grupo donde solo algunos miembros poseen el parámetro.
- Rechazar rangos, ad-hoc groups, `cue`, valores compuestos y expresiones como `unsupported`.
- Verificar que el parser nunca llama setters ni genera direcciones OSC mutantes.

### 11.2 Integración MCP simulada

- `qlab_get_workspace_setting_details(profile="safe")` conserva `instrument_index` y añade arrays normalizados.
- `technical` conserva payload profundo sin alterar redacciones.
- TCP fallback produce el mismo modelo que UDP.
- Analyzer exige UUID válido, limita tamaño y devuelve errores parciales por línea sin abortar líneas independientes.
- Patch vacío permite analizar solo como `unknown_target`, sin excepción.

### 11.3 Runtime read-only

- Repetir contra los tres UUID del snapshot.
- Confirmar 59/0/60 instrumentos y 6/0/13 grupos mientras los workspaces permanezcan sin cambios.
- Repetir query completa de Light Cues y registrar `matched_count`, `scanned_all_cues` y truncación.
- Leer varias cues por workspace, incluyendo una cue rota del workspace de prueba y cues con comandos de grupo/parámetro.
- Comparar analyzer contra identidad, grupos y parámetros del patch, sin ejecutar cues.
- Registrar cualquier diferencia como cambio de workspace o incompatibilidad de modelo; nunca “corregir” QLab automáticamente.

### 11.4 Criterios de aceptación

- Cero mensajes mutantes enviados a QLab.
- Todos los reads workspace-qualified con UUID.
- Modelo distingue vacío, omitido, unavailable, warning y error.
- Cada línea LCL produce resultado determinista y trazable.
- Sintaxis fuera del MVP queda explícitamente marcada.
- Cambios futuros conservan contratos existentes o documentan versión/migración.
