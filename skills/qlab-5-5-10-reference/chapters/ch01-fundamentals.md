# Fundamentals

## Workspace y estructura

Un **Workspace** contiene cue lists, cue carts, cues, patches y configuración. `Workspace Settings` pertenece al workspace que está al frente; sus cambios no afectan otros workspaces y viajan con él. Fuente: [Workspace Settings](https://reference.qlab.app/docs/v5/fundamentals/workspace-settings/).

`Cue Lists` sirven para secuencias; `Cue Carts` para disparos no secuenciales. El `Inspector` expone tabs comunes (`Basics`, `Triggers`) y tabs específicos del cue.

## Group cues

Un **Group cue** contiene child cues, incluso otros Groups. El modo del parent determina el flujo:

- `Timeline`: los hijos empiezan simultáneamente.
- `Playlist`: hijos secuenciales, con crossfading, looping y shuffling opcionales.
- `Start First And Enter`: el playhead entra en el primer hijo.
- `Start First`: arranca el primer hijo y el playhead continúa después del Group.
- `Start Random`: elige un hijo armado y no activo; mantiene una memoria round-robin hasta reabrir el workspace.

Fuente: [Group Cues](https://reference.qlab.app/docs/v5/fundamentals/group-cues/). No extrapoles side effects de reproducción a una edición MCP sin una prueba específica.

## Targets y seguridad de lectura

Distingue cue number, unique cue ID, selected cue, playhead cue y workspace-qualified target. Una consulta ambigua no debe convertirse en una escritura. Para nombres y rutas OSC exactas, usa la skill OSC separada.
