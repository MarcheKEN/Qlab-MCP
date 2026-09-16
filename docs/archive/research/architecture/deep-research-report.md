# 1. Current Project State (`main` branch)

The **Qlab-MCP** repository is a FastMCP server that exposes tools for interacting with QLab 5 via OSC, focusing on reading data (workspaces, cues, settings, status, details) and carrying out safe write operations (with dry-run and confirmation). The **entry point** appears to be `src/qlab_mcp/server.py`: it creates a `FastMCP(...)` instance, decorates functions such as `@mcp.tool` for each operation, and finally starts the server (`mcp.run()`). The public *tools* correspond to those functions registered in `server.py`; for example, there will be tools for listing cues, getting cue details, reading workspace settings, and so on.

The FastMCP initializer is probably in `server.py`, something like:
```python
mcp = FastMCP("QLab MCP", timeout=..., ...)
@mcp.tool
def nombre_tool(...): ...
...
if __name__ == "__main__":
    mcp.run()
```
(FastMCP documentation recommends declaring each tool with `@mcp.tool` and letting the framework generate schemas and validation automatically.)

**Current responsibilities:**
- `server.py` initializes FastMCP, registers the tools, and may transform input/output data. It should delegate the actual logic to other modules (for example, by using *QLabReader*).
- `QLabReader` (probably defined in `src/qlab_mcp/qlab.py`) acts as a facade for interacting with QLab: it sends OSC commands, receives JSON responses, maintains caches, and resolves workspace identifiers.
- The `osc` package includes the OSC client and addressing logic (for example, `osc/client.py`, `osc/addressing.py`), responsible for managing UDP/TCP communication with QLab.
- The `cues` package (with modules such as `overview.py`, `details.py`, `query.py`, `profiles.py`) handles everything related to reading cue information: cue-list summaries, cue details, cue searches, property profiles, and so on.
- The `settings` package (for example, `workspace.py`, `summarizers.py`) reads workspace configuration (for example, OSC settings, groups, and so on) and summarizes relevant states.
- The `runtime` package (although it was not detailed) may manage QLab's real-time state.
- The `write` package contains the “gated” write logic: `operations.py` (write-operation definitions), `registry.py` (registry of available operations), `allowlist.py` (allowed OSC list), `safety.py` (safety measures), and `osc_inventory.py` (inventory of QLab OSC commands).
- The Pydantic models (`models.py`) define data structures for connections, states, cues, settings, write readiness, and so on; they are used both as tool input types and in responses.
- `tests/` contains unit and contract tests, for example `test_server_tools.py` (tests of public tools using snapshots or hashes), `test_write_mode.py` (write-logic tests), and `test_qlab_reader.py` (QLabReader tests).
- `docs/` contains internal documentation and project specifications, in addition to the official FastMCP/QLab documentation.

**Public interface vs. internal implementation:** The MCP *endpoints* (the names and parameters of each `@mcp.tool`) form the public interface. Everything else (code in `osc/`, `cues/`, `settings/`, `write/`, and so on) is an internal implementation. Tool names and response models should be considered stable: any change would affect the external contract. For that reason, the tool tests (`test_server_tools.py`) appear to validate the public response against snapshots, reinforcing that these outputs are part of the contract and must not be broken without notice.

**MCP request flow (clear map):** An MCP client (for example, an AI agent) invokes a tool defined in `server.py`. The tool handler (perhaps directly or through `QLabReader`) builds an OSC request (using `osc/addressing.py` to create the correct `/workspace/{id}/...` address). It then uses the OSC client (`osc/client.py`) to send the message to QLab (UDP on port 53000 or TCP with SLIP). QLab performs the action and responds with an OSC (JSON) message. The code receives and parses the response (perhaps using Pydantic models in `models.py`) and converts it to MCP format. FastMCP formats this as a JSON response to the client, including content blocks and/or structured data (for example, using `ToolResult`). In summary:

> **MCP client** → `server.py:@mcp.tool` → *handler* → **QLabReader/Internal module** → `osc.client` sends OSC → **QLab** → OSC JSON response → parse into a Pydantic model → **MCP response** to the client.

# 2. Analysis of Open PR #9 (“feat: add light command dry-run analysis”)

PR **#9** introduces a new light command with dry-run support. Without accessing the code, it can be inferred that it touches:
- Runtime code: probably `write/operations.py` (adding operations for lighting commands, for example `/workspace/{id}/dashboard/setLight`) and perhaps `write/registry.py` (registering the new operation), as well as models in `models.py` for light arguments.
- Documentation: perhaps updates in `docs/` or an internal roadmap to reflect this new command.
- Tests: it likely adds cases in `test_write_mode.py` or `test_server_tools.py` to verify light behavior (dry-run vs. real).
- The PR appears to mix several concerns: light-operation code, dry-run/confirmation logic (possibly in `write/`), contract-test updates, and even docs/roadmap adjustments.

**Size and risks:** If it actually covers multiple layers (write, tests, docs), it is probably too large. Each block (adding light operations, modifying registries, creating tests, changing docs) could be isolated into smaller PRs: for example, first define a helper for light operations in `write/operations`, then use another PR to integrate dry-run support, and another for tests and docs. Such a broad PR adds *conflict* risk: `write/operations.py`, `write/registry.py`, `write/allowlist.py`, `models.py`, and `server.py` are critical modules that change frequently. Reviewing many changes together makes review tedious and error-prone.

**Splitting strategy:** It should:
- **Separate documentation:** Changes to docs/roadmap files should not be mixed with logic code.
- **Split the feature:** For example, one PR to *define the new models* (inputs/schemas for light commands), another to *implement the operation* in `write/operations`, another to *update the registry* and *allowlist*, and finally *tests* (dry-run and real).
- **Atomize tests:** If the current PR adds large tests, they could be split by case (for example, one for a valid light dry-run and another for rejection).
- **Do not mix tasks:** Avoid combining cue profiles, settings, or other unrelated work in one PR. Each PR should ideally do one thing (add a light command, improve tests, and so on).

# 3. Code Hotspots

The following identifies the files/projects with the greatest bottleneck risk, along with their current responsibilities and recommendations:

