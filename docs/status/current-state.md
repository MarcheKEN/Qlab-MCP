# Estado actual del proyecto

Snapshot provisional de preparación: **2026-08-13 Europe/Madrid**.

Este documento describe la rama de preparación de QLab MCP 0.3.0. El snapshot
canónico definitivo se actualizará mediante una PR docs-only después del merge
en `main`, antes del tag `v0.3.0`.

## Estado Git de preparación

```text
branch: codex/docs
HEAD: preparación local; consultar `git rev-parse HEAD`
base: origin/main verificado antes de iniciar; la rama contiene commits locales de preparación
worktree: commit local de preparación 0.3.0; snapshot aún provisional
```

La referencia remota se verificó con `git fetch origin` y
`git ls-remote origin refs/heads/main` antes de comenzar.

## Objetivo de la preparación

- versión contractual `0.3.0`;
- exactamente 13 tools FastMCP públicas;
- `qlab_edit_cues` como única tool pública de edición;
- CI reproducible en checkout limpio;
- documentación vigente y workorders auditados;
- auditoría arquitectónica sin refactor especulativo.

## Estado de verificación

Los entornos temporales `pip install -e ".[dev]"` y
`uv sync --locked --no-editable --python 3.11 --extra dev` instalaron
correctamente en la comparación inicial. La suite enfocada de contrato MCP y
write pasó con `2245 passed, 1 skipped`; la suite completa local pasó con
`2584 passed, 41 subtests passed` fuera del sandbox gestionado. La verificación
Linux de CI sigue pendiente.

La inspección FastMCP reportó 13 tools y `uv build` generó wheel y sdist
`0.3.0`. El snapshot final posterior al merge sigue pendiente.

## Workorders activos

Los workorders 017, 019, 021 y 022 quedan clasificados como implementación local
con validación runtime pendiente. El workorder 029 sigue siendo trabajo real de
validación runtime pendiente. Esta preparación no ejecuta nuevas pruebas en
QLab ni convierte implementación local en evidencia runtime.

La auditoría arquitectónica acotada está documentada en
[`architecture-audit-0.3.0.md`](architecture-audit-0.3.0.md) y concluye
`no extraction for 0.3.0`.

La investigación agent-facing y de limpieza de Edit está documentada en
[`2026-08-13-mcp-agent-ux-and-edit-cleanup.md`](../development/research/2026-08-13-mcp-agent-ux-and-edit-cleanup.md).

## Límite de evidencia

```text
implementación local
≠
runtime validado
≠
show listo para GO
```

No se ejecutan setters, Create, Delete, playback, GO, `/live` ni raw OSC.
Las referencias históricas y la evidencia runtime previa permanecen bajo
`docs/archive/` y no se reutilizan como prueba nueva de esta release.

## Verificación reproducible

```bash
cd <repo-root>
uv sync --locked --no-editable --python 3.11 --extra dev
PYTHONDONTWRITEBYTECODE=1 .venv/bin/pytest -q -p no:cacheprovider
uv lock --check
uv run fastmcp inspect fastmcp.json
uv build --out-dir /tmp/qlab-mcp-build
git diff --check
git status --short --branch
```

El snapshot final sustituirá este estado provisional después de la PR principal,
el merge en `main`, la PR docs-only final y la verificación del commit que
recibirá `v0.3.0`.
