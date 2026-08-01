# Muestras verificables

Las siguientes cadenas se comparan literalmente con `references/qlab_osc_dictionary.md`.

## Query de propiedad y preWait

```text
/cue/{cue_number}/preWait {number}
```

Sin argumento es lectura cuando la tabla concede `read`; con `{number}` es escritura solo si la columna de acceso lo concede.

## Selected cue

```text
/cue/selected/start
```

No lo sustituyas por un número o ID sin confirmar la intención.

## +/- y live

```text
/cue/10/preWait/+ 1
/cue/10/preWait/+/1
/cue/x/opacity/+/live 10
```

La forma `/live/+` está documentada como inválida para el caso combinado.

## Operación no documentada

Si se pide un path inexistente, no propongas uno parecido. Responde: `Not found in the supplied QLab OSC Dictionary.`
