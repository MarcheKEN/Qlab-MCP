---
name: agent-orchestrator
description: Guía a Codex sobre cuándo y cómo usar subagentes de forma segura en revisiones, auditorías y arreglos de código.
---

# Agent Orchestrator

Usar esta skill para decidir si conviene coordinar subagentes en un repositorio de código y para hacerlo sin crear cambios concurrentes, ruido o riesgo innecesario.

## Decisión rápida

Usar subagentes cuando el trabajo sea amplio, paralelo y mayormente de lectura:

- Revisiones grandes de repositorios, módulos o PRs extensos.
- Auditorías de seguridad que necesiten varias pasadas independientes.
- Búsqueda de bugs en muchas áreas desacopladas.
- Investigación de arquitectura, dependencias, flujos de datos o puntos de entrada.
- Mapeo de tests existentes y huecos de cobertura.
- Validación de hipótesis independientes.
- Refactors controlados que primero requieran inventario, riesgos y plan.

No usar subagentes cuando el agente principal pueda resolver bien con una lectura directa:

- Cambios pequeños o localizados en pocos archivos.
- Diffs pequeños donde basta revisar el parche.
- Tareas mecánicas simples.
- Bugs con causa evidente.
- Cambios donde varios agentes podrían pisarse.
- Cualquier tarea que requiera escribir sobre los mismos archivos desde varios contextos.

## Reglas de coordinación

- Mantener al agente principal como único coordinador.
- Usar subagentes principalmente en modo solo lectura.
- No permitir que varios subagentes modifiquen código a la vez.
- No permitir que varios agentes escriban sobre los mismos archivos.
- Autorizar escritura a un subagente solo si el usuario lo pidió de forma explícita y el alcance está aislado.
- Para arreglos, hacer que los subagentes investiguen y que el agente principal aplique los cambios.
- Mostrar plan antes de cambios importantes o de impacto medio/alto.
- Mostrar diff después de cambios.
- Ejecutar tests existentes cuando sea viable.
- No tocar secretos, credenciales, llaves, tokens, archivos externos al repo ni sistemas externos sin permiso explícito.
- Guardar reportes o artefactos fuera del repo, o en una carpeta claramente indicada y acordada.
- Si aparece conflicto entre hallazgos, reconciliar antes de actuar.

## Tipos recomendados

`explorer`

- Solo lectura.
- Mapea estructura, entry points, dependencias, ownership implícito y zonas de riesgo.
- Entrega archivos revisados, resumen de arquitectura y dudas.

`security-reviewer`

- Solo lectura.
- Busca riesgos reales con evidencia: source, sink, validación, impacto y condiciones de explotación.
- Evita reportar smells sin ruta explotable.

`tester`

- Solo lectura salvo autorización.
- Revisa tests existentes, comandos disponibles, fixtures y huecos de cobertura.
- Propone pruebas concretas con archivos objetivo.

`fixer`

- Usar con cuidado.
- Solo actúa cuando el usuario autoriza cambios explícitamente.
- Preferir que proponga patch o plan, y que el agente principal aplique.

`documenter`

- Solo lectura.
- Resume hallazgos, decisiones, tradeoffs, cambios propuestos y próximos pasos.
- Útil al final de revisiones grandes.

## Flujo recomendado

1. Entender la tarea, alcance, riesgo y criterio de éxito.
2. Decidir si el tamaño o la independencia del trabajo justifica subagentes.
3. Dividir por áreas, no por agentes genéricos: módulos, capas, superficies de ataque, tipos de test o flujos.
4. Dar instrucciones concretas a cada subagente:
   - objetivo;
   - límites;
   - archivos o áreas;
   - modo solo lectura o permiso de escritura;
   - formato de recibo.
5. Pedir recibos de trabajo:
   - archivos revisados;
   - comandos ejecutados;
   - hallazgos;
   - evidencia;
   - dudas;
   - confianza.
6. Reconciliar resultados.
7. Eliminar duplicados.
8. Priorizar por severidad, probabilidad, blast radius y facilidad de verificación.
9. Proponer siguientes pasos.
10. No aplicar cambios sin autorización cuando el impacto sea medio o alto.
11. Si se autorizan cambios, aplicar desde el agente principal.
12. Enseñar diff y ejecutar tests disponibles.

## Formato de recibo para subagentes

Pedir respuestas compactas y verificables:

```txt
Alcance:
- ...

Archivos revisados:
- ...

Comandos:
- ...

Hallazgos:
- [severidad] archivo:línea - evidencia - impacto

Dudas:
- ...

Confianza:
- baja/media/alta
```

## Ejemplos de prompts

### Revisión amplia solo lectura

```txt
Actúa como subagente explorer en modo solo lectura.

Objetivo: mapear el área <area> del repo y detectar riesgos de mantenimiento o bugs probables.

Límites:
- No modifiques archivos.
- No ejecutes comandos destructivos.
- Revisa solo <rutas>.

Entrega:
- Archivos revisados.
- Entry points.
- Dependencias internas relevantes.
- Hallazgos con evidencia archivo:línea.
- Dudas o zonas que requieren otra pasada.
```

### Auditoría de seguridad

```txt
Actúa como subagente security-reviewer en modo solo lectura.

Objetivo: buscar vulnerabilidades reales en <superficie>, con ruta source-to-sink cuando aplique.

Límites:
- No modifiques archivos.
- No reportes solo smells.
- No toques secretos ni credenciales.
- No hagas llamadas externas.

Entrega:
- Archivos revisados.
- Posibles entradas controladas por usuario.
- Sinks sensibles.
- Findings con evidencia, precondiciones, impacto y severidad.
- Falsos positivos descartados y por qué.
```

### Arreglar un finding usando subagentes solo para investigar

```txt
Actúa como subagente investigator en modo solo lectura.

Finding: <resumen del finding>.

Objetivo: validar causa raíz, archivos afectados y estrategia de arreglo mínima.

Límites:
- No modifiques archivos.
- No prepares commits.
- No edites tests.

Entrega:
- Confirmación de validez.
- Ruta exacta del bug o riesgo.
- Archivos que debería tocar el agente principal.
- Tests existentes relacionados.
- Propuesta de test nuevo o actualizado.
- Riesgos del arreglo.
```

### Evitar modificaciones concurrentes

```txt
Actúa como subagente de investigación en modo solo lectura.

Importante:
- No modifiques archivos.
- No generes patches aplicados.
- Si ves un arreglo, descríbelo en texto con archivos y líneas.
- El agente principal reconciliará resultados y aplicará cualquier cambio autorizado.

Entrega solo recibo de investigación con evidencia.
```

## Criterio final

Usar subagentes para aumentar cobertura e independencia, no para perder control. Si la coordinación cuesta más que la tarea, no lanzar subagentes.