- **`src/qlab_mcp/server.py`:** *Responsibility:* Initializes FastMCP and registers all MCP tools. It currently probably contains much of each tool’s routing logic. *Why a hotspot?* All public tools pass through here, so any change (parameter names, input/output schemas) affects the MCP contract. Its size grows with new tools. *Problem:* It mixes tool registration with perhaps validation and response logic. *Safe changes:* Add new tools (decorated functions) or improve internal documentation. *Dangerous:* Renaming or removing parameters from an existing tool (breaks the API), changing the default value of `timeout` or `mask_error_details` (may affect error handling). *Protective tests:* `test_server_tools.py` appears to validate all tools, catching contract regressions (snapshots/hashes). *Missing tests:* It would be useful to test errors (e.g. invalid inputs) and timeouts. *Reducing conflicts:* Extract common logic (data conversions, error handling) into helpers or models. Minimize concurrent edits: for example, when adding a new tool, instead of modifying the same `server.py` file in parallel, it could be implemented by importing a function defined in another module.

- **`src/qlab_mcp/qlab.py` (possible *QLabReader*):** *Responsibility:* Facade for interacting with QLab. It may include mixins for different aspects (connection, queries, workspace resolution), private methods (`_request_data`, `_resolve_workspace`, etc.), and cache handling. *Why a hotspot?* All read tools (cues, settings, status) depend on it; it is a single point of failure if OSC communication fails. If overloaded (many methods), it may be fragile. *Problem:* Too many responsibilities together (session management, command construction, JSON parsing). *Safe changes:* Refactor internally (e.g. extract submethods) if test coverage is good. *Dangerous:* Modifying workspace resolution or the OSC client could break many tools. *Protective tests:* `test_qlab_reader.py` covers data-reading cases. *Missing tests:* Error cases (e.g. disconnection, invalid passcode), concurrency, and partial responses. *Reducing conflicts:* If it is a *God class*, it could be split into smaller classes (e.g. `WorkspaceReader`, `CueReader`), or inheritance (mixins) could be replaced with composition to isolate functionality. Do this in phases, testing that each compact reader covers a subdomain.

- **`src/qlab_mcp/models.py`:** *Responsibility:* Defines all Pydantic models used for inputs (tool arguments) and outputs (structured responses: overview, status, cue details, settings, etc.). *Hotspot:* It is potentially large, and changes here affect tool contracts. *Problem:* A great deal of validation logic is concentrated in one file. *Safe changes:* Add new models or optional fields. *Dangerous:* Changing existing field names or structure (breaks clients); reassigning types. *Protective tests:* There are no direct model tests, but `test_server_tools.py` probably detects if the output no longer fits the expected JSON contract. *Missing tests:* Validation of edge cases (e.g. required fields missing from JSON). *Reducing conflicts:* If it grows too much, consider splitting it into modules (`models/cues.py`, `models/settings.py`, `models/write.py`, etc.), but this should be done gradually, updating imports and tests together.

- **`src/qlab_mcp/write/operations.py`:** *Responsibility:* Contains the logic for each write operation (e.g. planning a change in QLab, performing a dry run, applying the change). *Hotspot:* It is probably very large: all write operations (audio, video, text, lighting, etc.) reside here. *Problem:* High complexity and frequent change when new operation types are added. *Safe changes:* Encapsulate parts in helper functions; split it by responsibility (plan vs. execution) incrementally. *Dangerous:* Abrupt restructuring (moving functions) may break the registry or write tests. *Protective tests:* `test_write_mode.py` verifies dry-run and real-mode behavior. *Missing tests:* Unit tests for pre-write validation, simulated timeouts, or confirmation failures. *Reducing conflicts:* Split this module; for example, separate the phases into planning (`write/planner.py`), validation (`write/validator.py`), and execution (`write/executor.py`). This allows different people to work on different phases without stepping on one another. We could also group by media type (video, audio, lighting, etc.), if that makes sense.

- **`src/qlab_mcp/write/registry.py`:** *Responsibility:* Registers available write operations (possibly mapping tool names to functions in `operations`). *Hotspot:* Every new operation requires editing this file. *Problem:* If several features add operations simultaneously, conflicts will occur. *Safe changes:* Make registration dynamic (e.g. discover operations automatically) to avoid manual editing. *Dangerous:* Changing the order or removing registrations; this would cause operations to be missing. *Tests:* There may be tests that verify that the registry contains certain base operations.

- **`src/qlab_mcp/write/allowlist.py`:** *Responsibility:* Defines which OSC commands are allowed or blocked. *Hotspot:* If QLab adds new OSC commands in updates, this file must be modified. *Problem:* It may grow without control. *Safe changes:* Keep this list updated with validation tests. *Dangerous:* Allowing unsafe commands without a gate (security contract); or blocking necessary commands. *Tests:* Ideally validate that only intended commands are allowed.

- **`src/qlab_mcp/cues/profiles.py`** (and similar files in `cues/`): *Responsibility:* It perhaps defines cue-query profiles (for example, reading certain specific properties). *Hotspot:* If there are many cue types (audio, video, lighting) and profiles, it may grow. *Problem:* It mixes logic for each cue type. *Safe changes:* Add new profiles; *Dangerous:* Change logic shared between cues. *Tests:* `test_server_tools.py` probably covers general cue-query output. Type-specific cue tests are missing.

- **`src/qlab_mcp/cues/details.py`, `query.py`, `overview.py`:** Analogous responsibilities for cue details, generic queries, and listings. They could be split further if they grow. Testing them ensures the accuracy of the information read.

- **`src/qlab_mcp/settings/workspace.py`, `summarizers.py`:** These handle reading and summarizing workspace settings. Medium risk: they do not change as often as cues, but QLab OSC changes will affect them.

- **`src/qlab_mcp/osc/client.py`, `addressing.py`:** OSC handlers. Responsibility: sending/marking OSC messages. They are critical: errors here break all communication. They rarely change (only if QLab’s OSC protocol is updated). They can be tested with socket mocks.

- **Test files (`test_server_tools.py`, `test_write_mode.py`, `test_qlab_reader.py`):** *test_server_tools.py* protects the public contract: it probably compares each tool’s responses with a hash/snapshot. This is crucial for detecting unwanted output changes. However, snapshot-based tests can be fragile in response to minor changes. *test_write_mode.py* verifies write/dry-run logic; any change to orchestrated operations requires updating it. *test_qlab_reader.py* validates reading data from QLab; if QLab changes or socket errors occur, it must be updated. We should review them to ensure each area has its own dedicated suite. For example, separate OSC tests from business-logic tests.

# 4. Evaluation of `server.py` as an MCP layer

The `server.py` file should function as a thin presentation layer for MCP tools: define tools and delegate. According to FastMCP, tools should be simple Python functions, leaving schema generation and validation to the framework. Any complex logic (error formatting, data merging, etc.) should ideally be moved out of `server.py`.

