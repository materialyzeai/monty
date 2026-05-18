"""JSON serialization and deserialization utilities."""

from __future__ import annotations

import dataclasses
import datetime
import functools
import json
import os
import pathlib
import pickle
import sys
import traceback
import types
from collections import OrderedDict, defaultdict
from enum import Enum
from hashlib import sha1
from importlib import import_module
from inspect import getfullargspec, isclass
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import numpy as np

if TYPE_CHECKING:
    from typing import Any

try:
    import bson
    from bson import json_util

    _BSON_JSON_OPTIONS = json_util.JSONOptions(tz_aware=True)  # type: ignore[no-untyped-call]
except ImportError:
    bson = None  # type: ignore[assignment]
    json_util = None  # type: ignore[assignment]
    _BSON_JSON_OPTIONS = None  # type: ignore[assignment]

__version__ = "3.0.0"


# ---------------------------------------------------------------------------
# Cached helpers (perf hot paths)
# ---------------------------------------------------------------------------


@functools.cache
def _init_spec(cls: type):
    """Cache ``getfullargspec(cls.__init__)``.

    Typically the dominant cost of ``MSONable.as_dict``.
    """
    return getfullargspec(cls.__init__)  # type: ignore[misc]


@functools.cache
def _module_version(modname: str) -> str | None:
    """Cache the ``__version__`` lookup for a top-level module name.

    ``MSONable.as_dict`` and ``MontyEncoder.default`` both call this per
    encoded object; the result is determined entirely by the module name.
    """
    try:
        return str(import_module(modname).__version__)
    except (AttributeError, ImportError):
        return None


@functools.cache
def _resolve_class(modname: str, classname: str) -> type | None:
    """Cache ``__import__`` + ``getattr`` of a class by ``(module, name)``.

    ``ImportError`` is intentionally *not* swallowed — callers (notably the
    redirect path) rely on it surfacing when a redirect points at a missing
    module.
    """
    mod = __import__(modname, globals(), locals(), [classname], 0)
    return getattr(mod, classname, None)


_TYPE_STR_CACHE: dict[tuple[type, tuple[str, ...]], bool] = {}


def _type_str_match(tp: type, type_strs: tuple[str, ...]) -> bool:
    """Return whether ``tp.mro()`` contains any qualified name in ``type_strs``.

    Result is cached per ``(type, type_strs)`` pair — most callers query the
    same handful of strings against the same type repeatedly (``torch.Tensor``,
    ``pandas.DataFrame``, etc.).
    """
    key = (tp, type_strs)
    cached = _TYPE_STR_CACHE.get(key)
    if cached is not None:
        return cached
    result = any(
        f"{o.__module__}.{o.__qualname__}" == ts for o in tp.mro() for ts in type_strs
    )
    _TYPE_STR_CACHE[key] = result
    return result


class _LazyRedirect:
    """Class-level descriptor that loads ``~/.monty.yaml`` lazily on first access.

    Avoids paying the ``ruamel.yaml`` import and filesystem stat cost on every
    ``import monty.json`` (which is on the import path of pymatgen, matgl,
    matcalc, etc.).
    """

    def __init__(self) -> None:
        self._value: dict | None = None

    def __get__(self, instance, owner) -> dict:
        if self._value is None:
            self._value = _load_redirect(
                os.path.join(os.path.expanduser("~"), ".monty.yaml")
            )
        return self._value

    def __set__(self, instance, value) -> None:
        # Allow overriding (e.g. for tests).
        self._value = value


def _load_redirect(redirect_file) -> dict:
    # Defer the heavy ruamel.yaml import until we actually need to parse a
    # redirect file. This avoids pulling YAML in on every ``import monty.json``.
    try:
        f = open(redirect_file, encoding="utf-8")
    except OSError:
        return {}

    with f:
        from ruamel.yaml import YAML  # local import — cold path

        d = YAML().load(f)

    # Convert the full paths to module/class
    redirect_dict: dict = defaultdict(dict)
    for old_path, new_path in d.items():
        old_class = old_path.split(".")[-1]
        old_module = ".".join(old_path.split(".")[:-1])

        new_class = new_path.split(".")[-1]
        new_module = ".".join(new_path.split(".")[:-1])

        redirect_dict[old_module][old_class] = {
            "@module": new_module,
            "@class": new_class,
        }

    return dict(redirect_dict)


def _check_type(obj: object, type_str: tuple[str, ...] | str) -> bool:
    """Import-free alternative to ``isinstance`` based on qualified type names.

    Checks whether ``obj`` is an instance of the type identified by
    ``type_str`` (a fully qualified name like ``"torch.Tensor"``), which
    avoids importing the type explicitly. Subclasses are matched, mirroring
    ``isinstance`` semantics.

    Note for future developers: the ``type_str`` for a given object is not
    always obvious. Use ``type(obj).mro()`` to enumerate the qualified names
    that an object will match (in order of generality, with
    ``"builtins.object"`` last).
    """
    # This function is intended as an alternative of "isinstance",
    # therefore wouldn't check class
    if isclass(obj):
        return False

    type_strs = type_str if isinstance(type_str, tuple) else (type_str,)
    return _type_str_match(type(obj), type_strs)


def _recursive_as_dict(obj):
    """Recursive helper for ``MSONable.as_dict``.

    Kept at module level so it is not re-created on every ``as_dict`` invocation.
    """
    if isinstance(obj, (list, tuple)):
        return [_recursive_as_dict(it) for it in obj]
    if isinstance(obj, dict):
        return {kk: _recursive_as_dict(vv) for kk, vv in obj.items()}
    if hasattr(obj, "as_dict"):
        return obj.as_dict()
    if dataclasses.is_dataclass(obj):
        d = dataclasses.asdict(obj)
        d.update(
            {
                "@module": obj.__class__.__module__,
                "@class": obj.__class__.__name__,
            }
        )
        return d
    return obj


