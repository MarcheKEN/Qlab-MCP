"""Gated local QLab document lifecycle; fixed scripts and fresh native inventory."""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import secrets
import subprocess
import threading
import time
from typing import Any
from uuid import UUID

from .write.safety import check_write_readiness
from .write.tokens import decode_confirm_token, encode_confirm_token

_SECRET = secrets.token_bytes(32)
_LOCK = threading.RLock()
_USED: dict[str, float] = {}
_TOKEN_SECONDS = 300
_MAX_BYTES = 64 * 1024 * 1024
_MAX_ENTRIES = 4096

SCRIPT = '''use framework "AppKit"
on canonicalPath(rawPath)
 if rawPath is "" then return ""
 set p to current application's NSString's stringWithString:rawPath
 return (p's stringByStandardizingPath()'s stringByResolvingSymlinksInPath()) as text
end canonicalPath
on inventory(applicationPath)
 set rows to current application's NSMutableArray's array()
 using terms from application "/Applications/QLab.app"
 tell application applicationPath
  repeat with w in every workspace
   set workspaceRecord to current application's NSMutableDictionary's dictionary()
   workspaceRecord's setObject:(unique id of w) forKey:"workspace_id"
   workspaceRecord's setObject:(name of w) forKey:"name"
   set p to path of w
   if p is missing value then set p to ""
   workspaceRecord's setObject:(my canonicalPath(p)) forKey:"path"
   workspaceRecord's setObject:(modified of w) forKey:"modified"
   workspaceRecord's setObject:(edit mode of w) forKey:"edit_mode"
   workspaceRecord's setObject:(show mode of w) forKey:"show_mode"
   set activeIDs to current application's NSMutableArray's array()
   repeat with c in active cues of w
    activeIDs's addObject:(uniqueID of c)
   end repeat
   workspaceRecord's setObject:activeIDs forKey:"active_cue_ids"
   rows's addObject:workspaceRecord
  end repeat
 end tell
 end using terms from
 return rows
end inventory
on run argv
 set sent to false
 set output to current application's NSMutableDictionary's dictionary()
 try
  set raw to current application's NSString's stringWithString:(item 1 of argv)
  set payload to current application's NSJSONSerialization's JSONObjectWithData:(raw's dataUsingEncoding:(current application's NSUTF8StringEncoding)) options:0 |error|:(missing value)
  set actionName to (payload's objectForKey:"action") as text
  set apps to current application's NSRunningApplication's runningApplicationsWithBundleIdentifier:"com.figure53.QLab.5"
  set appCount to apps's |count|() as integer
  if appCount is 0 then error "No QLab instance is running."
  if appCount is greater than 1 then error "Multiple QLab instances are running."
  set runningPath to (((apps's firstObject())'s bundleURL()'s |path|()) as text)
  set bundle to current application's NSBundle's bundleWithPath:runningPath
  set appInfo to bundle's infoDictionary()
  set appIdentity to current application's NSMutableDictionary's dictionary()
  appIdentity's setObject:runningPath forKey:"path"
  appIdentity's setObject:((apps's firstObject())'s processIdentifier()) forKey:"pid"
  repeat with infoKey in {"CFBundleIdentifier", "CFBundleShortVersionString", "CFBundleVersion"}
   appIdentity's setObject:(appInfo's objectForKey:infoKey) forKey:infoKey
  end repeat
  if ((appInfo's objectForKey:"CFBundleIdentifier") as text) is not "com.figure53.QLab.5" then error "Unexpected QLab bundle identity."
  output's setObject:appIdentity forKey:"application"
  if actionName is not "read_inventory" and actionName is not "inventory" then
   if ((appInfo's objectForKey:"CFBundleShortVersionString") as text) is not "5.5.10" or ((appInfo's objectForKey:"CFBundleVersion") as text) is not "5510" then error "Native writes require QLab 5.5.10/build 5510."
   set expectedApp to payload's objectForKey:"expected_application"
   if expectedApp is missing value then error "Expected application identity is required."
   if not (appIdentity's isEqualToDictionary:expectedApp) then error "Running QLab identity changed."
  end if
  if actionName is "inventory" or actionName is "read_inventory" then
   output's setObject:(my inventory(runningPath)) forKey:"documents"
  else
   set targetPath to my canonicalPath((payload's objectForKey:"path") as text)
   using terms from application "/Applications/QLab.app"
   tell application runningPath
    if actionName is "open" then
     set currentRows to my inventory(runningPath)
     if (currentRows's |count|() as integer) is not 0 then error "Opening requires all existing workspaces to be closed."
     set expectedRows to payload's objectForKey:"expected_inventory"
     if not (currentRows's isEqualToArray:expectedRows) then error "Open workspace inventory changed."
     repeat with existingRow in currentRows
      if ((existingRow's objectForKey:"path") as text) is targetPath then error "Document is already open."
     end repeat
     set sent to true
     open (POSIX file targetPath)
    else if actionName is "save" or actionName is "close" then
     set wsid to (payload's objectForKey:"workspace_id") as text
     set matches to every workspace whose unique id is wsid
     if (count of matches) is not 1 then error "Workspace UUID must resolve exactly once."
     set w to item 1 of matches
     set currentRows to my inventory(runningPath)
     set pathMatches to 0
     repeat with existingRow in currentRows
      if targetPath is not "" and ((existingRow's objectForKey:"path") as text) is targetPath then set pathMatches to pathMatches + 1
     end repeat
     if targetPath is not "" and pathMatches is not 1 then error "Document path must resolve exactly once."
     set p to path of w
     if p is missing value then set p to ""
     if (my canonicalPath(p)) is not targetPath then error "Document path changed."
     if not (edit mode of w) or (show mode of w) or (count of active cues of w) is not 0 then error "Workspace must be inactive and in Edit Mode."
     if (modified of w) is not ((payload's objectForKey:"expected_modified") as boolean) then error "Document dirty flag changed."
     if actionName is "save" then
      if targetPath is "" then error "Save requires an existing path."
      set sent to true
      save w
     else
      if modified of w then error "Closing unsaved changes is forbidden."
      set sent to true
      close w saving no
     end if
    else
     error "Unsupported document action."
    end if
   end tell
   end using terms from
  end if
 on error messageText number errorNumber
  output's setObject:messageText forKey:"error"
  output's setObject:errorNumber forKey:"error_number"
 end try
 output's setObject:sent forKey:"sent"
 set dataJSON to current application's NSJSONSerialization's dataWithJSONObject:output options:0 |error|:(missing value)
 return (current application's NSString's alloc()'s initWithData:dataJSON encoding:(current application's NSUTF8StringEncoding)) as text
end run
'''


