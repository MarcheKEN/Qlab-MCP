"""Strict, bounded public inputs for batched Light Patch edits."""
from __future__ import annotations

from typing import Annotated, Literal, Union
import unicodedata

from pydantic import (
    BaseModel, ConfigDict, Field, StrictBool, StrictFloat, StrictInt, StrictStr,
    AfterValidator, model_validator,
)


def _name(value: str) -> str:
    if value != value.strip() or any(unicodedata.category(char).startswith("C") for char in value):
        raise ValueError("Names must not contain control characters or surrounding whitespace.")
    return value


def _patch_name(value: str) -> str:
    _name(value)
    if not all(char.isalnum() or char == " " for char in value):
        raise ValueError("New instrument and group names permit letters, numbers and spaces only.")
    return value


Name = Annotated[StrictStr, Field(min_length=1, max_length=256), AfterValidator(_name)]
NewPatchName = Annotated[StrictStr, Field(min_length=1, max_length=128), AfterValidator(_patch_name)]
Note = Annotated[StrictStr, Field(max_length=16_384)]
Address = Annotated[StrictInt, Field(ge=1, le=512)]
Universe = Annotated[StrictInt, Field(ge=0, le=15)]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    @model_validator(mode="after")
    def reject_explicit_null(self):
        # Omitted update fields preserve state; only default_parameter accepts an explicit null.
        for name in self.model_fields_set - {"default_parameter"}:
            if getattr(self, name) is None:
                raise ValueError(f"{name} must be omitted instead of null.")
        return self


class UnpatchedOutput(Input):
    backend: Literal["none"]


class ArtNetOutput(Input):
    backend: Literal["artnet"]
    net: Annotated[StrictInt, Field(ge=0, le=127)]
    subnet: Universe
    universe: Universe
    address: Address = Field(description="First DMX address as displayed in QLab (1–512).")


class USBOutput(Input):
    backend: Literal["usb"]
    device_serial: Name = Field(description="Exact USB-DMX device serial, not a guessed display name.")
    device_name: Name
    device_universes: Annotated[StrictInt, Field(ge=1, le=512)]
    universe: Annotated[StrictInt, Field(ge=0, le=511)]
    address: Address

    @model_validator(mode="after")
    def device_universe_exists(self):
        if self.universe >= self.device_universes:
            raise ValueError("USB universe must be less than device_universes.")
        return self


LightOutput = Annotated[Union[UnpatchedOutput, ArtNetOutput, USBOutput], Field(discriminator="backend")]


class ScalarParameter(Input):
    type: Literal["scalar"]
    name: NewPatchName
    two_bytes: StrictBool = False
    value_is_percentage: StrictBool = True
    home_value: Annotated[StrictInt | StrictFloat, Field(ge=0, le=65535, allow_inf_nan=False)] = Field(
        default=0, description="Home in percent (0–100, decimals allowed) when value_is_percentage; otherwise integer DMX (0–255 or 0–65535 for two_bytes).")

    @model_validator(mode="after")
    def home_fits_width(self):
        if self.value_is_percentage:
            if self.home_value > 100:
                raise ValueError("Percentage home_value must not exceed 100.")
        elif type(self.home_value) is not int or self.home_value > (65535 if self.two_bytes else 255):
            raise ValueError("DMX home_value must be an integer within the parameter's 8/16-bit range.")
        return self


class RGBParameter(Input):
    type: Literal["rgbcolor"]
    name: NewPatchName
    outputs: Annotated[list[Name], Field(min_length=3, max_length=3)] | dict[Literal['red', 'green', 'blue', 'white', 'warmwhite', 'amber', 'lime'], Name] = Field(
        description="Physical scalar names in RGB order, or native RGB plus optional white/warmwhite/amber/lime outputs.")

    @model_validator(mode="after")
    def distinct_outputs(self):
        values = list(self.outputs.values()) if isinstance(self.outputs, dict) else self.outputs
        if isinstance(self.outputs, dict) and not {'red', 'green', 'blue'} <= self.outputs.keys():
            raise ValueError("RGB outputs require red, green and blue.")
        if len(set(values)) != len(values):
            raise ValueError("RGB outputs must name distinct scalar parameters.")
        return self


class CMYParameter(Input):
    type: Literal["cmycolor"]
    name: NewPatchName
    outputs: dict[Literal['cyan', 'magenta', 'yellow'], Name]

    @model_validator(mode="after")
    def complete_outputs(self):
        if set(self.outputs) != {'cyan', 'magenta', 'yellow'} or len(set(self.outputs.values())) != 3:
            raise ValueError("CMY outputs require distinct cyan, magenta and yellow parameters.")
        return self