# ---------------------------------------------------------------------------
# Type handler plugin registry
# ---------------------------------------------------------------------------


class TypeHandler:
    """Plugin protocol for encoding and decoding a single external type.

    Subclasses set ``module`` and ``class_name`` class attributes (used for
    decoder dispatch and for the ``@module``/``@class`` keys of the emitted
    JSON dict) and implement :meth:`matches`, :meth:`encode`, and
    :meth:`decode`. ``class_name`` may be a tuple of strings when one
    handler covers more than one ``@class`` value (e.g. pandas DataFrame
    + Series); ``encode`` is then responsible for picking the right
    ``@class`` per object.

    Register custom handlers via :func:`register`. Built-in handlers for
    ``datetime``, ``uuid``, ``pathlib.Path``, ``numpy.ndarray``,
    ``torch.Tensor``, ``pandas.DataFrame``/``Series``, ``pint.Quantity``,
    and ``bson.ObjectId`` are registered at import time and are always
    checked first; user handlers run after.

    Examples:
        >>> class MyHandler(TypeHandler):
        ...     module = "mypkg"
        ...     class_name = "MyType"
        ...
        ...     def matches(self, obj):
        ...         return isinstance(obj, MyType)
        ...
        ...     def encode(self, obj):
        ...         return {"@module": "mypkg", "@class": "MyType", "value": obj.value}
        ...
        ...     def decode(self, d):
        ...         return MyType(d["value"])
        ...
        >>> register(MyHandler())
    """

    module: str = ""
    class_name: str | tuple[str, ...] = ""

    def matches(self, obj: Any) -> bool:
        """Return True if this handler should encode ``obj``."""
        raise NotImplementedError

    def encode(self, obj: Any) -> Any:
        """Return the JSON-compatible representation of ``obj``.

        Typically a dict carrying ``@module``, ``@class``, and type-specific
        fields. May also return a JSON-native primitive (int/float/bool/
        str/None) for types that collapse to a scalar on the wire (e.g.
        numpy scalars). Primitives are not reconstructed by the decoder's
        ``@module``/``@class`` dispatch — the standard JSON parser handles
        them on the way back.
        """
        raise NotImplementedError

    def decode(self, d: dict) -> Any:
        """Reconstruct the live object from its dict representation."""
        raise NotImplementedError


# Built-in handlers, checked first to preserve PR #791's hot-path order.
_BUILTIN_HANDLERS: list[TypeHandler] = []

# User-registered handlers, checked after the built-ins.
_USER_HANDLERS: list[TypeHandler] = []

# (module, class_name) -> handler for O(1) decoder dispatch.
_DECODER_HANDLERS: dict[tuple[str, str], TypeHandler] = {}

# Pre-bound ``(matches, encode)`` callable pairs for the encoder hot path.
# Iterating bound methods directly avoids the attribute-lookup cost of
# ``h.matches(obj)`` / ``h.encode(obj)`` per dispatch and recovers most of
# the perf delta vs. the legacy inline if/elif chain. Rebuilt whenever the
# user handler list changes; built-in pairs come first.
_ENCODER_DISPATCH: tuple[tuple[Any, Any], ...] = ()


def _rebuild_encoder_dispatch() -> None:
    global _ENCODER_DISPATCH  # noqa: PLW0603 — module-level dispatch tuple
    _ENCODER_DISPATCH = tuple(
        (h.matches, h.encode) for h in (*_BUILTIN_HANDLERS, *_USER_HANDLERS)
    )


def _handler_keys(handler: TypeHandler) -> list[tuple[str, str]]:
    """Return one ``(module, class_name)`` decoder key per name a handler claims."""
    names = handler.class_name
    if isinstance(names, str):
        names = (names,)
    return [(handler.module, n) for n in names]


def register(handler: TypeHandler) -> None:
    """Register a custom :class:`TypeHandler` with the JSON registry.

    The handler's ``encode(obj)`` is invoked when ``MontyEncoder`` encounters
    an instance for which ``handler.matches(obj)`` returns True. The
    ``decode(d)`` method is dispatched on the ``@module``/``@class`` keys
    of the incoming dict.

    A handler may claim multiple ``@class`` names by setting ``class_name``
    to a tuple — every entry is registered as its own decoder key.
    Re-registering for any of those keys replaces the previous registration.
    """
    keys = _handler_keys(handler)
    for key in keys:
        existing = _DECODER_HANDLERS.get(key)
        if existing is not None and existing in _USER_HANDLERS:
            _USER_HANDLERS.remove(existing)
    if handler not in _USER_HANDLERS:
        _USER_HANDLERS.append(handler)
    for key in keys:
        _DECODER_HANDLERS[key] = handler
    _rebuild_encoder_dispatch()


def unregister(handler: TypeHandler) -> None:
    """Remove a previously-registered user handler."""
    if handler in _USER_HANDLERS:
        _USER_HANDLERS.remove(handler)
    for key in _handler_keys(handler):
        if _DECODER_HANDLERS.get(key) is handler:
            del _DECODER_HANDLERS[key]
    _rebuild_encoder_dispatch()


def _register_builtin(handler: TypeHandler) -> None:
    _BUILTIN_HANDLERS.append(handler)
    for key in _handler_keys(handler):
        _DECODER_HANDLERS[key] = handler
    _rebuild_encoder_dispatch()