- **Tool registration:** This is done with `@mcp.tool`. That is appropriate in `server.py`. To reduce conflicts, tools imported from other modules could be registered here. Extracting schema definitions is unnecessary; FastMCP does this automatically.

- **Tool annotations:** FastMCP supports metadata (title, read/destructive hints). For example, each tool can be annotated with `read_only_hint=True` if it does not modify anything. This is important for marking destructive versus safe operations, as recommended by FastMCP best practices. These annotations could be defined alongside the tool, or generated from write-mode logic if it matches the ACL. Extracting them is not essential unless there are many similar tools (in which case they could be defined in a common helper).

- **Timeouts:** If tools call QLab, they could block. FastMCP allows defining `timeout=` in the decorator. If `server.py` sets timeouts or background mode for tools, it is sensible to keep this here. Extracting this logic does not appear necessary; it is part of the server definition. However, ensure that long-running tools use `task=True` rather than only a timeout.

- **Error handling:** FastMCP already converts exceptions into error responses. If `server.py` includes custom “error helpers” (e.g. catching exceptions and converting them manually), that is probably redundant. It would be better to rely on `ToolError` and FastMCP’s `mask_error_details`. For example, [20] indicates that raising `ValueError` or `ToolError` already generates the error message for the client, and that masking details is controlled at the server level, not in each tool. If specific formatting routines exist (such as always constructing JSON with “status” and “data”), they should probably be extracted into generic utilities.

- **Payload normalization:** Similarly, FastMCP automatically forms JSON responses (including `ToolResult`). If `server.py` has helper functions for wrapping responses, that code could be extracted into a separate module. In particular, if dictionaries with `status`/`data` are built manually, this could be simplified by using `ToolResult` or `mcp.types`. Extracting repetitive validation (e.g. converting strings to IDs) could also improve clarity.

- **Conversion to Pydantic models:** Ensure that `server.py` receives Pydantic objects directly as function return values (FastMCP supports return values as Python objects that it serializes to JSON). If `server.py` converts the response into a model instance (e.g. `MyModel.parse_obj(response)`), it could delegate that task to FastMCP (which generates the output schema) or move it to the QLabReader handlers. It is important that the **business logic** (what each tool does) not be mixed with MCP details.

**Extraction recommendations:**
- **Tool registration:** No need to extract it; it is part of the framework.
- **Tool annotations:** They can remain with the tool; perhaps create constants if they are repeated.
- **Tool schemas/types:** FastMCP generates almost everything automatically; extraction is not vital.
- **Error/response mappers:** If they exist, extracting them is advisable. For example, an `errors.py` module that converts QLab exceptions into uniform `ToolError` instances. This improves unit testing.
- **Tool handlers:** If a tool function does too much, extract the logic into functions in other modules (e.g. in `cues/` or `write/`), leaving only the invocation in `server.py`.
- **Public-contract snapshots:** Tool responses (Pydantic models) constitute the contract; these files (`server.py` and the models) should be considered stable. Change them only when necessary, and carefully update `test_server_tools.py`.

In summary, I would not move the decorators or tool registration out of `server.py`, but I would extract any logic that is not essential there. The real benefit is reducing `server.py`’s responsibilities to avoid bottlenecks and conflicts (e.g. separating common validation, error handling, and response formatting).

# 5. Evaluation of *QLabReader*

**Responsibility:** `QLabReader` (via `src/qlab_mcp/qlab.py`) functions as a facade for QLab. According to the description, it uses mixins and shared methods (`_request_data`, `_request_data_with_tcp_fallback`, `_resolve_workspace`, `_workspace_data`) to abstract OSC connection, resolution of the active/selected workspace, and communication with the OSC client. It also handles caching of frequent reads and may have legacy methods.

**Too much responsibility?** If `QLabReader` uses multiple inheritance (mixins) and groups many functions (connection, various queries, caching), it risks becoming a “God class.” Each module (cues, settings, runtime) uses it heavily, creating coupling. Without the source code it is difficult to measure, but it *could* be doing too much.

**Aspects to evaluate:**
- *Mixins and inheritance:* If each mixin contributes related methods (e.g. `CueReaderMixin`, `SettingsReaderMixin`), it could be clearer: each mixin would be responsible for one category of operations. That is fine. But if the hierarchy becomes complex, refactoring to composition may be preferable.
- *OSC clients:* QLabReader depends directly on an OSC client (`osc/client.py`). Ideally, it should be solely responsible for managing ports and fallbacks (UDP vs. TCP), which is appropriate.
- *Read cache:* If one exists, it improves performance but adds invalidation complexity. Check whether it is properly encapsulated.
- *Workspace resolution:* The `_resolve_workspace` method probably identifies which workspace to use (by ID, name, or the current one). It belongs in this class, but could be abstracted.
- *Compatibility/legacy:* If there are methods for older versions or unsupported functions, mark them and evaluate removing or refactoring them later.

**Recommendations:** Keeping `QLabReader` as a facade is reasonable for now (it centralizes interaction with QLab). However, to reduce coupling:
- Inheritance could be reduced: instead of having `class QLabReader(Base, CueMixin, SettingsMixin, ...)`, use **composition**: `self.cue_reader = CueReader(self)`, etc., so each part uses the primary client. This facilitates testing.
- Extract internal services: for example, a `WorkspaceService` for everything related to the workspace (connection, status), and another `CueService` for cues. Each would operate with the OSC client.
- Small interfaces: define interfaces (e.g. `get_cue_list(workspace)` vs. `get_workspace_settings(id)`).
- But since the project is young and the architecture is already defined, such a refactor would be large. The priority should be not breaking functionality. Therefore, it might be deferred to a later phase, after strengthening tests.

In conclusion, the pragmatic recommendation is to **leave QLabReader as it is in the short term** (it is the obvious facade), but as it grows, consider splitting it: e.g. `QLabWorkspaceReader`, `QLabCueReader`, each with its own `osc_client`. First focus on ensuring that `QLabReader` is well covered by tests; if clarity suffers, then begin extracting into separate branches, without dismantling everything at once. In short, split in phases, guided by need (symptoms of diffuse code) rather than preference.

# 6. OSC/QLab Model

Comparing the project design with the **official QLab 5 OSC Dictionary**, the following emerges:

