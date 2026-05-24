"""Minimal OSC 1.0 message encoder/decoder used for QLab replies."""

from __future__ import annotations

from dataclasses import dataclass
import struct
from typing import Any

from ..errors import OscProtocolError


@dataclass(frozen=True)
class OscMessage:
    address: str
    args: tuple[Any, ...] = ()


def _pad(data: bytes) -> bytes:
    padding = (4 - (len(data) % 4)) % 4
    return data + (b"\x00" * padding)


def _encode_string(value: str) -> bytes:
    return _pad(value.encode("utf-8") + b"\x00")


def encode_message(address: str, *args: Any) -> bytes:
    if not address.startswith("/"):
        raise OscProtocolError(f"OSC address must start with '/': {address!r}")

    tags = [","]
    payload = bytearray()

    for arg in args:
        if isinstance(arg, bool):
            tags.append("T" if arg else "F")
        elif isinstance(arg, int) and not isinstance(arg, bool):
            tags.append("i")
            payload.extend(struct.pack(">i", arg))
        elif isinstance(arg, float):
            tags.append("f")
            payload.extend(struct.pack(">f", arg))
        elif isinstance(arg, str):
            tags.append("s")
            payload.extend(_encode_string(arg))
        elif arg is None:
            tags.append("N")
        else:
            raise OscProtocolError(f"Unsupported OSC argument type: {type(arg).__name__}")

    return _encode_string(address) + _encode_string("".join(tags)) + bytes(payload)


def _read_string(packet: bytes, offset: int) -> tuple[str, int]:
    end = packet.find(b"\x00", offset)
    if end < 0:
        raise OscProtocolError("Unterminated OSC string")
    value = packet[offset:end].decode("utf-8")
    next_offset = end + 1
    next_offset += (4 - (next_offset % 4)) % 4
    if next_offset > len(packet):
        raise OscProtocolError("OSC string padding exceeds packet length")
    return value, next_offset


def decode_message(packet: bytes) -> OscMessage:
    address, offset = _read_string(packet, 0)
    if not address.startswith("/"):
        raise OscProtocolError(f"Invalid OSC address: {address!r}")

    tags, offset = _read_string(packet, offset)
    if not tags.startswith(","):
        raise OscProtocolError("OSC typetag string missing comma")

    args: list[Any] = []
    for tag in tags[1:]:
        if tag == "s":
            value, offset = _read_string(packet, offset)
            args.append(value)
        elif tag == "i":
            if offset + 4 > len(packet):
                raise OscProtocolError("OSC int argument truncated")
            args.append(struct.unpack(">i", packet[offset : offset + 4])[0])
            offset += 4
        elif tag == "f":
            if offset + 4 > len(packet):
                raise OscProtocolError("OSC float argument truncated")
            args.append(struct.unpack(">f", packet[offset : offset + 4])[0])
            offset += 4
        elif tag == "d":
            if offset + 8 > len(packet):
                raise OscProtocolError("OSC double argument truncated")
            args.append(struct.unpack(">d", packet[offset : offset + 8])[0])
            offset += 8
        elif tag == "T":
            args.append(True)
        elif tag == "F":
            args.append(False)
        elif tag == "N":
            args.append(None)
        else:
            raise OscProtocolError(f"Unsupported OSC typetag in reply: {tag!r}")

    return OscMessage(address=address, args=tuple(args))
