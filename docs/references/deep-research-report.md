# 1. Estado actual del proyecto (rama “main”)

El repositorio **Qlab-MCP** es un servidor FastMCP que expone herramientas (tools) para interactuar con QLab 5 vía OSC, enfocándose en leer datos (workspaces, cues, settings, estado, detalles) y en efectuar operaciones de escritura seguras (con dry-run y confirmación). El **entry point** parece ser el archivo `src/qlab_mcp/server.py`: allí se crea una instancia `FastMCP(...)`, se decoran funciones como `@mcp.tool` para cada operación, y finalmente se arranca el servidor (`mcp.run()`). Las *tools* públicas corresponden a esas funciones registradas en `server.py`; por ejemplo, habrá tools para listar cues, obtener detalles de cue, leer workspace settings, etc. 

El inicializador de FastMCP está probablemente en `server.py`, algo como:
```python
mcp = FastMCP("QLab MCP", timeout=..., ...)
@mcp.tool
def nombre_tool(...): ...
...
if __name__ == "__main__":
    mcp.run()
```
(la documentación de FastMCP recomienda declarar cada tool con `@mcp.tool` y dejar que el framework genere esquemas y validación automáticamente).

**Responsabilidades actuales:** 
- `server.py` se encarga de inicializar FastMCP, registrar las herramientas y quizá transformar los datos de entrada/salida. Debería delegar la lógica real a otros módulos (por ejemplo, usando *QLabReader*). 
- `QLabReader` (probablemente definido en `src/qlab_mcp/qlab.py`) actúa como fachada para interactuar con QLab: envía comandos OSC, recibe respuestas JSON, mantiene cachés y resuelve identificadores de workspace. 
- El paquete `osc` incluye el cliente OSC y la lógica de direccionamiento (por ej. `osc/client.py`, `osc/addressing.py`), responsables de gestionar la comunicación UDP/TCP con QLab. 
- El paquete `cues` (con módulos como `overview.py`, `details.py`, `query.py`, `profiles.py`) maneja todo lo relativo a leer información de cues: resúmenes de lista de cues, detalles de una cue, búsqueda de cues, perfiles de propiedades, etc. 
- El paquete `settings` (e.g. `workspace.py`, `summarizers.py`) lee la configuración del workspace (p. ej. ajustes de OSC, grupos, etc.) y resume estados relevantes. 
- El paquete `runtime` (aunque no se detalló, quizás gestiona estado en tiempo real de QLab). 
- El paquete `write` contiene la lógica de escritura “gateada”: incluye `operations.py` (definición de operaciones de escritura), `registry.py` (registro de operaciones disponibles), `allowlist.py` (lista de OSC permitidos), `safety.py` (medidas de seguridad), `osc_inventory.py` (inventario de comandos OSC de QLab). 
- Los modelos Pydantic (`models.py`) definen las estructuras de datos para conexiones, estados, cues, settings, write readiness, etc., usados tanto como tipos de entrada de las tools como en las respuestas. 
- `tests/` contiene tests unitarios y de contrato, p.ej. `test_server_tools.py` (pruebas de las herramientas públicas vía snapshots o hashes), `test_write_mode.py` (pruebas de la lógica de escritura), `test_qlab_reader.py` (pruebas de QLabReader). 
- `docs/` alberga documentación interna y especificaciones del proyecto, aparte de la documentación oficial de FastMCP/QLab. 

**Interfaz pública vs implementación interna:** Los *endpoints* MCP (los nombres y parámetros de cada `@mcp.tool`) constituyen la interfaz pública. Todo lo demás (código en `osc/`, `cues/`, `settings/`, `write/`, etc.) es implementación interna. Deberían considerarse estables los nombres de las tools y los modelos de respuesta: cualquier cambio afectaría el contrato externo. Por ello, los tests de herramientas (`test_server_tools.py`) parecen validar la respuesta pública contra snapshots, lo que refuerza que esos outputs son parte del contrato que no debe romperse sin aviso.

**Flujo de petición MCP (mapa claro):** Un cliente MCP (p.ej. un agente AI) invoca una tool definida en `server.py`. El handler de la tool (tal vez directamente o usando `QLabReader`) construye una solicitud OSC (usando `osc/addressing.py` para crear la dirección correcta `/workspace/{id}/...`). Luego usa el cliente OSC (`osc/client.py`) para enviar el mensaje a QLab (UDP en puerto 53000 o TCP con SLIP). QLab ejecuta la acción y responde con un mensaje OSC (JSON). El código recibe la respuesta, la parsea (quizá usando modelos Pydantic en `models.py`) y la convierte en el formato MCP. FastMCP formatea esto como JSON de respuesta al cliente, incluyendo bloques de contenido y/o datos estructurados (p.ej. usando `ToolResult`). En resumen: 

> **Cliente MCP** → `server.py:@mcp.tool` → *handler* → **QLabReader/Módulo interno** → `osc.client` envía OSC → **QLab** → OSC respuesta JSON → parseo a modelo Pydantic → **respuesta MCP** al cliente.

# 2. Análisis de la PR abierta #9 (“feat: add light command dry-run analysis”)

La PR **#9** introduce un nuevo comando de luces (light commands) con soporte de dry-run. Sin acceder al código, cabe inferir que toca: 
- Código runtime: probablemente `write/operations.py` (agregar operaciones para comandos de iluminación, p.ej. `/workspace/{id}/dashboard/setLight`) y quizás `write/registry.py` (registrar la nueva operación), así como modelos en `models.py` para los argumentos de luz. 
- Documentación: tal vez actualizaciones en `docs/` o un roadmap interno para reflejar este nuevo comando. 
- Tests: seguramente añade casos en `test_write_mode.py` o `test_server_tools.py` para verificar comportamiento de luz (dry-run vs real). 
- La PR parece mezclar varias preocupaciones: código de operaciones de luz, la lógica de dry-run/confirmación (posiblemente en `write/`), actualizaciones de tests de contratos, e incluso ajustes de docs/roadmap. 

**Tamaño y riesgos:** Si efectivamente cubre múltiples capas (escritura, tests, docs), es probablemente demasiado grande. Cada bloque (agregar operaciones de luz, modificar registros, crear tests, cambiar docs) podría aislarse en PRs más pequeñas: por ejemplo, primero definir un helper para operaciones de luces en `write/operations`, luego otro PR para integrar el dry-run sobre ellas, y otro para tests y docs. Una PR tan amplia añade riesgo de *conflictos*: `write/operations.py`, `write/registry.py`, `write/allowlist.py`, `models.py` y `server.py` son módulos críticos que cambian con frecuencia. Revisar muchos cambios juntos hace la revisión tediosa y propensa a errores. 

**Estrategia de división:** Se debería:
- **Separar la documentación:** Cualquier cambio en archivos de docs/roadmap no debería mezclarse con código lógico. 
- **Dividir el feature:** Por ejemplo, una PR para *definir los nuevos modelos* (inputs/schemas para comandos de luces), otra para *implementar la operación* en `write/operations`, otra para *actualizar el registry* y *allowlist*, y finalmente *pruebas* (dry-run y real). 
- **Atomizar tests:** Si la PR actual añade tests grandes, podrían dividirse por caso (p.ej. uno para dry-run válido de luz, otro para rechazo). 
- **No mezclar tareas:** Evitar en una sola PR combinar perfil de cues, settings u otros no relacionados. Cada PR idealmente haga sólo una cosa (añadir un comando de luz, o mejorar tests, etc.).

# 3. Hotspots del código

A continuación se identifican los archivos/proyectos de mayor riesgo de cuellos de botella, con sus responsabilidades actuales y recomendaciones:

- **`src/qlab_mcp/server.py`:** *Responsabilidad:* Inicializa FastMCP y registra todas las tools MCP. Actualmente probablemente contiene gran parte de la lógica de enrutamiento de cada tool. *¿Por qué hotspot?* Todas las herramientas públicas pasan por aquí, por lo que cualquier cambio (nombres de parámetros, esquemas de entrada/salida) afecta el contrato MCP. Su tamaño crece con nuevas tools. *Problema:* Mezcla registro de tools con quizás lógica de validación y respuesta. *Cambios seguros:* Agregar nuevas tools (funciones decoradas) o mejorar documentación interna. *Peligroso:* Renombrar o eliminar parámetros de una tool existente (rompe la API), cambiar el valor predeterminado de `timeout` o `mask_error_details` (puede afectar manejo de errores). *Pruebas protectoras:* `test_server_tools.py` parece validar todas las herramientas, atrapando regresiones de contrato (snapshots/hashes). *Faltan tests:* Es útil testear errores (e.g. inputs inválidos) y tiempo de espera. *Reducir conflictos:* Extraer lógica común (conversiones de datos, manejo de errores) a helpers o modelos. Minimizar las ediciones concurrentes: por ejemplo, si se añade una herramienta nueva, en lugar de modificar el mismo archivo `server.py` en paralelo, podría hacerse mediante import de una función definida en otro módulo. 

- **`src/qlab_mcp/qlab.py` (posible *QLabReader*):** *Responsabilidad:* Fachada para interactuar con QLab. Puede incluir mixins para distintos aspectos (conexión, consultas, resolución de workspace), métodos privados (`_request_data`, `_resolve_workspace`, etc.), y manejo de caché. *Por qué hotspot:* Todas las herramientas de lectura (cues, settings, status) dependen de ella; es punto único de error si falla la comunicación OSC. Si está sobrecargada (muchos métodos), puede ser frágil. *Problema:* Demasiadas responsabilidades juntas (gestión de sesión, construcción de comandos, parseo de JSON). *Cambios seguros:* Refactorizar internamente (p.ej. extraer submétodos) si hay buena cobertura de tests. *Peligroso:* Modificar la resolución de workspace o el cliente OSC podría romper muchas herramientas. *Pruebas protectoras:* `test_qlab_reader.py` cubre casos de lectura de datos. *Faltan tests:* Casos de error (e.g. desconexión, passcode inválido), concurrencia, y devoluciones parciales. *Reducir conflictos:* Si es un *God class*, se podría dividir en clases más pequeñas (e.g. `WorkspaceReader`, `CueReader`), o pasar de herencia (mixins) a composición para aislar funcionalidades. Hacerlo en fases, probando que cada lector compacto cubre un subdominio. 

- **`src/qlab_mcp/models.py`:** *Responsabilidad:* Define todos los modelos Pydantic usados para inputs ( argumentos de tools) y outputs (respuestas estructuradas: overview, status, cue details, settings, etc.). *Hotspot:* Es potencialmente voluminoso, y cambios aquí repercuten en contratos de tools. *Problema:* Se concentra mucha lógica de validación en un solo archivo. *Cambios seguros:* Agregar nuevos modelos o campos opcionales. *Peligroso:* Cambiar nombres de campos existentes o estructura (rompe clientes); reasignar tipos. *Pruebas protectoras:* No hay tests directos de modelos, pero `test_server_tools.py` probablemente detecta si la salida ya no encaja en el contrato JSON esperado. *Faltan tests:* Validación de casos límite (p.ej. campos obligatorios ausentes en JSON). *Reducir conflictos:* Si crece mucho, considerar dividir en módulos (`models/cues.py`, `models/settings.py`, `models/write.py`, etc.), pero esto debe hacerse poco a poco, actualizando importaciones y tests conjuntamente. 

- **`src/qlab_mcp/write/operations.py`:** *Responsabilidad:* Contiene la lógica de cada operación de escritura (p.ej. planificar un cambio en QLab, realizar dry-run, aplicar el cambio). *Hotspot:* Probablemente muy grande: todas las operaciones de write (audio, video, texto, luz, etc.) residen aquí. *Problema:* Alta complejidad y a menudo cambiante cuando se añaden nuevos tipos de operaciones. *Cambios seguros:* Encapsular partes en funciones auxiliares; fragmentarlo por responsabilidad (plan vs ejecución) de forma incremental. *Peligroso:* Reestructurar bruscamente (mover funciones) puede romper la registry o tests de write. *Pruebas protectoras:* `test_write_mode.py` verifica el comportamiento en modo dry-run y real. *Faltan tests:* Unitaros para validación previa a la escritura, simulación de timeouts o fallos de confirmación. *Reducir conflictos:* Dividir este módulo: por ejemplo, separar las fases – planificación (`write/planner.py`), validación (`write/validator.py`), ejecución (`write/executor.py`). Así, distintas personas pueden trabajar en diferentes fases sin pisarse. También podríamos agrupar por tipo de media (en video, audio, luz, etc.), si tiene sentido. 

- **`src/qlab_mcp/write/registry.py`:** *Responsabilidad:* Registra las operaciones de write disponibles (posiblemente mapea nombres de tools a funciones en `operations`). *Hotspot:* Cada operación nueva requiere editar este archivo. *Problema:* Si varios features añaden operaciones simultáneamente, habrá conflictos. *Cambios seguros:* Dinamizar el registro (p.ej. descubrir operaciones automáticamente) para evitar editar manualmente. *Peligroso:* Cambiar el orden o eliminar registros; causaría operaciones faltantes. *Pruebas:* Podrían existir tests que verifiquen que el registro contenga ciertas operaciones base. 

- **`src/qlab_mcp/write/allowlist.py`:** *Responsabilidad:* Define qué comandos OSC están permitidos o bloqueados. *Hotspot:* Si QLab agrega nuevas OSC en actualizaciones, este archivo se modifica. *Problema:* Puede crecer sin control. *Cambios seguros:* Mantener este listado actualizado con tests de validación. *Peligroso:* Permitir comandos no seguros sin gate (contrato de seguridad); o bloquear comandos necesarios. *Pruebas:* Idealmente validar que solo están permitidos comandos intencionados. 

- **`src/qlab_mcp/cues/profiles.py`** (y similares en `cues/`): *Responsabilidad:* Quizá define perfiles de consulta de cues (por ejemplo, leer ciertas propiedades específicas). *Hotspot:* Si hay muchos tipos de cues (audio, video, luz) y perfiles, puede crecer. *Problema:* Mezcla lógica de cada tipo de cue. *Cambios seguros:* Agregar nuevos perfiles; *Peligroso:* Cambiar lógica compartida entre cues. *Pruebas:* `test_server_tools.py` probablemente cubre output de consultas de cues generales. Faltaría tests específicos por tipo de cue. 

- **`src/qlab_mcp/cues/details.py`, `query.py`, `overview.py`:** Responsabilidades análogas para detalles de cues, consultas genéricas, y listados. Podrían fragmentarse si crecen. Testearlos asegura la precisión de la información leída. 

- **`src/qlab_mcp/settings/workspace.py`, `summarizers.py`:** Se encargan de leer y resumir settings de workspace. Riesgo medio: no cambian tan a menudo como cues, pero cambios de QLab en OSC afectarán aquí. 

- **`src/qlab_mcp/osc/client.py`, `addressing.py`:** Manejadores de OSC. Responsabilidad: enviar/marcar mensajes OSC. Son críticos: errores aquí rompen toda la comunicación. Rara vez cambian (solo si actualiza protocolo OSC de QLab). Testeables con mocks de sockets. 

- **Test files (`test_server_tools.py`, `test_write_mode.py`, `test_qlab_reader.py`):** *test_server_tools.py* protege el contrato público: probablemente compara respuestas de cada tool con un hash/snapshot. Esto es crucial para detectar cambios no deseados en la salida. Sin embargo, los tests basados en snapshots pueden ser frágiles ante cambios mínimos. *test_write_mode.py* verifica la lógica de escritura/dry-run; cualquier cambio en operaciones orquestadas requiere actualizarlo. *test_qlab_reader.py* valida la lectura de datos QLab; si QLab cambia o hay errores de socket, se debe actualizar. Debemos revisarlos para asegurar que cada área tenga su suite dedicada. Por ejemplo, separar tests de OSC de tests de lógica de negocio. 

# 4. Evaluación de `server.py` como capa MCP

El archivo `server.py` debería funcionar como capa delgada de presentación de herramientas MCP: definir herramientas y delegar. Según FastMCP, las herramientas deben ser funciones Python simples, dejando que el framework genere esquemas y valide. Cualquier lógica compleja (formateo de errores, mezcla de datos, etc.) idealmente debe salir de `server.py`.