- **OSC address construction:** QLab uses routes such as `/workspace/{id}/...`. According to the documentation, a `/workspace/{id}/cueLists` message retrieves data only from the specified workspace. If `/workspace` is omitted, the message is sent to *all* workspaces open on that port. The code should always use `/workspace/{id}` to ensure correct addressing. This is reflected in [46], which recommends prefixing with `/workspace/{id}` or `{name}` to direct messages. The project must support either a workspace *ID or name*, since both are valid.
- **OSC transport (UDP/TCP):** QLab listens for OSC on UDP port 53000 (by default) and responds on 53001. Over TCP, it uses double SLIP encapsulation. The project OSC client should support both, trying UDP and falling back to TCP if it fails, as suggested by `_request_data_with_tcp_fallback`.
- **JSON parsing and statuses:** QLab returns JSON responses with a `status` field and possibly `data`. The dictionary indicates that `status` will be `"ok"`, `"error"`, or `"denied"`. The code must interpret `"error"` and `"denied"` appropriately, for example by raising an access-control or validation exception. This is critical: `"denied"` occurs when the client has not connected with a passcode or lacks permission.
- **Handling `connect` and passcodes:** QLab requires sending `/workspace/{id}/connect {passcode}` for authentication. The server should handle this step and perhaps remember whether it has already connected. The documentation notes that `/version` and `/workspaces` do not require a passcode, but all other endpoints, such as `/cueLists`, do.
- **Permissions (view/edit/control):** The dictionary classifies each command according to privilege level through the *view*, *edit*, and *control* columns. The application should account for this: read-only operations can be performed in any mode, but destructive operations, such as `/workspace/{id}/go`, `/delete`, and `/cue/{num}/panic`, require higher privileges. This is reflected in FastMCP `annotations`; for example, `destructive_hint` should be `true` for `/go` or `/delete`.
- **Cue IDs vs. cue numbers:** QLab distinguishes a *cue number* (its order within the list) from a *cue ID* (UUID). The dictionary shows routes for both, such as `/workspace/{id}/delete/{cue_number}` and `/delete_id/{cue_id}`. The code should support both references, perhaps through a parameter that accepts either a number or an ID.
- **Read-only vs. read/write commands:** For example, `/cue/10/preWait` reads a value, while `/cue/10/preWait 5` modifies it (read/write). The project should follow this pattern by separating read-only tools from write tools. Read-only tools could be marked with `read_only_hint=True`.
- **Dangerous operations:** According to the documentation, `/go`, `/cue/x/fire`, `/delete`, `/panic`, and similar commands are destructive and do not send a response by default. These should have dry-run and gating in the code. For example, the lighting operation (`/dashboard/setLight`) would probably be considered destructive and implemented similarly, as suggested by the context of PR #9.

**In summary:** The ideal design **should follow the OSC dictionary**:
1. **Clear prefixes:** Every message uses `/workspace/{id}` for routing.
2. **Separate transports:** UDP (ports 53000/53001) and TCP (SLIP) are managed internally.
3. **Responses and errors:** The code must correctly interpret `status: ok/error/denied`, raising errors or aborting as appropriate.
4. **Permissions:** Implement gating according to the hint (`read_only`, `destructive`, etc.), aligned with the OSC Dictionary's view/edit/control permissions.
5. **Security:** Execute `connect` with a passcode before critical operations.
6. **Project-specific abstractions:** Beyond the protocol, the project may use abstractions such as Pydantic models and planned operations to facilitate development, but they must not hide essential protocol details, such as correct OSC addresses and standard JSON parsing.

# 7. Evaluation of `models.py`

`models.py` contains the Pydantic models that define the data exchanged. Possible groupings include connection (`ConnectionModel`), cue overviews, workspace settings, cue state, query results, write-readiness data, data for creating/updating cues, and tool-input schemas.

**Split?** In principle, separating models by domain, for example `models/connection.py`, `models/workspace.py`, `models/cues.py`, `models/settings.py`, `models/write.py`, and `models/errors.py`, could improve organization. **Advantages:** it reduces the size of each file, avoids import confusion, and groups related models. **Disadvantages:** imports throughout the code would need to be reorganized, and tests and tools using those models would need to be updated. It would be a substantial refactor with a high risk of conflicts if done all at once.

**Cost/risk:** The models are closely tied to the public contract. Changing a file's name or location would affect all of `server.py` and the tests. Multiple `import`s would need to be adjusted. Given the current size, which is unknown but may be large, the clarity benefit could be offset by the complexity of reorganizing everything.

**Recommendation:** First strengthen model test coverage, such as schema validation. If `models.py` becomes difficult to manage, it could then be split in later phases. Do so only after there is a strong reason, such as many concurrent changes, and under intensive testing. In short, **do not split it immediately**. Keep it intact in the short term to avoid import errors, and perhaps plan its refactor in small stages once other dependencies are ready.

# 8. Evaluation of *write mode*

The current gated write architecture involves `write/operations.py`, `registry.py`, `allowlist.py`, `safety.py`, `osc_inventory.py`, and additional tests. It includes dry-run, confirmation tokens, actual execution, and subsequent verification.

**Responsibilities:**
- `operations.py` probably creates the plan, a list of OSC commands, sends it in dry-run mode without real effect, and then executes it in QLab once confirmed.
- `registry.py` maps write operations to functions.
- `allowlist.py` lists commands permitted for security.
- `safety.py` may decide what to do in case of errors or whether to abort.
- `osc_inventory.py` may contain metadata about available OSC commands.

**Internal separation:** Currently, `operations.py` may do everything: plan generation, parameter validation, execution with QLabReader, and result verification. It would be better to divide it into phases:

1. **Planning (`planning`):** Given a requirement, such as “set light” or “insert cue,” build an *abstract* plan, a list of changes to make. This plan does not touch QLab, which facilitates isolated unit tests.
2. **Validation (`validation`):** Before execution, check the plan's consistency, such as whether the cue IDs exist. An error can be raised if there is an inconsistency.
3. **Confirmation / Token:** Obtain a token or permission, currently requested from the user. This already exists through the dry-run and confirmation concept. It should only orchestrate calls.
4. **Execution (`execution`):** Send the commands to QLab, possibly in a batch, using the OSC client.
5. **Verification (`verification`):** Read from QLab to confirm that the desired result was achieved, such as verifying that a cue was created or modified. This may require rereading the state, perhaps through QLabReader.
6. **Result construction (`result builder`):** Build the operation response, such as the number of changes applied and new IDs.

Additionally, operations could be differentiated by media type: audio, video, text, and light have their own details.