# ---------------------------------------------------------------------------
# Built-in type handlers
# ---------------------------------------------------------------------------


class DatetimeHandler(TypeHandler):
    """Encode and decode :class:`datetime.datetime` instances."""

    module = "datetime"
    class_name = "datetime"

    def matches(self, obj: Any) -> bool:
        return isinstance(obj, datetime.datetime)

    def encode(self, obj: Any) -> dict:
        return {
            "@module": "datetime",
            "@class": "datetime",
            "string": str(obj),
        }

    def decode(self, d: dict) -> Any:
        s = d["string"]
        try:
            # ``fromisoformat`` is ~5x faster than ``strptime`` and handles
            # fractional seconds and ``+HH:MM`` timezone suffixes natively.
            return datetime.datetime.fromisoformat(s)
        except ValueError:
            # Fall back to the legacy parser for non-ISO inputs.
            s = s.split("+")[0]
            try:
                return datetime.datetime.strptime(s, "%Y-%m-%d %H:%M:%S.%f")
            except ValueError:
                return datetime.datetime.strptime(s, "%Y-%m-%d %H:%M:%S")


class UUIDHandler(TypeHandler):
    """Encode and decode :class:`uuid.UUID` instances."""

    module = "uuid"
    class_name = "UUID"

    def matches(self, obj: Any) -> bool:
        return isinstance(obj, UUID)

    def encode(self, obj: Any) -> dict:
        return {"@module": "uuid", "@class": "UUID", "string": str(obj)}

    def decode(self, d: dict) -> Any:
        return UUID(d["string"])


class PathHandler(TypeHandler):
    """Encode and decode :class:`pathlib.Path` instances."""

    module = "pathlib"
    class_name = "Path"

    def matches(self, obj: Any) -> bool:
        return isinstance(obj, Path)

    def encode(self, obj: Any) -> dict:
        return {"@module": "pathlib", "@class": "Path", "string": str(obj)}

    def decode(self, d: dict) -> Any:
        return Path(d["string"])


class TorchTensorHandler(TypeHandler):
    """Encode and decode ``torch.Tensor`` (lazy ``torch`` import)."""

    module = "torch"
    class_name = "Tensor"

    def matches(self, obj: Any) -> bool:
        # ``sys.modules`` gate skips the (cached but non-free) MRO scan when
        # torch hasn't been imported yet — see PR #791.
        return "torch" in sys.modules and _check_type(obj, "torch.Tensor")

    def encode(self, obj: Any) -> dict:
        d: dict[str, Any] = {
            "@module": "torch",
            "@class": "Tensor",
            "dtype": obj.type(),
            "size": list(obj.size()),
        }
        if "Complex" in obj.type():
            d["data"] = [obj.real.tolist(), obj.imag.tolist()]
        else:
            d["data"] = obj.numpy().tolist()
        return d

    def decode(self, d: dict) -> Any:
        import torch  # heavy import deferred until first decode

        if "Complex" in d["dtype"]:
            if "size" in d and d["data"] == [[], []]:
                return torch.empty(d["size"]).type(d["dtype"])
            return torch.tensor(
                [
                    np.array(r) + np.array(i) * 1j
                    for r, i in zip(*d["data"], strict=True)
                ],
            ).type(d["dtype"])
        if "size" in d and d["data"] == []:
            return torch.empty(d["size"]).type(d["dtype"])
        return torch.tensor(d["data"]).type(d["dtype"])


class NumpyHandler(TypeHandler):
    """Encode and decode numpy arrays and scalars.

    ``np.ndarray`` round-trips through the ``@module``/``@class`` envelope;
    ``np.generic`` scalars collapse to native Python primitives on the
    wire (decoded by stdlib ``json``).
    """

    module = "numpy"
    class_name = "array"

    def matches(self, obj: Any) -> bool:
        # Match both ndarray and scalar in one branch so the order of
        # operations between them lives entirely inside ``encode``.
        return isinstance(obj, (np.ndarray, np.generic))

    def encode(self, obj: Any) -> Any:
        # Numpy scalars collapse to a JSON-native primitive — no envelope.
        if isinstance(obj, np.generic):
            return obj.item()
        if str(obj.dtype).startswith("complex"):
            return {
                "@module": "numpy",
                "@class": "array",
                "dtype": str(obj.dtype),
                "data": [obj.real.tolist(), obj.imag.tolist()],
            }
        return {
            "@module": "numpy",
            "@class": "array",
            "dtype": str(obj.dtype),
            "data": obj.tolist(),
        }

    def decode(self, d: dict) -> Any:
        if d["dtype"].startswith("complex"):
            return np.array(
                [
                    np.array(r) + np.array(i) * 1j
                    for r, i in zip(*d["data"], strict=True)
                ],
                dtype=d["dtype"],
            )
        return np.array(d["data"], dtype=d["dtype"])


class PandasHandler(TypeHandler):
    """Encode and decode ``pandas.DataFrame`` / ``Series`` (lazy ``pandas`` import).

    A single handler covers both because they share the same encoding shape
    (``to_json`` payload). The emitted ``@class`` is ``"DataFrame"`` or
    ``"Series"`` depending on the concrete object so the decoder can pick
    the right pandas constructor.
    """

    module = "pandas"
    class_name = ("DataFrame", "Series")

    # Qualified names matched by ``_check_type``. DataFrame's are listed
    # first so ``encode`` can discriminate without re-walking the MRO.
    _DF_QUALNAMES = ("pandas.core.frame.DataFrame", "pandas.DataFrame")
    _SERIES_QUALNAMES = ("pandas.core.series.Series", "pandas.Series")

    def matches(self, obj: Any) -> bool:
        return "pandas" in sys.modules and _check_type(
            obj, self._DF_QUALNAMES + self._SERIES_QUALNAMES
        )

    def encode(self, obj: Any) -> dict:
        cls_name = "DataFrame" if _check_type(obj, self._DF_QUALNAMES) else "Series"
        return {
            "@module": "pandas",
            "@class": cls_name,
            "data": obj.to_json(default_handler=MontyEncoder().encode),
        }

    def decode(self, d: dict) -> Any:
        import pandas as pd

        pd_cls = pd.DataFrame if d["@class"] == "DataFrame" else pd.Series
        return pd_cls(MontyDecoder().decode(d["data"]))