def _uuid(value: Any) -> str:
    if not isinstance(value, str) or str(UUID(value)).casefold() != value.casefold():
        raise ValueError("workspace_id must be a complete UUID.")
    return value.upper()


def _local(reader: Any) -> None:
    if reader.client.config.host not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("Native document operations require local QLab.")


def _native_request(reader: Any, action: str = "inventory", **payload: Any) -> dict:
    _local(reader)
    if action not in {"inventory", "read_inventory", "save", "close", "open"}:
        raise ValueError("Unsupported document action.")
    timeout = reader.client.config.timeout
    if type(timeout) not in {int, float} or not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("Native timeout must be positive and finite.")
    result = subprocess.run(["/usr/bin/osascript", "-", json.dumps(
        {"action": action, **payload}, allow_nan=False)], input=SCRIPT, text=True,
        capture_output=True, check=False, timeout=timeout)
    if result.returncode:
        raise ValueError(f"Native document script failed: {result.stderr.strip()}")
    response = json.loads(result.stdout)
    if not isinstance(response, dict):
        raise ValueError("Invalid native document response.")
    return response


def _inventory(reader: Any, *, running_bundle: bool = False) -> dict:
    _local(reader)
    response = _native_request(reader, "read_inventory") if running_bundle else _native_request(reader)
    if response.get("error") or not isinstance(response.get("documents"), list):
        raise ValueError(response.get("error") or "Native document inventory is unavailable.")
    documents = []
    for original in response["documents"]:
        row = dict(original)
        row["workspace_id"] = _uuid(row.get("workspace_id"))
        if not isinstance(row.get("name"), str) or not isinstance(row.get("path"), str):
            raise ValueError("Native document path/name is unavailable.")
        if row["path"]:
            if not Path(row["path"]).is_absolute():
                raise ValueError("Native document path must be absolute.")
            row["path"] = str(Path(row["path"]).resolve())
        if any(type(row.get(flag)) is not bool for flag in ("modified", "edit_mode", "show_mode")):
            raise ValueError("Native document mode/dirty state is unavailable.")
        if not isinstance(row.get("active_cue_ids"), list):
            raise ValueError("Native active cue inventory is unavailable.")
        row["active_cue_ids"] = [_uuid(uid) for uid in row["active_cue_ids"]]
        documents.append(row)
    result = {"documents": documents}
    if "application" in response:
        app = response["application"]
        if (not isinstance(app, dict) or app.get("CFBundleIdentifier") != "com.figure53.QLab.5"
                or not isinstance(app.get("path"), str) or not Path(app["path"]).is_absolute()
                or type(app.get("pid")) is not int or app["pid"] <= 0):
            raise ValueError("Invalid running QLab identity.")
        result["application"] = app
    return result