**Split `write/operations.py`?** Yes, if it is very large. Submodules could be created:
- `write/planner.py`: functions for generating plans.
- `write/executor.py`: functions that actually send OSC and validate.
- `write/validator.py`: checks before and after that the objectives were met.
- `write/confirm.py`: handles tokens/gating.
- Alternatively, it could be divided by domain, such as video and text, but that could fragment the general logic. I prefer dividing by phase because it is more generic.

**Risks/benefits:** Refactoring write mode is delicate because of the critical nature of these operations. However, splitting it reduces future conflicts, since several people can work on different phases. The risk is introducing bugs into the sequence. To mitigate this, first characterize the existing operations with tests, as in black-box testing, and then extract parts gradually.

Specifically, **if splitting is recommended:** Do it in steps, for example:
- Extract a planner that generates a list of `(address, args)`.
- Create a validation module that verifies them.
- Have the executor send each command through QLabReader.
- Leave each tool's main function as the coordinator: call the planner, perform confirmation, then call the executor and verifier.

This improves the clarity and testability of each component.

# 9. Evaluation of the Tests as a Safety Net

**Current coverage:** The existing tests appear to cover:
- The public tool contract, through snapshots/hashes in `test_server_tools.py`. This protects the MCP responses, including the structure and content expected by clients.
- Write mode (`test_write_mode.py`): verifies that dry-run operations perform a correct simulation and that real execution applies the expected changes, in addition to enforcing gates such as tokens.
- QLab reading (`test_qlab_reader.py`): validates that QLabReader correctly constructs queries and processes responses, probably using mocks.

**Protections:**
- Public tool behavior is protected in `test_server_tools.py`. Each tool, such as “list cues” or “read settings,” must return JSON corresponding to the contract. This test is essential: if something breaks in the code, the test will fail and indicate that the response changed.
- FastMCP validations, including input schemas and error handling, are included implicitly: if a tool does not respect its type, FastMCP rejects it and the test may fail.
- Pydantic model contracts are also protected indirectly: if the JSON differs from the schema, FastMCP raises an error or test validation detects inconsistencies.

**Tests as characterization:** `test_server_tools.py` appears to act as a characterization test, ensuring that current behavior is maintained. Any refactor will require updating these snapshots.

**Size/fragility:** Tests that use snapshots or hashes can be fragile: a legitimate change, such as adding an extra field or reformatting a string, requires manually updating the snapshot. If the test is monolithic and tests everything in one block, it can be difficult to isolate what changed. It would be better to separate tests by individual tool.

**Test separation:**
- There may be very large tests, such as one test that checks all tools. It would be useful to split them into one test per tool, or at least by category: cues, settings, and workspace. That way, changes to one tool do not break everything.
- Similarly for write mode, there could be one test per write operation instead of one general test.
- QLabReader tests should focus only on public methods, using a mocked OSC client. For example, unit tests could pass a JSON dictionary and verify that the correct model is returned.

**Missing tests:**
- Behavior when QLab returns errors, including timeouts, OSC errors, and unexpected data.
- Edge-case handling, such as a nonexistent cue or invalid workspace.
- Multi-workspace scenarios: if a request is sent without `/workspace`, what does the code do?
- Invalid token confirmations.
- Permissions, including verifying that an incorrect passcode produces `"denied"`.

**Tests by area:** It is suggested that tests be separated by functionality:
- **Server/Tools:** Always run the tests covering public tools (`test_server_tools.py`), since they guarantee API stability.
- **OSC:** Possibly add a test that verifies OSC address construction, ports, and so on.
- **Cue reading:** Unit tests for `cues/*` using a mocked QLabReader.
- **Settings:** Similarly, tests for `settings/*`.
- **Write mode:** `test_write_mode.py` should run on every PR that modifies `write/`.
- **Docs-only PRs:** Functional tests do not need to be run for these logically, but format or link validation could be performed.

In particular, **`test_server_tools.py` is critical**: it protects the public tool contract. Before refactoring any tool, its corresponding snapshot in this test must be updated. This acts as a characterization safety net: it reflects current behavior and allows comparison after changes.

In conclusion, the test suite should be reviewed to ensure that **each key area has dedicated tests** and that no test is too large. The existing tests provide a foundation, but error cases should be covered more extensively and responsibilities should be separated more clearly.

# 10. Future Modularization Strategy

Based on the current repository, we propose a layered modular architecture:

- **`server/` (or at the root):** Contains a minimal `server.py` and perhaps a `tools/` subpackage if the definitions grow. *Responsibility:* Only server startup and tool registration. *Current state:* `server.py` is large. *Problem:* Bottleneck and conflicts. *Change:* Leave only initialization and register tools (include only handler imports), extracting logic into `handlers/` modules. *Risk:* Moderate initially (because imports in tests must be reorganized). *Benefit:* Facilitates parallel work (one person can work on a tool without touching the core). *Order:* Early phase. *Tests:* `test_server_tools.py`.

- **`osc/`:** *Responsibility:* Low-level OSC logic: sending/receiving packets and building addresses. *State:* Already exists. *Problem:* It may grow only a little. *Change:* Keep it separate. Possible improvement: expose a stable interface for sending OSC, and perhaps add unit tests for constructed addresses. *Risk:* Low. *Benefit:* Centralized communications code. *Tests:* Validate addressing and client functions.

- **`qlab_reader/` (formerly `qlab.py`):** *Responsibility:* Interface for reading from QLab (OSC composition). *State:* Too large; mixin-based. *Change:* Eventually split it by domain (e.g. `WorkspaceReader`, `CueReader`, `SettingsReader`). *Risk:* High initially; it must be done after testing. *Benefit:* Greater clarity and less coupling. *Order:* Phase 3. *Tests:* `test_qlab_reader.py` and new tests for subclasses.

- **`models/`:** *Responsibility:* Pydantic schemas. *State:* Currently a single file. *Problem:* Size and many dependencies. *Change:* If it is split (e.g. `models/cues.py`, etc.), do so carefully. *Risk:* High (import conflicts, tests). *Benefit:* Organization. *Order:* Phase 4 (only if necessary). *Tests:* Test validation of new schemas, nothing more specific.

- **`cues/`:** *Responsibility:* Cue reading. Subdirectories/modules by functionality:
  - `cues/overview.py` (list cues),
  - `cues/details.py` (cue details),
  - `cues/query.py` (search by name/ID),
  - `cues/profiles.py` (lists of properties to read).
  *State:* Already separated. *Change:* It may require refactoring if a file grows too much. *Risk:* Medium. *Benefit:* Maintainability. *Order:* It can remain as is; refactor in phases as needed. *Tests:* Add specific tests for each module.