class PintQuantityHandler(TypeHandler):
    """Encode and decode ``pint.Quantity`` (lazy ``pint`` import)."""

    module = "pint"
    class_name = "Quantity"

    def matches(self, obj: Any) -> bool:
        return "pint" in sys.modules and _check_type(obj, "pint.Quantity")

    def encode(self, obj: Any) -> dict:
        return {
            "@module": "pint",
            "@class": "Quantity",
            "data": str(obj),
            "@version": _module_version("pint"),
        }

    def decode(self, d: dict) -> Any:
        from pint import UnitRegistry

        ureg = UnitRegistry()
        return ureg.Quantity(d["data"])


class BsonObjectIdHandler(TypeHandler):
    """Encode and decode ``bson.objectid.ObjectId`` (requires ``bson``)."""

    module = "bson.objectid"
    class_name = "ObjectId"

    def matches(self, obj: Any) -> bool:
        return bson is not None and isinstance(obj, bson.objectid.ObjectId)

    def encode(self, obj: Any) -> dict:
        return {
            "@module": "bson.objectid",
            "@class": "ObjectId",
            "oid": str(obj),
        }

    def decode(self, d: dict) -> Any:
        return bson.objectid.ObjectId(d["oid"])


# Register built-ins in the order the legacy if/elif chain checked them.
# Ordering is load-bearing for performance (see PR #791): cheap isinstance
# checks first, then ``sys.modules``-gated qualified-name matches.
_register_builtin(DatetimeHandler())
_register_builtin(UUIDHandler())
_register_builtin(PathHandler())
_register_builtin(TorchTensorHandler())
_register_builtin(NumpyHandler())
_register_builtin(PandasHandler())
_register_builtin(PintQuantityHandler())
_register_builtin(BsonObjectIdHandler())


