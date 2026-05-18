"""msgpack serialization and deserialization utilities.

A thin shim over ``monty.json``'s encoder/decoder. The naming matches
msgpack's ``default`` and ``object_hook`` parameters.
"""

from __future__ import annotations

from monty.json import MontyDecoder, MontyEncoder


def default(obj: object) -> dict:
    """Encode an object for ``msgpack.packb(obj, default=default)``.

    Supports Monty's ``as_dict`` protocol, numpy arrays, and ``datetime``.
    """
    return MontyEncoder().default(obj)


def object_hook(d: dict) -> object:
    """Decode a dict from ``msgpack.unpackb(..., object_hook=object_hook)``.

    Supports Monty's ``as_dict`` protocol, numpy arrays, and ``datetime``.
    """
    return MontyDecoder().process_decoded(d)