class HSIParameter(Input):
    type: Literal["hsicolor"]
    name: NewPatchName
    outputs: dict[Literal['hue', 'saturation', 'intensity'], Name]

    @model_validator(mode="after")
    def complete_outputs(self):
        if set(self.outputs) != {'hue', 'saturation', 'intensity'} or len(set(self.outputs.values())) != 3:
            raise ValueError("HSI outputs require distinct hue, saturation and intensity parameters.")
        return self


class PanTiltParameter(Input):
    type: Literal["pantilt"]
    name: NewPatchName
    outputs: dict[Literal['pan', 'tilt'], Name]

    @model_validator(mode="after")
    def complete_outputs(self):
        if set(self.outputs) != {'pan', 'tilt'} or len(set(self.outputs.values())) != 2:
            raise ValueError("Pan/Tilt outputs require distinct pan and tilt parameters.")
        return self


class MuxerParameter(Input):
    type: Literal["muxer"]
    name: NewPatchName
    outputs: Annotated[list[Name], Field(min_length=1, max_length=512)]

    @model_validator(mode="after")
    def distinct_outputs(self):
        if len(set(self.outputs)) != len(self.outputs):
            raise ValueError("Muxer outputs must name distinct parameters.")
        return self


DefinitionParameter = Annotated[Union[
    ScalarParameter, RGBParameter, CMYParameter, HSIParameter, PanTiltParameter, MuxerParameter,
], Field(discriminator="type")]
Parameters = Annotated[list[DefinitionParameter], Field(min_length=1, max_length=512)]
Members = Annotated[list[Name], Field(max_length=4096)]


class CreateInstrument(Input):
    action: Literal["create_instrument"]
    name: NewPatchName
    definition: Name
    note: Note = ""
    output: LightOutput | None = None


class UpdateInstrument(Input):
    action: Literal["update_instrument"]
    name: Name = Field(description="Exact existing instrument name.")
    definition: Name | None = None
    note: Note | None = None
    output: LightOutput | None = None


class RenameInstrument(Input):
    action: Literal["rename_instrument"]
    name: Name
    new_name: NewPatchName


class DeleteInstrument(Input):
    action: Literal["delete_instrument"]
    name: Name


class CreateGroup(Input):
    action: Literal["create_group"]
    name: NewPatchName
    note: Note = ""
    members: Members = Field(default_factory=list)


class UpdateGroup(Input):
    action: Literal["update_group"]
    name: Name
    note: Note | None = None
    members: Members | None = None


class RenameGroup(Input):
    action: Literal["rename_group"]
    name: Name
    new_name: NewPatchName


class DeleteGroup(Input):
    action: Literal["delete_group"]
    name: Name


class CreateDefinition(Input):
    action: Literal["create_definition"]
    name: Name
    manufacturer: Name
    parameters: Parameters
    default_parameter: Name | None = Field(
        default=None, description="Exact default parameter name; null selects no default.")


class UpdateDefinition(Input):
    action: Literal["update_definition"]
    name: Name
    manufacturer: Name | None = None
    parameters: Parameters | None = None
    default_parameter: Name | None = None


class RenameDefinition(Input):
    action: Literal["rename_definition"]
    name: Name
    new_name: Name


class DeleteDefinition(Input):
    action: Literal["delete_definition"]
    name: Name


LightPatchOperation = Annotated[Union[
    CreateInstrument, UpdateInstrument, RenameInstrument, DeleteInstrument,
    CreateGroup, UpdateGroup, RenameGroup, DeleteGroup,
], Field(discriminator="action")]
LightPatchOperations = Annotated[list[LightPatchOperation], Field(min_length=1, max_length=100, strict=True)]


class ImportDefinition(Input):
    action: Literal['import_definition']
    definition_id: Annotated[StrictStr, Field(min_length=1, max_length=256)]
    name: Name | None = None


DefinitionOperation = Annotated[Union[
    CreateDefinition, UpdateDefinition, RenameDefinition, DeleteDefinition, ImportDefinition,
], Field(discriminator='action')]
DefinitionOperations = Annotated[list[DefinitionOperation], Field(min_length=1, max_length=100, strict=True)]
# Internal archive planner retains mixed operations for fixture construction and migrations.
ArchiveOperation = Annotated[Union[
    CreateInstrument, UpdateInstrument, RenameInstrument, DeleteInstrument,
    CreateGroup, UpdateGroup, RenameGroup, DeleteGroup,
    CreateDefinition, UpdateDefinition, RenameDefinition, DeleteDefinition,
], Field(discriminator='action')]
ArchiveOperations = Annotated[list[ArchiveOperation], Field(min_length=1, max_length=100, strict=True)]
