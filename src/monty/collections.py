"""Useful collection classes:
- tree: A recursive `defaultdict` for creating nested dictionaries
    with default values.
- ControlledDict: A base dict class with configurable mutability.
- frozendict: An immutable dictionary.
- Namespace: A dict doesn't allow changing values, but could
    add new keys,
- AttrDict: A dict whose values could be access as `dct.key`.
- FrozenAttrDict: An immutable version of `AttrDict`.
- MongoDict: A dict-like object whose values are nested dicts
    could be accessed as attributes.
"""

from __future__ import annotations

import collections
import warnings
from abc import ABC
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable
    from typing import Any


# Cache the set of names exposed by ``dict`` once, so AttrDict.__setitem__
# does not have to call ``dir(dict)`` (which builds a fresh ~50-entry list)
# on every assignment.
_DICT_METHOD_NAMES: frozenset[str] = frozenset(dir(dict))


def tree() -> collections.defaultdict:
    """A tree object, which is effectively a recursive defaultdict that
    adds tree as members.

    Usage:
        x = tree()
        x["a"]["b"]["c"] = 1

    Returns:
        A tree.
    """
    return collections.defaultdict(tree)


class ControlledDict(dict, ABC):
    """A base dictionary class with configurable mutability.

    Subclasses ``dict`` directly (rather than ``collections.UserDict``) so the
    common read paths run at C speed; mutation methods are overridden in pure
    Python to enforce the ``_allow_*`` flags. ``dict.__init__`` bypasses
    ``__setitem__`` entirely, so initialization is unaffected by the flags.

    Attributes:
        _allow_add (bool): Whether new keys can be added.
        _allow_del (bool): Whether existing keys can be deleted.
        _allow_update (bool): Whether existing keys can be updated.

    Configurable Operations:
        This class allows controlling the following dict operations (refer to
        https://docs.python.org/3.13/library/stdtypes.html#mapping-types-dict for details):

        - Adding or updating items:
            - setter method: `__setitem__`
            - `setdefault`
            - `update`

        - Deleting items:
            - `del dict[key]`
            - `pop(key)`
            - `popitem`
            - `clear()`
    """

    _allow_add: bool = True
    _allow_del: bool = True
    _allow_update: bool = True

    # Override add/update operations
    def __setitem__(self, key, value) -> None:
        """Forbid adding or updating keys based on _allow_add and _allow_update."""
        if key not in self and not self._allow_add:
            raise TypeError(f"Cannot add new key {key!r}, because add is disabled.")
        if key in self and not self._allow_update:
            raise TypeError(f"Cannot update key {key!r}, because update is disabled.")

        dict.__setitem__(self, key, value)

    def update(self, *args, **kwargs) -> None:
        """Forbid adding or updating keys based on _allow_add and _allow_update."""
        # Materialize once so iterators are not consumed twice between
        # validation and the actual update.
        updates = dict(*args, **kwargs)
        if not (self._allow_add and self._allow_update):
            for key in updates:
                if key not in self and not self._allow_add:
                    raise TypeError(
                        f"Cannot add new key {key!r} using update, because add is disabled."
                    )
                if key in self and not self._allow_update:
                    raise TypeError(
                        f"Cannot update key {key!r} using update, because update is disabled."
                    )

        dict.update(self, updates)

    def setdefault(self, key, default=None) -> Any:
        """Forbid adding or updating keys based on _allow_add and _allow_update.

        Note: if not _allow_update, this method would NOT check whether the
            new default value is the same as current value for efficiency.
        """
        if key not in self:
            if not self._allow_add:
                raise TypeError(
                    f"Cannot add new key using setdefault: {key!r}, because add is disabled."
                )
        elif not self._allow_update:
            raise TypeError(
                f"Cannot update key using setdefault: {key!r}, because update is disabled."
            )

        return dict.setdefault(self, key, default)

    # Override delete operations
    def __delitem__(self, key) -> None:
        """Forbid deleting keys when self._allow_del is False."""
        if not self._allow_del:
            raise TypeError(f"Cannot delete key {key!r}, because delete is disabled.")
        dict.__delitem__(self, key)

    def pop(self, key: Any, *args: Any) -> Any:
        """Forbid popping keys when self._allow_del is False."""
        if not self._allow_del:
            raise TypeError(f"Cannot pop key {key!r}, because delete is disabled.")
        return dict.pop(self, key, *args)

    def popitem(self) -> tuple[Any, Any]:
        """Pop the FIRST item (FIFO).

        Preserves the previous ``collections.UserDict``-inherited semantics —
        plain ``dict.popitem`` is LIFO, but monty users have historically
        relied on FIFO behaviour.
        """
        if not self._allow_del:
            raise TypeError("Cannot pop item, because delete is disabled.")
        if not self:
            raise KeyError("dictionary is empty")
        key = next(iter(self))
        value = dict.pop(self, key)
        return key, value

    def clear(self) -> None:
        """Forbid clearing the dictionary when self._allow_del is False."""
        if not self._allow_del:
            raise TypeError("Cannot clear dictionary, because delete is disabled.")
        dict.clear(self)


class frozendict(ControlledDict):
    """A dictionary that does not permit changes. The naming
    violates PEP 8 to be consistent with the built-in `frozenset` naming.
    """

    _allow_add: bool = False
    _allow_del: bool = False
    _allow_update: bool = False


