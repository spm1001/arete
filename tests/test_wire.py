"""The protobuf wire reader."""

import pytest

from arete import wire


def varint(value: int) -> bytes:
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        out.append(byte | (0x80 if value else 0))
        if not value:
            return bytes(out)


def tag(number: int, wire_type: int) -> bytes:
    return varint(number << 3 | wire_type)


def msg(number: int, payload: bytes) -> bytes:
    return tag(number, wire.LENGTH) + varint(len(payload)) + payload


def num(number: int, value: int) -> bytes:
    return tag(number, wire.VARINT) + varint(value)


@pytest.mark.parametrize("value", [0, 1, 127, 128, 300, 200, 1000, 2**31, 2**63 - 1])
def test_varint_round_trips(value):
    assert wire.read_varint(varint(value), 0) == (value, len(varint(value)))


def test_truncated_varint_raises():
    with pytest.raises(wire.WireError):
        wire.read_varint(b"\x80\x80\x80", 0)


def test_overlong_varint_raises():
    with pytest.raises(wire.WireError):
        wire.read_varint(b"\x80" * 12 + b"\x01", 0)


def test_fields_reads_mixed_types():
    data = num(1, 42) + msg(2, b"hello") + num(3, 7)
    assert [(f, v) for f, _, v in wire.fields(data)] == [
        (1, 42), (2, b"hello"), (3, 7),
    ]


def test_fields_stops_at_truncation_rather_than_raising():
    # A snapshot has sections this reader does not model; a partial walk of
    # one must not fail the whole read.
    data = num(1, 42) + tag(2, wire.LENGTH) + varint(99) + b"short"
    assert [(f, v) for f, _, v in wire.fields(data)] == [(1, 42)]


def test_fields_stops_on_field_number_zero():
    assert list(wire.fields(b"\x00" + num(1, 5))) == []


def test_fields_stops_on_reserved_wire_type():
    data = num(1, 1) + tag(2, 3) + num(3, 3)
    assert [f for f, _, _ in wire.fields(data)] == [1]


def test_child_returns_first_match_only():
    data = msg(1, b"first") + msg(1, b"second")
    assert wire.child(data, 1) == b"first"


def test_child_ignores_varints_of_the_same_number():
    assert wire.child(num(1, 5), 1) is None


def test_repeated_collects_every_match():
    data = msg(4, b"a") + msg(5, b"x") + msg(4, b"b")
    assert wire.repeated(data, 4) == [b"a", b"b"]


def test_scalar_reads_a_varint_field():
    assert wire.scalar(num(9, 1234), 9) == 1234
    assert wire.scalar(num(9, 1234), 8) is None


def test_path_walks_nested_messages():
    data = msg(1, msg(2, msg(3, b"deep")))
    assert wire.path(data, 1, 2, 3) == b"deep"


def test_path_returns_none_for_a_missing_link():
    data = msg(1, msg(2, b"x"))
    assert wire.path(data, 1, 99, 3) is None


def test_path_on_none_is_none():
    assert wire.path(None, 1) is None


def test_empty_input_yields_nothing():
    assert list(wire.fields(b"")) == []