class MSONable:
    """Mix-in base class specifying an API for msonable objects.

    MSON is Monty JSON. Essentially, MSONable objects must implement an
    as_dict method, which must return a json serializable dict and must also
    support no arguments (though optional arguments to finetune the output
    is ok), and a from_dict class method that regenerates the object from
    the dict generated by the as_dict method. The as_dict method should
    contain the "@module" and "@class" keys which will allow the
    MontyEncoder to dynamically deserialize the class. E.g.::

        d["@module"] = self.__class__.__module__
        d["@class"] = self.__class__.__name__

    A default implementation is provided in MSONable, which automatically
    determines if the class already contains self.argname or self._argname
    attributes for every arg. If so, these will be used for serialization in
    the dict format. Similarly, the default from_dict will deserialization
    classes of such form. An example is given below::

        class MSONClass(MSONable):

        def __init__(self, a, b, c, d=1, **kwargs):
            self.a = a
            self.b = b
            self._c = c
            self._d = d
            self.kwargs = kwargs

    For such classes, you merely need to inherit from MSONable and you do not
    need to implement your own as_dict or from_dict protocol.

    New to Monty V2.0.6....
    Classes can be redirected to moved implementations by putting in the old
    fully qualified path and new fully qualified path into .monty.yaml in the
    home folder

    Example:
    old_module.old_class: new_module.new_class

    """

    # Backwards-compatible class attribute. The redirect file is loaded the
    # first time it is accessed via the ``_LazyRedirect`` descriptor.
    REDIRECT = _LazyRedirect()

    def as_dict(self) -> dict:
        """A JSON serializable dict representation of an object."""
        cls = self.__class__
        d: dict[str, Any] = {
            "@module": cls.__module__,
            "@class": cls.__name__,
        }

        parent_module = cls.__module__.partition(".")[0]
        d["@version"] = _module_version(parent_module)

        spec = _init_spec(cls)  # type: ignore[arg-type]

        for c in spec.args + spec.kwonlyargs:
            if c != "self":
                try:
                    a = getattr(self, c)
                except AttributeError:
                    try:
                        a = getattr(self, "_" + c)
                    except AttributeError as exc:
                        raise NotImplementedError(
                            "Unable to automatically determine as_dict "
                            "format from class. MSONAble requires all "
                            "args to be present as either self.argname or "
                            "self._argname, and kwargs to be present under "
                            "a self.kwargs variable to automatically "
                            "determine the dict format. Alternatively, "
                            "you can implement both as_dict and from_dict."
                        ) from exc
                d[c] = _recursive_as_dict(a)
        if hasattr(self, "kwargs"):
            d.update(**self.kwargs)
        if spec.varargs is not None and getattr(self, spec.varargs, None) is not None:
            d.update({spec.varargs: getattr(self, spec.varargs)})
        if hasattr(self, "_kwargs"):
            d.update(**self._kwargs)
        if isinstance(self, Enum):
            d.update({"value": self.value})
        return d

    @classmethod
    def from_dict(cls, d: dict) -> MSONable:
        """Reconstruct an MSONable object from a dict.

        Args:
            d: Dict representation.

        Returns:
            MSONable class.

        """
        # Reuse a single module-level decoder rather than allocating a new
        # ``MontyDecoder`` for every key, which used to dominate this path.
        decoded = {
            k: _SHARED_DECODER.process_decoded(v)
            for k, v in d.items()
            if not k.startswith("@")
        }
        return cls(**decoded)

    def to_json(self) -> str:
        """Returns a json string representation of the MSONable object."""
        return json.dumps(self, cls=MontyEncoder)

    def unsafe_hash(self) -> Any:
        """Return a hash of the current object.

        This uses a generic but low performance method of converting the
        object to a dictionary, flattening any nested keys, and then
        performing a hash on the resulting object.
        """

        def flatten(obj, separator="."):
            # Flattens a dictionary

            flat_dict = {}
            for key, value in obj.items():
                if isinstance(value, dict):
                    flat_dict.update(
                        {
                            separator.join([key, _key]): _value
                            for _key, _value in flatten(value).items()
                        }
                    )
                elif isinstance(value, list):
                    list_dict = {
                        f"{key}{separator}{num}": item for num, item in enumerate(value)
                    }
                    flat_dict.update(flatten(list_dict))
                else:
                    flat_dict[key] = value

            return flat_dict

        ordered_keys = sorted(
            flatten(jsanitize(self.as_dict())).items(), key=lambda x: x[0]
        )
        ordered_keys = [item for item in ordered_keys if "@" not in item[0]]
        # sha1 is used here as a fingerprint, not for cryptographic security.
        return sha1(
            json.dumps(OrderedDict(ordered_keys)).encode("utf-8"),
            usedforsecurity=False,
        )

    @classmethod
    def _validate_monty(cls, __input_value):
        """Pydantic Validator for MSONable pattern."""
        if isinstance(__input_value, cls):
            return __input_value
        if isinstance(__input_value, dict):
            # Do not allow generic exceptions to be raised during deserialization
            # since pydantic may handle them incorrectly.
            try:
                new_obj = MontyDecoder().process_decoded(__input_value)
                if isinstance(new_obj, cls):
                    return new_obj
                return cls(**__input_value)
            except Exception as exc:
                raise ValueError(
                    f"Error while deserializing {cls.__name__} "
                    f"object: {traceback.format_exc()}"
                ) from exc

        raise ValueError(
            f"Must provide {cls.__name__}, the as_dict form, or the proper"
        )

    @classmethod
    def validate_monty_v1(cls, __input_value):
        """Pydantic validator with correct signature for pydantic v1.x."""
        return cls._validate_monty(__input_value)

    @classmethod
    def validate_monty_v2(cls, __input_value, _):
        """Pydantic validator with correct signature for pydantic v2.x."""
        return cls._validate_monty(__input_value)

    @classmethod
    def __get_validators__(cls):
        """Return validators for use in pydantic."""
        yield cls.validate_monty_v1

    @classmethod
    def __get_pydantic_core_schema__(cls, source_type, handler):
        """Pydantic v2 core schema definition."""
        try:
            from pydantic_core import core_schema

        except ImportError as exc:
            raise RuntimeError("Pydantic >= 2.0 is required for validation") from exc

        s = core_schema.with_info_plain_validator_function(cls.validate_monty_v2)

        return core_schema.json_or_python_schema(json_schema=s, python_schema=s)

    @classmethod
    def _generic_json_schema(cls):
        return {
            "type": "object",
            "properties": {
                "@class": {"enum": [cls.__name__], "type": "string"},
                "@module": {"enum": [cls.__module__], "type": "string"},
                "@version": {"type": "string"},
            },
            "required": ["@class", "@module"],
        }

    @classmethod
    def __get_pydantic_json_schema__(cls, core_schema, handler):
        """JSON schema for MSONable pattern."""
        return cls._generic_json_schema()

    @classmethod
    def __modify_schema__(cls, field_schema):
        """JSON schema for MSONable pattern."""
        custom_schema = cls._generic_json_schema()
        field_schema.update(custom_schema)

    def save(
        self,
        json_path: os.PathLike | str,
        mkdir: bool = True,
        json_kwargs: dict | None = None,
        pickle_kwargs: dict | None = None,
        strict: bool = True,
    ) -> None:
        """Serialize the instance to JSON on disk, pickling fields if needed.

        For a fully MSONable class, only ``{save_dir}/class.json`` is written.
        For a partially MSONable class, non-serializable attributes are
        pickled individually into the same directory, keeping the JSON
        portion readable.

        Args:
            json_path: The file to which to save the JSON object. A pickled
                companion file with the same stem but a different extension
                may also be written if the class is not entirely MSONable.
            mkdir: If True, create the target directory (including parents).
            json_kwargs: Keyword arguments forwarded to the JSON serializer.
            pickle_kwargs: Keyword arguments forwarded to ``pickle.dump``.
            strict: If True, refuse to overwrite existing files.

        """
        save(
            self,
            json_path,
            mkdir=mkdir,
            json_kwargs=json_kwargs,
            pickle_kwargs=pickle_kwargs,
            strict=strict,
        )

    @classmethod
    def load(cls, file_path: os.PathLike | str) -> MSONable:
        """Load an instance from a JSON file written by :meth:`save`.

        Args:
            file_path: The JSON file to load from.

        Returns:
            An instance of the class being reloaded.

        """
        d = load2dict(file_path)
        return cls.from_dict(d)


