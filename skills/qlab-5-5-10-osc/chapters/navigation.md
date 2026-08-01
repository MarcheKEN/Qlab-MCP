# OSC navigation

## Correlation and transport concepts

La fuente documenta UDP en port 53000, replies UDP por 53001 por defecto y TCP con SLIP. Un mensaje que llega a un puerto puede ser recibido por todos los workspaces abiertos que escuchen ese puerto; workspace-qualified paths o puertos distintos aíslan el destino.

## Replies y updates

Reply:

```text
/reply/{/invoked/osc/method} json_string
```

El JSON puede incluir `workspace_id`, `address`, `status` (`ok`, `error`, `denied`) y `data`. Las notifications de estado usan `/update/workspace/{workspace_id}` y variantes de cue/cue list; se habilitan con `/updates 1` y se detienen con `/updates 0`.

## Acceso y booleanos

Lee la tabla de cada entrada: `view`, `edit`, `control`, `query`, `+/-?`, `Live`. QLab acepta boolean OSC, números y strings según las reglas de la fuente; `toggle` solo existe donde el diccionario lo permite.

## Targets y variantes

- Cue number: `/cue/{cue_number}/...`.
- Selected cue: `/cue/selected/...` cuando la entrada lo permite.
- Unique ID y workspace-qualified address: usa exactamente las formas documentadas.
- Live: añade `/live` al final.
- Increment/decrement: usa `/+` o `/-` y respeta el orden `/+/live`.

Estas reglas son navegación; la firma real siempre se copia de la entrada original.
