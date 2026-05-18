"""Serialization helpers for common formats (JSON, JSONL, YAML, msgpack)."""

from __future__ import annotations

import json
import os
import pathlib
from typing import TYPE_CHECKING, Literal, TextIO, cast

from ruamel.yaml import YAML

from monty.io import zopen
from monty.json import MontyDecoder, MontyEncoder, MSONable
from monty.msgpack import default, object_hook

try:
    import msgpack
except ImportError:
    msgpack = None

if TYPE_CHECKING:
    from pathlib import Path
    from typing import Any

    from monty.shutil import PathLike

_FILE_TYPE = Literal["json", "jsonl", "yaml", "mpk"]

# A single ``YAML()`` instance is reusable across calls and avoids per-call
# construction cost (the constructor walks ruamel.yaml resolver tables).
_YAML = YAML()

# Bridge the JSON ``TypeHandler`` plugin registry into ruamel.yaml so MSONable
# subclasses and every registered handler type (numpy, pandas, pint, torch,
# uuid, bson, user-registered) round-trip through ``dumpfn`` / ``loadfn`` the
# same way they do via JSON. ruamel.yaml retains its native rendering for
# types it already supports (datetime, set, OrderedDict, bytes, primitives).
_MONTY_ENCODER = MontyEncoder()


def _represent_via_monty(representer: Any, data: Any) -> Any:
    """Encode ``data`` via :class:`MontyEncoder` and represent the result.

    Used as a ruamel.yaml multi-representer for ``MSONable`` / ``PurePath``
    and as the fallback for the ``None``-keyed dispatch slot (replacing
    ``represent_undefined``). The encoder returns a JSON-compatible value —
    typically a dict with ``@module``/``@class`` — which ruamel.yaml then
    represents recursively, so nested non-native types route through the
    same hook.
    """
    return representer.represent_data(_MONTY_ENCODER.default(data))


_YAML.representer.add_multi_representer(MSONable, _represent_via_monty)
# Paths would otherwise hit ruamel.yaml's default ``str(obj)`` fallback,
# which is lossy on load. Route them through the PathHandler envelope.
_YAML.representer.add_multi_representer(pathlib.PurePath, _represent_via_monty)
# Replace the ``None`` slot — invoked when neither yaml_representers nor
# yaml_multi_representers match — with a hook that tries MontyEncoder first,
# falling back to the original ``represent_undefined`` (which raises
# ``RepresenterError``) if MontyEncoder cannot serialize the object either.
_ORIG_REPRESENT_UNDEFINED = _YAML.representer.yaml_representers[None]


def _represent_undefined(representer: Any, data: Any) -> Any:
    try:
        return _represent_via_monty(representer, data)
    except TypeError:
        return _ORIG_REPRESENT_UNDEFINED(representer, data)


_YAML.representer.yaml_representers[None] = _represent_undefined


def _identify_format(file_name: str | Path) -> _FILE_TYPE:
    """Identify the format of a file with name ``file_name``.

    Detection is based on extension (suffix) rather than substring match so a
    file called ``"myjsonlist.json"`` is not mis-classified as JSON-lines and
    ``"data.mpkfoo"`` is not classified as msgpack.
    """
    # ``os.path.basename`` is fast and avoids a ``Path`` allocation. We strip
    # one layer of common compression suffixes so e.g. ``foo.json.gz`` is
    # detected as JSON.
    basename = os.path.basename(str(file_name)).lower()
    for compressed_ext in (".gz", ".bz2", ".xz", ".lzma", ".z"):
        if basename.endswith(compressed_ext):
            basename = basename[: -len(compressed_ext)]
            break

    if basename.endswith(".mpk"):
        return "mpk"
    if basename.endswith((".yaml", ".yml")):
        return "yaml"
    if basename.endswith(".jsonl"):
        return "jsonl"
    return "json"