def _document(inventory: dict, ws: str) -> dict:
    matches = [row for row in inventory["documents"] if row["workspace_id"] == ws]
    if len(matches) != 1:
        raise ValueError("Workspace UUID must resolve exactly once in native inventory.")
    row = matches[0]
    if row["path"] and sum(item["path"] == row["path"] for item in inventory["documents"]) != 1:
        raise ValueError("Document path must resolve exactly once in native inventory.")
    return row


def _path(value: Any) -> Path:
    if not isinstance(value, str) or not value or "\x00" in value or not Path(value).is_absolute():
        raise ValueError("An absolute existing .qlab5 path is required.")
    path = Path(value).resolve(strict=True)
    if path.suffix.casefold() != ".qlab5" or not (path.is_file() or path.is_dir()) or not os.access(path, os.R_OK):
        raise ValueError("The path must be a readable .qlab5 file or package.")
    return path


def _fingerprint(path: Path) -> str:
    """Bound reads to 64 MiB/4096 entries; reject symlinks inside packages."""
    digest = hashlib.sha256()
    entries = [path]
    if path.is_dir():
        for entry in path.rglob("*"):
            entries.append(entry)
            if len(entries) > _MAX_ENTRIES:
                raise ValueError("Workspace package exceeds bounded fingerprint entry limit.")
        entries.sort()
    size = 0
    for entry in entries:
        if entry.is_symlink() or not (entry.is_file() or entry.is_dir()):
            raise ValueError("Workspace package contains an unsupported entry.")
        stat = entry.stat()
        digest.update(json.dumps([str(entry.relative_to(path)) if entry != path else ".",
            entry.is_dir(), stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns],
            separators=(",", ":")).encode())
        if entry.is_file():
            if size + stat.st_size > _MAX_BYTES:
                raise ValueError("Workspace exceeds bounded fingerprint byte limit.")
            with entry.open("rb") as stream:
                for chunk in iter(lambda: stream.read(65536), b""):
                    size += len(chunk)
                    if size > _MAX_BYTES:
                        raise ValueError("Workspace exceeds bounded fingerprint byte limit.")
                    digest.update(chunk)
    return digest.hexdigest()