def save(
    obj: Any,
    json_path: os.PathLike | str,
    mkdir: bool = True,
    json_kwargs: dict | None = None,
    pickle_kwargs: dict | None = None,
    strict: bool = True,
) -> None:
    """Serialize an object to JSON on disk, pickling fields if needed.

    For a fully MSONable object, only ``{save_dir}/class.json`` is written.
    For a partially MSONable object, non-serializable attributes are pickled
    individually into the same directory, keeping the JSON portion readable.

    Args:
        obj: The object to save.
        json_path: The file to which to save the JSON object. A pickled
            companion file with the same stem but a different extension may
            also be written if ``obj`` is not entirely MSONable.
        mkdir: If True, create the target directory (including parents).
        json_kwargs: Keyword arguments forwarded to the JSON serializer.
        pickle_kwargs: Keyword arguments forwarded to ``pickle.dump``.
        strict: If True, refuse to overwrite existing files.

    """
    json_path = Path(json_path)
    save_dir = json_path.parent

    json_kwargs = json_kwargs or {}
    pickle_kwargs = pickle_kwargs or {}

    encoded, name_object_map = partial_monty_encode(obj, json_kwargs)

    if mkdir:
        save_dir.mkdir(exist_ok=True, parents=True)

    # Define the pickle path
    pickle_path = save_dir / f"{json_path.stem}.pkl"

    # Check if the files exist and the strict parameter is True
    if strict and json_path.exists():
        raise FileExistsError(f"strict is true and file {json_path} exists")
    if strict and pickle_path.exists():
        raise FileExistsError(f"strict is true and file {pickle_path} exists")

    # Save the json file
    with open(json_path, "w", encoding="utf-8") as outfile:
        outfile.write(encoded)

    # Save the pickle file if we have anything to save from the name_object_map
    if name_object_map is not None:
        with open(pickle_path, "wb") as f:
            pickle.dump(name_object_map, f, **pickle_kwargs)


def load(path: os.PathLike | str) -> MSONable:
    """Load an MSONable object from a JSON file written by :func:`save`.

    Args:
        path: Path to the JSON file to load.

    Returns:
        The reconstructed MSONable instance.

    """
    d = load2dict(path)
    module = d["@module"]
    klass = d["@class"]
    module = import_module(module)
    klass = getattr(module, klass)
    return klass.from_dict(d)


def load2dict(file_path: os.PathLike | str) -> dict:
    """Load a JSON file written by :func:`save` into a dictionary.

    Args:
        file_path (str): Path to the JSON file.

    Returns:
        dict: The dictionary representation of the JSON file.

    """
    json_path = Path(file_path)
    save_dir = json_path.parent
    pickle_path = save_dir / f"{json_path.stem}.pkl"

    with open(json_path, encoding="utf-8") as infile:
        d = json.loads(infile.read())

    if pickle_path.exists():
        with open(pickle_path, "rb") as pkl_file:
            name_object_map = pickle.load(pkl_file)
        d = _recursive_name_object_map_replacement(d, name_object_map)
    return d


def _recursive_name_object_map_replacement(d, name_object_map):
    if isinstance(d, dict):
        if "@object_reference" in d:
            name = d["@object_reference"]
            return name_object_map.pop(name)
        return {
            k: _recursive_name_object_map_replacement(v, name_object_map)
            for k, v in d.items()
        }
    if isinstance(d, list):
        return [_recursive_name_object_map_replacement(x, name_object_map) for x in d]
    return d


class MontyEncoder(json.JSONEncoder):
    """JSON encoder that supports the MSONable API.

    Adds support for NumPy arrays, ``datetime`` objects, and bson
    ``ObjectId`` (when ``bson`` is installed).

    Examples:
        >>> import json
        >>> json.dumps(object, cls=MontyEncoder)

    """

    def __init__(
        self, *args, allow_unserializable_objects: bool = False, **kwargs
    ) -> None:
        super().__init__(*args, **kwargs)
        self._allow_unserializable_objects = allow_unserializable_objects
        self._name_object_map: dict[str, Any] = {}
        self._index: int = 0

    def _update_name_object_map(self, o):
        name = f"{self._index:012}-{uuid4()!s}"
        self._index += 1
        self._name_object_map[name] = o
        return {"@object_reference": name}

    def default(self, o) -> Any:
        """Encode an object for JSON serialization.

        Type-specific handling is delegated to :class:`TypeHandler` plugins
        registered via :func:`register` (built-in handlers cover datetime,
        uuid, pathlib, numpy, torch, pandas, pint, bson). The fallback
        chain dispatches on pydantic / non-MSONable dataclass / MSONable
        ``as_dict`` / ``Enum`` in that order and injects ``@module``,
        ``@class``, and ``@version`` keys when they are missing.

        Args:
            o: Python object.

        Returns:
            A JSON-compatible value — typically a dict with ``@module`` and
            ``@class`` keys, but may also be a JSON-native primitive (e.g.
            for numpy scalars).
        """
        # Plugin dispatch (datetime, uuid, pathlib, numpy, torch, pandas,
        # pint, bson + any user-registered handlers). The tuple holds
        # pre-bound ``(matches, encode)`` pairs to avoid per-iteration
        # attribute lookups.
        for matches, encode in _ENCODER_DISPATCH:
            if matches(o):
                return encode(o)

        if callable(o) and not isinstance(o, MSONable):
            try:
                return _serialize_callable(o)
            except AttributeError as e:
                # Some callables may not have instance __name__
                if self._allow_unserializable_objects:
                    return self._update_name_object_map(o)
                raise AttributeError(e) from e

        try:
            if "pydantic" in sys.modules and _check_type(o, "pydantic.main.BaseModel"):
                d = o.model_dump()
            elif (
                dataclasses is not None
                and (not issubclass(o.__class__, MSONable))
                and dataclasses.is_dataclass(o)
            ):
                # This handles dataclasses that are not subclasses of MSONAble.
                d = dataclasses.asdict(o)  # type: ignore[call-overload, arg-type]
            elif hasattr(o, "as_dict"):
                d = o.as_dict()
            elif isinstance(o, Enum):
                d = {"value": o.value}
            elif self._allow_unserializable_objects:
                # Last resort logic. We keep track of some name of the object
                # as a reference, and instead of the object, store that
                # name, which of course is json-serializable
                d = self._update_name_object_map(o)
            else:
                raise TypeError(
                    f"Object of type {o.__class__.__name__} is not JSON serializable"
                )

            if "@module" not in d:
                d["@module"] = str(o.__class__.__module__)
            if "@class" not in d:
                d["@class"] = str(o.__class__.__name__)
            if "@version" not in d:
                d["@version"] = _module_version(
                    o.__class__.__module__.partition(".")[0]
                )
            return d
        except AttributeError:
            return json.JSONEncoder.default(self, o)


