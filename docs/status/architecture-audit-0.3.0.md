# Auditoría arquitectónica 0.3.0

Fecha: 2026-08-13

## Resultado

`no extraction for 0.3.0`.

La auditoría no encontró una extracción inequívoca que reduzca riesgo sin
mezclar cambios de contrato FastMCP, tokens, validación o runtime. Se conserva
la arquitectura actual para esta release.

## Evidencia

```text
src/qlab_mcp/write/operations.py  11,516 líneas / 490,785 bytes
src/qlab_mcp/write/registry.py     2,555 líneas / 124,438 bytes
src/qlab_mcp/server.py             1,306 líneas / 50,260 bytes
```

`operations.py` concentra el mixin de escritura, Create, Edit, Move, Delete,
preflight, confirm tokens, ejecución y readback de varias familias QLab. Sus
helpers comparten estado, contratos de resultado y límites de seguridad; una
separación durante 0.3.0 tendría riesgo de alterar orden de preflight, consumo
de tokens o verificación posterior.

`registry.py` concentra especificaciones de propiedades, normalización,
validadores, gates y catálogo de capacidades. Es un límite natural para una
revisión posterior, pero no una extracción segura de una sola familia sin
cambiar el contrato de perfiles y operaciones.

`server.py` mantiene la frontera FastMCP: registro de tools, schemas,
anotaciones, timeouts y modelos de respuesta. Eliminar el alias público es una
reducción localizada; no justifica reestructurar el registro en esta release.

## Criterio para después de 0.3.0

Una extracción futura deberá aislar una familia completa, conservar imports y
schemas públicos, mantener los mismos gates/token payloads, y pasar primero los
tests contractuales y de escritura de esa familia. Hasta que exista ese límite,
la prioridad es estabilidad y evidencia de release.