class Namespace(ControlledDict):
    """A dictionary that does not permit update/delete its values (but allows add)."""

    _allow_add: bool = True
    _allow_del: bool = False
    _allow_update: bool = False


class AttrDict(dict):
    """Allow accessing values as `dct.key` in addition to the traditional way `dct["key"]`.

    Examples:
        >>> dct = AttrDict(foo=1, bar=2)
        >>> assert dct["foo"] is dct.foo
        >>> dct.bar = "hello"

    Warnings:
        When shadowing dict methods, e.g.:
            >>> dct = AttrDict(update="value")
            >>> dct.update()  # TypeError (the `update` method is overwritten)

    References:
        https://stackoverflow.com/a/14620633/24021108
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.__dict__ = self

    def __setitem__(self, key, value) -> None:
        """Check if the key shadows dict method."""
        if key in _DICT_METHOD_NAMES:
            warnings.warn(
                f"'{key=}' shadows dict method. This may lead to unexpected behavior.",
                UserWarning,
                stacklevel=2,
            )
        super().__setitem__(key, value)


class FrozenAttrDict(frozendict):
    """A dictionary that:
    - Does not permit changes (add/update/delete).
    - Allows accessing values as `dct.key` in addition to
        the traditional way `dct["key"]`.
    """

    def __init__(self, *args, **kwargs) -> None:
        """Allow add during init, as __setattr__ is called unlike frozendict."""
        self._allow_add = True
        super().__init__(*args, **kwargs)
        self._allow_add = False

    def __getattribute__(self, name: str) -> Any:
        try:
            return object.__getattribute__(self, name)
        except AttributeError:
            return self[name]

    def __setattr__(self, name: str, value: Any) -> None:
        if not self._allow_add and name != "_allow_add":
            raise TypeError(
                f"{self.__class__.__name__} does not support item assignment."
            )
        super().__setattr__(name, value)

    def __delattr__(self, name: str) -> None:
        raise TypeError(f"{self.__class__.__name__} does not support item deletion.")


class MongoDict:
    """This dict-like object allows one to access the entries in a nested dict as
    attributes.
    Entries (attributes) cannot be modified. It also provides Ipython tab
    completion hence this object is particularly useful if you need to analyze
    a nested dict interactively (e.g. documents extracted from a MongoDB
    database).

    >>> m_dct = MongoDict({"a": {"b": 1}, "x": 2})
    >>> assert m_dct.a.b == 1 and m_dct.x == 2
    >>> assert "a" in m_dct and "b" in m_dct.a
    >>> m_dct["a"]
    {"b": 1}

    Notes:
        Cannot inherit from ABC collections.Mapping because otherwise
        dict.keys and dict.items will pollute the namespace.
        e.g MongoDict({"keys": 1}).keys would be the ABC dict method.
    """

    def __init__(self, *args, **kwargs) -> None:
        """Args:
        args: Passthrough arguments for standard dict.
        kwargs: Passthrough keyword arguments for standard dict.
        """
        self.__dict__["_mongo_dict_"] = dict(*args, **kwargs)

    def __repr__(self) -> str:
        return str(self)

    def __str__(self) -> str:
        return str(self._mongo_dict_)

    def __setattr__(self, name: str, value: Any) -> None:
        raise NotImplementedError(
            f"You cannot modify attribute {name} of {self.__class__.__name__}"
        )

    def __getattribute__(self, name: str) -> Any:
        try:
            return super().__getattribute__(name)
        except AttributeError:
            try:
                a = self._mongo_dict_[name]
                if isinstance(a, collections.abc.Mapping):
                    a = self.__class__(a)
                return a
            except Exception as exc:
                raise AttributeError(str(exc)) from exc

    def __getitem__(self, slice_) -> Any:
        return self._mongo_dict_.__getitem__(slice_)

    def __iter__(self) -> Iterable:
        return iter(self._mongo_dict_)

    def __len__(self) -> int:
        return len(self._mongo_dict_)

    def __dir__(self) -> list:
        """For Ipython tab completion.
        See http://ipython.org/ipython-doc/dev/config/integrating.html.
        """
        return sorted(k for k in self._mongo_dict_ if not callable(k))


def dict2namedtuple(*args, **kwargs) -> tuple:
    """Helper function to create a `namedtuple` from a dictionary.

    Examples:
        >>> tpl = dict2namedtuple(foo=1, bar="hello")
        >>> assert tpl.foo == 1 and tpl.bar == "hello"

        >>> tpl = dict2namedtuple([("foo", 1), ("bar", "hello")])
        >>> assert tpl[0] is tpl.foo and tpl[1] is tpl.bar

    Warnings:
        - The order of the items in the namedtuple is not deterministic if
          `kwargs` are used. namedtuples, however, should always be accessed
          by attribute hence this behaviour should not be a serious problem.

        - Don't use this function in code where memory and performance are
          crucial, since a dict is needed to instantiate the tuple!
    """
    dct = collections.OrderedDict(*args)
    dct.update(**kwargs)
    return collections.namedtuple(
        typename="dict2namedtuple", field_names=list(dct.keys())
    )(**dct)