class MontyDecoder(json.JSONDecoder):
    """JSON decoder that supports the MSONable API.

    Inspects each decoded dict for ``@module``/``@class`` keys and rebuilds
    the corresponding object when possible, falling back to the raw dict
    otherwise. Nested lists and dicts of MSONable objects decode correctly.

    Examples:
        >>> import json
        >>> json.loads(json_string, cls=MontyDecoder)

    """

    def process_decoded(self, d: Any) -> Any:
        """Recursively decode dicts and lists containing MSONable objects."""
        if isinstance(d, dict):
            modname: str | None
            classname: str | None
            if "@module" in d and "@class" in d:
                modname = d["@module"]
                classname = d["@class"]
                if cls_redirect := MSONable.REDIRECT.get(modname, {}).get(classname):
                    classname = cls_redirect["@class"]
                    modname = cls_redirect["@module"]

            elif "@module" in d and "@callable" in d:
                modname = d["@module"]
                objname = d["@callable"]
                classname = None
                if d.get("@bound", None) is not None:
                    # if the function is bound to an instance or class, first
                    # deserialize the bound object and then remove the object name
                    # from the function name.
                    obj = self.process_decoded(d["@bound"])
                    objname = objname.split(".")[1:]
                else:
                    # if the function is not bound to an object, import the
                    # function from the module name
                    obj = __import__(modname, globals(), locals(), [objname], 0)
                    objname = objname.split(".")
                try:
                    # the function could be nested. e.g., MyClass.NestedClass.function
                    # so iteratively access the nesting
                    for attr in objname:
                        obj = getattr(obj, attr)

                    return obj

                except AttributeError:
                    pass
            else:
                modname = None
                classname = None

            if classname and modname:
                # Plugin dispatch: O(1) lookup keyed on ``(@module, @class)``.
                # Covers datetime, uuid, pathlib, torch, numpy, pandas, pint,
                # bson, and any user-registered handlers. ``modname`` is only
                # ever ``None`` when ``classname`` is too (see the branches
                # above); the joint guard keeps mypy happy.
                handler = _DECODER_HANDLERS.get((modname, classname))
                if handler is not None:
                    try:
                        return handler.decode(d)
                    except ImportError:
                        # Optional decoder dependency missing (e.g. torch).
                        # Fall through to the generic resolver / raw dict.
                        pass
                else:
                    # Generic class resolution for MSONable / Enum / pydantic /
                    # non-MSONable dataclass classes.
                    cls_ = _resolve_class(modname, classname)
                    if cls_ is not None:
                        data = {k: v for k, v in d.items() if not k.startswith("@")}
                        if hasattr(cls_, "from_dict"):
                            return cls_.from_dict(data)
                        if issubclass(cls_, Enum):
                            return cls_(d["value"])

                        if "pydantic" in sys.modules:
                            import pydantic

                            if issubclass(cls_, pydantic.BaseModel):
                                d = {
                                    k: self.process_decoded(v) for k, v in data.items()
                                }
                                return cls_(**d)

                        if (
                            not issubclass(cls_, MSONable)
                        ) and dataclasses.is_dataclass(cls_):
                            d = {k: self.process_decoded(v) for k, v in data.items()}
                            return cls_(**d)  # type: ignore[operator]

            return {
                self.process_decoded(k): self.process_decoded(v) for k, v in d.items()
            }

        if isinstance(d, list):
            return [self.process_decoded(x) for x in d]

        return d

    def decode(self, s: str) -> Any:  # type: ignore[override]
        """Override decode from JSONDecoder.

        Args:
            s: JSON string.

        Returns:
            Decoded object.

        """
        if bson is not None:
            # ``JSONOptions`` is moved to module scope so we do not allocate
            # a fresh options object on every decode call.
            d = json_util.loads(s, json_options=_BSON_JSON_OPTIONS)
        else:
            d = json.loads(s)
        return self.process_decoded(d)


# Module-level decoder reused by ``MSONable.from_dict`` so we avoid the
# allocation cost of constructing a fresh decoder on every key.
_SHARED_DECODER = MontyDecoder()


class MSONError(Exception):
    """Exception class for serialization errors."""