def loadfn(
    fn: PathLike,
    *args,
    fmt: _FILE_TYPE | None = None,
    **kwargs,
) -> Any:
    """Load JSON/JSONL/YAML/msgpack from a filename.

    Supports BZ2 (``.bz2``), GZIP (``.gz``, ``.z``), XZ (``.xz``, ``.lzma``)
    compressed inputs transparently. YAML support requires ``ruamel.yaml``.
    Format is auto-detected from the (case-insensitive) extension: ``.yaml``
    / ``.yml`` → YAML; ``.mpk`` → msgpack; ``.jsonl`` → JSON lines; otherwise
    JSON.

    Args:
        fn (str | Path): Filename or ``pathlib.Path``.
        *args: Any of the args supported by ``json``/``yaml``/``msgpack.load``.
        fmt ("json" | "jsonl" | "yaml" | "mpk"): If provided, overrides the
            auto-detected format.
        **kwargs: Any of the kwargs supported by ``json``/``yaml``/``msgpack.load``.

    Returns:
        object: Result of ``json``/``yaml``/``msgpack.load``.

    """
    fmt = fmt or _identify_format(fn)

    if fmt == "mpk":
        if msgpack is None:
            raise RuntimeError(
                "Loading of message pack files is not possible as msgpack-python is not installed."
            )
        if "object_hook" not in kwargs:
            kwargs["object_hook"] = object_hook
        with zopen(fn, mode="rb") as fp:
            return msgpack.load(fp, *args, **kwargs)  # pylint: disable=E1101
    else:
        with zopen(fn, mode="rt", encoding="utf-8") as fp:
            if fmt == "yaml":
                if YAML is None:
                    raise RuntimeError("Loading of YAML files requires ruamel.yaml.")
                # ``cls`` is a monty-level kwarg (not ruamel.yaml's) — pop it
                # before forwarding so ``_YAML.load`` doesn't choke. Passing
                # ``cls=None`` opts out of MSONable reconstruction, matching
                # the JSON path's escape hatch.
                cls = kwargs.pop("cls", MontyDecoder)
                loaded = _YAML.load(fp, *args, **kwargs)
                if cls is not None:
                    loaded = MontyDecoder().process_decoded(loaded)
                return loaded

            if fmt in {"json", "jsonl"}:
                if "cls" not in kwargs:
                    kwargs["cls"] = MontyDecoder

                if fmt == "jsonl":
                    return [json.loads(jline, *args, **kwargs) for jline in fp]
                return json.load(fp, *args, **kwargs)

            raise TypeError(f"Invalid format: {fmt}")


def dumpfn(
    obj: object,
    fn: PathLike,
    *args,
    fmt: _FILE_TYPE | None = None,
    **kwargs,
) -> None:
    """Dump an object to a JSON/JSONL/YAML/msgpack file by filename.

    Supports BZ2 (``.bz2``), GZIP (``.gz``, ``.z``), XZ (``.xz``, ``.lzma``)
    compressed outputs transparently. YAML support requires ``ruamel.yaml``.
    Format is auto-detected from the (case-insensitive) extension: ``.yaml``
    / ``.yml`` → YAML; ``.mpk`` → msgpack; ``.jsonl`` → JSON lines; otherwise
    JSON.

    Args:
        obj (object): Object to dump.
        fn (str | Path): Filename or ``pathlib.Path``.
        fmt ("json" | "jsonl" | "yaml" | "mpk"): If provided, overrides the
            auto-detected format.
        *args: Any of the args supported by ``json``/``yaml``/``msgpack.dump``.
        **kwargs: Any of the kwargs supported by ``json``/``yaml``/``msgpack.dump``.

    """
    fmt = fmt or _identify_format(fn)

    if fmt == "mpk":
        if msgpack is None:
            raise RuntimeError(
                "Loading of message pack files is not possible as msgpack-python is not installed."
            )
        if "default" not in kwargs:
            kwargs["default"] = default
        with zopen(fn, mode="wb") as fp:
            msgpack.dump(obj, fp, *args, **kwargs)  # pylint: disable=E1101
    else:
        with zopen(fn, mode="wt", encoding="utf-8") as fp:
            fp = cast(TextIO, fp)

            if fmt == "yaml":
                if YAML is None:
                    raise RuntimeError("Loading of YAML files requires ruamel.yaml.")
                _YAML.dump(obj, fp, *args, **kwargs)
            elif fmt in {"json", "jsonl"}:
                if "cls" not in kwargs:
                    kwargs["cls"] = MontyEncoder
                if fmt == "jsonl":
                    write = fp.write
                    for jobj in obj:  # type: ignore[var-annotated,attr-defined]
                        # Two writes avoid creating an intermediate ``str + "\n"``
                        # for every record.
                        write(json.dumps(jobj, *args, **kwargs))
                        write("\n")
                else:
                    fp.write(json.dumps(obj, *args, **kwargs))
            else:
                raise TypeError(f"Invalid format: {fmt}")