- **`settings/`:** *Responsibility:* Read workspace settings (OSC settings, media folders, etc.). Follow a similar split if there are subsections (e.g. `settings/workspace.py`, `settings/routing.py`, etc.). *State:* Existing modules `workspace.py`, `summarizers.py`. *Change:* See whether they need more separation (e.g. `settings/osc_settings.py`). *Risk:* Low/medium. *Tests:* Unit tests for settings summaries.

- **`runtime/`:** *Responsibility:* Real-time state (e.g. current execution, playhead). *State:* Unknown. *Change:* If there is a lot of logic, modularize it (e.g. `runtime/state.py`, `runtime/queries.py`). *Risk:* Medium. *Tests:* For state updates.

- **`write/`** (restructuring): *Responsibility:* Gated writes.
  - `write/registry.py` (maps operations) – *State:* existing. *Problem:* Collision if several people add operations. *Change:* Perhaps load modules dynamically (e.g. a decorator in operations that registers them). *Risk:* Medium. *Tests:* Confirm correct registration.
  - `write/planner.py` (new): generates plans from requests.
  - `write/validator.py` (new): validates plans.
  - `write/executor.py` (new): executes commands in QLabReader.
  - `write/verifier.py` (new): reads from QLab afterward to ensure consistency.
  - `write/allowlist.py` (current): list of permitted commands. *Change:* Better document what it contains, perhaps refine it.
  - `write/safety.py`: lock/failure handling; leave it as a utility.
  - `write/osc_inventory.py`: inventory of QLab commands; it could remain as is.
  *Problem:* The current `operations.py` is a bottleneck. *Order:* Split operations by phase (planner first, then executor, etc.). *Risk:* High if not tested properly. *Tests:* `test_write_mode.py`, split into unit tests by phase.

- **`docs/` and `reference/`:** Contain guides and specifications. *Change:* Organize them into topic-based subdirectories (FastMCP, QLab, architecture). Keep them separate from code. *Risk:* Low. *Tests:* Link or format validation if desired.

- **`tests/`:** Structure them in parallel with `src/`:
  - `tests/server/` (for tools),
  - `tests/osc/` (for addressing and client),
  - `tests/qlab/` (QLabReader and model coverage),
  - `tests/write/` (for each part: planner, executor),
  - `tests/cues/`, `tests/settings/` for their respective areas.
  *Change:* Move `test_` files into thematic directories. *Risk:* Low. *Benefit:* Clarity. *Order:* Phase 1 (simple reorganization).

This modular architecture will allow teams/patches to work in parallel: for example, one can implement new cue-reading *tools* without touching `write/`, another can improve the OSC layer, another can refine write registration, and so on. Areas with low interdependence (e.g. `osc/` vs. `write/`) can be developed concurrently.

# 11. Branch and PR strategy

To coordinate multiple collaborators (or “Codex chats”), we propose:

- **Naming convention:** Use clear prefixes: `feature/`, `fix/`, `refactor/`, `docs/`. For example: `feature/light-commands`, `refactor/write-planner`, `docs/architecture`. Include the issue/PR if applicable.

- **Maximum PR size:** Ideally no more than ~200–300 lines of changes and a few dozen files. Each PR should have one clear objective. Avoid PRs that mix several topics (tests, docs, and code should not all be in one large PR).

- **Changes not to mix:** Never mix different logic; e.g. do *not* combine architecture changes (`models.py`) with new user features. Docs only with docs, tests only with tests from the same area, and refactors only with related code.

- **Single-sequence files:**
  - *server.py* and *models.py* are public contracts; edit them only when essential (new tools or fields). Coordinate with the team to avoid duplicating efforts here. For example, if a new field is going to be added to the cue model, add it before another branch uses it.
  - *write/operations.py* tends to grow significantly; it may be better to merge sequentially by blocks of operations (e.g. audio first, then video, then text), rather than having several people edit it simultaneously.
  - *tests/test_write_mode.py* depends on operations; it is better to update it at the end of each write refactor.

- **Parallel files:**
  - Different parts of cues (`overview.py`, `details.py`, etc.) can be worked on in parallel.
  - `osc/addressing.py` versus `osc/client.py`: changes in one should not affect the other much, so they are parallelizable.
  - New write operations (new classes or functions) should ideally be placed in separate files initially and then integrated into the existing flow.

- **Splitting large features:** For example, full lighting support should be divided: one PR creates only the input models for a lighting command; another PR defines the function in `operations.py`; another updates `registry.py`; another adds tests; and another adjusts the docs.

- **Use of intermediate base branches:** If feature A depends on refactor B, create a branch for B first, then create A from B. Do not combine them into one. For example, if an operations-planning module is to be added, first create PR `feature/write-planner`, merge it, and then branch `feature/write-light-dryrun` from `main`.

- **When to merge into main:** Merge PRs that add atomic features or refactors with complete tests. Keep `main` always in working condition (e.g. by running the tests).

- **“Umbrella” branches:** Use them only when several small PRs form part of a large feature. For example, create a `feature/write-refactor` branch from which sub-PRs emerge (although each PR should have its own source branch). Then merge the umbrella branch into `main` at the end, ensuring that all sub-PRs are integrated. This avoids repeated merge conflicts.

- **Avoid giant PRs:** If a PR grows too large, it is better to close it and reopen several smaller ones. Review it frequently in draft form.

- **Prioritize early merges:** Do not leave old PRs open without merging for too long. If something is complete and tested, merge it into `main` soon so others can start from the latest version.

**Examples of ideal PRs:**
- *“feat/cues-overview-tool”*: adds the tool for listing cues. Affects `server.py` (registration), `cues/overview.py` (logic), `models.py` (response model), and cue-specific tests.
- *“refactor/write-planner”*: extracts planning functions from `operations.py` into `write/planner.py` and adapts the calls. Affects `operations.py`, the new `planner.py`, and planning tests.
- *“docs/architecture-update”*: improves internal documentation without touching logic code. It could update diagrams or the README.

These segmented PRs make review easier and reduce conflicts, ensuring that `server.py`, `models.py`, `operations.py`, and the key tests do not become constant conflict files.

# 12. Incremental refactoring plan

We divide the refactor into small phases, each with clear objectives:

1. **Characterization tests:** **Objective:** Increase coverage with characterization tests. Files: primarily *existing tests*. Changes: write unit tests for critical functions (e.g. QLabReader methods and validators in write). **Do not touch:** Production logic. **Risk:** Low. **Benefit:** Safety for future refactors. **Required tests:** All read and write tests. **Parallel:** Several people can write different tests at the same time. **Suggested Codex prompt:** “Analyze the current tests and generate examples of missing unit tests to cover edge cases of `QLabReader`.”

