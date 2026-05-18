"""This module implements serialization support for common formats such as json
and yaml.
"""

from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING, Literal, TextIO, cast

from ruamel.yaml import YAML

from monty.io import zopen
from monty.json import MontyDecoder, MontyEncoder
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
    """Loads json/yaml/msgpack directly from a filename instead of a
    File-like object. File may also be a BZ2 (".BZ2") or GZIP (".GZ", ".Z")
    compressed file.
    For YAML, ruamel.yaml must be installed. The file type is automatically
    detected from the file extension (case insensitive).
    YAML is assumed if the filename contains ".yaml" or ".yml".
    Msgpack is assumed if the filename contains ".mpk".
    JSON lines is assumed if the filename contains "jsonl".
    JSON is otherwise assumed.

    Args:
        fn (str/Path): filename or pathlib.Path.
        *args: Any of the args supported by json/yaml.load.
        fmt ("json" | "jsonl" | "yaml" | "mpk"): If specified, the fmt
            specified would be used instead of autodetection from filename.
        **kwargs: Any of the kwargs supported by json/yaml.load.

    Returns:
        object: Result of json/yaml/msgpack.load.
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
                return _YAML.load(fp, *args, **kwargs)

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
    """Dump to a json/yaml directly by filename instead of a
    File-like object. File may also be a BZ2 (".BZ2") or GZIP (".GZ", ".Z")
    compressed file.
    For YAML, ruamel.yaml must be installed. The file type is automatically
    detected from the file extension (case insensitive). YAML is assumed if the
    filename contains ".yaml" or ".yml".
    Msgpack is assumed if the filename contains ".mpk".
    JSON lines is assumed if the filename contains "jsonl".
    JSON is otherwise assumed.

    Args:
        obj (object): Object to dump.
        fn (str/Path): filename or pathlib.Path.
        fmt ("json" | "jsonl" | "yaml" | "mpk"): If specified, the fmt specified would
            be used instead of autodetection from filename.
        *args: Any of the args supported by json/yaml.dump.
        **kwargs: Any of the kwargs supported by json/yaml.dump.

    Returns:
        (object) Result of json.load.
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
