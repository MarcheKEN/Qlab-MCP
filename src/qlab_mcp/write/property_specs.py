"""Internal edit property spec helpers for QLab write metadata."""

from __future__ import annotations

from dataclasses import dataclass
from string import Formatter
from typing import Any


@dataclass(frozen=True)
class CuePropertySpec:
    name: str
    path: str | None = None
    args: tuple[tuple[str, str], ...] = (("value", "any"),)
    osc_args: tuple[str, ...] = ("value",)
    read_key: str | None = None
    modes: tuple[str, ...] = ("saved",)
    risk_tier: str = "safe"
    real_write_enabled: bool = False
    planned_only_reason: str | None = None
    doc_section: str | None = None
    osc_paths: tuple[str, ...] = ()
    capability_gate: str | None = None
    readback: str = "value"
    contextual_requirements: tuple[str, ...] = ()


@dataclass(frozen=True)
class UpdateProfileSpec:
    name: str
    cue_types: tuple[str, ...]
    properties: tuple[CuePropertySpec, ...]
    risk_tier: str
    real_write_enabled: bool
    description: str


def _prop(
    name: str,
    validator: str = "any",
    *,
    path: str | None = None,
    read_key: str | None = None,
    modes: tuple[str, ...] = ("saved",),
    risk_tier: str = "safe",
    real_write_enabled: bool = False,
    planned_only_reason: str | None = None,
    doc_section: str | None = None,
    osc_paths: tuple[str, ...] = (),
    capability_gate: str | None = None,
    readback: str = "value",
    contextual_requirements: tuple[str, ...] = (),
) -> CuePropertySpec:
    return CuePropertySpec(
        name=name,
        path=path,
        args=(("value", validator),),
        osc_args=("value",),
        read_key=read_key if read_key is not None else name,
        modes=modes,
        risk_tier=risk_tier,
        real_write_enabled=real_write_enabled,
        planned_only_reason=planned_only_reason,
        doc_section=doc_section,
        osc_paths=osc_paths,
        capability_gate=capability_gate,
        readback=readback,
        contextual_requirements=contextual_requirements,
    )


def _op(
    name: str,
    args: tuple[tuple[str, str], ...],
    *,
    path: str | None = None,
    osc_args: tuple[str, ...] | None = None,
    read_key: str | None = None,
    modes: tuple[str, ...] = ("saved",),
    risk_tier: str = "medium",
    real_write_enabled: bool = False,
    planned_only_reason: str = "planned_only_until_real_world_validation",
    doc_section: str | None = None,
    osc_paths: tuple[str, ...] = (),
    capability_gate: str | None = None,
    readback: str = "value",
    contextual_requirements: tuple[str, ...] = (),
) -> CuePropertySpec:
    path_args = _path_arg_names(path or name)
    return CuePropertySpec(
        name=name,
        path=path,
        args=args,
        osc_args=osc_args if osc_args is not None else tuple(arg for arg, _ in args if arg not in path_args),
        read_key=read_key,
        modes=modes,
        risk_tier=risk_tier,
        real_write_enabled=real_write_enabled,
        planned_only_reason=planned_only_reason if not real_write_enabled else None,
        doc_section=doc_section,
        osc_paths=osc_paths,
        capability_gate=capability_gate,
        readback=readback,
        contextual_requirements=contextual_requirements,
    )


def _planned_prop(
    name: str,
    validator: str = "any",
    *,
    path: str | None = None,
    read_key: str | None = None,
    reason: str,
    modes: tuple[str, ...] = ("saved",),
    capability_gate: str | None = None,
    doc_section: str | None = None,
    osc_paths: tuple[str, ...] = (),
    contextual_requirements: tuple[str, ...] = (),
) -> CuePropertySpec:
    return _prop(
        name,
        validator,
        path=path,
        read_key=read_key,
        modes=modes,
        risk_tier="high",
        real_write_enabled=False,
        planned_only_reason=reason,
        capability_gate=capability_gate,
        doc_section=doc_section,
        osc_paths=osc_paths,
        contextual_requirements=contextual_requirements,
    )


def _path_arg_names(path: str) -> tuple[str, ...]:
    return tuple(field_name for _, field_name, _, _ in Formatter().parse(path) if field_name)