def jsanitize(
    obj: Any,
    strict: bool = False,
    allow_bson: bool = False,
    enum_values: bool = False,
    recursive_msonable: bool = False,
) -> Any:
    """Recursively sanitize a JSON-like object for serialization.

    Walks lists/dicts (nested or otherwise), converts non-string dict keys to
    strings, and recursively encodes objects via Monty's ``as_dict`` protocol.

    Args:
        obj: input json-like object.
        strict (bool): This parameter sets the behavior when jsanitize
            encounters an object it does not understand. If strict is True,
            jsanitize will try to get the as_dict() attribute of the object. If
            no such attribute is found, an attribute error will be thrown. If
            strict is False, jsanitize will simply call str(object) to convert
            the object to a string representation.  If "skip" is provided,
            jsanitize will skip and return the original object without modification.
        allow_bson (bool): This parameter sets the behavior when jsanitize
            encounters a bson supported type such as objectid and datetime. If
            True, such bson types will be ignored, allowing for proper
            insertion into MongoDB databases.
        enum_values (bool): Convert Enums to their values.
        recursive_msonable (bool): If True, uses .as_dict() for MSONables regardless
            of the value of strict.

    Returns:
        Sanitized dict that can be json serialized.

    """
    if isinstance(obj, Enum):
        if enum_values:
            return obj.value
        if hasattr(obj, "as_dict"):
            return obj.as_dict()
        return MontyEncoder().default(obj)

    if allow_bson and (
        isinstance(obj, (datetime.datetime, bytes))
        or (bson is not None and isinstance(obj, bson.objectid.ObjectId))
    ):
        return obj

    if isinstance(obj, (list, tuple)):
        return [
            jsanitize(
                i,
                strict=strict,
                allow_bson=allow_bson,
                enum_values=enum_values,
                recursive_msonable=recursive_msonable,
            )
            for i in obj
        ]

    if isinstance(obj, np.ndarray):
        try:
            return [
                jsanitize(
                    i,
                    strict=strict,
                    allow_bson=allow_bson,
                    enum_values=enum_values,
                    recursive_msonable=recursive_msonable,
                )
                for i in obj.tolist()
            ]
        except TypeError:
            return obj.tolist()

    if isinstance(obj, np.generic):
        return obj.item()

    # Fast path: skip the pandas type-check entirely if pandas isn't loaded.
    if "pandas" in sys.modules and _check_type(
        obj,
        (
            "pandas.core.series.Series",
            "pandas.Series",
            "pandas.core.frame.DataFrame",
            "pandas.DataFrame",
            "pandas.core.base.PandasObject",
        ),
    ):
        return obj.to_dict()

    if isinstance(obj, dict):
        return {
            str(k): jsanitize(
                v,
                strict=strict,
                allow_bson=allow_bson,
                enum_values=enum_values,
                recursive_msonable=recursive_msonable,
            )
            for k, v in obj.items()
        }

    if isinstance(obj, (int, float)):
        return obj

    if obj is None:
        return None

    if isinstance(obj, (pathlib.Path, datetime.datetime)):
        return str(obj)

    if callable(obj) and not isinstance(obj, MSONable):
        try:
            return _serialize_callable(obj)
        except TypeError:
            pass

    if recursive_msonable:
        try:
            return jsanitize(
                obj.as_dict(),
                strict=strict,
                allow_bson=allow_bson,
                enum_values=enum_values,
                recursive_msonable=recursive_msonable,
            )
        except AttributeError:
            pass

    if strict is False:
        return str(obj)

    if isinstance(obj, str):
        return obj

    if "pydantic" in sys.modules and _check_type(obj, "pydantic.main.BaseModel"):
        return jsanitize(
            MontyEncoder().default(obj),
            strict=strict,
            allow_bson=allow_bson,
            enum_values=enum_values,
            recursive_msonable=recursive_msonable,
        )

    try:
        return jsanitize(
            obj.as_dict(),
            strict=strict,
            allow_bson=allow_bson,
            enum_values=enum_values,
            recursive_msonable=recursive_msonable,
        )
    except Exception:
        if strict == "skip":
            return obj
        raise


def _serialize_callable(o):
    if isinstance(o, types.BuiltinFunctionType):
        # don't care about what builtin functions (sum, open, etc) are bound to
        bound = None
    else:
        # bound methods (i.e., instance methods) have a __self__ attribute
        # that points to the class/module/instance
        bound = getattr(o, "__self__", None)

    # we are only able to serialize bound methods if the object the method is
    # bound to is itself serializable
    if bound is not None:
        try:
            bound = MontyEncoder().default(bound)
        except TypeError as exc:
            raise TypeError(
                "Only bound methods of classes or MSONable instances are supported."
            ) from exc

    return {
        "@module": o.__module__,
        "@callable": getattr(o, "__qualname__", o.__name__),
        "@bound": bound,
    }


def _get_partial_json(obj, json_kwargs):
    """Return the JSON representation of an object with unserializable parts substituted.

    Unserializable components are replaced with hash references that
    :func:`partial_monty_encode` can map back to pickled companions.
    """
    json_kwargs = json_kwargs or {}
    encoder = MontyEncoder(allow_unserializable_objects=True, **json_kwargs)
    encoded = encoder.encode(obj)
    return encoder, encoded


def partial_monty_encode(
    obj: object, json_kwargs: dict | None = None
) -> tuple[str, dict | None]:
    """Encode an object that may contain unhashable parts.

    Args:
        obj: The object to encode.
        json_kwargs: Keyword arguments forwarded to the JSON serializer.

    Returns:
        A ``(json_string, name_object_map)`` pair. The map is ``None`` when
        no unserializable parts were encountered — previously an empty dict
        was returned, which caused ``save()`` to always write an empty
        ``.pkl`` companion file.

    """
    encoder, encoded = _get_partial_json(
        obj=obj,
        json_kwargs=json_kwargs,
    )
    name_object_map = encoder._name_object_map
    return encoded, (name_object_map or None)
