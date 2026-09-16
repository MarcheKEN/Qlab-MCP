# Verifiable samples

The following strings are compared literally with `references/qlab_osc_dictionary.md`.

## Property query and preWait

```text
/cue/{cue_number}/preWait {number}
```

Without an argument, this is a read when the table grants `read`; with `{number}`, it is a write only if the access column grants it.

## Selected cue

```text
/cue/selected/start
```

Do not replace it with a number or ID without confirming the intent.

## +/- and live

```text
/cue/10/preWait/+ 1
/cue/10/preWait/+/1
/cue/x/opacity/+/live 10
```

The `/live/+` form is documented as invalid for the combined case.

## Undocumented operation

If a nonexistent path is requested, do not suggest a similar one. Respond: `Not found in the supplied QLab OSC Dictionary.`
