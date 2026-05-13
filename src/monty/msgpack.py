"""msgpack serialization and deserialization utilities. Right now, this is a stub
using monty.json encoder and decoders. The naming is just for clearer usage with
msgpack's default and object_hook naming.
"""

from __future__ import annotations

from monty.json import MontyDecoder, MontyEncoder


def default(obj: object) -> dict:
    """For use with msgpack.packb(obj, default=default). Supports Monty's as_dict
    protocol, numpy arrays and datetime.
    """
    return MontyEncoder().default(obj)


def object_hook(d: dict) -> object:
    """For use with msgpack.unpackb(dict, object_hook=object_hook.).  Supports
    Monty's as_dict protocol, numpy arrays and datetime.
    """
    return MontyDecoder().process_decoded(d)
