"""A minimal protobuf wire-format reader.

MindNode snapshots are protobuf with no schema published, so this reads the
wire format generically: enough to walk to a known field path, and no more.
Nothing here knows anything about MindNode — see `snapshot` for that.
"""

from __future__ import annotations

from typing import Iterator, Optional, Tuple

VARINT, FIXED64, LENGTH, FIXED32 = 0, 1, 2, 5


class WireError(ValueError):
    """The bytes are not well-formed protobuf."""


def read_varint(data: bytes, index: int) -> Tuple[int, int]:
    shift = value = 0
    while index < len(data):
        byte = data[index]
        index += 1
        value |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return value, index
        shift += 7
        if shift > 63:
            raise WireError("varint longer than 64 bits")
    raise WireError("truncated varint")


def fields(data: bytes) -> Iterator[Tuple[int, int, object]]:
    """Yield (field_number, wire_type, value) for one message.

    Stops at the first malformed record rather than raising: a snapshot
    contains sections this reader does not model, and a partial walk of a
    section we do not use must not fail the whole read.
    """
    index = 0
    while index < len(data):
        try:
            key, index = read_varint(data, index)
        except WireError:
            return
        number, wire_type = key >> 3, key & 7
        if number == 0:
            return
        try:
            if wire_type == VARINT:
                value, index = read_varint(data, index)
                yield number, wire_type, value
            elif wire_type == FIXED64:
                yield number, wire_type, data[index:index + 8]
                index += 8
            elif wire_type == LENGTH:
                length, index = read_varint(data, index)
                if index + length > len(data):
                    return
                yield number, wire_type, data[index:index + length]
                index += length
            elif wire_type == FIXED32:
                yield number, wire_type, data[index:index + 4]
                index += 4
            else:  # groups (3, 4) are not emitted by any modern encoder
                return
        except WireError:
            return


def child(data: bytes, number: int) -> Optional[bytes]:
    """The first sub-message or bytes value with this field number."""
    for found, wire_type, value in fields(data):
        if found == number and wire_type == LENGTH:
            return value
    return None


def path(data: Optional[bytes], *numbers: int) -> Optional[bytes]:
    """Walk a chain of single-valued length-delimited fields."""
    current = data
    for number in numbers:
        if current is None:
            return None
        current = child(current, number)
    return current


def repeated(data: bytes, number: int) -> list[bytes]:
    return [v for f, wt, v in fields(data) if f == number and wt == LENGTH]


def scalar(data: bytes, number: int) -> Optional[int]:
    for found, wire_type, value in fields(data):
        if found == number and wire_type == VARINT:
            return value  # type: ignore[return-value]
    return None