- **Registro de herramientas:** Se realiza con `@mcp.tool`. Esto está bien en `server.py`. Para reducir conflictos, podría registrarse herramientas importadas desde otros módulos. Extraer la definición de schemas no es necesario, FastMCP lo hace automáticamente. 

- **Anotaciones de herramientas:** FastMCP permite metadatos (title, hints de lectura/destrucción). Por ejemplo, cada tool puede anotar `read_only_hint=True` si no modifica nada. Esto es importante para marcar operaciones destrucivas vs seguras, como indican las buenas prácticas de FastMCP. Dichas anotaciones podrían definirse junto a la herramienta, o generarse desde la lógica de write-mode si coincide con ACL. No es imprescindible extraerlas, a menos que haya muchas herramientas similares (en cuyo caso podrían definirse en un helper común).

- **Timeouts:** Si las herramientas llaman a QLab, podrían bloquear. FastMCP permite definir `timeout=` en la decoración. Si `server.py` fija tiempos de espera o modo background en herramientas, conviene mantenerlo aquí. No parece necesario extraer esta lógica; es parte de la definición del servidor. Sin embargo, asegúrese de que herramientas de largo plazo usen `task=True` en lugar de solo timeout. 

- **Manejo de errores:** FastMCP ya convierte excepciones en respuestas de error. Si `server.py` incluye “helpers de error” personalizados (e.g. catch de excepciones y conversión manual), probablemente es redundante. Sería mejor confiar en `ToolError` y en `mask_error_details` de FastMCP. Por ejemplo, en [20] se indica que lanzar `ValueError` o `ToolError` ya genera el mensaje de error al cliente, y que enmascarar detalles se controla en el servidor, no en cada herramienta. Si existen rutinas específicas de formateo (como armar siempre un JSON con “status” y “data”), convendría extraerlas como utilidades genéricas.

- **Normalización de payloads:** De manera similar, FastMCP forma automáticamente las respuestas JSON (incluyendo `ToolResult`). Si `server.py` tiene funciones auxiliares para envolver respuestas, podría extraer ese código a un módulo aparte. En particular, si se construyen manualmente diccionarios con `status`/`data`, se podría simplificar usando `ToolResult` o `mcp.types`. Extraer validaciones repetitivas (p. ej. convertir strings a ID) también puede mejorar claridad.

- **Conversión a modelos Pydantic:** Asegurarse de que `server.py` reciba objetos Pydantic directamente como retorno de funciones (FastMCP soporta retornos como objetos Python que castea a JSON). Si `server.py` convierte la respuesta a instancia de modelo (p.ej. `MyModel.parse_obj(response)`), podría delegar esa tarea a FastMCP (el cual genera el esquema de salida) o moverla a los handlers de QLabReader. Es importante que la **lógica de negocio** (lo que hace cada tool) no esté mezclada con detalles de MCP.

**Recomendaciones de extracción:** 
- **Registro de herramientas:** No es necesario extraer; es parte del framework. 
- **Anotaciones de herramienta:** Se pueden dejar con la herramienta, quizá crear constantes si se repiten. 
- **Schemas/tipos de herramientas:** FastMCP genera casi todo automáticamente; no es vital extraer. 
- **Mapeadores de error/respuestas:** Si existen, conviene extraer. Por ejemplo, un módulo `errors.py` que convierta excepciones de QLab en `ToolError` uniformes. Esto mejora pruebas unitarias. 
- **Handlers de herramientas:** Si la función del tool hace demasiado, extraer la lógica a funciones en otros módulos (p.ej. en `cues/` o `write/`), dejando en `server.py` solo la invocación. 
- **Snapshots de contrato público:** Las respuestas de las tools (modelos Pydantic) constituyen el contrato; estos archivos (`server.py` y modelos) deben considerarse estables. Cambiarlos solo si es necesario, y con cuidado de actualizar `test_server_tools.py`.

En resumen, no movería las decoraciones ni registro de herramientas fuera de `server.py`, pero sí extraería cualquier lógica que no sea imprescindible allí. El beneficio real es reducir las responsabilidades de `server.py` para evitar cuellos de botella y conflictos (p.ej. separar validación común, manejo de errores y formateo de respuestas). 

# 5. Evaluación de *QLabReader*

**Responsabilidad:** `QLabReader` (vía `src/qlab_mcp/qlab.py`) funciona como fachada de QLab. Según la descripción, usa mixins y métodos compartidos (`_request_data`, `_request_data_with_tcp_fallback`, `_resolve_workspace`, `_workspace_data`) para abstraer la conexión OSC, resolución del workspace activo/seleccionado y la comunicación con el cliente OSC. También maneja caché de lecturas frecuentes y puede tener métodos legacy. 

**¿Demasiada responsabilidad?** Si `QLabReader` utiliza herencia múltiple (mixins) y agrupa muchas funcionalidades (conexión, consultas varias, caching), corre el riesgo de convertirse en una “God class”. Cada módulo (cues, settings, runtime) lo utiliza intensamente, generando acoplamiento. Sin el código fuente es difícil medir, pero *podría* estar haciendo demasiado. 

**Aspectos a evaluar:** 
- *Mixins y herencia:* Si cada mixin aporta métodos relacionados (p.ej. `CueReaderMixin`, `SettingsReaderMixin`), podría ser más claro: cada mixin sería responsable de una categoría de operaciones. Eso está bien. Pero si se llega a una jerarquía compleja, quizás convenga refactorizar a composición. 
- *Clientes OSC:* QLabReader depende directamente de un cliente OSC (`osc/client.py`). Idealmente, sería el encargado único de gestionar puertos y fallbacks (UDP vs TCP), lo que está bien. 
- *Caché de lectura:* Si existe, mejora el rendimiento pero añade complejidad de invalidación. Ver si está bien encapsulado. 
- *Resolución de workspace:* Método `_resolve_workspace` probablemente identifica qué workspace usar (por ID, nombre o el actual). Bien en esta clase, pero podría abstraerse. 
- *Compatibilidad/legacy:* Si hay métodos para versiones antiguas o sin soporte de ciertas funciones, conviene marcarlos y evaluar remover o refactorizar más tarde. 

**Recomendaciones:** Mantener `QLabReader` como fachada es razonable por ahora (centraliza la interacción con QLab). Sin embargo, para disminuir acoplamiento:
- Se podría reducir la herencia: en lugar de tener `class QLabReader(Base, CueMixin, SettingsMixin, ...)`, usar **composición**: `self.cue_reader = CueReader(self)`, etc., para que cada parte use al cliente principal. Esto facilita testing. 
- Extraer servicios internos: por ejemplo, un `WorkspaceService` para todo lo de workspace (conexión, status), y otro `CueService` para cues. Cada uno operaría con el cliente OSC. 
- Interfaces pequeñas: definir interfaces (p.ej. `get_cue_list(workspace)` vs `get_workspace_settings(id)`). 
- Pero: ya que el proyecto es joven y la arquitectura está definida, tal refactor sería grande. La prioridad debería ser no romper funcionalidad. Por ello, quizá quede para una fase posterior, tras reforzar tests. 

En conclusión, la recomendación pragmática es: **dejar QLabReader como está en el corto plazo** (es la fachada obvia), pero a medida que crezca, contemplar dividirlo: p.ej. `QLabWorkspaceReader`, `QLabCueReader`, cada una con su `osc_client`. Primero enfocarse en que `QLabReader` esté bien cubierto por tests; si falla la claridad, entonces empezar a extraer en ramas separadas, sin desmantelar todo de golpe. En resumidas cuentas: dividir por fases, guiado por necesidad (síntomas de código difuso) más que por simpatía. 

# 6. Modelo OSC/QLab

Comparando el diseño del proyecto con el **OSC Dictionary oficial de QLab 5**, se observa:

- **Construcción de direcciones OSC:** QLab usa rutas como `/workspace/{id}/...`. Según la doc, un mensaje `/workspace/{id}/cueLists` obtiene datos sólo del workspace especificado. Si se omite `/workspace`, el mensaje se envía a *todos* los workspaces abiertos en ese puerto. El código debería usar siempre `/workspace/{id}` para asegurar la dirección correcta. Se nota en [46] que se recomienda prefijar con `/workspace/{id}` o `{name}` para dirigir mensajes. El proyecto debe manejar *ID o nombre* del workspace, pues ambos son válidos. 
- **Transporte OSC (UDP/TCP):** QLab escucha OSC en UDP puerto 53000 (por defecto) y responde en 53001. En TCP utiliza encapsulado SLIP doble. El proyecto OSC client debe soportar ambos, probando UDP y cayendo a TCP si falla, tal como sugiere `_request_data_with_tcp_fallback`. 
- **Parsing JSON y estados:** QLab devuelve respuestas JSON con campo `status` y (posiblemente) `data`. El diccionario indica que `status` será `"ok"`, `"error"` o `"denied"`. El código debe interpretar `"error"` y `"denied"` adecuadamente (por ejemplo, lanzar excepción de control de acceso o validación). Es crítico: `"denied"` ocurre si no se ha conectado con passcode o sin permisos. 
- **Manejo de “connect” y passcode:** QLab requiere enviar `/workspace/{id}/connect {passcode}` para autenticarse. El servidor debe manejar ese paso; incluso recordar si ya se conectó. La doc nota que `/version` y `/workspaces` no requieren passcode, pero todos los demás (p.ej. `/cueLists`) sí. 
- **Permisos (view/edit/control):** El diccionario clasifica cada comando según privilegios (columnas *view*, *edit*, *control*). La app debería contemplar esto: operaciones de solo lectura se pueden hacer en cualquier modo, pero operaciones destructivas (p.ej. `/workspace/{id}/go`, `/delete`, `/cue/{num}/panic`) requieren permisos mayores. Esto se refleja en `annotations` de FastMCP (p.ej. `destructive_hint` debería ser `true` para `/go` o `/delete`). 
- **Cue IDs vs Cue números:** QLab distingue *cue number* (orden dentro de la lista) de *cue ID* (UUID). El dict. muestra rutas para ambos: p.ej. `/workspace/{id}/delete/{cue_number}` y `/delete_id/{cue_id}`. El código debe permitir ambas referencias (quizá un parámetro permite número o ID). 
- **Comandos read-only vs read/write:** Por ejemplo, `/cue/10/preWait` lee un valor; `/cue/10/preWait 5` lo modifica (read/write). El proyecto debería usar ese patrón: separar herramientas de solo lectura de las de escritura. Las herramientas read-only podrían marcarse con `read_only_hint=True`. 
- **Operaciones peligrosas:** Según la doc, `/go`, `/cue/x/fire`, `/delete`, `/panic`, etc., no envían respuesta por defecto y son destructivas. Estas deben tener “dry-run” y gates en el código. Por ejemplo, la operación de luz (`/dashboard/setLight`) probablemente sea considerada destructiva y se implementaría similarmente (como sugiere el contexto de PR #9). 

**En resumen:** El diseño ideal **debería seguir el diccionario OSC**: 
1. **Prefijos claros:** Cada mensaje usa `/workspace/{id}` para dirigirlo.  
2. **Transportes separados:** UDP (puerto 53000/53001) y TCP (SLIP) gestionados internamente.  
3. **Respuestas y errores:** El código debe interpretar correctamente `status: ok/error/denied`, lanzando errores o abortando según corresponda.  
4. **Permisos:** Implementar gating según hint (read_only, destructive, etc.), alineado a permisos view/edit/control del OSC Dict.  
5. **Seguridad:** Ejecutar `connect` con passcode antes de operaciones críticas.  
6. **Abstracciones propias:** Más allá del protocolo, el proyecto puede tener abstracciones (models Pydantic, operaciones planificadas) para facilitar el trabajo, pero no deben ocultar detalles esenciales del protocolo (p.ej. direcciones OSC correctas, parseo JSON estándar).

# 7. Evaluación de `models.py`

`models.py` contiene los modelos Pydantic que definen los datos intercambiados. Posibles agrupaciones: conexión (`ConnectionModel`), overview de cues, settings de workspace, estado de cue, resultados de queries, datos de readiness de escritura, datos para crear/actualizar cues, esquemas de herramientas de entrada. 

**¿Dividir?** En principio, separar modelos por dominio (por ejemplo, `models/connection.py`, `models/workspace.py`, `models/cues.py`, `models/settings.py`, `models/write.py`, `models/errors.py`) puede mejorar la organización. **Ventajas:** reduce tamaño de cada archivo, evita confusiones al importar, agrupa relacionados. **Inconvenientes:** reestructurar imports en todo el código, actualizar tests y herramientas que usen esos modelos. Sería un refactor considerable con alto riesgo de conflictos si se hace de golpe.

**Coste/riesgo:** Los modelos están intimamente ligados al contrato público. Un cambio de archivo (nombre o ubicación) afectaría a todo `server.py` y tests. Se tendrían que ajustar múltiples `import`. Dado el tamaño actual (desconocido, pero puede ser grande), el beneficio de claridad podría ser contra-restado por la complejidad de reorganizar. 

**Recomendación:** Primero reforzar cobertura de tests de los modelos (p. ej. validación de esquemas). Si se observa que `models.py` se ha vuelto difícil de manejar, entonces en fases posteriores se podría dividir. Pero hacerlo solo tras tener una razón fuerte (por ejemplo, muchos cambios concurrentes) y bajo tests intensivos. En resumen, **no dividir inmediatamente**. Mantenerlo intacto en el corto plazo para evitar errores de import, y quizá planificar su refactor en etapas pequeñas una vez que otras dependencias estén listas.

# 8. Evaluación del *write mode*

La arquitectura actual de escritura “gateada” implica: `write/operations.py`, `registry.py`, `allowlist.py`, `safety.py`, `osc_inventory.py`, más tests. Contempla dry-run, confirm tokens, actual execution con verificación posterior. 

**Responsabilidades:** 
- `operations.py` probablemente crea el plan (lista de comandos OSC), la envía en modo dry-run (sin efecto real) y luego (al confirmarse) lo ejecuta en QLab. 
- `registry.py` mapea operaciones escritas a funciones.
- `allowlist.py` lista comandos permitidos para seguridad.
- `safety.py` quizás decide qué hacer en caso de errores o si abortar.
- `osc_inventory.py` puede contener metadatos de OSC disponibles. 

**Separación interna:** Actualmente puede que `operations.py` haga todo: generación del plan, validación de parámetros, ejecución con QLabReader, verificación de resultados. Sería mejor dividirlo en fases: 

1. **Planificación (`planning`):** Dado un requerimiento (por ej. “setear luz” o “insertar cue”), construir un plan *abstracto* (lista de cambios a realizar). Este plan no toca QLab. Facilita tests unitarios aislados. 
2. **Validación (`validation`):** Antes de ejecutar, chequear coherencia del plan (p.ej. que los cue IDs existen). Se puede lanzar error si hay inconsistencia. 
3. **Confirmación / Token:** Obtener un token o permiso (actualmente lo pide el usuario). Esto ya existe con el concepto de “dry-run” y confirmación. Solo debe orquestar calls.
4. **Ejecución (`execution`):** Enviar los comandos al QLab (posiblemente en batch) usando el cliente OSC. 
5. **Verificación (`verification`):** Leer de QLab para confirmar que el resultado fue el deseado (p.ej. verificar que una cue fue creada o modificada). Esto puede requerir re-lectura del estado (¿quizá con QLabReader?). 
6. **Construcción de resultados (`result builder`):** Formar la respuesta de la operación (p.ej. cuántos cambios aplicados, nuevos IDs). 

Además, dentro de operaciones podrían diferenciarse por tipo de media: audio, video, text, light tienen detalles propios. 

**¿Dividir `write/operations.py`?** Sí, conviene si está muy grande. Se podría crear submódulos:
- `write/planner.py`: funciones para generar planes.
- `write/executor.py`: funciones que realmente envían los OSC y validan. 
- `write/validator.py`: comprueba antes y después que los objetivos se cumplan. 
- `write/confirm.py`: maneja tokens/semaforización. 
- O bien dividir por dominio (video, text, etc.), pero eso puede fragmentar la lógica general. Prefiero por fase, ya que es más genérico.

**Riesgos/beneficios:** Refactorizar write-mode es delicado por la naturaleza crítica de las operaciones. Pero dividir reduce conflictos futuros (varias personas pueden trabajar en diferente fase). El riesgo es introducir bugs en la secuencia. Para mitigarlo: primero caracterizar con tests las operaciones existentes (como en un juego de pruebas de caja negra), luego extraer partes gradualmente. 

En concreto, **si se recomienda división:** Hacerlo en pasos, p. ej.:
- Extraer un “planificador” que genere lista de (address, args).
- Crear un módulo de validación que las verifique.
- El executor envía cada comando con QLabReader. 
- Dejar la función principal de cada tool como coordinador: llamada a planificador, confirmación, luego a executor y verificador. 

Esto mejora la claridad y testabilidad de cada componente.

# 9. Evaluación de los tests como red de seguridad

**Cobertura actual:** Los tests existentes parecen cubrir:
- Contrato de las herramientas públicas (mediante snapshots/hashes) en `test_server_tools.py`. Protege las respuestas MCP (estructura y contenido) que los clientes esperan. 
- Modo escritura (`test_write_mode.py`): verifica que las operaciones dry-run realicen una simulación correcta y que la ejecución real aplique los cambios esperados, además de gates (tokens). 
- Lectura QLab (`test_qlab_reader.py`): valida que QLabReader construya correctamente las consultas y procese las respuestas (probablemente usando mocks). 

**Protecciones:**
- El comportamiento público de las tools está protegido en `test_server_tools.py`. Cada herramienta (por ejemplo, “listar cues”, “leer settings”) debe devolver un JSON que corresponde al contrato. Este test es clave: si se rompe algo en el código, este test fallará (indicando que la respuesta cambió). 
- Validaciones de FastMCP (esquemas de entrada, manejo de errores) se incluyen implícitamente: si una herramienta no respeta su tipo, FastMCP lo rechaza y podría fallar el test. 
- Los contratos de modelos Pydantic también están protegidos indirectamente: si JSON difiere del esquema, FastMCP lanzará error o la validación de test detectará inconsistencias. 

**Tests como characterization:** Parece que `test_server_tools.py` actúa como test de caracterización: asegura que el comportamiento actual se mantenga. Cualquier refactor requerirá actualizar estos snapshots. 

**Tamaño/fragilidad:** Los tests que usan snapshots o hashes pueden ser frágiles: un cambio legítimo (por ejemplo, añadir un campo extra o reformatear un string) requiere actualizar manualmente el snapshot. Si el test es monolítico (prueba todo en bloque), puede ser difícil aislar qué cambió. Sería mejor separar pruebas por tool individual. 

**Separación de tests:** 
- Puede haber tests muy grandes (p.ej. uno solo que comprueba todas las herramientas). Sería útil dividirlos: un test por tool (o al menos por categoría: cues, settings, workspace). Así, cambios en una tool no rompen todos.
- Similar para write: quizás un test específico por operación write, en lugar de un solo test general. 
- Tests de QLabReader deberían enfocarse solo en métodos públicos, con un cliente OSC simulado. Por ejemplo, pruebas unitarias que pasen un diccionario JSON y verifiquen que retorna el modelo correcto. 

**Tests faltantes:** 
- Comportamiento en caso de errores de QLab (timeouts, errores OSC, datos inesperados).
- Estado de edge cases (cue no existe, workspace invalid). 
- Escenarios multi-workspace: si se envía sin `/workspace`, ¿qué hace el código? 
- Confirmaciones de tokens inválidos. 
- Permisos (ver que al usar passcode incorrecto obtenga “denied”). 

**Tests específicos por área:** Se sugiere separar tests según funcionalidad: 
- **Servidor/Tools:** Ejecutar siempre los tests que cubren las herramientas públicas (`test_server_tools.py`), pues garantizan estabilidad de la API. 
- **OSC:** Tal vez un test que verifique construcción de direcciones OSC, puertos, etc. 
- **Lectura de cues:** Tests unitarios de `cues/*` usando QLabReader simulado. 
- **Settings:** Similar para `settings/*`. 
- **Write mode:** `test_write_mode.py` debe ejecutarse en cada PR que modifique `write/`. 
- **Docs-only PRs:** No necesitan correr lógicamente los tests funcionales, pero se podría ejecutar una validación de formatos o links. 

En especial, **`test_server_tools.py` es crítico**: protege el contrato público de las tools. Antes de refactorizar cualquier tool, hay que actualizar su correspondiente snapshot en este test. Esto funciona como red de seguridad (characterization): refleja el comportamiento actual y permite compararlo tras cambios. 

En conclusión, la suite de tests debe revisarse para asegurarse de que **cada área clave tenga tests dedicados** y que ningún test sea demasiado grande. Los tests existentes conforman una base, pero convendría aumentarlos para cubrir casos de error y separar mejor las responsabilidades. 

# 10. Estrategia de modularización futura

Basándonos en el repo actual, proponemos una arquitectura modular en capas:

- **`server/` (o en raíz):** Contiene `server.py` mínimo y tal vez un subpaquete `tools/` si las definiciones crecen. *Responsabilidad:* Solo el arranque del servidor y registro de herramientas. *Estado actual:* `server.py` grande. *Problema:* Cuello de botella, conflictos. *Cambio:* Dejar solo inicialización y registrar herramientas (incluir solo importaciones de handlers), extraer lógica a módulos `handlers/`. *Riesgo:* Moderado al principio (porque hay que reorganizar imports en tests). *Beneficio:* Facilita paralelismo (una persona trabaja en una herramienta sin tocar el core). *Orden:* Fase temprana. *Tests:* `test_server_tools.py`.

- **`osc/`:** *Responsabilidad:* Lógica OSC de bajo nivel: enviar/recibir paquetes, armar direcciones. *Estado:* Ya existe. *Problema:* Podría crecer poco. *Cambio:* Mantener separado. Posible mejora: exponer interfaz estable para enviar OSC, y quizá tests unitarios para direcciones construidas. *Riesgo:* Bajo. *Beneficio:* Código centralizado de comunicaciones. *Tests:* Validar funciones de addressing, cliente. 

- **`qlab_reader/` (anterior `qlab.py`):** *Responsabilidad:* Interfaz de lectura a QLab (composición de osc). *Estado:* Demasiado grande; basado en mixins. *Cambio:* Eventualmente dividirlo por dominios (ej. `WorkspaceReader`, `CueReader`, `SettingsReader`). *Riesgo:* Alto de inicio, debe hacerse después de tests. *Beneficio:* Mayor claridad, menos acoplamiento. *Orden:* Fase 3. *Tests:* `test_qlab_reader.py` y nuevos tests para subclases.

- **`models/`:** *Responsabilidad:* Esquemas Pydantic. *Estado:* Actualmente único archivo. *Problema:* Tamaño, muchas dependencias. *Cambio:* Si se divide (p.ej. `models/cues.py`, etc.), hacerlo cuidadosamente. *Riesgo:* Alto (conflitos de import, tests). *Beneficio:* Organización. *Orden:* Fase 4 (solo si es necesario). *Tests:* Testear validación de esquemas nuevos, nada más específico.

- **`cues/`:** *Responsabilidad:* Lectura de cues. Subcarpetas/module por funcionalidad: 
  - `cues/overview.py` (listar cues), 
  - `cues/details.py` (detalles de un cue), 
  - `cues/query.py` (búsqueda por nombre/ID), 
  - `cues/profiles.py` (listas de propiedades a leer). 
  *Estado:* Separado ya. *Cambio:* Podría requerir refactor si un archivo crece mucho. *Riesgo:* Medio. *Beneficio:* Mantenibilidad. *Orden:* Puede mantenerse, refactor en fases según necesidad. *Tests:* Agregar tests específicos para cada módulo.

- **`settings/`:** *Responsabilidad:* Leer settings de workspace (ajustes de OSC, carpetas de media, etc.). Seguir una división similar si hay subsecciones (por ejemplo, `settings/workspace.py`, `settings/routing.py`, etc.). *Estado:* Módulos existentes `workspace.py`, `summarizers.py`. *Cambio:* Ver si necesitan más separación (p.ej. `settings/osc_settings.py`). *Riesgo:* Bajo/medio. *Tests:* Tests unitarios para resúmenes de settings. 

- **`runtime/`:** *Responsabilidad:* Estado en tiempo real (e.g. ejecución actual, playhead). *Estado:* Incógnito. *Cambio:* Si existe mucha lógica, modularizar (ej. `runtime/state.py`, `runtime/queries.py`). *Riesgo:* Medio. *Tests:* Para actualizaciones de estado. 

- **`write/`** (reestructuración): *Responsabilidad:* Escritura gateada. 
  - `write/registry.py` (mapea operaciones) – *Estado:* existente. *Problema:* Colisión si varios agregan operaciones. *Cambio:* Tal vez cargar módulos dinámicamente (p.ej. un decorador en operaciones que registra). *Riesgo:* Medio. *Tests:* Confirma registro correcto.
  - `write/planner.py` (nuevo): genera planes a partir de peticiones. 
  - `write/validator.py` (nuevo): valida planes. 
  - `write/executor.py` (nuevo): ejecuta comandos en QLabReader. 
  - `write/verifier.py` (nuevo): lee de QLab después para asegurar consistencia. 
  - `write/allowlist.py` (actual): cont. de comandos permitidos. *Cambio:* Documentar mejor qué contiene, quizá refinarlo. 
  - `write/safety.py`: manejos de bloqueo/fallos, dejarlo como utilidad. 
  - `write/osc_inventory.py`: inventario de comandos QLab, podría mantenerse. 
  *Problema:* `operations.py` actual es un bottleneck. *Orden:* Separar operaciones por fase (planner primero, luego executor, etc.). *Riesgo:* Alto si no se testea bien. *Tests:* `test_write_mode.py`, dividir en tests unitarios por fase.

- **`docs/` y `reference/`:** Contienen guías y especificaciones. *Cambio:* Organizar en subcarpetas por tema (FastMCP, QLab, arquitectura). Mantener separados de código. *Riesgo:* Bajo. *Tests:* Validación de enlaces o formato si se desea. 

- **`tests/`:** Estructurar en paralelo a `src/`: 
  - `tests/server/` (para herramientas), 
  - `tests/osc/` (para addressing y client), 
  - `tests/qlab/` (cubrimiento de QLabReader y modelos), 
  - `tests/write/` (para cada parte: planner, executor), 
  - `tests/cues/`, `tests/settings/` para sus áreas. 
  *Cambio:* Mover test_ files a carpetas temáticas. *Riesgo:* Bajo. *Beneficio:* Claridad. *Orden:* Fase 1 (reorganización sencilla). 

Esta arquitectura por módulos permitirá que equipos/parches trabajen en paralelo: por ejemplo, uno puede implementar nuevas *tools* de cues leyendo sin tocar `write/`, otro puede mejorar la capa OSC, otro puede refinar el registro de writes, etc. Las áreas con baja interdependencia (p.ej. `osc/` vs `write/`) pueden hacerse concurrentemente. 

# 11. Estrategia de ramas y PRs

Para coordinar múltiples colaboradores (o “chats de Codex”), proponemos:

- **Convención de nombres:** Usar prefijos claros: `feature/`, `fix/`, `refactor/`, `docs/`. Por ejemplo: `feature/light-commands`, `refactor/write-planner`, `docs/architecture`. Incluir issue/PR si aplica. 

- **Tamaño máximo PR:** Idealmente no mayor a ~200-300 líneas de cambio y pocas decenas de archivos. Cada PR debe tener un objetivo único claro. Evitar PRs con mezclas de varios temas (ni tests, ni docs, ni código en un solo PR grande). 

- **Cambios a no mezclar:** Nunca mezclar lógicas diferentes: p.ej., *no* juntar cambios de arquitectura (`models.py`) con nuevas features de usuario. Docs sólo con docs, tests sólo con tests de la misma área, refactorizaciones sólo con código relacionado. 

- **Archivos de secuencia única:** 
  - *server.py* y *models.py* son contratos públicos; editar solo cuando sea imprescindible (nuevas tools o campos). Coordinar con el equipo para no duplicar esfuerzos aquí. Por ejemplo, si se va a añadir un nuevo campo al modelo de cue, hacerlo antes de que otra rama lo use. 
  - *write/operations.py* tiende a crecer mucho; quizás hacer merge secuencial por bloques de operaciones (p.ej. primero audio, luego video, luego texto), en lugar de que varios lo editen simultáneamente. 
  - *tests/test_write_mode.py* depende de operaciones; mejor actualizarlo al final de cada refactor de write. 

- **Archivos paralelos:** 
  - Diferentes partes de cues (`overview.py`, `details.py`, etc.) pueden trabajarse en paralelo. 
  - `osc/addressing.py` vs `osc/client.py`: cambios en uno no deberían afectar tanto al otro, así paralelizable. 
  - Nuevas operaciones de write (nuevas clases o funciones) idealmente en archivos separados al principio, luego integrarlos en el flujo existente. 

- **Separación de features grandes:** Por ejemplo, la característica de soporte completo de luz debería dividirse: una PR solo crea los modelos (inputs) para un comando de luz; otra PR define la función en `operations.py`; otra actualiza `registry.py`; otra agrega tests; otra ajusta docs. 

- **Uso de ramas base intermedias:** Si un feature A depende del refactor B, hacer primero una rama para B, luego en B crear A. No mezclar en una sola. Por ejemplo, si se quiere agregar un módulo de planificación de operaciones, primero crear PR `feature/write-planner`, mergear, luego ramificar `feature/write-light-dryrun` desde `main`. 

- **Cuándo mergear a main:** Mergear PRs que añadan features atómicos o refactors con tests completos. Dejar `main` siempre en estado funcionando (p.ej. ejecutando tests). 

- **Ramas “umbrella”:** Usar solo si varias PRs pequeñas forman parte de un gran feature. Por ejemplo, crear una rama `feature/write-refactor` desde la cual salen sub-PRs (aunque cada PR debería tener su propia rama en origen). Luego fusionar la rama umbrella a main al final, asegurando que todas las sub-PRs estén integradas. Esto evita conflictos repetidos de merge. 

- **Evitar PRs gigantes:** Si una PR creció demasiado, es mejor cerrarla y reabrir múltiples. Se debe revisar en draft frecuentemente. 

- **Priorizar merges tempranos:** No dejar PRs viejos abiertos sin merge por mucho tiempo. Si algo está hecho y testeado, fusionarlo en main pronto para que otros partan de la última versión. 

**Ejemplos de PRs ideales:** 
- *“feat/cues-overview-tool”*: agrega la tool para listar cues. Afecta `server.py` (registro), `cues/overview.py` (lógica), `models.py` (modelo de respuesta), tests específicos de cues. 
- *“refactor/write-planner”*: extrae funciones de planificación de `operations.py` a `write/planner.py` y adapta llamadas. Afecta `operations.py`, nuevo `planner.py`, tests de planificación. 
- *“docs/architecture-update”*: mejora la documentación interna, sin tocar código de lógica. Podría actualizar diagramas o README. 

Estos PRs segmentados facilitan revisión y reducen conflictos, cumpliendo que `server.py`, `models.py`, `operations.py` y los tests clave no sean file de conflicto constante.

# 12. Plan de refactorización incremental

Dividimos el refactor en fases pequeñas, cada una con objetivos claros:

1. **Caracterización de tests:** **Objetivo:** Aumentar cobertura con tests de caracterización. Archivos: *tests existentes*, principalmente. Cambios: escribir tests unitarios para funciones críticas (p.ej. métodos de QLabReader y validadores en write). **No tocar:** Lógica de producción. **Riesgo:** Bajo. **Beneficio:** Seguridad para refactorizaciones futuras. **Tests obligatorios:** Todos de lectura y escritura. **Paralelo:** Varios pueden escribir tests diferentes al mismo tiempo. **Prompt Codex sugerido:** “Analiza los tests actuales y genera ejemplos de tests unitarios faltantes para cubrir casos borde de `QLabReader`.”

2. **Extraer helpers de error/response de `server.py`:** **Objetivo:** Mover lógica de manejo de errores o normalización de respuestas a un módulo separado (ej. `server/errors.py`). Archivos: `server.py`, nuevo `errors.py`. Cambios: Identificar código repetido (p.ej. manejo de exceptions) y moverlo. **No tocar:** Definiciones de herramientas o modelos. **Riesgo:** Bajo/Medio (puede romper el formateo de respuestas si no se hace bien). **Beneficio:** Menos peso en `server.py`. **Tests:** `test_server_tools.py` debe seguir pasando. **Paralelo:** Puede hacerse mientras otros trabajan en módulos `cues/`, etc. **Prompt Codex:** “Extrae la lógica de manejo de excepciones de las funciones en `server.py` a un nuevo módulo de utilidades, modificando las llamadas.”

3. **Extraer tipos/schemas de tools:** **Objetivo:** Si hay argumentos que usan Pydantic o `Annotated`, extraer definiciones de tipos en `models.py`. Archivos: `server.py`, `models.py`. Cambios: Mover definiciones complejas (enums, Literal) a `models`. **No tocar:** Funcionalidad, solo refactor de import. **Riesgo:** Bajo. **Beneficio:** Claridad en `server.py`. **Tests:** Ninguno nuevo, solo revisar comportamiento. **Paralelo:** Sí, varios handlers pueden hacer esto por separado. **Prompt:** “Crea modelos Pydantic para los argumentos de las tools de `server.py` y actualiza las firmas de las funciones para usarlos.”

4. **Reducir hotspots en operaciones de write:** **Objetivo:** Dividir `write/operations.py` en partes. Archivos: `write/operations.py`, crear `write/planner.py`, `write/executor.py`, etc. Cambios: Mover funciones coherentes a los nuevos módulos y modificar llamadas. **No tocar:** Lógica interna de cada función (aún). **Riesgo:** Medio/Alto (error en imports o lógica de secuencia). **Beneficio:** Menos conflictos al agregar nuevas operaciones. **Tests:** `test_write_mode.py` para confirmar que nada cambia externamente. **Paralelo:** Otro puede trabajar en operaciones específicas mientras se reestructura. **Prompt:** “Refactoriza el archivo `write/operations.py` separando la parte de planificación de la parte de ejecución en módulos distintos, manteniendo el mismo comportamiento.”

5. **Reorganizar modelos (`models.py`):** **Objetivo:** Dividir `models.py` en varios archivos según dominio. Archivos: `models.py` reemplazado por carpeta `models/` con `workspace.py`, `cues.py`, etc. Cambios: Crear nuevos archivos de modelos, ajustar imports en el código. **No tocar:** semántica de modelos. **Riesgo:** Alto (múltiples imports en todo el proyecto). **Beneficio:** Mejor organización a largo plazo. **Tests:** Todos, para asegurarse de que los modelos se cargan correctamente. **Paralelo:** Sí, pero coordinar para no duplicar esfuerzos en importar modelos. **Prompt:** “Divide `models.py` en archivos por categoría (p.ej. cues, settings, write) y actualiza las referencias en el proyecto.”

6. **Mejorar documentación de arquitectura:** **Objetivo:** Añadir diagramas o explicaciones claras en `docs/`. Archivos: en `docs/`. Cambios: Crear un documento de arquitectura con flujo de datos. **No tocar:** Código. **Riesgo:** Bajo. **Beneficio:** Ayuda a nuevos contribuyentes a entender modularización. **Tests:** No aplica. **Paralelo:** Sí. **Prompt:** “Genera un diagrama y texto explicativo del flujo de datos en el servidor MCP para `docs/arquitectura.md`.”

7. **Reglas para futuras features:** **Objetivo:** Escribir guía (tal vez en `docs/`) con buenas prácticas para este proyecto (basadas en MCP y QLab). Archivos: nuevo documento en `docs/`. **Riesgo:** Bajo. **Beneficio:** Previene crecimiento desordenado. **Tests:** No. **Paralelo:** Sí. **Prompt:** “Redacta un documento de reglas de arquitectura para este proyecto, incluyendo pautas sobre tools, modelos y segregación de lógicas.”

Cada fase debe ser una PR independiente, suficientemente pequeña para revisión. Se puede trabajar en paralelo en áreas distintas (p.ej. un desarrollador mejora tests mientras otro extrae helpers).

# 13. Riesgo de conflictos (por archivo)

| **Archivo**                   | **Motivo de conflicto**                                             | **Frecuencia de cambios** | **Riesgo**  | **Quienes lo tocan**         | **Estrategia para reducir conflictos**               | **Tests asociados**                    | **Recomendación**               |
|-------------------------------|--------------------------------------------------------------------|---------------------------|-------------|-----------------------------|-----------------------------------------------------|----------------------------------------|-------------------------------|
| `server.py`                   | Registro de herramientas (cualquier nueva tool)                    | Alto (nuevo feature)      | Alto        | Módulos de features, integradores de API | Extraer lógica repetitiva, minimizar cambios de firmas | `test_server_tools.py`                | Evitar tocar salvo necesidad; manejar secuencialmente |
| `qlab.py` (QLabReader)        | Lógica de comunicación con QLab (muy central)                     | Medio                     | Alto        | Funcionalidad de lectura/escritura    | Refactorizar en fases, cubrir con tests antes     | `test_qlab_reader.py`                 | Tocar sólo con gran cuidado (facade)   |
| `models.py`                   | Modelos de datos compartidos (muchas dependencias)                 | Medio                     | Alto        | Cualquier tool o validación        | Consolidar antes de dividir, revisar imports       | Varios tests de output               | Solo cambios planificados secuencialmente |
| `write/operations.py`         | Lógica de cada operación de escritura                              | Alto (nuevas ops)         | Alto        | Desarrollo de features de write    | Dividir por responsabilidades (planner/executor)   | `test_write_mode.py`                 | Evitar edición simultánea de varias operaciones |
| `write/registry.py`          | Registro de operaciones (agregar nuevas)                          | Medio                     | Medio       | Desarrollo de features de write    | Auto-registro basado en decoradores               | `test_write_mode.py`                 | Coordinar paralelismo (una persona añade ops a la vez) |
| `write/allowlist.py`         | Lista de comandos permitidos (actualizaciones de lista)           | Bajo                      | Medio       | Seguridad/Permisos               | Mantener actualizado con tests de permisos        | N/A (implicito en tests de write)    | Cambios ocasionales, baja concurrencia |
| `cues/overview.py` y co.     | Lógica de lectura de cues (alta demanda de features)              | Medio                     | Medio       | Desarrollo features de cues       | Modularizar funcionalidades independientes         | `test_server_tools.py` (salida cues)  | Múltiples pueden trabajar (una cue tipo por PR) |
| `settings/`                  | Lectura de settings del workspace                                 | Bajo                      | Bajo        | Mejoras de config/OSC         | Seguir modularidad existente                      | `test_server_tools.py` (salida settings) | Cambio poco frecuente, paralelizable |
| `osc/client.py`, `addressing.py` | Comunicación básica OSC (poca lógica de negocio)                  | Bajo                      | Bajo        | Raremente; solo evoluciones protocol | Asegurar interfase estable; tests de unitarios      | Tests unitarios de OSC (pendiente)   | Poco conflictivo, paralelo posible |
| `tests/test_server_tools.py`  | Snapshots de todas las tools (actualizaciones contractuales)       | Alto (con nuevas tools)   | Alto        | Integradores de features         | Usar tests por herramienta para aislar impactos    | N/A (mismo test)                     | Ejecutar siempre; evitar ediciones manuales simultáneas |
| `tests/test_write_mode.py`    | Verificación integral de write-mode (cubre todo `operations.py`) | Alto (cambios en write)   | Alto        | Desarrollo de write-mode        | Dividir tests por escenario (dry-run, real, fallo) | N/A (mismo test)                     | Tocar secuencialmente al modificar write/ops |

La tabla indica que *server.py*, *qlab.py*, *models.py* y los tests de contrato tienen alto riesgo de conflicto. Deben ser modificados con cuidado y preferiblemente en ramas separadas. Otras áreas (`osc/`, `cues/`, `settings/`) presentan riesgo menor y pueden trabajarse en paralelo.

# 14. Reglas de arquitectura para el futuro

Para evitar que el código crezca desordenado, proponemos reglas concretas basadas en las prácticas anteriores:

- **Las tools MCP deben ser delgadas:** Cada herramienta definida en `server.py` no debe contener lógica de negocio compleja. Si la tarea es complicada, delegar a funciones auxiliares fuera de `server.py`. (FastMCP sugiere que la herramienta solo invoque lógica externa.) 
- **Names/parámetros de tools son contrato público:** No cambiar nombres de herramientas ni parámetros existentes salvo motivo crítico. Cualquier modificación debe implicar actualización de tests de contrato y versión mayor. 
- **Modelos Pydantic de respuesta son contrato:** Los campos de las respuestas enviadas a cliente no deben cambiar sin revisión. Testear esquemas con tests de contrato. 
- **Cliente OSC sin lógica de negocio:** El cliente OSC (`osc/client.py`) y direccionamiento (`osc/addressing.py`) solo deberían encargarse de transporte, no de decidir lógicas de QLab. Esto facilita cambios en el protocolo sin tocar negocio. 
- **Modo write bien segmentado:** El flujo de escritura debe separar claramente las fases: *planificación* (dry-run), *ejecución real*, *verificación*. Cada herramienta write debe manejar dry-run primero y solo ejecutar tras confirmación. 
- **Clasificación de operaciones QLab:** Documentar en el código (comentarios o en docs) si cada operación es *read-only*, *read/write*, *control*, *view*, o *destructiva*. Usar esas etiquetas en `@mcp.tool(annotations=...)`. Por ejemplo, herramientas destructivas (`/go`, `/delete`, `/panic`) deben marcarse con `destructive_hint=True` y default a `readOnlyHint=False`. 
- **Dry-run obligatorio:** Cualquier nueva familia de operaciones de escritura (p.ej. soporte para un tipo de cue o setting) debe implementarse primero con dry-run simulado y tests que validen que el plan es correcto, antes de permitir la ejecución real. 
- **Cobertura de contrato con snapshots:** Al añadir nuevas tools, siempre actualizar los snapshots en `test_server_tools.py`. Toda nueva herramienta debe tener un test que cubra al menos una ejecución típica y verifique la salida. 
- **Rechazos y errores:** Para cada operación real (escritura), debe implementarse el caso de rechazo y dry-run. Además, siempre probar ejecución con rollback/verification: si la operación falla a mitad, ¿qué hace el sistema? Documentarlo. 
- **Datos estructurados vs humanos:** Si una herramienta puede devolver datos estructurados (JSON) además de texto, usar `ToolResult(structured_content=...)` para que clientes puedan procesarlos. 
- **Separar documentación grande:** Los documentos de diseño o guía no deben mezclarse en un mismo PR con lógica de código, para simplificar revisiones. 
- **Actualización gradual:** No proponer reescrituras completas. Cualquier refactor grande debe dividirse e ir fusionándose a `main` por fases pequeñas. 

Estas reglas, si se siguen, guiarán las futuras contribuciones a mantener el proyecto modular, probado y estable.

# 15. Resultado final esperado

Tras la refactorización, el proyecto debería quedar así:

- **Estructura de carpetas:**   
  ```
  qlab_mcp/
    server.py      # entrypoint mínimo, registra tools
    osc/           # cliente y direccionamiento OSC
    qlab/          # (o qlab_reader/) clases lectoras de QLab
    models/        # modelos Pydantic (divididos por dominio)
    cues/
      overview.py
      details.py
      query.py
      profiles.py
    settings/
      workspace.py
      summarizers.py
    write/
      registry.py
      planner.py
      validator.py
      executor.py
      verifier.py
      allowlist.py
      safety.py
      osc_inventory.py
    tests/         # tests separados por módulo
      server/
      osc/
      qlab/
      cues/
      settings/
      write/
    docs/
      arquitectura.md
      rules.md
      (…)
  ```
- **Flujo de petición MCP:** (como mapeado en el diagrama del docs)  
  Cliente MCP → `server.py:@mcp.tool` (entrada) → delega a función handler que usa QLabReader y módulos internos → `osc.client` envía OSC → QLab (respuesta JSON) → `QLabReader` / `models` parsean a objeto Python → se devuelve respuesta MCP (posiblemente usando `ToolResult`). 

- **Flujo de lectura QLab:** `QLabReader` hace `client.send_and_receive(address, args)` → recibe JSON → convierte a Pydantic model en `models/` → retorna resultado. 

- **Flujo write dry-run:** Tool write crea `plan = planner.create_plan(args)` → valida plan con `validator` → retorna resumen del plan al usuario (dry-run). 

- **Flujo write real:** Tras confirmación, tool llama a `planner`, luego `executor.execute(plan)` (envía OSC a QLab), luego `verifier.verify(plan)` para confirmar cambios. 

- **Zonas no-hotspot:** Los archivos más conflictivos (server.py, models, operations) deberían quedar más pequeños o con lógica delegada, reduciendo futuros conflictos. Los contratos públicos (nombres de tools, modelos de salida) se mantienen claros y documentados. 

- **Zonas paralelizables:** Por ejemplo, se podrá trabajar en paralelo en `osc/` (cliente), `cues/overview`, `settings/`, y `write/executor` porque están desacoplados. Mientras, trabajos secuenciales irán en áreas de mayor fricción (p.ej. actualizar `server.py` solo cuando todas las herramientas estén listas).

En resumen, el producto final será un código más modular, con responsabilidades claramente separadas, tests ampliados, y un flujo de petición MCP-documentado que cualquiera pueda seguir. Las áreas centrales de contrato se habrán consolidado y testeado para evitar roturas inadvertidas.

# 16. Prompts ejecutables para Codex

1. **Tests de caracterización:**  
   `"Analiza los tests en tests/test_server_tools.py y los modelos de salida actuales. Escribe nuevos casos de prueba de caracterización para funciones faltantes de QLabReader que validen respuestas JSON típicas (por ejemplo, leer el estado de una cue y obtener los campos esperados)."`

2. **Extraer helpers de `server.py`:**  
   `"Identifica cualquier lógica repetida de manejo de errores o formateo de respuestas en `src/qlab_mcp/server.py`. Extrae esa lógica a un nuevo módulo `src/qlab_mcp/server_errors.py` (o similar) e importa allí las funciones para simplificar `server.py`. Asegúrate de mantener el mismo comportamiento."`

3. **Dividir `write/operations.py`:**  
   `"Refactoriza `src/qlab_mcp/write/operations.py` separando la parte de planificación de comandos (`planning`) y la de ejecución (`executor`) en dos archivos nuevos (`write/planner.py` y `write/executor.py`). Actualiza las referencias en el resto del código para que usen estas nuevas funciones sin cambiar la lógica externa."`

4. **Separar modelos Pydantic (si se considera):**  
   `"Crea una carpeta `src/qlab_mcp/models/` y divide `models.py` en archivos por tema: por ejemplo, `cues.py` para modelos de cues, `settings.py` para modelos de workspace, `write.py` para esquemas de escritura. Actualiza los imports en el código y tests para usar los nuevos módulos."`

5. **Partir la PR #9 en PRs más pequeñas (ejemplo de prompt):**  
   `"En la PR actual que añade comandos de luz con dry-run, identifica componentes separados. Sugiere dos PRs: uno que defina los modelos y funciones básicas para 'setLight' en `write/operations.py` (dry-run incluido) y otro PR que añada el registro en `registry.py`, tests actualizados y documentación. Describe los cambios específicos para cada PR."`

6. **Actualizar documentación de arquitectura:**  
   `"Escribe un breve documento `docs/arquitectura.md` que describa el flujo de una petición MCP en este servidor: qué hace cada módulo (`server.py`, `QLabReader`, `osc`, etc.) y cómo se conectan. Incluye un diagrama ASCII simple si es útil."`

7. **Guía de trabajo con ramas/PRs:**  
   `"Redacta una guía de convención para ramas y PRs en este proyecto: incluye formato de nombres (por ejemplo `feature/xyz`), tamaño recomendado de PR (cambios de ~200 líneas), y ejemplos de cómo dividir un feature grande (por ejemplo, agregar soporte de video-light en cues). Indica qué tipos de cambios deben estar en PRs separados (docs, código, tests)."`

Cada prompt debe centrarse en un cambio concreto, permitiendo a Codex realizar tareas pequeñas y manejables, tal como se solicita.