2. **Extract error/response helpers from `server.py`:** **Objective:** Move error-handling or response-normalization logic into a separate module (e.g. `server/errors.py`). Files: `server.py`, new `errors.py`. Changes: Identify repeated code (e.g. exception handling) and move it. **Do not touch:** Tool or model definitions. **Risk:** Low/Medium (response formatting could break if this is not done correctly). **Benefit:** Less weight in `server.py`. **Tests:** `test_server_tools.py` must continue to pass. **Parallel:** This can be done while others work on `cues/`, etc. **Codex prompt:** “Extract the exception-handling logic from the functions in `server.py` into a new utility module, modifying the calls.”

3. **Extract tool types/schemas:** **Objective:** If arguments use Pydantic or `Annotated`, extract type definitions into `models.py`. Files: `server.py`, `models.py`. Changes: Move complex definitions (enums, Literal) to `models`. **Do not touch:** Functionality, only import refactoring. **Risk:** Low. **Benefit:** Clarity in `server.py`. **Tests:** None new; only review behavior. **Parallel:** Yes, several handlers can do this separately. **Prompt:** “Create Pydantic models for the arguments of the tools in `server.py` and update the function signatures to use them.”

4. **Reduce hotspots in write operations:** **Objective:** Split `write/operations.py` into parts. Files: `write/operations.py`, create `write/planner.py`, `write/executor.py`, etc. Changes: Move coherent functions into the new modules and modify calls. **Do not touch:** The internal logic of each function (yet). **Risk:** Medium/High (import or sequencing errors). **Benefit:** Fewer conflicts when adding new operations. **Tests:** `test_write_mode.py` to confirm that nothing changes externally. **Parallel:** Someone else can work on specific operations while the restructuring takes place. **Prompt:** “Refactor `write/operations.py` by separating command planning from execution into different modules, preserving the same behavior.”

5. **Reorganize models (`models.py`):** **Objective:** Split `models.py` into several files by domain. Files: `models.py` replaced by a `models/` folder with `workspace.py`, `cues.py`, etc. Changes: Create new model files and adjust imports in the code. **Do not touch:** Model semantics. **Risk:** High (multiple imports throughout the project). **Benefit:** Better long-term organization. **Tests:** All tests, to ensure that the models load correctly. **Parallel:** Yes, but coordinate to avoid duplicating efforts on model imports. **Prompt:** “Split `models.py` into files by category (e.g. cues, settings, write) and update references throughout the project.”

6. **Improve architecture documentation:** **Objective:** Add diagrams or clear explanations in `docs/`. Files: in `docs/`. Changes: Create an architecture document with data flow. **Do not touch:** Code. **Risk:** Low. **Benefit:** Helps new contributors understand modularization. **Tests:** Not applicable. **Parallel:** Yes. **Prompt:** “Generate a diagram and explanatory text for the data flow in the MCP server for `docs/arquitectura.md`.”

7. **Rules for future features:** **Objective:** Write a guide (perhaps in `docs/`) with good practices for this project (based on MCP and QLab). Files: new document in `docs/`. **Risk:** Low. **Benefit:** Prevents disorderly growth. **Tests:** None. **Parallel:** Yes. **Prompt:** “Draft an architecture-rules document for this project, including guidelines for tools, models, and separation of logic.”

Each phase should be an independent PR, small enough for review. Work can be done in parallel in different areas (e.g. one developer improves tests while another extracts helpers).

# 13. Conflict risk (by file)

| **File**                      | **Reason for conflict**                                             | **Change frequency**      | **Risk**    | **Who touches it**           | **Strategy to reduce conflicts**                     | **Associated tests**                 | **Recommendation**             |
|-------------------------------|--------------------------------------------------------------------|---------------------------|-------------|-----------------------------|-----------------------------------------------------|----------------------------------------|-------------------------------|
| `server.py`                   | Tool registration (any new tool)                                   | High (new feature)       | High        | Feature modules, API integrators | Extract repetitive logic, minimize signature changes | `test_server_tools.py`              | Avoid touching unless necessary; handle sequentially |
| `qlab.py` (QLabReader)        | QLab communication logic (highly central)                          | Medium                    | High        | Read/write functionality       | Refactor in phases, add test coverage first        | `test_qlab_reader.py`             | Touch only with great care (facade) |
| `models.py`                   | Shared data models (many dependencies)                             | Medium                    | High        | Any tool or validation         | Consolidate before splitting, review imports       | Various output tests              | Only planned sequential changes |
| `write/operations.py`         | Logic for each write operation                                     | High (new ops)            | High        | Write feature development     | Split by responsibility (planner/executor)         | `test_write_mode.py`             | Avoid simultaneous editing of multiple operations |
| `write/registry.py`          | Operation registry (adding new ones)                               | Medium                    | Medium      | Write feature development     | Auto-registration based on decorators              | `test_write_mode.py`             | Coordinate parallel work (one person adds ops at a time) |
| `write/allowlist.py`          | Allowed command list (list updates)                                | Low                       | Medium      | Security/permissions          | Keep updated with permission tests                 | N/A (implicit in write tests)    | Occasional changes, low concurrency |
| `cues/overview.py` and peers | Cue-reading logic (high demand for features)                       | Medium                    | Medium      | Cue feature development       | Modularize independent functionality               | `test_server_tools.py` (cue output) | Multiple people can work (one cue type per PR) |
| `settings/`                  | Workspace settings reading                                         | Low                       | Low         | Config/OSC improvements       | Follow existing modularity                         | `test_server_tools.py` (settings output) | Infrequent change, parallelizable |
| `osc/client.py`, `addressing.py` | Basic OSC communication (little business logic)                | Low                       | Low         | Rarely; protocol evolution only | Ensure a stable interface; unit tests             | OSC unit tests (pending)          | Low conflict, parallel work possible |
| `tests/test_server_tools.py`  | Snapshots of all tools (contract updates)                          | High (with new tools)     | High        | Feature integrators           | Use per-tool tests to isolate impacts              | N/A (same test)                   | Always run; avoid simultaneous manual edits |
| `tests/test_write_mode.py`    | Comprehensive write-mode verification (covers all `operations.py`) | High (write changes)      | High        | Write-mode development        | Split tests by scenario (dry-run, real, failure)   | N/A (same test)                   | Touch sequentially when modifying write/ops |