def _result(ok: bool, status: str, **values: Any) -> dict:
    return {"ok": ok, "status": status, "planned_operations": [], "executed_operations": [], **values}


def _token(action: str, baseline: dict) -> str:
    return encode_confirm_token("workspaceDocument", 1, {
        "action": action, "baseline": baseline, "expires_at": time.time() + _TOKEN_SECONDS,
        "nonce": secrets.token_hex(16)}, _SECRET)


def _reserve(token: Any, action: str, baseline: dict) -> None:
    if not isinstance(token, str):
        raise ValueError("A fresh document confirmation token is required.")
    payload, error = decode_confirm_token(token, "workspaceDocument", 1, _SECRET)
    if error or payload is None:
        raise ValueError(f"Invalid document confirmation token: {error}.")
    expiry = payload.get("expires_at")
    if type(expiry) not in {int, float} or not math.isfinite(expiry) or time.time() >= expiry:
        raise ValueError("Document confirmation token expired.")
    if payload.get("action") != action or payload.get("baseline") != baseline:
        raise ValueError("Document confirmation token does not match the fresh plan.")
    with _LOCK:
        for used, deadline in list(_USED.items()):
            if time.time() >= deadline:
                del _USED[used]
        if token in _USED:
            raise ValueError("Document confirmation token was already used.")
        _USED[token] = expiry


def get_workspace_document(reader: Any, workspace_id: str) -> dict:
    try:
        ws = _uuid(workspace_id)
        inventory = _inventory(reader)
        return _result(True, "read", workspace_id=ws, document=_document(inventory, ws), readback=inventory)
    except Exception as exc:
        return _result(False, "blocked", error=str(exc))


def _existing(reader: Any, workspace_id: str, action: str, dry_run: bool, confirm_token: str | None) -> dict:
    try:
        ws = _uuid(workspace_id)
        if type(dry_run) is not bool:
            raise ValueError("dry_run must be boolean.")
        _local(reader)
        readiness = check_write_readiness(reader, ws)
        if not readiness.get("ok"):
            return _result(False, "blocked", error="Workspace write readiness is blocked.", readiness=readiness)
        inventory = _inventory(reader)
        row = _document(inventory, ws)
        if not row["edit_mode"] or row["show_mode"] or row["active_cue_ids"]:
            raise ValueError("Workspace must be inactive and in Edit Mode.")
        if action == "close" and row["modified"]:
            raise ValueError("Closing unsaved changes is forbidden; save explicitly first.")
        baseline = {"document": row, "application": inventory.get("application")}
        if action == "save":
            baseline["fingerprint"] = _fingerprint(_path(row["path"]))
        operation = {"action": action, "workspace_id": ws, "path": row["path"], "transport": "applescript"}
        plan = _result(True, "planned", workspace_id=ws, document=row, planned_operations=[operation],
            warnings=["Save includes all current unsaved changes; modified is a dirty flag, not an edit revision."] if action == "save" else [],
            readback=inventory)
        if dry_run:
            return {**plan, "confirm_token": _token(action, baseline)}
        _reserve(confirm_token, action, baseline)
    except Exception as exc:
        return _result(False, "blocked", error=str(exc))
    with _LOCK:
        return _execute(reader, action, operation, plan, baseline, workspace_id=ws,
            path=row["path"], expected_modified=row["modified"])


def save_workspace(reader: Any, workspace_id: str, dry_run: bool = True, confirm_token: str | None = None) -> dict:
    return _existing(reader, workspace_id, "save", dry_run, confirm_token)


def close_workspace(reader: Any, workspace_id: str, dry_run: bool = True, confirm_token: str | None = None) -> dict:
    return _existing(reader, workspace_id, "close", dry_run, confirm_token)