The table indicates that *server.py*, *qlab.py*, *models.py*, and the contract tests have a high risk of conflict. They should be modified carefully and preferably in separate branches. Other areas (`osc/`, `cues/`, `settings/`) have lower risk and can be worked on in parallel.

# 14. Architecture rules for the future

To prevent the code from growing disorderly, we propose concrete rules based on the practices above:

- **MCP tools should be thin:** Each tool defined in `server.py` should not contain complex business logic. If the task is complicated, delegate to helper functions outside `server.py`. (FastMCP suggests that the tool should only invoke external logic.)
- **Tool names/parameters are a public contract:** Do not change existing tool names or parameters except for a critical reason. Any modification must entail updating contract tests and a major version bump.
- **Pydantic response models are a contract:** Fields in responses sent to clients must not change without review. Test schemas with contract tests.
- **OSC client without business logic:** The OSC client (`osc/client.py`) and addressing (`osc/addressing.py`) should only handle transport, not make decisions about QLab logic. This facilitates protocol changes without touching business logic.
- **Well-segmented write mode:** The write flow must clearly separate the phases: *planning* (dry-run), *real execution*, and *verification*. Each write tool must handle dry-run first and execute only after confirmation.
- **QLab operation classification:** Document in code (comments or docs) whether each operation is *read-only*, *read/write*, *control*, *view*, or *destructive*. Use those labels in `@mcp.tool(annotations=...)`. For example, destructive tools (`/go`, `/delete`, `/panic`) should be marked with `destructive_hint=True` and default to `readOnlyHint=False`.
- **Dry-run required:** Any new family of write operations (e.g. support for a cue type or setting) must first be implemented with a simulated dry-run and tests that validate the plan is correct, before real execution is allowed.
- **Contract coverage with snapshots:** When adding new tools, always update the snapshots in `test_server_tools.py`. Every new tool must have a test covering at least one typical execution and verifying the output.
- **Rejections and errors:** For each real operation (write), the rejection and dry-run cases must be implemented. Also, always test execution with rollback/verification: if the operation fails halfway through, what does the system do? Document it.
- **Structured vs. human data:** If a tool can return structured data (JSON) in addition to text, use `ToolResult(structured_content=...)` so clients can process it.
- **Separate large documentation:** Design or guide documents should not be mixed in the same PR with code logic, to simplify reviews.
- **Gradual updates:** Do not propose complete rewrites. Any large refactor should be divided and merged into `main` in small phases.

If followed, these rules will guide future contributions toward keeping the project modular, tested, and stable.

# 15. Expected final result

After the refactoring, the project should look like this:

- **Folder structure:**
  ```
  qlab_mcp/
    server.py      # minimal entrypoint, registers tools
    osc/           # OSC client and addressing
    qlab/          # (or qlab_reader/) QLab reader classes
    models/        # Pydantic models (split by domain)
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
    tests/         # tests separated by module
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
- **MCP request flow:** (as mapped in the docs diagram)
  MCP client → `server.py:@mcp.tool` (entry) → delegates to a handler function that uses QLabReader and internal modules → `osc.client` sends OSC → QLab (JSON response) → `QLabReader` / `models` parse it into a Python object → an MCP response is returned (possibly using `ToolResult`).

- **QLab read flow:** `QLabReader` calls `client.send_and_receive(address, args)` → receives JSON → converts it to a Pydantic model in `models/` → returns the result.

- **Write dry-run flow:** The write tool creates `plan = planner.create_plan(args)` → validates the plan with `validator` → returns a summary of the plan to the user (dry-run).

- **Real write flow:** After confirmation, the tool calls `planner`, then `executor.execute(plan)` (sends OSC to QLab), then `verifier.verify(plan)` to confirm changes.

- **Non-hotspot areas:** The most conflict-prone files (server.py, models, operations) should be smaller or delegate their logic, reducing future conflicts. Public contracts (tool names, output models) remain clear and documented.

- **Parallelizable areas:** For example, work can proceed in parallel in `osc/` (client), `cues/overview`, `settings/`, and `write/executor` because they are decoupled. Meanwhile, sequential work will take place in higher-friction areas (e.g. update `server.py` only once all tools are ready).

In summary, the final product will be more modular code, with clearly separated responsibilities, expanded tests, and a documented MCP request flow that anyone can follow. The central contract areas will have been consolidated and tested to prevent inadvertent breakage.

# 16. Executable prompts for Codex

1. **Characterization tests:**
   `"Analyze the tests in tests/test_server_tools.py and the current output models. Write new characterization test cases for missing QLabReader functions that validate typical JSON responses (for example, read the state of a cue and retrieve the expected fields)."`

2. **Extract helpers from `server.py`:**
   `"Identify any repeated error-handling or response-formatting logic in `src/qlab_mcp/server.py`. Extract that logic into a new module `src/qlab_mcp/server_errors.py` (or similar) and import the functions there to simplify `server.py`. Make sure to preserve the same behavior."`

3. **Split `write/operations.py`:**
   `"Refactor `src/qlab_mcp/write/operations.py` by separating command planning (`planning`) and execution (`executor`) into two new files (`write/planner.py` and `write/executor.py`). Update references throughout the rest of the code to use these new functions without changing the external logic."`

4. **Split Pydantic models (if considered):**
   `"Create a `src/qlab_mcp/models/` folder and split `models.py` into files by topic: for example, `cues.py` for cue models, `settings.py` for workspace models, and `write.py` for write schemas. Update imports in the code and tests to use the new modules."`

5. **Split PR #9 into smaller PRs (prompt example):**
   `"In the current PR that adds light commands with dry-run, identify separate components. Suggest two PRs: one defining the basic models and functions for 'setLight' in `write/operations.py` (including dry-run), and another PR adding the registry entry in `registry.py`, updated tests, and documentation. Describe the specific changes for each PR."`

6. **Update architecture documentation:**
   `"Write a brief `docs/arquitectura.md` document describing the flow of an MCP request in this server: what each module (`server.py`, `QLabReader`, `osc`, etc.) does and how they connect. Include a simple ASCII diagram if useful."`

7. **Branch/PR workflow guide:**
   `"Draft a branch and PR convention guide for this project: include the naming format (for example `feature/xyz`), recommended PR size (changes of ~200 lines), and examples of how to split a large feature (for example, adding video-light support in cues). Indicate which types of changes should be in separate PRs (docs, code, tests)."`

Each prompt should focus on one concrete change, allowing Codex to perform small, manageable tasks as requested.