def open_workspace(reader: Any, path: str, dry_run: bool = True, confirm_token: str | None = None) -> dict:
    try:
        target = _path(path)
        if type(dry_run) is not bool:
            raise ValueError("dry_run must be boolean.")
        _local(reader)
        if not reader.client.config.enable_write:
            raise ValueError("QLAB_ENABLE_WRITE must be enabled for document operations.")
        inventory = _inventory(reader)
        rows = inventory["documents"]
        if rows:
            raise ValueError("Opening requires all existing workspaces to be closed; file UUID cannot be verified before open.")
        baseline = {"path": str(target), "fingerprint": _fingerprint(target), "inventory": rows, "application": inventory.get("application")}
        operation = {"action": "open", "path": str(target), "transport": "applescript"}
        plan = _result(True, "planned", planned_operations=[operation], path=str(target), readback=inventory)
        if dry_run:
            return {**plan, "confirm_token": _token("open", baseline)}
        _reserve(confirm_token, "open", baseline)
    except Exception as exc:
        return _result(False, "blocked", error=str(exc))
    with _LOCK:
        return _execute(reader, "open", operation, plan, baseline, path=str(target), expected_inventory=rows)


def _execute(reader: Any, action: str, operation: dict, plan: dict, baseline: dict, **payload: Any) -> dict:
    try:
        # Recheck disk after reserving the token and before the single native event.
        if "fingerprint" in baseline:
            path = payload["path"]
            if _fingerprint(_path(path)) != baseline["fingerprint"]:
                return {**plan, "ok": False, "status": "blocked", "error": "Workspace file changed before event."}
    except Exception as exc:
        return {**plan, "ok": False, "status": "blocked", "error": str(exc)}
    error = None
    response = None
    received_response = False
    timed_out = False
    try:
        response = _native_request(reader, action, expected_application=baseline.get("application"), **payload)
        received_response = True
        if isinstance(response, dict):
            if response.get("sent") is False:
                return {
                    **plan,
                    "ok": False,
                    "status": "blocked",
                    "error": response.get("error") or "Native document event was not sent.",
                }
            error = response.get("error")
        else:
            error = "Native document bridge returned an invalid response."
    except Exception as exc:
        error = str(exc)
        timed_out = isinstance(exc, subprocess.TimeoutExpired)
    result = {**plan, "ok": False, "status": "uncertain", "executed_operations": [{**operation, "sent": "attempted"}]}
    if error:
        result["event_error"] = error
    try:
        inventory = _inventory(reader)
        result["readback"] = inventory
        if inventory.get("application") != baseline.get("application"):
            raise ValueError("Running QLab identity changed during the operation.")
        if action == "close":
            confirmed = not any(row["workspace_id"] == payload["workspace_id"] or
                (payload["path"] and row["path"] == payload["path"]) for row in inventory["documents"])
            result["document"] = None
        elif action == "save":
            row = _document(inventory, payload["workspace_id"])
            result["document"] = row
            confirmed = row["path"] == payload["path"] and not row["modified"] and _path(row["path"]).exists()
        else:
            matches = [row for row in inventory["documents"] if row["path"] == payload["path"]]
            confirmed = len(matches) == 1
            if confirmed:
                row = _document(inventory, matches[0]["workspace_id"])
                confirmed = row["workspace_id"] not in {item["workspace_id"] for item in baseline["inventory"]}
                result.update(workspace_id=row["workspace_id"], document=row)
        response_sent = response.get("sent") if isinstance(response, dict) else None
        if confirmed and (not received_response or response_sent is True):
            status = {"save": "saved", "close": "closed", "open": "opened"}[action]
            result.update(ok=True, status=status + ("_with_confirmed_timeout" if timed_out else "_with_confirmed_error" if error else ""))
        else:
            result["error"] = (
                "Fresh native inventory or event acknowledgement did not confirm the document operation; "
                "do not retry automatically."
            )
    except Exception as exc:
        result.update(error=f"Fresh readback failed: {exc}. Do not retry automatically.", readback=None)
    return result
